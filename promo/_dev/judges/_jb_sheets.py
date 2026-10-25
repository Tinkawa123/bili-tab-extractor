"""Build labelled contact strips (adjacent frames) + 1s overview sheets."""
import sys
from pathlib import Path
import numpy as np, cv2

HERE = Path(__file__).resolve().parent
FR = HERE / "out" / "frames_p1"
OUT = HERE / "out" / "jb"
OUT.mkdir(parents=True, exist_ok=True)
FPS = 30


def load(i):
    return cv2.imdecode(np.fromfile(str(FR / f"f_{i:05d}.jpg"), dtype=np.uint8), cv2.IMREAD_COLOR)


def strip(t, n=6, step=1, scale=0.5, tag=""):
    """n frames starting at frame t, step frames apart, laid horizontally."""
    f0 = int(round(t * FPS))
    imgs = []
    for k in range(n):
        i = f0 + k * step
        im = load(i)
        if im is None:
            continue
        im = cv2.resize(im, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        cv2.putText(im, f"f{i} {i/FPS:.3f}s", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)
        cv2.rectangle(im, (0, 0), (im.shape[1] - 1, im.shape[0] - 1), (60, 60, 60), 1)
        imgs.append(im)
    if not imgs:
        return None
    h = imgs[0].shape[0]
    sheet = np.hstack(imgs)
    p = OUT / f"strip_{tag or f'{t:.2f}'}.png"
    cv2.imencode(".png", sheet)[1].tofile(str(p))
    return p


def grid(times, cols=3, scale=0.4, tag="grid"):
    imgs = []
    for t in times:
        i = int(round(t * FPS))
        im = load(i)
        if im is None:
            continue
        im = cv2.resize(im, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        cv2.putText(im, f"{t:.2f}s f{i}", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1, cv2.LINE_AA)
        imgs.append(im)
    rows = []
    for r in range(0, len(imgs), cols):
        row = imgs[r:r + cols]
        while len(row) < cols:
            row.append(np.zeros_like(imgs[0]))
        rows.append(np.hstack(row))
    sheet = np.vstack(rows)
    p = OUT / f"{tag}.png"
    cv2.imencode(".png", sheet)[1].tofile(str(p))
    return p


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "strips"):
        times = [2.2, 4.4, 6.4, 12.5, 16.5, 19.5, 22.5, 27.5, 30.0, 33.5, 37.5, 39.5, 41.5, 47.5, 53.5]
        for t in times:
            print(strip(t, 6, 1, 0.45))
            print(strip(t, 6, 3, 0.45, tag=f"{t:.2f}_wide"))
    if which in ("all", "grid"):
        print(grid([i + 0.5 for i in range(0, 60, 2)], 6, 0.30, "ov_2s"))
