import numpy as np
from scipy.io import wavfile
from scipy import signal
sr,x=wavfile.read("out/jb/mp4_audio.wav")
if x.ndim>1: x=x.mean(axis=1)
x=x.astype(np.float32)/32768.0
b,a=signal.butter(4,[1500/(sr/2),min(9000,sr*0.45)/(sr/2)],btype="band")
hf=signal.lfilter(b,a,x)
hop=sr//200; win=512
n=1+(len(hf)-win)//hop
env=np.zeros(n)
for i in range(n):
    seg=hf[i*hop:i*hop+win]*np.hanning(win)
    env[i]=np.sqrt(np.mean(seg**2))
db=20*np.log10(env+1e-7)
# onset = positive diff, peak pick with 90ms refractory
d=np.maximum(0,np.diff(db))
i0=int(14.6*200); i1=int(21.2*200)
cand=[]
for i in range(i0+1,i1-1):
    if d[i]>=d[i-1] and d[i]>d[i+1] and d[i]>1.5:
        cand.append((i/200.0, float(d[i])))
merged=[]
for t,v in cand:
    if merged and t-merged[-1][0]<0.09:
        if v>merged[-1][1]: merged[-1]=(t,v)
    else: merged.append((t,v))
print("click/HF onsets 14.6-21.2:")
for t,v in merged:
    print(f"  {t:6.3f}  {v:5.1f}")
print("\ndeltas:")
for k in range(1,len(merged)):
    print(f"  {merged[k-1][0]:6.3f} -> {merged[k][0]:6.3f}  = {merged[k][0]-merged[k-1][0]:.3f}")
