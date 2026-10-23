# -*- coding: utf-8 -*-
"""完整流程测试：AI 识别 + 碎片/去重 + 清理 + 输出 PDF + 逐页检查。"""
import glob
import json
import os
import sys

sys.path.insert(0, r"C:\Users\20849\Desktop\视频扒谱\bili_tab_extractor")
from util import imread, imwrite
from vlm_recognize import (analyze_rows, find_duplicate_groups,
                           find_incomplete_rows, duplicate_reasons)
from stitch import make_pdf_from_rows, verify_and_clean_pdf
from pipeline import TabRow
import numpy as np

files = sorted(glob.glob("_vlm_rec_rows/r*.png"))
rows = []
for f in files:
    img = imread(f)
    if img is not None:
        rows.append(TabRow(img, 0, os.path.basename(f), 0))
print(f"载入 {len(rows)} 行")

cache = os.path.join("_vlm_rec_work", "vlm_analysis_cache.json")
analyses = analyze_rows(rows, cache_path=cache, max_workers=4,
                        progress=lambda d, t: print(f"  分析 {d}/{t}", end="\r"))
print()

frags = find_incomplete_rows(analyses, rows)
groups = find_duplicate_groups(analyses)
print(f"碎片/空谱行: {len(frags)} -> {frags}")
print(f"重复组: {len(groups)} 组")
for g in groups:
    print(f"  组 {g}")
    reasons = duplicate_reasons({i: analyses[i] for i in g})
    for pair, why in reasons.items():
        print(f"    {pair}: {why}")

# 清理：删碎片 + 重复组留第一个
to_del = set(frags)
for g in groups:
    for i in g[1:]:
        to_del.add(i)
print(f"\n将删除 {len(to_del)} 行: {sorted(to_del)}")
kept = [r for i, r in enumerate(rows) if i not in to_del]
print(f"保留 {len(kept)} 行")

os.makedirs("_ai_out", exist_ok=True)
for i, r in enumerate(kept):
    imwrite(os.path.join("_ai_out", f"行{i + 1:03d}.png"), r.image)
pdf = "_ai_out/AI清理后.pdf"
make_pdf_from_rows([(r.image, r.source, r.index) for r in kept], pdf, "AI清理后")
verify_and_clean_pdf(pdf)
print(f"PDF: {pdf}")

# 保存分析结果供检查
with open("_ai_out/analyses.json", "w", encoding="utf-8") as f:
    json.dump(analyses, f, ensure_ascii=False, indent=1)
