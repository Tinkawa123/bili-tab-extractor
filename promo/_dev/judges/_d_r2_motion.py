"""JudgeD round-2 motion probe: coarse diff across the whole film (0.5 s) + fine on the ending."""
import sys, json
from pathlib import Path
import numpy as np, cv2

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "film"))
import film

def small(img, w=320):
    h = int(round(img.shape[0] * w / img.shape[1]))
    return cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)

def probe(times, tag):
    prev = None
    out = []
    for t in times:
        g = cv2.cvtColor((np.clip(film.frame(t), 0, 1) * 255 + .5).astype(np.uint8), cv2.COLOR_RGB2GRAY)
        s = small(g).astype(np.float32)
        d = 0.0 if prev is None else float(np.abs(s - prev).mean()) / 255.0
        # also: difference after aligning scale (is it just a push?): compare against resized prev
        d_shift = None
        if prev is not None:
            # estimate best small scale change around 1.0 to see if motion is pure zoom
            best = None
            for k in np.arange(-0.012, 0.0121, 0.004):
                M = cv2.getRotationMatrix2D((s.shape[1] / 2, s.shape[0] / 2), 0, 1.0 + k)
                w = cv2.warpAffine(prev, M, (s.shape[1], s.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
                dd = float(np.abs(w - s).mean()) / 255.0
                if best is None or dd < best[1]:
                    best = (k, dd)
            d_shift = best
        out.append((round(t, 3), round(d, 5), None if d_shift is None else round(d_shift[0], 4), None if d_shift is None else round(d_shift[1], 5)))
        prev = s
        print(f"{tag} t={t:6.2f} diff={d:.5f}" + ("" if d_shift is None else f"  bestzoom={d_shift[0]:+.3f} diff_at_zoom={d_shift[1]:.5f}"), flush=True)
        prev = s
    return out

coarse = list(np.arange(0.0, 60.0, 0.5))
print("== coarse 0.5s whole film ==")
c = probe(coarse, "C")
fine = list(np.arange(54.0, 60.0, 0.1))
print("== fine 0.1s ending ==")
f = probe(fine, "F")
json.dump({"coarse": c, "fine": f}, open(HERE / "_d_r2_motion.json", "w"))
print("done")
