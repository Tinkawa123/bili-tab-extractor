import sys
from pathlib import Path
sys.path.insert(0, r"C:\Users\20849\Desktop\视频扒谱\promo")
import numpy as np, cv2
HERE = Path(r"C:\Users\20849\Desktop\视频扒谱\promo")
FR = HERE/"out"/"frames_p1"
def load(i):
    b = np.fromfile(str(FR/f"f_{i:05d}.jpg"), dtype=np.uint8)
    return cv2.imdecode(b, cv2.IMREAD_COLOR)
im = load(900); print(im.shape)
