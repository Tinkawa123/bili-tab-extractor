"""Contact sheets v2: 3x2 grids, readable size."""
import sys
from pathlib import Path
import numpy as np, cv2

HERE = Path(__file__).resolve().parent
FR = HERE / "out" / "frames_p1"
OUT = HERE / "out" / "jb"
OUT.mkdir(parents=True, exist_ok=True)
FPS = 30


def load(i):
    p = FR / f"f_{i:05d}.jpg"
    if not p.exists():
        return None
    return cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)


def save(img, name):
    p = OUT / name
    cv2.imencode(".png", img)[1].tofile(str(p))
    return p


def grid(frames, cols, scale, label, tag):
    imgs = []
    for i in frames:
        im = load(i)
        if im is None:
            continue
        im = cv2.resize(im, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        cv2.putText(im, f"f{i} {i/FPS:.3f}s", (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 255, 255), 1, cv2.LINE_AA)
        cv2.rectangle(im, (0, 0), (im.shape[1] - 1, im.shape[0] - 1), (70, 70, 70), 1)
        imgs.append(im)
    rows = []
    for r in range(0, len(imgs), cols):
        row = imgs[r:r + cols]
        while len(row) < cols:
            row.append(np.zeros_like(imgs[0]))
        rows.append(np.hstack(row))
    return save(np.vstack(rows), f"{tag}.png")


def seq(t, n=6, step=1, tag=None, cols=3, scale=0.6):
    f0 = int(round(t * FPS))
    return grid([f0 + k * step for k in range(n)], cols, scale, f"{t}", tag or f"s_{t:.2f}_x{step}")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("all", "key"):
        for t in [2.2, 4.4, 6.4, 12.5, 16.5, 19.5, 22.5, 27.5, 30.0, 33.5, 37.5, 39.5, 41.5, 47.5, 53.5]:
            print(seq(t, 6, 1))
    if what in ("all", "ov"):
        fs = [int(i * FPS + 15) for i in range(0, 60, 2)]
        print(grid(fs, 6, 0.30, "ov", "ov_2s"))
