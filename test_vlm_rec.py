# -*- coding: utf-8 -*-
"""VLM 识别 + 语义去重测试（富士山下）。"""
import json
import os
import sys
import time

sys.path.insert(0, r"C:\Users\20849\Desktop\视频扒谱\bili_tab_extractor")
from pipeline import process
from vlm import load_model
from vlm_recognize import analyze_rows, find_duplicate_groups, duplicate_reasons
from util import imwrite

work = os.path.abspath("_vlm_rec_work")
result = process(video=os.path.abspath("fuji.mp4"), title="VLM识别测试",
                 work_dir=work, max_height=360,
                 progress=lambda t, f: None)
rows = result.kept_rows
print(f"pipeline: {len(rows)} 行")

# 保存所有行图供检查
os.makedirs("_vlm_rec_rows", exist_ok=True)
for i, r in enumerate(rows):
    imwrite(os.path.join("_vlm_rec_rows", f"r{i:03d}.png"), r.image)

t0 = time.time()
cache = os.path.join(work, "vlm_analysis_cache.json")
analyses = analyze_rows(rows, cache_path=cache, max_workers=4,
                        progress=lambda d, t: print(f"  识别 {d}/{t}", end="\r"))
print(f"\n识别完成，耗时 {time.time() - t0:.0f}s")

# 打印每行识别结果
for i in sorted(analyses):
    a = analyses[i]
    print(f"[{i:02d}] type={a.get('row_type'):<13} chords={a.get('chords')} "
          f"rhythm={a.get('rhythm')[:20]!r} bars={a.get('bar_numbers')} "
          f"lyrics={a.get('lyrics')[:15]!r}")

# 去重组
groups = find_duplicate_groups(analyses)
print(f"\n=== 发现 {len(groups)} 组重复 ===")
reasons = duplicate_reasons(analyses)
for g in groups:
    print(f"组 {g}:")
    for pair, why in reasons.items():
        if pair[0] in g and pair[1] in g:
            print(f"   {pair}: {why}")

# 保存结果
with open("_vlm_rec_result.json", "w", encoding="utf-8") as f:
    json.dump({"analyses": analyses, "groups": groups,
               "reasons": {f"{k[0]}-{k[1]}": v for k, v in reasons.items()}},
              f, ensure_ascii=False, indent=1)
print("\n结果已保存 _vlm_rec_result.json")
