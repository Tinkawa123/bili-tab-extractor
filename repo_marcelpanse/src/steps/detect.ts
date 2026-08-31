import Anthropic from "@anthropic-ai/sdk";
import sharp from "sharp";
import { log } from "../util/logger.js";

/** Bounding box in normalized 0–1000 coordinates (origin top-left). */
export interface Box {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

/** Fractional box (each edge 0..1) used internally. */
interface FBox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

// Vision only needs to locate *which region* the tab sits in, so a coarse
// labeled grid is plenty — models are reliable at picking labeled cells but
// unreliable at precise pixel coordinates. The exact edges are then snapped by
// refineBox() below.
const ROWS = 12;
const COLS = 12;

// White-paper mask thresholds: sheet music is dark content on a light, nearly
// unsaturated background, unlike the colourful photographic performer/backdrop.
const WHITE_MIN_BRIGHTNESS = 170; // max(r,g,b) at least this…
const WHITE_MAX_CHROMA = 45; // …and (max-min) channel spread below this
const PROJECTION_FRACTION = 0.35; // a row/col is "paper" if this fraction is white
const REFINE_WIDTH = 320; // downscaled width for the pixel scan

function prompt(): string {
  return (
    `The image has a grid: ${ROWS} rows labeled on the left in red (0=top..${ROWS - 1}=bottom) ` +
    `and ${COLS} columns labeled on top in blue (0=left..${COLS - 1}=right). Find the guitar ` +
    "sheet-music region (a standard-notation staff and/or the TAB block of horizontal string " +
    "lines with fret numbers). It may be an overlay box anywhere in the frame, not necessarily " +
    "full width. List every row number and every column number that the sheet music overlaps, " +
    "including the row with the bottom TAB fret numbers. Ignore the performer, hands, instrument, " +
    'and background. Respond with ONLY JSON: {"tab":bool,"rows":[int,...],"cols":[int,...]}.'
  );
}

/** Resize to 1024w and overlay a labeled row/column grid, as JPEG base64. */
async function griddedImage(path: string): Promise<string> {
  const base = sharp(path).resize({ width: 1024, withoutEnlargement: true });
  const meta = await base.metadata();
  const W = meta.width ?? 1024;
  const H = meta.height ?? 576;

  let g = "";
  for (let i = 0; i <= ROWS; i++) {
    const y = Math.round((i / ROWS) * H);
    g += `<line x1="0" y1="${y}" x2="${W}" y2="${y}" stroke="red" stroke-width="1" opacity="0.6"/>`;
  }
  for (let j = 0; j <= COLS; j++) {
    const x = Math.round((j / COLS) * W);
    g += `<line x1="${x}" y1="0" x2="${x}" y2="${H}" stroke="red" stroke-width="1" opacity="0.6"/>`;
  }
  for (let i = 0; i < ROWS; i++) {
    const y = Math.round(((i + 0.5) / ROWS) * H);
    g +=
      `<rect x="0" y="${y - 9}" width="26" height="18" fill="red"/>` +
      `<text x="3" y="${y + 5}" fill="white" font-size="14" font-family="monospace" font-weight="bold">${i}</text>`;
  }
  for (let j = 0; j < COLS; j++) {
    const x = Math.round(((j + 0.5) / COLS) * W);
    g +=
      `<rect x="${x - 10}" y="0" width="21" height="18" fill="blue"/>` +
      `<text x="${x - 7}" y="14" fill="white" font-size="14" font-family="monospace" font-weight="bold">${j}</text>`;
  }
  const svg = Buffer.from(`<svg width="${W}" height="${H}">${g}</svg>`);
  const buf = await base.composite([{ input: svg }]).jpeg({ quality: 88 }).toBuffer();
  return buf.toString("base64");
}

interface Region {
  rows: number[];
  cols: number[];
}

async function detectRegion(
  client: Anthropic,
  model: string,
  framePath: string,
): Promise<Region | null> {
  const data = await griddedImage(framePath);
  const resp = await client.messages.create({
    model,
    max_tokens: 200,
    messages: [
      {
        role: "user",
        content: [
          { type: "image", source: { type: "base64", media_type: "image/jpeg", data } },
          { type: "text", text: prompt() },
        ],
      },
    ],
  });
  const text = resp.content
    .filter((b): b is Anthropic.TextBlock => b.type === "text")
    .map((b) => b.text)
    .join("");
  return parseRegion(text);
}

function parseRegion(text: string): Region | null {
  const match = text.match(/\{[\s\S]*\}/);
  if (!match) return null;
  try {
    const obj = JSON.parse(match[0]);
    if (!obj.tab) return null;
    const rows = toIndices(obj.rows, ROWS);
    const cols = toIndices(obj.cols, COLS);
    if (rows.length === 0 || cols.length === 0) return null;
    return { rows, cols };
  } catch {
    return null;
  }
}

function toIndices(arr: unknown, max: number): number[] {
  if (!Array.isArray(arr)) return [];
  return arr
    .map((n) => Number(n))
    .filter((n) => Number.isInteger(n) && n >= 0 && n < max);
}

function median(nums: number[]): number {
  const sorted = [...nums].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

function clamp01(n: number): number {
  return Math.min(1, Math.max(0, n));
}

/**
 * Snap `prior` (a generous search window, fractional) to the tight bounding box
 * of the sheet-music "paper" inside it, using a low-saturation/high-brightness
 * mask and row/column projection. Returns null if no clear paper region is
 * found (e.g. a dark-themed tab), so the caller can fall back to the prior.
 */
async function refineBox(framePath: string, prior: FBox): Promise<FBox | null> {
  const { data, info } = await sharp(framePath)
    .resize({ width: REFINE_WIDTH })
    .raw()
    .toBuffer({ resolveWithObject: true });
  const w = info.width;
  const h = info.height;
  const ch = info.channels;

  const isWhite = (px: number): boolean => {
    const r = data[px];
    const g = data[px + 1];
    const b = data[px + 2];
    const mx = Math.max(r, g, b);
    const mn = Math.min(r, g, b);
    return mx > WHITE_MIN_BRIGHTNESS && mx - mn < WHITE_MAX_CHROMA;
  };

  const sx0 = Math.floor(prior.x0 * w);
  const sx1 = Math.ceil(prior.x1 * w);
  const sy0 = Math.floor(prior.y0 * h);
  const sy1 = Math.ceil(prior.y1 * h);

  const colCount = new Array(w).fill(0);
  const rowCount = new Array(h).fill(0);
  for (let y = sy0; y < sy1; y++) {
    for (let x = sx0; x < sx1; x++) {
      if (isWhite((y * w + x) * ch)) {
        colCount[x]++;
        rowCount[y]++;
      }
    }
  }

  const colThresh = (sy1 - sy0) * PROJECTION_FRACTION;
  const rowThresh = (sx1 - sx0) * PROJECTION_FRACTION;
  let cx0 = sx0;
  let cx1 = sx1 - 1;
  let cy0 = sy0;
  let cy1 = sy1 - 1;
  while (cx0 < cx1 && colCount[cx0] < colThresh) cx0++;
  while (cx1 > cx0 && colCount[cx1] < colThresh) cx1--;
  while (cy0 < cy1 && rowCount[cy0] < rowThresh) cy0++;
  while (cy1 > cy0 && rowCount[cy1] < rowThresh) cy1--;

  const box: FBox = {
    x0: cx0 / w,
    y0: cy0 / h,
    x1: (cx1 + 1) / w,
    y1: (cy1 + 1) / h,
  };
  // Reject a degenerate result so the caller falls back to the vision prior.
  if (box.x1 - box.x0 < 0.05 || box.y1 - box.y0 < 0.03) return null;
  return box;
}

/** Pick ~`sample` frames spread evenly across the list. */
function pickSample(frames: string[], sample: number): string[] {
  if (frames.length <= sample) return frames;
  const step = frames.length / sample;
  const picked: string[] = [];
  for (let i = 0; i < sample; i++) {
    picked.push(frames[Math.floor(i * step + step / 2)]);
  }
  return picked;
}

/**
 * Detect the tab region in two stages:
 *  1. Claude reads a labeled grid on `--sample` frames to locate the coarse
 *     region (which rows/columns the sheet music occupies).
 *  2. That region (padded) is snapped to the actual paper edges with an image
 *     mask, so the box hugs the tab even when it is a corner overlay rather than
 *     a full-width strip.
 * Edges are combined across samples with a per-edge median. Throws if no
 * sampled frame shows a tab.
 */
export async function detectTabBox(
  apiKey: string,
  model: string,
  frames: string[],
  sample: number,
): Promise<Box> {
  const client = new Anthropic({ apiKey });
  const picks = pickSample(frames, sample);
  log.step(`Detecting tab region from ${picks.length} sampled frames (${model})…`);

  const regions = await Promise.all(picks.map((p) => detectRegion(client, model, p)));
  const tabPicks = picks.filter((_, i) => regions[i] !== null);
  const tabRegions = regions.filter((r): r is Region => r !== null);
  log.debug(
    "regions per sample: " +
      regions
        .map((r) => (r ? `r[${r.rows.join(",")}] c[${r.cols.join(",")}]` : "none"))
        .join(" | "),
  );

  if (tabRegions.length === 0) {
    throw new Error(
      "No guitar sheet music detected in any sampled frame. Try a larger --sample, a smaller " +
        "--interval, or verify the video actually shows tabs.",
    );
  }

  // Coarse vision box (fractions), padded by one grid cell each side so the true
  // edges are safely inside the refinement search window.
  const padX = 1 / COLS;
  const padY = 1 / ROWS;
  const prior: FBox = {
    x0: clamp01(median(tabRegions.map((r) => Math.min(...r.cols))) / COLS - padX),
    y0: clamp01(median(tabRegions.map((r) => Math.min(...r.rows))) / ROWS - padY),
    x1: clamp01((median(tabRegions.map((r) => Math.max(...r.cols))) + 1) / COLS + padX),
    y1: clamp01((median(tabRegions.map((r) => Math.max(...r.rows))) + 1) / ROWS + padY),
  };

  // Snap to the actual paper edges on each tab frame, then median the results.
  const refined = (
    await Promise.all(tabPicks.map((p) => refineBox(p, prior)))
  ).filter((b): b is FBox => b !== null);

  let fbox: FBox;
  if (refined.length > 0) {
    fbox = {
      x0: median(refined.map((b) => b.x0)),
      y0: median(refined.map((b) => b.y0)),
      x1: median(refined.map((b) => b.x1)),
      y1: median(refined.map((b) => b.y1)),
    };
    log.debug("refined box to actual paper edges");
  } else {
    fbox = prior;
    log.debug("no clear paper region found; using vision box directly");
  }

  const box: Box = {
    x0: Math.round(fbox.x0 * 1000),
    y0: Math.round(fbox.y0 * 1000),
    x1: Math.round(fbox.x1 * 1000),
    y1: Math.round(fbox.y1 * 1000),
  };
  log.success(
    `Tab region: x ${box.x0}–${box.x1}, y ${box.y0}–${box.y1} (of 1000)`,
  );
  return box;
}
