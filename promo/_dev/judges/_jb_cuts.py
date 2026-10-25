import numpy as np
from scipy.io import wavfile
sr,x=wavfile.read("out/jb/mp4_audio.wav")
if x.ndim>1: x=x.mean(axis=1)
x=x.astype(np.float32)/32768.0
for a,b in [(7.10,7.32),(26.24,26.52),(45.46,45.70),(52.40,52.60)]:
    print(f"--- {a}-{b}")
    for t in np.arange(a,b,0.02):
        s=x[int(t*sr):int((t+0.02)*sr)]
        v=20*np.log10(np.sqrt(np.mean(s**2))+1e-9)
        print(f"  {t:6.2f} {v:6.1f} " + "#"*max(0,int((v+45)*2)))
