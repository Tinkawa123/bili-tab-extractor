import numpy as np
from pathlib import Path
d = np.load("_jb_diff.npy"); lum = np.load("_jb_lum.npy")
FPS=30
print("idx t diff  (scene3 14.4-26.4)")
for i in range(int(14.4*FPS), int(26.5*FPS)):
    print(f"{i:4d} {i/FPS:6.2f} {d[i]:.4f} {lum[i]:.3f}")
