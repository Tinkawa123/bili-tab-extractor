import numpy as np, cv2
from pathlib import Path
FR = Path("out/frames_p1")
def g(i):
    return cv2.imdecode(np.fromfile(str(FR/f"f_{i:05d}.jpg"), dtype=np.uint8), cv2.IMREAD_GRAYSCALE).astype(np.float32)
for a,b in [(568,615),(585,590),(568,569),(600,601),(614,615),(444,447),(900,910)]:
    A,B = g(a),g(b)
    d = np.abs(A-B)
    print(f"f{a}-f{b}: mean={d.mean()/255:.5f} max={d.max():.0f} p99={np.percentile(d,99):.1f} frac>10={np.mean(d>10)*100:.2f}%")
