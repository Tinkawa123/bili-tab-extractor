"""JudgeD r2: lean motion probe for the ending only (no zoom search -> less RAM)."""
import sys
from pathlib import Path
import numpy as np, cv2

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "film"))
import film

prev = None
rows = []
for k in range(52):
    t = 47.0 + k * 0.25
    g = cv2.cvtColor((np.clip(film.frame(t), 0, 1) * 255 + .5).astype(np.uint8), cv2.COLOR_RGB2GRAY)
    s = cv2.resize(g, (320, 180), interpolation=cv2.INTER_AREA).astype(np.float32)
    d = 0.0 if prev is None else float(np.abs(s - prev).mean()) / 255.0
    mx = 0.0 if prev is None else float(np.abs(s - prev).max()) / 255.0
    rows.append((t, d, mx, float(s.mean()) / 255.0))
    print(f"t={t:5.2f} diff={d:.5f} maxdiff={mx:.3f} mean={s.mean()/255:.3f}", flush=True)
    prev = s
