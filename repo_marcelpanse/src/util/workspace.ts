import { mkdtempSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { log } from "./logger.js";

export interface Workspace {
  root: string;
  framesDir: string;
  cropsDir: string;
  videoPath: string;
  cleanup(): void;
}

/**
 * Create a per-run temp workspace with the sub-directories the pipeline needs.
 * Cleaned up on cleanup() unless `keep` is set.
 */
export function createWorkspace(keep: boolean): Workspace {
  const root = mkdtempSync(join(tmpdir(), "tab-parser-"));
  const framesDir = join(root, "frames");
  const cropsDir = join(root, "crops");
  mkdirSync(framesDir, { recursive: true });
  mkdirSync(cropsDir, { recursive: true });
  log.debug(`workspace: ${root}`);

  return {
    root,
    framesDir,
    cropsDir,
    videoPath: join(root, "video.mp4"),
    cleanup(): void {
      if (keep) {
        log.info(`kept intermediate files in ${root}`);
        return;
      }
      try {
        rmSync(root, { recursive: true, force: true });
        log.debug(`cleaned up ${root}`);
      } catch (err) {
        log.warn(`failed to clean up ${root}: ${(err as Error).message}`);
      }
    },
  };
}
