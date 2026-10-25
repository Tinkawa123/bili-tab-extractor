import numpy as np, cv2
from pathlib import Path
FR = Path("out/frames_p1"); FPS=30
def g(i):
    return cv2.imdecode(np.fromfile(str(FR/f"f_{i:05d}.jpg"), dtype=np.uint8), cv2.IMREAD_GRAYSCALE).astype(np.float32)
prev=None
for i in range(int(45.6*FPS), int(59.3*FPS)):
    im=g(i)
    if prev is not None:
        d=np.abs(im-prev)
        band = d[300:1000, 300:1700]
        pct=(band>12).mean()*100
        if pct>0.35:
            print(f"f{i} t={i/FPS:6.2f} textband={pct:5.2f}%")
    prev=im
print("--- flip window 38.4-40.2 whole-frame")
prev=None
for i in range(int(38.4*FPS), int(40.3*FPS)):
    im=g(i)
    if prev is not None:
        d=np.abs(im-prev)
        print(f"f{i} t={i/FPS:6.2f} d={(d>12).mean()*100:5.2f}%")
    prev=im
