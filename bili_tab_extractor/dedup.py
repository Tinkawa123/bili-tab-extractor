# -*- coding: utf-8 -*-
"""去重模块：从裁剪帧中筛出"内容不同"的谱面片段。

B 站教学视频播放时，画面底部谱面上会有一个**播放光标**扫过当前行，
此时整帧画面在持续变化，若按整帧相似度判断，同一行会被保留多次；
而谱面行与行之间"弦线完全相同、只有数字/音符不同"，粗粒度感知哈希
（如 9x8 dHash）无法区分（实测 Hamming 距离为 0）。

判定思路（替代 marcelpanse 的 LLM 读小节号方案，纯 CV 无需 API key）：

1. **彩色光标免疫** —— 播放光标/高亮通常是高饱和彩色（红/黄/绿），
   而谱面墨迹是低饱和的。先把两帧中高饱和像素抹白，再做差异分析，
   彩色光标移动就不产生任何差异。
2. **差异列段分析** —— 差异像素按水平方向分段：
   - 播放光标（无论彩色还是黑色）是 1~2 个窄列段（紧凑物体）；
   - 真实换行/翻页时，变化的数字/音符散布全行，形成 >= 4 个列段；
   - 平滑滚动/整页替换时，差异像素占比大（>15%），直接判定为变化。

滚动检测：对保留帧两两做相位相关，估计垂直位移；若普遍存在持续同向
位移，说明是"平滑滚动"型谱面，位移序列供拼接模块使用。
"""

from __future__ import annotations

import cv2
import numpy as np

from util import imread, imwrite, log

SAT_CHROMA = 50       # 高饱和判定：通道差 > 50
SAT_VALUE = 80        # 且亮度 > 80
DIFF_PX = 40          # 像素差异阈值
OBJ_COUNT = 4         # 差异列段数 >= 4 => 内容变化
AREA_FRAC = 0.15      # 差异像素占比 > 15% => 大面积变化（滚动/翻页）


# ---------- 彩色光标免疫 ----------

def _blank_saturated(bgr: np.ndarray) -> np.ndarray:
    """把高饱和像素（彩色光标/高亮）抹白，返回灰度图。"""
    mx = bgr.max(axis=2).astype(np.int16)
    mn = bgr.min(axis=2).astype(np.int16)
    sat = (mx - mn > SAT_CHROMA) & (mx > SAT_VALUE)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray[sat] = 255
    return gray


# ---------- 像素差异分析 ----------

def _col_segments(col_diff: np.ndarray, max_gap: int = 2) -> list[tuple[int, int]]:
    """把差异列分段（允许 max_gap 列的小间隙），返回 [(s, e), ...]。"""
    segs: list[tuple[int, int]] = []
    start = None
    gap = 0
    for i, v in enumerate(col_diff):
        if v:
            if start is None:
                start = i
            gap = 0
        elif start is not None:
            gap += 1
            if gap > max_gap:
                segs.append((start, i - 1))
                start = None
                gap = 0
    if start is not None:
        segs.append((start, len(col_diff) - 1))
    return segs


def _object_diff(gray_a: np.ndarray, gray_b: np.ndarray) -> bool:
    """灰度图差异分析：返回 True 表示谱面内容变化。

    对差异像素（|Δ|>40）做水平方向列段分析：
    - 差异像素占比 > 15% => 大面积变化（平滑滚动/整页替换）
    - 差异列形成 >= 4 个分散列段 => 换行/翻页（变化的数字散布全行）
    - 1~2 个窄列段 => 播放光标（紧凑物体）
    - 3 个列段 => 用总宽度占比兜底
    """
    if gray_a.shape != gray_b.shape:
        return True
    diff = np.abs(gray_a.astype(np.int16) - gray_b.astype(np.int16)) > DIFF_PX
    if not diff.any():
        return False

    frac = float(diff.mean())
    if frac > AREA_FRAC:
        return True

    w = diff.shape[1]
    col_diff = diff.any(axis=0)
    segs = _col_segments(col_diff)
    if len(segs) >= OBJ_COUNT:
        return True
    if len(segs) <= 2:
        return False
    total_w = sum(e - s + 1 for s, e in segs)
    return total_w / w > 0.25


def content_changed(prev_bgr: np.ndarray, cur_bgr: np.ndarray) -> bool:
    """判断两帧谱面内容是否真的变化（区别于光标移动）。"""
    if prev_bgr.shape != cur_bgr.shape:
        return True

    # 1) 抹除彩色光标/高亮后比较（覆盖彩色光标场景）
    if _object_diff(_blank_saturated(prev_bgr), _blank_saturated(cur_bgr)):
        return True

    # 2) 原始灰度比较（覆盖黑色/无色光标场景）
    pg = cv2.cvtColor(prev_bgr, cv2.COLOR_BGR2GRAY)
    cg = cv2.cvtColor(cur_bgr, cv2.COLOR_BGR2GRAY)
    return _object_diff(pg, cg)


# ---------- 滚动位移估计 ----------

def vertical_shift(prev_gray: np.ndarray, cur_gray: np.ndarray) -> float:
    """用相位相关估计 cur 相对 prev 的垂直位移（像素，向下为正）。"""
    if prev_gray.shape != cur_gray.shape:
        return 0.0
    h, w = prev_gray.shape
    if h < 32 or w < 32:
        return 0.0
    a = cv2.GaussianBlur(prev_gray, (3, 3), 0).astype(np.float32)
    b = cv2.GaussianBlur(cur_gray, (3, 3), 0).astype(np.float32)
    try:
        hann = cv2.createHanningWindow((w, h), cv2.CV_32F)
        (_dx, dy), _resp = cv2.phaseCorrelate(a * hann, b * hann)
        return float(dy)
    except cv2.error:
        return 0.0


# ---------- 主流程 ----------

def dedup_crops(crops: list[str]) -> tuple[list[str], list[float]]:
    """对裁剪图去重。

    返回 (保留的裁剪图路径列表, 相邻保留帧之间的垂直位移列表)。
    位移列表供滚动拼接使用；若全部接近 0 说明是"翻页/逐行"型。
    """
    if not crops:
        return [], []

    log.step(f"去重 {len(crops)} 张裁剪图（内容指纹，光标免疫）…")

    kept: list[str] = []
    shifts: list[float] = []
    prev_bgr: np.ndarray | None = None

    for path in crops:
        bgr = imread(path)
        if bgr is None:
            continue

        if prev_bgr is not None:
            if not content_changed(prev_bgr, bgr):
                continue
            shifts.append(vertical_shift(
                cv2.cvtColor(prev_bgr, cv2.COLOR_BGR2GRAY),
                cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)))
        else:
            shifts.append(0.0)

        kept.append(path)
        prev_bgr = bgr

    log.success(f"去重完成：保留 {len(kept)} 张（丢弃 {len(crops) - len(kept)} 张）")

    # 统计滚动程度：|位移| 显著且方向一致的帧占比
    if len(shifts) > 1:
        significant = [s for s in shifts[1:] if abs(s) >= 4]
        if significant:
            same_dir = sum(1 for s in significant if s * np.mean(significant) > 0)
            frac = same_dir / len(significant)
            if frac > 0.6:
                log.info(f"检测到平滑滚动（平均位移 {np.mean(significant):.1f}px/帧，占比 {frac:.0%}），启用滚动拼接")
            else:
                log.info("相邻帧位移方向不一致，按翻页/逐行模式处理")
        else:
            log.info("相邻帧几乎无位移，按翻页/逐行模式处理")

    return kept, shifts
