import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "film"))

import film  # noqa: E402
import design as D  # noqa: E402
from engine import save_png, grid_imgs  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("times", nargs="+", type=float)
ap.add_argument("--out", default=str(HERE / "out" / "stills"))
ap.add_argument("--prefix", default="t")
ap.add_argument("--sheet", default="")
ap.add_argument("--cols", type=int, default=3)
ap.add_argument("--scale", type=float, default=1.0)
ap.add_argument("--crop", default="")
args = ap.parse_args()

out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)
imgs = []
t0 = time.time()
for t in args.times:
    ts = time.time()
    img = film.render(t)
    dt = time.time() - ts
    if args.crop:
        x, y, w, h = [int(v) for v in args.crop.split(",")]
        img = img[y : y + h, x : x + w]
    if args.scale != 1.0:
        img = cv2.resize(img, None, fx=args.scale, fy=args.scale, interpolation=cv2.INTER_AREA)
    name = f"{args.prefix}{t:06.2f}.png"
    save_png(img, out / name)
    print(f"t={t:6.2f}  {dt*1000:6.0f} ms  -> {name}")
    imgs.append(img)

if args.sheet:
    sheet_imgs = []
    for im in imgs:
        h, w = im.shape[:2]
        tw = 560
        th = int(h * tw / w)
        sheet_imgs.append(cv2.resize(im, (tw, th), interpolation=cv2.INTER_AREA))
    sheet = grid_imgs(sheet_imgs, args.cols, gap=8)
    save_png(sheet, out / args.sheet)
    print("sheet ->", out / args.sheet)
print(f"total {time.time()-t0:.2f}s for {len(args.times)} frames")
