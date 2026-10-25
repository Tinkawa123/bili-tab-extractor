import numpy as np
from scipy.io import wavfile
from scipy import signal
sr,x=wavfile.read("out/jb/mp4_audio.wav")
if x.ndim>1: x=x.mean(axis=1)
x=x.astype(np.float32)/32768.0
b,a=signal.butter(4,[3000/(sr/2),min(12000,sr*0.45)/(sr/2)],btype="band")
hf=signal.lfilter(b,a,x)
hop=sr//200  # 5ms
win=512
n=1+(len(hf)-win)//hop
env=np.zeros(n)
for i in range(n):
    seg=hf[i*hop:i*hop+win]*np.hanning(win)
    env[i]=np.sqrt(np.mean(seg**2))
db=20*np.log10(env+1e-7)
print("HF band onset peaks 3.8-6.2s (5ms res):")
for a_,b_ in [(3.8,4.6),(4.6,5.2),(5.2,6.2)]:
    i0=int(a_*200); i1=int(b_*200)
    seg=db[i0:i1]
    idx=np.argsort(seg)[-6:][::-1]
    print(f"  {a_}-{b_}: " + "  ".join(f"{(i0+j)/200:.3f}({seg[j]:.1f})" for j in idx))
print()
print("HF level around 4.30/4.95/5.60 (baseline vs peak):")
for t in [4.30,4.95,5.60,4.58,9.90]:
    i=int(t*200)
    lo=max(0,i-40); hi=min(n,i+40)
    print(f"  t={t:.2f}: local max {db[lo:hi].max():.1f} dB at {lo+int(np.argmax(db[lo:hi]))/200:.3f}s, floor {np.median(db[max(0,i-200):i+200]):.1f}")
