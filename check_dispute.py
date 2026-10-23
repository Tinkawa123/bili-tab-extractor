# -*- coding: utf-8 -*-
"""检查争议行的 VLM 分析结果。"""
import json
import sys

sys.path.insert(0, r"C:\Users\20849\Desktop\视频扒谱\bili_tab_extractor")
from util import imread
from vlm_recognize import _img_hash

cache = json.load(open("_vlm_rec_work/vlm_analysis_cache.json", encoding="utf-8"))
print(f"缓存条目: {len(cache)}")
for i in [3, 6, 17, 19, 22, 14, 16, 12, 13]:
    img = imread(f"_vlm_rec_rows/r{i:03d}.png")
    a = cache.get(_img_hash(img), {})
    print(f"\nr{i:03d} {img.shape[1]}x{img.shape[0]}")
    print(f"  chords={a.get('chords')}")
    print(f"  rhythm={str(a.get('rhythm'))[:40]!r}")
    print(f"  content={str(a.get('content'))[:100]}")
    print(f"  is_complete={a.get('is_complete')}")
