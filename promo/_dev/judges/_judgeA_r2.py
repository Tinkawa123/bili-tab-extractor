"""Judge A round-2 measurements on 1080p stills."""
import sys, json
from pathlib import Path
import numpy as np
import cv2

S = Path(__file__).resolve().parent / "out" / "stills"


def load(t):
    p = S / f"still_{t:06.2f}.png"
    b = np.fromfile(str(p), np.uint8)
    im = cv2.imdecode(b, cv2.IMREAD_COLOR)[..., ::-1].astype(np.float32) / 255.0
    return im


def lum(im):
    return im @ np.array([0.2126, 0.7152, 0.0722], np.float32)


def stats(im):
    l = lum(im)
    q = np.percentile(l, [1, 5, 25, 50, 75, 95, 99])
    black = float(np.mean(np.all(im < 2 / 255, axis=2)))
    low = float(np.mean(l < 8 / 255))
    return dict(mean=round(float(l.mean()) * 255, 1), p1=round(q[0] * 255, 1), p5=round(q[1] * 255, 1),
                p25=round(q[2] * 255, 1), p50=round(q[3] * 255, 1), p75=round(q[4] * 255, 1),
                p95=round(q[5] * 255, 1), p99=round(q[6] * 255, 1),
                black_pct=round(black * 100, 1), low_pct=round(low * 100, 1))


def med(im, x0, y0, x1, y1):
    r = im[y0:y1, x0:x1].reshape(-1, 3)
    m = np.median(r, axis=0) * 255
    p95 = np.percentile(r @ np.array([0.2126, 0.7152, 0.0722], np.float32), 95) * 255
    return [int(v) for v in m], round(float(p95), 1)


def bright_bbox(im, thr=0.55):
    m = lum(im) > thr
    if not m.any():
        return None
    ys, xs = np.where(m)
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def vprofile(im, x0, x1, y0=0, y1=1080):
    p = lum(im)[:, x0:x1].mean(axis=1)
    return np.round(p * 255, 1)


def rowjump(im, x0, y0, x1, y1):
    """max |row-mean difference| inside a box: a vertical wipe shows one big step."""
    p = lum(im)[y0:y1, x0:x1].mean(axis=1)
    d = np.abs(np.diff(p))
    i = int(np.argmax(d))
    return round(float(d.max()) * 255, 1), y0 + i, round(float(p.max() - p.min()) * 255, 1)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "stats":
        for a in sys.argv[2:]:
            t = float(a)
            im = load(t)
            print(f"t={t:5.2f}", json.dumps(stats(im), ensure_ascii=False))
    elif cmd == "med":
        # med t x0 y0 x1 y1
        t = float(sys.argv[2]); x0, y0, x1, y1 = map(int, sys.argv[3:7])
        im = load(t)
        print("t=%.2f box=(%d,%d,%d,%d)" % (t, x0, y0, x1, y1), med(im, x0, y0, x1, y1))
    elif cmd == "vprof":
        t = float(sys.argv[2]); x0, x1 = map(int, sys.argv[3:5])
        p = vprofile(load(t), x0, x1)
        for y in range(0, 1080, 10):
            print(y, p[y])
    elif cmd == "bbox":
        t = float(sys.argv[2]); thr = float(sys.argv[3])
        print("t=%.2f" % t, bright_bbox(load(t), thr))
    elif cmd == "jump":
        t = float(sys.argv[2]); x0, y0, x1, y1 = map(int, sys.argv[3:7])
        print("t=%.2f" % t, rowjump(load(t), x0, y0, x1, y1))
