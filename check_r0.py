# -*- coding: utf-8 -*-
"""检查前几行的碎片判定。"""
import json
import sys

sys.path.insert(0, r"C:\Users\20849\Desktop\视频扒谱\bili_tab_extractor")
import cv2

from util import imread
from vlm_recognize import _img_hash, cv_is_likely_fragment

cache = json.load(open("_vlm_rec_work/vlm_analysis_cache.json", encoding="utf-8"))
print("缓存条目:", len(cache))
for i in range(8):
    img = imread(f"_vlm_rec_rows/r{i:03d}.png")
    a = cache.get(_img_hash(img), {})
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    frac = (gray < 150).mean()
    print(f"r{i:03d}: is_complete={a.get('is_complete')} cv_frag={cv_is_likely_fragment(img)} "
          f"h={h} dark={frac * 100:.2f}%")
