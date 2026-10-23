# -*- coding: utf-8 -*-
"""检查争议行的 lyrics/content 字段。"""
import json
import sys

sys.path.insert(0, r"C:\Users\20849\Desktop\视频扒谱\bili_tab_extractor")
from util import imread
from vlm_recognize import _img_hash

cache = json.load(open("_vlm_rec_work/vlm_analysis_cache.json", encoding="utf-8"))
for i in [10, 12, 13, 38, 44, 47]:
    img = imread(f"_vlm_rec_rows/r{i:03d}.png")
    a = cache.get(_img_hash(img), {})
    print(f"\nr{i:03d}:")
    print(f"  lyrics={a.get('lyrics')!r}")
    print(f"  content={str(a.get('content'))!r}")
