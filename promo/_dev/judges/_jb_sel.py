import numpy as np, cv2
from pathlib import Path
FR = Path("out/frames_p1"); FPS=30
def g(i):
    return cv2.imdecode(np.fromfile(str(FR/f"f_{i:05d}.jpg"), dtype=np.uint8), cv2.IMREAD_GRAYSCALE).astype(np.float32)
for a,b,label,box in [(27.35,27.75,"sel appear",(160,300,90,300)),(30.10,30.55,"sel vanish",(160,300,90,300)),(29.30,30.20,"drag",(160,300,90,300))]:
    print(f"--- {label} {a}-{b}")
    prev=None
    for i in range(int(a*FPS),int(b*FPS)+1):
        im=g(i)
        if prev is not None:
            y0,y1,x0,x1=box
            d=np.abs(im-prev)[y0:y1,x0:x1]
            print(f"  f{i} t={i/FPS:6.2f} {(d>12).mean()*100:5.2f}%")
        prev=im
