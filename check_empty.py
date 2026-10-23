# -*- coding: utf-8 -*-
"""排查空谱：统计每行图的内容量，找出空白/内容过少的行。"""
import glob
import os
import sys

sys.path.insert(0, r"C:\Users\20849\Desktop\视频扒谱\bili_tab_extractor")
import numpy as np
import cv2

from util import imread

files = sorted(glob.glob("_vlm_rec_rows/r*.png"))
print(f"共 {len(files)} 行图\n")
print(f"{'行':<4} {'尺寸':<12} {'暗像素%':<8} {'长线数':<6} {'判定'}")
suspicious = []
for f in files:
    img = imread(f)
    if img is None:
        print(f"{os.path.basename(f)}: 读取失败")
        continue
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    dark = gray < 150
    dark_frac = dark.mean()
    # 长线数（横跨 40% 宽度的暗行）
    n_long = 0
    for y in range(h):
        cols = np.where(dark[y])[0]
        if len(cols) > 0 and cols.max() - cols.min() > 0.4 * w:
            n_long += 1
    verdict = "OK"
    if dark_frac < 0.005:
        verdict = "⚠ 空白/几乎无内容"
        suspicious.append((f, "空白"))
    elif dark_frac < 0.02 and n_long < 3:
        verdict = "⚠ 内容过少"
        suspicious.append((f, "内容少"))
    print(f"{os.path.basename(f):<8} {w}x{h:<8} {dark_frac * 100:>6.2f}%  {n_long:<6} {verdict}")

print(f"\n疑似问题行: {len(suspicious)}")
for f, why in suspicious:
    print(f"  {os.path.basename(f)}: {why}")
