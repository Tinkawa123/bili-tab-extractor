# -*- coding: utf-8 -*-
"""检查被判定为碎片的行的 VLM 分析。"""
import json
import sys

sys.path.insert(0, r"C:\Users\20849\Desktop\视频扒谱\bili_tab_extractor")
from util import imread
from vlm_recognize import _img_hash

cache = json.load(open("_vlm_rec_work/vlm_analysis_cache.json", encoding="utf-8"))
for i in [0, 1, 2, 4, 5, 26, 29]:
    img = imread(f"_vlm_rec_rows/r{i:03d}.png")
    a = cache.get(_img_hash(img), {})
    print(f"\nr{i:03d} {img.shape[1]}x{img.shape[0]} is_complete={a.get('is_complete')}")
    print(f"  type={a.get('row_type')} chords={a.get('chords')}")
    print(f"  content={str(a.get('content'))}")
