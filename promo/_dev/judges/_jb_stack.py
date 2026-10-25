import numpy as np, cv2
from pathlib import Path
FR = Path("out/frames_p1"); FPS=30
def g(i):
    im = cv2.imdecode(np.fromfile(str(FR/f"f_{i:05d}.jpg"), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    return im.astype(np.float32)
# stack region in 960x540 preview coords
def region(im, x0,x1,y0,y1): return im[y0:y1, x0:x1]
prev=None; out=[]
for i in range(int(14.6*FPS), int(21.5*FPS)):
    im = g(i)
    r = region(im, 560, 960, 40, 540)
    if prev is not None:
        out.append((i, float(np.abs(r-prev).mean())))
    prev=r
out=np.array(out)
# find arrival spikes
thr = out[:,1].mean()+2.2*out[:,1].std()
print("thr", round(float(thr),2), "mean", round(float(out[:,1].mean()),2))
for i,v in out:
    if v>thr:
        print(f"  f{int(i):4d} t={i/FPS:6.2f} stackDiff={v:6.2f}")
