import numpy as np
import cv2
from pathlib import Path

S = Path("out/stills")
LUM = np.array([0.2126, 0.7152, 0.0722], np.float32)


def load(t):
    p = S / f"still_{t:06.2f}.png"
    return cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)[..., ::-1].astype(np.float32) / 255.0


def med(im, x0, y0, x1, y1):
    r = im[y0:y1, x0:x1].reshape(-1, 3)
    return [int(v) for v in np.median(r, axis=0) * 255]


def contrast(im, x0, y0, x1, y1):
    sub = im[y0:y1, x0:x1]
    L = sub @ LUM
    return dict(p50=round(float(np.percentile(L, 50) * 255)), p99=round(float(np.percentile(L, 99) * 255)),
                max=round(float(L.max() * 255)), p01=round(float(np.percentile(L, 1) * 255)))


print("S1 strip paper (wide median, avoids ink):", med(load(3.30), 200, 930, 1700, 1010), med(load(6.60), 200, 930, 1700, 1010))
print("S1 strip paper 3.30 mid band:", med(load(3.30), 150, 860, 500, 900))

im6 = load(57.20)
L = im6 @ LUM
# mark brackets bbox: bright paper-white pixels in top area
m = L[100:520, 600:1320] > 0.80
ys, xs = np.where(m)
print("S6 mark bright bbox:", xs.min() + 600, ys.min() + 100, xs.max() + 600, ys.max() + 100)
# name row band
m2 = L[500:640, 400:1520] > 0.75
ys2, xs2 = np.where(m2)
print("S6 name bbox:", xs2.min() + 400, ys2.min() + 500, xs2.max() + 400, ys2.max() + 500)
# subtitle / CTA rows: find text row bands by ink
for (name, y0, y1) in [("subtitle", 640, 690), ("slogan", 720, 780), ("cta1", 800, 830), ("cta2", 835, 875), ("cta3", 878, 910)]:
    c = contrast(im6, 600, y0, 1320, y1)
    print(name, c)
# couplet centering at 51
im5 = load(51.0)
L5 = im5 @ LUM
for (nm, y0, y1) in [("line1", 360, 520), ("line2", 520, 660)]:
    mm = L5[y0:y1, :] > 0.5
    ys3, xs3 = np.where(mm)
    print(nm, "ink x", xs3.min(), xs3.max(), "center", (xs3.min() + xs3.max()) / 2)
