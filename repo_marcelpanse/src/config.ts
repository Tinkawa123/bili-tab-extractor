export interface Options {
  url: string;
  interval: number;
  model: string;
  sample: number;
  dedupThreshold: number;
  maxHeight: number;
  keepTemp: boolean;
}

export const DEFAULTS = {
  interval: 2,
  model: "claude-sonnet-5",
  sample: 6,
  dedupThreshold: 12,
  maxHeight: 720,
  keepTemp: false,
} as const;

// Output goes here with zero configuration; the file is named after the video.
export const OUTPUT_DIR = "out";

export function resolveApiKey(): string {
  const key = process.env.ANTHROPIC_API_KEY;
  if (!key) {
    throw new Error(
      "ANTHROPIC_API_KEY is not set. Export it or put it in a .env file and run with `node --env-file=.env`.",
    );
  }
  return key;
}
