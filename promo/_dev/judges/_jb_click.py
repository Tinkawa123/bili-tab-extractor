import numpy as np
from scipy.io import wavfile
sr,x=wavfile.read("out/jb/mp4_audio.wav")
if x.ndim>1: x=x.mean(axis=1)
x=x.astype(np.float32)/32768.0
def env(t0,t1,step=0.01):
    out=[]
    for t in np.arange(t0,t1,step):
        s=x[int(t*sr):int((t+step)*sr)]
        out.append((t, 20*np.log10(np.sqrt(np.mean(s**2))+1e-9)))
    return out
print("full-band RMS 10ms, 9.70-10.10 (click should pop at 9.90)")
for t,v in env(9.70,10.10):
    bar="#"*max(0,int((v+45)*2))
    print(f"  {t:6.2f} {v:6.1f} {bar}")
print()
print("full-band RMS 10ms, 4.20-4.40 (shutter1)")
for t,v in env(4.20,4.40):
    print(f"  {t:6.2f} {v:6.1f} " + "#"*max(0,int((v+45)*2)))
