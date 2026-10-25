import sys, numpy as np, cv2
sys.path.insert(0, "film")
from pathlib import Path
import film
FR = Path("out/frames_p1")
def load(i):
    return cv2.imdecode(np.fromfile(str(FR/f"f_{i:05d}.jpg"), dtype=np.uint8), cv2.IMREAD_COLOR).astype(np.float32)
ts = [2.0, 4.4, 7.5, 9.9, 12.5, 16.5, 19.5, 22.3, 25.0, 27.5, 30.0, 33.5, 36.3, 39.5, 42.7, 44.5, 47.5, 50.0, 53.5, 56.5]
for t in ts:
    img = film.frame(t)
    u8 = (np.clip(img,0,1)*255+0.5).astype(np.uint8)
    small = cv2.resize(u8, (960,540), interpolation=cv2.INTER_AREA).astype(np.float32)
    i = int(round(t*30))
    ref = load(i)
    d = np.abs(small-ref).mean()
    print(f"t={t:5.2f} f{i:4d}  meanAbsDiff={d:7.2f}  (identical if <3)")
