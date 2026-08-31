import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import type { Options } from "./config.js";
import { OUTPUT_DIR, resolveApiKey } from "./config.js";
import { createWorkspace } from "./util/workspace.js";
import { downloadVideo } from "./steps/download.js";
import { extractFrames } from "./steps/frames.js";
import { detectTabBox } from "./steps/detect.js";
import { cropFrames } from "./steps/crop.js";
import { dedupCrops } from "./steps/dedup.js";
import { dedupeByBar } from "./steps/classify.js";
import { buildPdf } from "./steps/pdf.js";

/** Turn a video title into a safe file name (no path separators / reserved chars). */
function sanitizeFilename(name: string): string {
  return (
    name
      .replace(/[/\\?%*:|"<>]/g, "")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 120) || "tabs"
  );
}

/** Run the full URL → PDF pipeline. Returns the absolute output path. */
export async function run(opts: Options): Promise<string> {
  const apiKey = resolveApiKey();
  const ws = createWorkspace(opts.keepTemp);

  try {
    const title = await downloadVideo(opts.url, ws.videoPath, opts.maxHeight);
    const frames = await extractFrames(ws.videoPath, ws.framesDir, opts.interval);

    const box = await detectTabBox(apiKey, opts.model, frames, opts.sample);
    const crops = await cropFrames(frames, box, ws.cropsDir);

    // Cheap local pre-dedup drops near-identical consecutive frames to cut the
    // number of vision calls; the bar-number pass is the authoritative dedup.
    const distinctCrops = await dedupCrops(crops, opts.dedupThreshold);
    const tabs = await dedupeByBar(apiKey, opts.model, distinctCrops);

    const outPath = resolve(OUTPUT_DIR, `${sanitizeFilename(title)}.pdf`);
    mkdirSync(dirname(outPath), { recursive: true });
    await buildPdf(tabs, outPath, title);
    return outPath;
  } finally {
    ws.cleanup();
  }
}
