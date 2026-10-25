import numpy as np
from scipy.io import wavfile
from scipy import signal
sr,x=wavfile.read("out/jb/mp4_audio.wav")
if x.ndim>1: x=x.mean(axis=1)
x=x.astype(np.float32)/32768.0
seg=x[int(14.0*sr):int(22.0*sr)].copy()
del x
b,a=signal.butter(4,[1500/(sr/2),min(9000,sr*0.45)/(sr/2)],btype="band")
hf=signal.lfilter(b,a,seg).astype(np.float32)
hop=sr//200; win=512
n=1+(len(hf)-win)//hop
env=np.zeros(n,np.float32)
for i in range(n):
    w=hf[i*hop:i*hop+win]*np.hanning(win)
    env[i]=np.sqrt(np.mean(w*w))
db=20*np.log10(env+1e-7)
d=np.maximum(0,np.diff(db))
i0=int(0.6*200); i1=int(7.2*200)
cand=[]
for i in range(i0+1,i1-1):
    if d[i]>=d[i-1] and d[i]>d[i+1] and d[i]>1.5:
        cand.append((14.0+i/200.0, float(d[i])))
merged=[]
for t,v in cand:
    if merged and t-merged[-1][0]<0.09:
        if v>merged[-1][1]: merged[-1]=(t,v)
    else: merged.append((t,v))
print("onsets (rel 14.0 offset applied):")
prev=None
for t,v in merged:
    dl = f"{t-prev:+.3f}" if prev else "  -  "
    print(f"  {t:7.3f}  amp{v:5.1f}  dt{dl}")
    prev=t
