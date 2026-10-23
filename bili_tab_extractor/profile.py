# -*- coding: utf-8 -*-
"""谱面视觉特征分析（自适应阈值）。

思路：不写死"白底=230、墨迹=100"这类阈值，而是先分析视频谱面的实际特征：
- 背景有多亮（纯白 255 / 浅灰 217 / 米色 …）
- 墨迹有多暗（黑字 / 灰字 …）
- 对比度、背景色调（饱和度）
- 内容密度（墨迹像素占比）

然后据此**动态计算阈值**，并打上特征标签。任何谱面风格都能自适应，
避免"针对某个视频调参数"的特化调试。
"""

from __future__ import annotations

import numpy as np

import cv2


def analyze_profile(crop_imgs, sample: int = 8) -> dict:
    """分析谱面视觉特征，返回特征字典 + 自适应阈值。

    crop_imgs: 裁剪后的谱面帧（BGR ndarray 列表）
    返回:
    {
      "bg_gray": int,      # 背景灰度（亮峰，约 90 分位）
      "ink_gray": int,     # 墨迹灰度（暗峰，约 10 分位）
      "contrast": int,     # 对比度 = bg - ink
      "bg_sat": int,       # 背景饱和度（背景区域 S 中位数）
      "content_frac": float,  # 内容密度（墨迹像素比例）
      "labels": [...],     # 特征标签
      "thresholds": {      # 自适应阈值（供各行过滤函数使用）
          "bright": int,   # 灰度 > bright 视为"背景/亮区"
          "dark": int,     # 灰度 < dark 视为"墨迹"
          "skin_sat": int, # 肤色饱和度下限（避免米色/暖色背景误判）
          "skin_v": int,   # 肤色亮度下限
          "screen_bright": int,  # 画面行亮度上限（低于此视为演奏画面）
          "screen_sat": int,     # 画面行饱和度下限
      }
    }
    """
    if not crop_imgs:
        return _default_profile()

    # 采样若干帧
    step = max(1, len(crop_imgs) // sample)
    picks = crop_imgs[::step][:sample]

    bg_vals, ink_vals, sat_bg_vals = [], [], []
    content_fracs = []
    for img in picks:
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            g = gray.reshape(-1)
            # 背景/墨迹：用分位数（抗噪）
            bg = float(np.percentile(g, 90))
            ink = float(np.percentile(g, 10))
            bg_vals.append(bg)
            ink_vals.append(ink)
            # 背景区域饱和度（灰度接近 bg 的像素）
            bg_mask = gray > (bg - 8)
            if bg_mask.any():
                sat_bg_vals.append(float(np.median(hsv[:, :, 1][bg_mask])))
            # 内容密度（墨迹占比，用中值阈值）
            thr = (bg + ink) / 2
            content_fracs.append(float((gray < thr).mean()))
        except Exception:
            continue

    if not bg_vals:
        return _default_profile()

    bg_gray = int(np.median(bg_vals))
    ink_gray = int(np.median(ink_vals))
    contrast = bg_gray - ink_gray
    bg_sat = int(np.median(sat_bg_vals)) if sat_bg_vals else 0
    content_frac = float(np.median(content_fracs))

    # ---------- 特征标签 ----------
    labels = []
    if bg_gray >= 240:
        labels.append("纯白背景")
    elif bg_gray >= 185:
        labels.append("浅灰/米色背景")
    else:
        labels.append("暗背景")
    if contrast >= 120:
        labels.append("高对比")
    elif contrast >= 60:
        labels.append("中对比")
    else:
        labels.append("低对比")
    if bg_sat >= 30:
        labels.append("有色背景（暖/冷调）")
    if content_frac < 0.05:
        labels.append("稀疏内容")
    elif content_frac > 0.25:
        labels.append("密集内容")

    # ---------- 自适应阈值 ----------
    thresholds = {
        # 亮区（背景）判定：比背景中值低 40 左右仍算亮
        "bright": int(max(160, bg_gray - 40)),
        # 墨迹判定：背景与墨迹中点再偏墨迹一侧（保证墨迹被识别）
        "dark": int(min(160, ink_gray + max(20, contrast * 0.45))),
        # 肤色饱和度下限：比背景饱和度高一截（米色背景约 10-20，肤色 60+）
        "skin_sat": int(max(55, bg_sat + 40)),
        # 肤色亮度下限：墨迹亮度之上
        "skin_v": int(max(60, ink_gray + 40)),
        # 演奏画面行：亮度低于背景 60 以上，或饱和度高
        "screen_bright": int(max(120, bg_gray - 60)),
        "screen_sat": int(max(50, bg_sat + 45)),
    }

    return {
        "bg_gray": bg_gray,
        "ink_gray": ink_gray,
        "contrast": contrast,
        "bg_sat": bg_sat,
        "content_frac": round(content_frac, 4),
        "labels": labels,
        "thresholds": thresholds,
    }


def _default_profile() -> dict:
    """兜底（纯白背景的经典参数）。"""
    return {
        "bg_gray": 245,
        "ink_gray": 40,
        "contrast": 205,
        "bg_sat": 10,
        "content_frac": 0.1,
        "labels": ["默认（未分析）"],
        "thresholds": {
            "bright": 190,
            "dark": 100,
            "skin_sat": 55,
            "skin_v": 80,
            "screen_bright": 170,
            "screen_sat": 60,
        },
    }
