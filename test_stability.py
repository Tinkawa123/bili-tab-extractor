# -*- coding: utf-8 -*-
"""检查 VLM 识别稳定性：同一批图两次识别的差异。"""
import glob
import json
import os
import sys

sys.path.insert(0, r"C:\Users\20849\Desktop\视频扒谱\bili_tab_extractor")
from util import imread
from vlm_recognize import analyze_row
from pipeline import TabRow

# 用 _vlm_rec_rows 的 51 张图，重新识别（不读缓存）
files = sorted(glob.glob("_vlm_rec_rows/r*.png"))
rows = []
for f in files:
    img = imread(f)
    if img is not None:
        rows.append(TabRow(img, 0, os.path.basename(f), 0))

# 读第一次缓存（test_ai_full 的结果）
cache_path = os.path.join("_vlm_rec_work", "vlm_analysis_cache.json")
old = {}
if os.path.isfile(cache_path):
    old = json.load(open(cache_path, encoding="utf-8"))

print(f"第一次缓存条目: {len(old)}")
old_incomplete = sum(1 for a in old.values() if not a.get("is_complete", True))
print(f"第一次 is_complete=False: {old_incomplete}")

# 重新识别前 10 行，对比
print("\n重新识别前 10 行，对比 is_complete：")
from vlm_recognize import _img_hash

n_diff = 0
for i in range(min(10, len(rows))):
    h = _img_hash(rows[i].image)
    old_a = old.get(h, {})
    new_a = analyze_row(rows[i].image)
    old_c = old_a.get("is_complete", None)
    new_c = new_a.get("is_complete", None)
    old_chords = old_a.get("chords", [])
    new_chords = new_a.get("chords", [])
    diff = (old_c != new_c) or (old_chords != new_chords)
    if diff:
        n_diff += 1
    print(f"行{i:02d}: complete {old_c}->{new_c}  chords {old_chords} -> {new_chords} {'<<差异' if diff else ''}")
print(f"\n差异行数: {n_diff}/10")
