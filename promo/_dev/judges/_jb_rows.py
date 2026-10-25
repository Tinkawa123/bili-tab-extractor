import numpy as np, cv2
from pathlib import Path
FR = Path("out/frames_p1"); FPS=30
def g(i):
    return cv2.imdecode(np.fromfile(str(FR/f"f_{i:05d}.jpg"), dtype=np.uint8), cv2.IMREAD_GRAYSCALE).astype(np.float32)
counts=[]
for i in range(int(14.6*FPS), int(19.6*FPS)):
    im = g(i)
    prof = im[:, 640:800].mean(axis=1)   # 960-wide coords, stack column
    b = prof > 90
    # count runs
    runs = 0; prev=False
    for v in b:
        if v and not prev: runs+=1
        prev=v
    counts.append((i, runs, float(prof.max())))
prev=None
for i,c,m in counts:
    if prev is None or c!=prev:
        print(f"  f{i:4d} t={i/FPS:6.2f} rows={c}")
    prev=c
