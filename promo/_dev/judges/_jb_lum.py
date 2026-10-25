import numpy as np
lum=np.load("_jb_lum.npy"); d=np.load("_jb_diff.npy"); FPS=30
for a,b,name in [(6.90,7.30,"cut 7.2"),(26.10,26.50,"cut 26.4"),(34.60,36.10,"flash 34.7/35.7"),(35.90,36.30,"cut 36.0"),(45.40,45.80,"cut 45.6"),(14.20,14.60,"cut 14.4"),(4.20,4.50,"shutter1"),(4.85,5.10,"shutter2"),(5.50,5.80,"shutter3")]:
    print(f"--- {name}")
    i0=int(a*FPS); i1=int(b*FPS)
    print("  " + "  ".join(f"{i/FPS:.2f}:{lum[i]:.2f}/{d[i]:.3f}" for i in range(i0,i1+1)))
