import numpy as np
from scipy.io import wavfile
sr,x = wavfile.read("out/jb/mp4_audio.wav")
if x.ndim>1: x=x.mean(axis=1)
x=x.astype(np.float32)/32768.0
print("dur", len(x)/sr, "rms", 20*np.log10(np.sqrt(np.mean(x**2))+1e-9))
hop=sr//100; win=1024
n=1+(len(x)-win)//hop
db=np.zeros(n,np.float32)
for i in range(n):
    seg=x[i*hop:i*hop+win]*np.hanning(win)
    db[i]=20*np.log10(np.sqrt(np.mean(seg**2))+1e-6)
flux=np.maximum(0,np.diff(db))
for a,b,label in [(4.0,4.6,"shutter1"),(4.6,5.2,"shutter2"),(5.2,5.9,"shutter3"),(9.5,10.2,"click"),(14.2,14.6,"impact14.4"),(15.2,16.0,"tick0?"),(19.0,19.5,"19.2"),(20.0,21.1,"dedupe"),(22.0,22.3,"sweep"),(26.1,26.5,"impact26.4"),(38.2,38.6,"38.4 hit"),(38.6,39.0,"flip sfx"),(45.4,45.8,"impact45.6"),(47.0,47.4,"chime47.15"),(49.0,49.5,"chime49.2"),(50.4,50.9,"chime50.6"),(52.4,52.7,"logo whoosh"),(53.2,53.6,"chime53.35"),(55.2,55.7,"chime55.35"),(56.0,56.5,"chime56.2")]:
    i0=int(a*100); i1=int(b*100)
    seg=flux[i0:i1]
    if len(seg)==0: continue
    k=int(np.argmax(seg))
    print(f"{label:16s} peak t={ (i0+k)/100:6.2f} flux={seg[k]:5.1f}  top3={[round((i0+j)/100,2) for j in np.argsort(seg)[-3:][::-1]]}")
