import numpy as np, cv2
from pathlib import Path
FR = Path("out/frames_p1"); FPS=30
def g(i):
    return cv2.imdecode(np.fromfile(str(FR/f"f_{i:05d}.jpg"), dtype=np.uint8), cv2.IMREAD_GRAYSCALE).astype(np.float32)
print("text zone y480-1060 only (below logo), 47.0-59.4, per-frame >0.05%")
prev=None
for i in range(int(47.0*FPS), int(59.4*FPS)):
    im=g(i)
    if prev is not None:
        d=np.abs(im-prev)[480:1060, 300:1700]
        pct=(d>10).mean()*100
        if pct>0.05:
            print(f"f{i} t={i/FPS:6.2f} {pct:5.2f}%")
    prev=im
