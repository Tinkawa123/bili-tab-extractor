import numpy as np
d = np.load("_jb_diff.npy"); lum = np.load("_jb_lum.npy"); FPS=30
# motion "events": frames with diff above 0.0025, grouped into bursts separated by >=5 quiet frames
thr=0.0025
act = d > thr
bursts=[]; i=0; n=len(d)
while i < n:
    if act[i]:
        j=i
        while j+1<n and (act[j+1] or (j+6<n and act[j+1:j+6].any())):
            j+=1
        bursts.append((i,j))
        i=j+1
    else: i+=1
print("bursts (motion), 30fps:")
for a,b in bursts:
    seg=d[a:b+1]
    print(f"  {a/FPS:6.2f}-{b/FPS:6.2f}  {b-a+1:3d}f  peak={seg.max():.3f}@{a+int(seg.argmax())/FPS if False else (a+int(seg.argmax()))/FPS:6.2f}  lum={lum[a]:.2f}")
print()
print("quiet gaps >0.6s:")
for k in range(len(bursts)-1):
    gap=(bursts[k+1][0]-bursts[k][1]-1)/FPS
    if gap>0.6:
        print(f"  {bursts[k][1]/FPS:6.2f} -> {bursts[k+1][0]/FPS:6.2f}  {gap:5.2f}s quiet")
