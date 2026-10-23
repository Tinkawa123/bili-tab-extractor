# -*- coding: utf-8 -*-
"""测试 VLM 碎片检测（圣诞结真实碎片图）。"""
import os
import sys

sys.path.insert(0, r"C:\Users\20849\Desktop\视频扒谱\bili_tab_extractor")
from util import imread
from vlm_recognize import analyze_row

base = r"C:\Users\20849\Desktop\视频扒谱\out\「圣诞结」完整还原前奏、间奏和尾奏的吉他改编\谱行图片"
tests = ["行052.png", "行053.png", "行054.png", "行055.png", "行056.png", "行050.png", "行051.png"]
for t in tests:
    path = os.path.join(base, t)
    img = imread(path)
    if img is None:
        print(t, "读取失败")
        continue
    r = analyze_row(img)
    print(f"{t} {img.shape[1]}x{img.shape[0]}: complete={r.get('is_complete')} "
          f"type={r.get('row_type')} chords={r.get('chords')} "
          f"rhythm={str(r.get('rhythm', ''))[:15]!r}")
