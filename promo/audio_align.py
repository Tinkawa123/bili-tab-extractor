"""Check that the score's transients line up with the film's cut points."""
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy import signal

HERE = Path(__file__).resolve().parent
sr, x = wavfile.read(str(HERE / "out" / "score.wav"))
x = x.astype(np.float32) / 32768.0
mono = x.mean(axis=1)
print(f"duration {len(x)/sr:.2f}s  peak {np.abs(x).max():.3f}  rms {20*np.log10(np.sqrt((x**2).mean())+1e-9):.1f} dBFS")

# section energy
for name, t0, t1 in [
    ("S1 intro", 0, 7.2), ("S2 input", 7.2, 14.4), ("S3 extract", 14.4, 26.4),
    ("S4 review", 26.4, 36.0), ("S5 paper", 36.0, 45.6), ("S6 brand", 45.6, 60.0),
]:
    seg = mono[int(t0 * sr) : int(t1 * sr)]
    rms = 20 * np.log10(np.sqrt((seg**2).mean()) + 1e-9)
    peak = np.abs(seg).max()
    print(f"{name:12s} rms {rms:6.1f} dBFS  peak {peak:.3f}")

# onset detection on a high-passed band
hp = signal.lfilter(*signal.butter(2, 200 / (sr / 2), "high"), mono)
env = np.abs(signal.hilbert(hp))
env = signal.lfilter(*signal.butter(2, 30 / (sr / 2)), env)
d = np.diff(env, prepend=env[0])
d = np.maximum(d, 0)
# peak picking
peak_idx, props = signal.find_peaks(d, height=np.percentile(d, 99.0), distance=int(0.05 * sr))
times = peak_idx / sr
print(f"\nstrong onsets: {len(times)}")

cuts = [7.2, 14.4, 26.4, 36.0, 45.6, 52.55, 53.35, 55.35]
for c in cuts:
    near = times[np.abs(times - c) < 0.35]
    if len(near):
        print(f"cut {c:6.2f}s -> onsets {', '.join(f'{v-c:+.3f}' for v in near[:3])}")
    else:
        print(f"cut {c:6.2f}s -> NO onset within 0.35s  <-- check")

# clicks expected
clicks = [9.90, 27.45, 28.45, 33.20, 4.30, 4.90, 5.50]
for c in clicks:
    near = times[np.abs(times - c) < 0.15]
    mark = "ok" if len(near) else "MISSING"
    print(f"click {c:5.2f}s -> {len(near)} onsets {mark}")
