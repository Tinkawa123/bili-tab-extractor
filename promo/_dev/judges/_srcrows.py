from pathlib import Path
import numpy as np
from PIL import Image
d = Path(r"C:\Users\20849\Desktop\视频扒谱\out\测试集\Paranoid")
fs = sorted(d.glob("*.png"))
print(len(fs))
imgs=[]
for p in fs:
    im = np.asarray(Image.open(str(p)).convert("L"))
    h = 120; w = int(round(im.shape[1]*h/im.shape[0]))
    imgs.append((p.name, im.shape, np.asarray(Image.fromarray(im).resize((w,h)))))
for i,(n,s,_) in enumerate(imgs): print(i,n,s)
for i in range(len(imgs)-1):
    a = imgs[i][2].astype(np.int16); b = imgs[i+1][2].astype(np.int16)
    print(f"{imgs[i][0]} vs {imgs[i+1][0]}: {np.abs(a-b).mean():.1f}")
