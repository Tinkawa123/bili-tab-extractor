import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent


def load(frames_dir, idx):
    p = Path(frames_dir) / f"f_{idx:05d}.jpg"
    img = cv2.imread(str(p))
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB) if img is not None else None


def sheet(imgs, cols, tw=480, gap=6, label=None):
    th = int(tw * imgs[0].shape[0] / imgs[0].shape[1])
    rows = (len(imgs) + cols - 1) // cols
    W = cols * tw + (cols - 1) * gap
    H = rows * th + (rows - 1) * gap
    out = np.full((H, W, 3), 12, np.uint8)
    for i, im in enumerate(imgs):
        r, c = divmod(i, cols)
        y, x = r * (th + gap), c * (tw + gap)
        out[y : y + th, x : x + tw] = cv2.resize(im, (tw, th), interpolation=cv2.INTER_AREA)
    return out


ap = argparse.ArgumentParser()
ap.add_argument("--frames", required=True)
ap.add_argument("--fps", type=float, default=30)
ap.add_argument("--step", type=float, default=1.0, help="seconds between samples")
ap.add_argument("--t0", type=float, default=0.0)
ap.add_argument("--t1", type=float, default=60.0)
ap.add_argument("--cols", type=int, default=6)
ap.add_argument("--out", default=str(HERE / "out" / "sheet.png"))
a = ap.parse_args()

times = np.arange(a.t0, a.t1, a.step)
imgs = []
valid = []
for t in times:
    idx = int(round(t * a.fps))
    im = load(a.frames, idx)
    if im is None:
        continue
    imgs.append(im)
    valid.append(t)
print("frames:", len(imgs))
s = sheet(imgs, a.cols)
p = Path(a.out)
p.parent.mkdir(parents=True, exist_ok=True)
cv2.imwrite(str(p), cv2.cvtColor(s, cv2.COLOR_RGB2BGR))
print("saved", p, s.shape)
# timestamps
print("times:", ", ".join(f"{t:.1f}" for t in valid))
