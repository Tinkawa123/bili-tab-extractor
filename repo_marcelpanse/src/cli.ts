#!/usr/bin/env node
import { Command } from "commander";
import { DEFAULTS, OUTPUT_DIR, type Options } from "./config.js";
import { run } from "./pipeline.js";
import { log } from "./util/logger.js";

function toInt(name: string) {
  return (value: string): number => {
    const n = Number(value);
    if (!Number.isFinite(n) || n <= 0) {
      throw new Error(`--${name} must be a positive number (got "${value}")`);
    }
    return n;
  };
}

const program = new Command();

program
  .name("tab-parser")
  .description(
    `Turn a YouTube guitar-lesson video into a PDF of the guitar tab (written to ${OUTPUT_DIR}/<video-title>.pdf).`,
  )
  .argument("<youtube-url>", "YouTube video URL")
  .option("-i, --interval <seconds>", "screenshot interval in seconds", toInt("interval"), DEFAULTS.interval)
  .option("--model <id>", "Claude vision model", DEFAULTS.model)
  .option("--sample <n>", "frames sampled for tab-region detection", toInt("sample"), DEFAULTS.sample)
  .option("--dedup-threshold <n>", "pre-dedup Hamming distance (cost control)", toInt("dedup-threshold"), DEFAULTS.dedupThreshold)
  .option("--max-height <px>", "cap download resolution", toInt("max-height"), DEFAULTS.maxHeight)
  .option("--keep-temp", "keep intermediate frames/crops", DEFAULTS.keepTemp)
  .action(async (url: string, raw: Record<string, unknown>) => {
    const opts: Options = {
      url,
      interval: raw.interval as number,
      model: raw.model as string,
      sample: raw.sample as number,
      dedupThreshold: raw.dedupThreshold as number,
      maxHeight: raw.maxHeight as number,
      keepTemp: Boolean(raw.keepTemp),
    };

    try {
      const out = await run(opts);
      console.log(out);
    } catch (err) {
      log.error((err as Error).message);
      if ((err as Error).stack) {
        console.error((err as Error).stack);
      }
      process.exitCode = 1;
    }
  });

program.parseAsync(process.argv).catch((err) => {
  log.error((err as Error).message);
  process.exitCode = 1;
});
