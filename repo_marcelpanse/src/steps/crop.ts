import { basename, join } from "node:path";
import sharp from "sharp";
import type { Box } from "./detect.js";
import { log } from "../util/logger.js";

/**
 * Crop every frame to the normalized `box`, writing PNGs into `cropsDir`.
 * Returns the sorted list of cropped file paths (chronological order preserved).
 */
export async function cropFrames(
  frames: string[],
  box: Box,
  cropsDir: string,
): Promise<string[]> {
  log.step(`Cropping ${frames.length} frames to the tab region…`);

  const meta = await sharp(frames[0]).metadata();
  const width = meta.width ?? 0;
  const height = meta.height ?? 0;
  if (!width || !height) {
    throw new Error(`Could not read dimensions of ${frames[0]}`);
  }

  const left = Math.round((box.x0 / 1000) * width);
  const top = Math.round((box.y0 / 1000) * height);
  const cropW = Math.max(1, Math.round(((box.x1 - box.x0) / 1000) * width));
  const cropH = Math.max(1, Math.round(((box.y1 - box.y0) / 1000) * height));
  const extract = {
    left,
    top,
    width: Math.min(cropW, width - left),
    height: Math.min(cropH, height - top),
  };
  log.debug(`crop rect (px): ${JSON.stringify(extract)}`);

  const out: string[] = [];
  for (const frame of frames) {
    const dest = join(cropsDir, basename(frame));
    await sharp(frame).extract(extract).toFile(dest);
    out.push(dest);
  }

  log.success(`Cropped ${out.length} images`);
  return out;
}
