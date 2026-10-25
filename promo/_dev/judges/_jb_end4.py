import numpy as np, cv2
from pathlib import Path
FR = Path("out/frames_p1"); FPS=30
def g(i):
    return cv2.imdecode(np.fromfile(str(FR/f"f_{i:05d}.jpg"), dtype=np.uint8), cv2.IMREAD_GRAYSCALE).astype(np.float32)
prev=None
print("headline zone y120-280 x120-840 (540p), 47.0-52.6")
for i in range(int(47.0*FPS), int(52.6*FPS)):
    im=g(i)
    if prev is not None:
        d=np.abs(im-prev)[120:280, 120:840]
        pct=(d>10).mean()*100
        if pct>0.1:
            print(f"f{i} t={i/FPS:6.2f} {pct:5.2f}%")
    prev=im
