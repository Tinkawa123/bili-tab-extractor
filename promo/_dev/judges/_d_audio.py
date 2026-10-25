import numpy as np
from scipy.io import wavfile
sr, x = wavfile.read(r"out/score.wav")
if x.ndim > 1: x = x.mean(axis=1)
x = x.astype(np.float32)/32768.0
print("sr", sr, "dur", len(x)/sr)
for s in range(0, 60, 1):
    seg = x[int(s*sr):int((s+1)*sr)]
    rms = 20*np.log10(np.sqrt(np.mean(seg**2))+1e-9)
    pk = 20*np.log10(np.abs(seg).max()+1e-9)
    print(f"{s:2d}s rms {rms:6.1f} dB  peak {pk:6.1f} dB")
# last 8 s in 0.25 steps
print("\n-- last 8s @0.25 --")
for k in range(32):
    t0 = 52.0 + k*0.25
    seg = x[int(t0*sr):int((t0+0.25)*sr)]
    rms = 20*np.log10(np.sqrt(np.mean(seg**2))+1e-9)
    print(f"{t0:5.2f} rms {rms:6.1f}")
