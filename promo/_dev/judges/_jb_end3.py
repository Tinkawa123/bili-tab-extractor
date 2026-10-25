import numpy as np, cv2
from pathlib import Path
FR = Path("out/frames_p1"); FPS=30
def g(i):
    return cv2.imdecode(np.fromfile(str(FR/f"f_{i:05d}.jpg"), dtype=np.uint8), cv2.IMREAD_GRAYSCALE).astype(np.float32)
print("=== text zone y270-535 x150-850 (540p), 46.8-59.4")
prev=None
for i in range(int(46.8*FPS), int(59.4*FPS)):
    im=g(i)
    if prev is not None:
        d=np.abs(im-prev)[270:535, 150:850]
        pct=(d>10).mean()*100
        if pct>0.15:
            print(f"f{i} t={i/FPS:6.2f} {pct:5.2f}%")
    prev=im
print("=== logo zone y100-270 x300-660, 51.5-56.0")
prev=None
for i in range(int(51.5*FPS), int(56.0*FPS)):
    im=g(i)
    if prev is not None:
        d=np.abs(im-prev)[100:270, 300:660]
        pct=(d>10).mean()*100
        if pct>0.15:
            print(f"f{i} t={i/FPS:6.2f} {pct:5.2f}%")
    prev=im
