"""JudgeB probe: per-frame motion energy + audio onset envelope + grid alignment."""
import sys, json
import numpy as np, cv2
from pathlib import Path
from scipy.io import wavfile

HERE = Path(__file__).resolve().parent
FR = HERE / "out" / "frames_p1"
N = len(list(FR.glob("f_*.jpg")))
FPS = 30.0
prev = None
lum = []
diff = []
for i in range(N):
    _b = np.fromfile(str(FR / f"f_{i:05d}.jpg"), dtype=np.uint8); img = cv2.imdecode(_b, cv2.IMREAD_GRAYSCALE)
    small = cv2.resize(img, (240, 135), interpolation=cv2.INTER_AREA)
    lum.append(float(small.mean()) / 255.0)
    if prev is None:
        diff.append(0.0)
    else:
        diff.append(float(np.abs(small.astype(np.float32) - prev).mean()) / 255.0)
    prev = small.astype(np.float32)

lum = np.array(lum); diff = np.array(diff)
np.save(HERE / "_jb_diff.npy", diff); np.save(HERE / "_jb_lum.npy", lum)

# smoothen diff for trend
k = 3
sm = np.convolve(diff, np.ones(k) / k, mode="same")

# peaks: local maxima above adaptive threshold
thr = np.median(sm) * 3.0 + 0.004
peaks = []
for i in range(1, N - 1):
    if sm[i] >= sm[i - 1] and sm[i] > sm[i + 1] and sm[i] > thr:
        peaks.append((i, round(i / FPS, 3), round(float(sm[i]), 4)))
print("frames", N)
print("lum min/max/mean", round(lum.min(), 3), round(lum.max(), 3), round(lum.mean(), 3))
print("diff p50/p90/p99", round(float(np.percentile(diff, 50)), 4), round(float(np.percentile(diff, 90)), 4), round(float(np.percentile(diff, 99)), 4))
print("top 60 diff frames:")
idx = np.argsort(diff)[::-1][:60]
for i in sorted(idx):
    print(f"  f{i:4d} t={i/FPS:6.2f} d={diff[i]:.4f} lum={lum[i]:.3f}")

# near-zero motion (frozen) runs
frozen = diff < 0.0015
runs = []
s = None
for i, f in enumerate(frozen):
    if f and s is None: s = i
    if (not f) and s is not None:
        if i - s >= 4: runs.append((s, i - 1, i - s))
        s = None
if s is not None and N - s >= 4: runs.append((s, N - 1, N - s))
print("frozen runs (>=4 frames, diff<0.0015):")
for a, b, n in runs:
    print(f"  f{a}-f{b}  t={a/FPS:.2f}-{b/FPS:.2f}  ({n}f / {n/FPS:.2f}s)  luma={lum[a]:.3f}")

# ---- audio -------------------------------------------------------------
sr, x = wavfile.read(HERE / "out" / "score.wav")
if x.ndim > 1: x = x.mean(axis=1)
x = x.astype(np.float32) / 32768.0
hop = sr // 100  # 10 ms
win = 1024
frames = 1 + (len(x) - win) // hop
env = np.zeros(frames, np.float32)
for i in range(frames):
    seg = x[i * hop:i * hop + win] * np.hanning(win)
    env[i] = np.sqrt(float(np.mean(seg * seg)))
db = 20 * np.log10(env + 1e-6)
# onset = positive spectral flux on band-limited energy
flux = np.maximum(0, np.diff(db))
onsets = []
for i in range(1, len(flux) - 1):
    if flux[i] > flux[i - 1] and flux[i] >= flux[i + 1] and flux[i] > 2.5:
        onsets.append((i / 100.0, float(flux[i])))
# merge within 40ms
merged = []
for t, v in onsets:
    if merged and t - merged[-1][0] < 0.04:
        if v > merged[-1][1]: merged[-1] = (t, v)
    else:
        merged.append((t, v))
print("\naudio onsets (db-flux > 2.5), n=", len(merged))
bar = 2.4; sixteenth = 0.15
def off_grid(t):
    r = (t / sixteenth) % 1.0
    return min(r, 1 - r) * sixteenth * 1000.0
print("time   flux  dev16th(ms) devbar(ms)")
for t, v in merged:
    print(f"{t:6.2f} {v:5.1f}  {off_grid(t):6.1f}")
print("\nRMS per second:")
for s in range(60):
    seg = x[int(s*sr):int((s+1)*sr)]
    print(f"  {s:2d}s {20*np.log10(np.sqrt(np.mean(seg**2))+1e-9):6.1f} dB")
