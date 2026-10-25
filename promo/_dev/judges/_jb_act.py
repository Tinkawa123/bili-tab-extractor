import numpy as np, cv2
from pathlib import Path
FR = Path("out/frames_p1"); FPS=30
def g(i):
    return cv2.imdecode(np.fromfile(str(FR/f"f_{i:05d}.jpg"), dtype=np.uint8), cv2.IMREAD_GRAYSCALE).astype(np.float32)
prev=None; act=np.zeros(1800, np.float32); amp=np.zeros(1800, np.float32)
for i in range(1800):
    im=g(i)
    if prev is not None:
        d=np.abs(im-prev)
        act[i]=float((d>10).mean()*100)   # % pixels changed noticeably
        amp[i]=float(np.percentile(d,99.5))
    prev=im
np.save("_jb_act.npy", act); np.save("_jb_amp.npy", amp)
print("per-0.5s: mean active% (pixels changing >10 levels)")
line=[]
for s in range(120):
    a=act[s*15:(s+1)*15]
    line.append(f"{s*0.5:5.1f}:{a.mean():4.1f}")
print("  ".join(line[:40])); print("  ".join(line[40:80])); print("  ".join(line[80:]))
print()
for a,b,name in [(0,7.2,"S1"),(7.2,14.4,"S2"),(14.4,26.4,"S3"),(26.4,36.0,"S4"),(36.0,45.6,"S5"),(45.6,60,"S6")]:
    seg=act[int(a*FPS):int(b*FPS)]
    print(f"{name} {a:5.1f}-{b:5.1f}: mean active {seg.mean():5.2f}%  median {np.median(seg):5.2f}%  frac<1% {np.mean(seg<1)*100:5.1f}%  frac<3% {np.mean(seg<3)*100:5.1f}%")
print(f"ALL: mean {act[1:].mean():.2f}%  frac<1% {np.mean(act[1:]<1)*100:.1f}%")
