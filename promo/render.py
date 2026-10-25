"""Frame renderer + encoder for the promo film.

  # preview stills
  python render.py stills 1.2 4.4 11.0 --scale 0.5

  # full film (parallel chunks, then ffmpeg mux)
  python render.py video --fps 30 --scale 1.0 --workers 4

Chrome is not involved: every frame comes from film.frame(t) (numpy/OpenCV).
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import os
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "film"))

FFMPEG = r"C:\Users\20849\AppData\Local\Programs\Python\Python314\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
OUT = HERE / "out"


def _save(img, path, quality=95):
    u8 = (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8) if img.dtype != np.uint8 else img
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(u8, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("encode failed")
    path.write_bytes(buf.tobytes())


def render_chunk(start, end, fps, scale, outdir, quality=95):
    import cv2 as _cv2

    thr = os.environ.get("DSH_CV_THREADS")
    if thr:
        _cv2.setNumThreads(int(thr))
    import film

    outdir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for i in range(start, end):
        t = i / fps
        img = film.frame(t)
        if scale != 1.0:
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        _save(img, outdir / f"f_{i:05d}.jpg", quality)
    return start, end, time.time() - t0


def _worker_main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--end", type=int, required=True)
    ap.add_argument("--fps", type=float, required=True)
    ap.add_argument("--scale", type=float, required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--quality", type=int, default=95)
    ap.add_argument("--threads", type=int, default=0)
    a = ap.parse_args()
    if a.threads:
        os.environ["DSH_CV_THREADS"] = str(a.threads)
    render_chunk(a.start, a.end, a.fps, a.scale, Path(a.outdir), a.quality)


def cmd_stills(args):
    import film

    outdir = OUT / "stills"
    outdir.mkdir(parents=True, exist_ok=True)
    for t in args.times:
        t0 = time.time()
        img = film.frame(t)
        if args.scale != 1.0:
            img = cv2.resize(img, None, fx=args.scale, fy=args.scale, interpolation=cv2.INTER_AREA)
        p = outdir / f"still_{t:06.2f}.png"
        u8 = (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)
        ok, buf = cv2.imencode(".png", cv2.cvtColor(u8, cv2.COLOR_RGB2BGR))
        p.write_bytes(buf.tobytes())
        print(f"t={t:.2f} {1000*(time.time()-t0):.0f}ms -> {p.name}")


def cmd_video(args):
    import film

    fps = args.fps
    total = int(round(film.D.DURATION * fps))
    outdir = OUT / ("frames_" + args.tag)
    outdir.mkdir(parents=True, exist_ok=True)
    for f in outdir.glob("f_*.jpg"):
        f.unlink()
    n = max(1, args.workers)
    chunks = []
    per = (total + n - 1) // n
    for i in range(n):
        s = i * per
        e = min(total, (i + 1) * per)
        if s < e:
            chunks.append((s, e))
    print(f"rendering {total} frames ({total/fps:.1f}s) @ {fps}fps scale {args.scale} in {len(chunks)} chunks")
    t0 = time.time()
    procs = []
    logs = []
    for s, e in chunks:
        log = open(outdir / f"log_{s}_{e}.txt", "w")
        logs.append(log)
        p = subprocess.Popen(
            [
                sys.executable,
                str(HERE / "render.py"),
                "_worker",
                "--start", str(s),
                "--end", str(e),
                "--fps", str(fps),
                "--scale", str(args.scale),
                "--outdir", str(outdir),
                "--quality", str(args.quality),
                "--threads", str(args.threads),
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        procs.append(p)
    last = 0
    while any(p.poll() is None for p in procs):
        done = len(list(outdir.glob("f_*.jpg")))
        if done - last >= max(1, total // 20):
            el = time.time() - t0
            print(f"  {done}/{total} frames  {el:.1f}s  eta {el/max(done,1)*(total-done):.0f}s")
            last = done
        time.sleep(1.0)
    for p in procs:
        if p.returncode != 0:
            print("WORKER FAILED", p.returncode)
            for lg in logs:
                lg.close()
            raise SystemExit(1)
    for lg in logs:
        lg.close()
    el = time.time() - t0
    have = len(list(outdir.glob("f_*.jpg")))
    print(f"frames done: {have}/{total} in {el:.1f}s ({el/max(have,1)*1000:.0f} ms/frame effective)")

    audio = Path(args.audio)
    out_mp4 = Path(args.out)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG, "-y", "-loglevel", "error",
        "-framerate", str(fps),
        "-i", str(outdir / "f_%05d.jpg"),
    ]
    if audio.exists():
        cmd += ["-i", str(audio)]
    cmd += [
        "-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
    ]
    if audio.exists():
        cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += [str(out_mp4)]
    print("encoding…", " ".join(cmd[-6:]))
    subprocess.run(cmd, check=True)
    print("wrote", out_mp4, f"{out_mp4.stat().st_size/1e6:.1f} MB")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("stills")
    s.add_argument("times", nargs="+", type=float)
    s.add_argument("--scale", type=float, default=1.0)

    v = sub.add_parser("video")
    v.add_argument("--fps", type=float, default=30.0)
    v.add_argument("--scale", type=float, default=1.0)
    v.add_argument("--workers", type=int, default=4)
    v.add_argument("--quality", type=int, default=95)
    v.add_argument("--tag", default="v1")
    v.add_argument("--audio", default=str(OUT / "score.wav"))
    v.add_argument("--out", default=str(OUT / "promo_v1.mp4"))
    v.add_argument("--crf", type=int, default=17)
    v.add_argument("--preset", default="medium")
    v.add_argument("--threads", type=int, default=2)

    w = sub.add_parser("_worker")
    w.add_argument("--start", type=int, required=True)
    w.add_argument("--end", type=int, required=True)
    w.add_argument("--fps", type=float, required=True)
    w.add_argument("--scale", type=float, required=True)
    w.add_argument("--outdir", required=True)
    w.add_argument("--quality", type=int, default=95)
    w.add_argument("--threads", type=int, default=0)

    args = ap.parse_args()
    if args.cmd == "stills":
        cmd_stills(args)
    elif args.cmd == "video":
        cmd_video(args)
    elif args.cmd == "_worker":
        if getattr(args, "threads", 0):
            os.environ["DSH_CV_THREADS"] = str(args.threads)
        render_chunk(args.start, args.end, args.fps, args.scale, Path(args.outdir), args.quality)


if __name__ == "__main__":
    main()
