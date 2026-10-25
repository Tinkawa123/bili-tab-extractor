import numpy as np, cv2
from pathlib import Path
FR = Path("out/frames_p1"); FPS=30
def g(i):
    return cv2.imdecode(np.fromfile(str(FR/f"f_{i:05d}.jpg"), dtype=np.uint8), cv2.IMREAD_GRAYSCALE).astype(np.float32)
vals=[]
for i in range(int(15.0*FPS), int(19.4*FPS)):
    im = g(i)
    col = im[:, 640:800].mean(axis=1)          # stack column profile (960x540)
    b = col > 85
    # ignore the HUD/dust: only y 40..520
    ys = np.where(b[40:520])[0]
    bottom = (ys.max()+40) if len(ys) else 0
    cnt = 0; prev=False
    for v in b[40:520]:
        if v and not prev: cnt+=1
        prev=v
    vals.append((i, cnt, bottom))
base=None
for i,c,bo in vals:
    print(f"f{i} t={i/FPS:6.2f} rows={c:2d} bottom={bo:3d}")
