import sys
from pathlib import Path
import numpy as np, cv2
HERE = Path(r"C:\Users\20849\Desktop\视频扒谱\promo")
sys.path.insert(0, str(HERE / "film"))
import film
def run(t0, t1, tag):
    prev=None; ds=[]
    t=t0
    while t < t1 - 1e-9:
        g = cv2.cvtColor((np.clip(film.frame(t),0,1)*255+.5).astype(np.uint8), cv2.COLOR_RGB2GRAY)
        s = cv2.resize(g,(320,180),interpolation=cv2.INTER_AREA).astype(np.float32)
        d = 0.0 if prev is None else float(np.abs(s-prev).mean())/255.0
        if prev is not None: ds.append(d)
        prev=s; t=round(t+0.25,2)
    print(f"{tag}: n={len(ds)} mean={np.mean(ds):.5f} p90={np.percentile(ds,90):.5f} max={max(ds):.5f}")
run(8.0, 13.0, "8.0-13.0")
run(26.5, 29.5, "26.5-29.5")
run(36.2, 40.5, "36.2-40.5")
