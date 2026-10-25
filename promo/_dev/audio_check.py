from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile
from PIL import Image

HERE = Path(__file__).resolve().parent
sr, x = wavfile.read(str(HERE / "out" / "score.wav"))
x = x.astype(np.float32) / 32768.0
mono = x.mean(axis=1)
print("dur", len(x) / sr, "peak", np.abs(x).max(), "rms", np.sqrt((x**2).mean()))

# spectrogram
f, t, Z = signal.stft(mono, sr, nperseg=2048, noverlap=1536)
mag = np.abs(Z)
db = 20 * np.log10(mag + 1e-8)
db = np.clip((db + 90) / 90, 0, 1)
img = (db[::-1] * 255).astype(np.uint8)
img = np.asarray(Image.fromarray(img).resize((1800, 500), Image.BILINEAR))
rgb = np.stack([img, img, img], axis=2)

# waveform strip
W = 1800
env = np.abs(mono).reshape(-1, len(mono) // W)[:W].max(axis=1)
wf = np.zeros((220, W, 3), np.uint8)
for i, v in enumerate(env):
    h = int(v * 210)
    wf[110 - h : 110 + h, i] = [80, 220, 190]
out = np.vstack([wf, rgb])
# grid every bar (2.4 s)
bar_px = int(W * 2.4 / (len(mono) / sr))
for b in range(1, 26):
    xx = b * bar_px
    if xx < W:
        out[220:, xx : xx + 1] = [255, 90, 80]
Image.fromarray(out).save(str(HERE / "out" / "audio_check.png"))
print("saved audio_check.png")
