import { execa } from "execa";
import { existsSync, statSync } from "node:fs";
import { log } from "../util/logger.js";

// YouTube currently forces SABR streaming on its default web/tv clients, which
// fails with "The page needs to be reloaded". Trying these clients in order
// works around it; yt-dlp falls through to the next when one yields no formats.
const PLAYER_CLIENTS = "youtube:player_client=android,web,ios";

/**
 * Download the video to `outPath` with yt-dlp, capping resolution to `maxHeight`
 * for cheaper/faster frame extraction. Returns the resolved video title.
 */
export async function downloadVideo(
  url: string,
  outPath: string,
  maxHeight: number,
): Promise<string> {
  await assertBinary("yt-dlp");

  // Shells sometimes pass URLs with literal backslashes (e.g. `watch\?v\=…`);
  // a real URL never contains them, so strip them to avoid yt-dlp misparsing
  // the URL as a channel/tab and silently downloading nothing.
  url = url.replace(/\\/g, "").trim();
  if (!/^https?:\/\//i.test(url)) {
    throw new Error(`"${url}" does not look like a valid URL.`);
  }

  log.step(`Downloading video (≤${maxHeight}p)…`);
  await execa(
    "yt-dlp",
    [
      "-f",
      `bestvideo[height<=${maxHeight}][ext=mp4]+bestaudio[ext=m4a]/best[height<=${maxHeight}][ext=mp4]/best[height<=${maxHeight}]`,
      "--merge-output-format",
      "mp4",
      "--extractor-args",
      PLAYER_CLIENTS,
      "-o",
      outPath,
      "--no-playlist",
      "--force-overwrites",
      url,
    ],
    { stdout: "ignore", stderr: "inherit", reject: false },
  );

  if (!existsSync(outPath) || statSync(outPath).size === 0) {
    throw new Error(
      "yt-dlp did not produce a video file. Check that the URL points to a single, " +
        "available video (not a channel/playlist/private video) and that yt-dlp is up to date.",
    );
  }

  const { stdout, exitCode } = await execa(
    "yt-dlp",
    [
      "--no-playlist",
      "--extractor-args",
      PLAYER_CLIENTS,
      "--print",
      "title",
      "--skip-download",
      url,
    ],
    { reject: false },
  );
  const title = exitCode === 0 && stdout.trim() ? stdout.trim() : "tab";

  log.success(`Downloaded "${title}"`);
  return title;
}

async function assertBinary(name: string): Promise<void> {
  try {
    await execa(name, ["--version"]);
  } catch {
    throw new Error(
      `Required binary "${name}" was not found on PATH. Please install it (e.g. \`brew install ${name}\`).`,
    );
  }
}
