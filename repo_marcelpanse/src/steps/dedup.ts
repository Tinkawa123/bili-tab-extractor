import sharp from "sharp";
import { log } from "../util/logger.js";

/**
 * Compute a 64-bit dHash for an image: resize to 9x8 grayscale, then for each
 * row compare adjacent pixels (left < right => 1 bit). Returned as a BigInt.
 */
async function dHash(path: string): Promise<bigint> {
  const raw = await sharp(path)
    .grayscale()
    .resize(9, 8, { fit: "fill" })
    .raw()
    .toBuffer();

  let hash = 0n;
  let bit = 0n;
  for (let row = 0; row < 8; row++) {
    for (let col = 0; col < 8; col++) {
      const left = raw[row * 9 + col];
      const right = raw[row * 9 + col + 1];
      if (left < right) hash |= 1n << bit;
      bit++;
    }
  }
  return hash;
}

function hamming(a: bigint, b: bigint): number {
  let x = a ^ b;
  let count = 0;
  while (x > 0n) {
    count += Number(x & 1n);
    x >>= 1n;
  }
  return count;
}

/**
 * Drop near-identical consecutive crops. Keeps a crop only when its dHash differs
 * from the last kept crop by more than `threshold` bits. Order is preserved.
 */
export async function dedupCrops(
  crops: string[],
  threshold: number,
): Promise<string[]> {
  log.step(`De-duplicating ${crops.length} crops (threshold ${threshold})…`);

  const kept: string[] = [];
  let lastHash: bigint | null = null;

  for (const crop of crops) {
    const hash = await dHash(crop);
    if (lastHash === null || hamming(hash, lastHash) > threshold) {
      kept.push(crop);
      lastHash = hash;
    }
  }

  log.success(`Kept ${kept.length} distinct tab images (dropped ${crops.length - kept.length})`);
  return kept;
}
