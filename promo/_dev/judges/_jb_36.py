import numpy as np
from scipy.io import wavfile
sr,x=wavfile.read("out/jb/mp4_audio.wav")
if x.ndim>1: x=x.mean(axis=1)
x=x.astype(np.float32)/32768.0
for t in np.arange(35.80,36.50,0.02):
    s=x[int(t*sr):int((t+0.02)*sr)]
    v=20*np.log10(np.sqrt(np.mean(s**2))+1e-9)
    print(f"  {t:6.2f} {v:6.1f} " + "#"*max(0,int((v+45)*2)))
