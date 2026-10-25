# -*- coding: utf-8 -*-
"""谱面小节线 & 播放光标检测（CV，移植自 BiliTabCapture / score_capture 思路）。

用途：
1. detect_barlines(image)：检测谱面上的小节线（竖线）x 坐标。
   - 横向滚动谱带（Guitar Pro 类）：**不依赖 VLM 也能按小节切分/排序**，
     VLM 额度耗尽时作为兜底。
2. detect_playhead(image)：检测"播放光标"竖条（B 站谱面视频常见蓝/绿色高亮条）。
   - 同一行谱面在光标位置不同时会被当成不同帧 → 去重时可用 mask_playhead 忽略光标区域。
3. split_into_measures(image, bars)：按小节线切竖条（对齐小节，避免切到一半）。

算法来源：detect_horizontal_lines → get_score_lines 定位谱表行区域；
形态学闭运算连接竖线断点；逐列墨迹比 + 上下对称性/白占比过滤音符符干；
最后合并过近双竖线（反复记号），回退到逐列墨迹占比启发式。
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class _StaffLine:
    """简化线段：start 为法向起始坐标（横线=y，竖线=x），thickness 为粗细。"""

    start: int
    thickness: int
    direction: str

    @property
    def end_index(self) -> int:
        return self.start + self.thickness - 1


def _to_gray(image) -> np.ndarray:
    """接受 BGR/RGB/Gray ndarray 或 PIL Image，返回灰度 uint8。"""
    if hasattr(image, "convert"):   # PIL
        return np.array(image.convert("L"), dtype=np.uint8)
    if image.ndim == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image.astype(np.uint8)


def detect_horizontal_lines(gray: np.ndarray, coefficient: float = 0.7) -> list[_StaffLine]:
    """识别白底图中的水平线（黑线），返回行线段列表。"""
    gray = _to_gray(gray)
    if float(np.average(gray)) < 128:
        gray = 255 - gray
    img_adaptive = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 5, 7)
    average_row = np.average(img_adaptive, axis=1)
    hit = average_row < 255 * coefficient

    lines: list[_StaffLine] = []
    current_y = 1
    point_y = 0
    for i in range(len(average_row)):
        if bool(hit[i]) and not point_y:
            point_y = current_y
        elif not bool(hit[i]) and point_y:
            thickness = current_y - point_y
            lines.append(_StaffLine(start=point_y, thickness=thickness, direction="H"))
            point_y = 0
        current_y += 1
    return lines


def get_score_lines(horizontal_lines: list[_StaffLine]) -> list[_StaffLine]:
    """从水平线检测结果中筛出谱表（staff）部分的横线。"""
    if len(horizontal_lines) < 3:
        return []
    ys = np.asarray([line.start for line in horizontal_lines])
    distance = ys[1:] - ys[:-1]
    if distance.size == 0:
        return []
    index = np.flatnonzero(
        (distance - np.average(distance)) / (np.std(distance) + 0.1) > 2) + 1
    index = np.sort(np.append(index, [0, len(horizontal_lines)]))
    index = [(int(index[i]), int(index[i + 1])) for i in range(len(index) - 1)]
    index = [i for i in index if (i[1] - i[0]) > 3]
    try:
        return [horizontal_lines[i:j] for i, j in index][-1]
    except IndexError:
        return []


def _preprocess_vertical(gray: np.ndarray) -> np.ndarray:
    """灰度图 → 「黑底白线」二值图（用于竖线检测）。"""
    img = _to_gray(gray)
    if float(np.average(img)) > 128:
        img = cv2.adaptiveThreshold(
            img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 5, 7)
        img = 255 - img
    else:
        img = 255 - img
        img = cv2.adaptiveThreshold(
            img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 5, 7)
        img = 255 - img
    return img


def _detect_bar_lines(img: np.ndarray, top_line_y: int, bottom_line_y: int,
                      edge_top: int, edge_bottom: int,
                      coefficient: float) -> list[np.ndarray]:
    """img 为「黑底白线」二值图，返回每条小节线对应的连续列索引组。"""
    sum_columns = np.sum(img[top_line_y:bottom_line_y], axis=0).astype(np.float64)
    sum_columns_ex = np.sum(img[edge_top:edge_bottom], axis=0).astype(np.float64)

    columns_midpoint = (np.max(sum_columns) + np.min(sum_columns)) // 2
    sum_columns[np.where(sum_columns < columns_midpoint)[0]] = 0
    columns_ex_midpoint = (np.max(sum_columns_ex) + np.min(sum_columns_ex)) // 2
    sum_columns_ex[np.where(sum_columns_ex < columns_ex_midpoint)[0]] = 0

    if sum_columns.shape[0] == 0 or sum_columns_ex.shape[0] == 0:
        return []
    bar_lines = np.where(
        (sum_columns / sum_columns.shape[0]
         - sum_columns_ex / sum_columns_ex.shape[0] * coefficient) > 0)[0]
    if bar_lines.size == 0:
        return []

    # 去掉上下不对称（方差过大）的列 → 过滤音符符干
    std_y = np.std(img[top_line_y:bottom_line_y, bar_lines], axis=0)
    bar_lines = np.delete(bar_lines, np.where(std_y > 100)[0])
    if bar_lines.size == 0:
        return []

    # 去掉前景占比过少的列
    white_ratio_y = (np.sum(img[top_line_y:bottom_line_y, bar_lines], axis=0)
                     / 255 / (bottom_line_y - top_line_y))
    bar_lines = np.delete(bar_lines, np.where(white_ratio_y < 0.93)[0])
    if bar_lines.size == 0:
        return []

    split_index = np.where((bar_lines[1:] - bar_lines[:-1]) != 1)[0] + 1
    split_index = np.sort(np.append(split_index, [0, len(bar_lines)]))[1:-1]
    return list(np.split(bar_lines, split_index))


def detect_vertical_lines(gray: np.ndarray,
                          horizontal_lines: list[_StaffLine] | None = None,
                          coefficient: float = 0.8) -> list[_StaffLine]:
    """识别谱表区域内的竖直线（小节线），返回竖线段列表。"""
    img = _preprocess_vertical(gray)
    if horizontal_lines is None:
        horizontal_lines = detect_horizontal_lines(img)
    if not horizontal_lines:
        return []
    horizontal_lines = get_score_lines(horizontal_lines)
    if not horizontal_lines:
        return []

    top_line_y = horizontal_lines[0].start
    bottom_line_y = horizontal_lines[-1].end_index
    h = img.shape[0]
    expand = int((bottom_line_y - top_line_y) / 5)
    edge_top = max(0, top_line_y - expand)
    edge_bottom = min(h - 1, bottom_line_y + expand)

    kernel_h = max(1, int((bottom_line_y - top_line_y) / 15))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, kernel_h))
    img = cv2.morphologyEx(img, cv2.MORPH_CLOSE, vertical_kernel)

    groups = _detect_bar_lines(img, top_line_y, bottom_line_y,
                               edge_top, edge_bottom, coefficient)
    result: list[_StaffLine] = []
    for group in groups:
        if group.size == 0:
            continue
        result.append(_StaffLine(start=int(group[0]),
                                 thickness=int(group.size), direction="V"))
    return result


def detect_barlines_robust(image, coefficient_horizontal: float = 0.7,
                           coefficient_vertical: float = 0.8,
                           min_margin: int = 3) -> list[int]:
    """鲁棒小节线检测，返回升序 x 像素坐标。"""
    gray = _to_gray(image)
    horizontal_lines = detect_horizontal_lines(gray, coefficient_horizontal)
    vertical_lines = detect_vertical_lines(gray, horizontal_lines, coefficient_vertical)
    if not vertical_lines:
        return []

    centers = np.asarray([line.start + (line.thickness - 1) / 2.0
                          for line in vertical_lines])
    if centers.size > 1:
        distance = centers[1:] - centers[:-1]
        avg = float(np.average(distance))
        if avg > 0:
            merged: list[float] = []
            i = 0
            while i < centers.size:
                j = i
                while j + 1 < centers.size and centers[j + 1] - centers[j] < avg / 5.0:
                    j += 1
                merged.append(float(np.mean(centers[i:j + 1])))
                i = j + 1
            centers = np.asarray(merged)

    w = _to_gray(image).shape[1]
    return sorted(int(round(c)) for c in centers
                  if min_margin <= int(round(c)) <= w - min_margin)


def _heuristic_barlines(image, ink_threshold: int = 150,
                        staff_row_ratio: float = 0.30,
                        span_ratio: float = 0.50,
                        merge_gap: int = 4, min_margin: int = 3) -> list[int]:
    """回退：逐列墨迹占比启发式。"""
    gray = _to_gray(image)
    if float(gray.mean()) < 128:
        gray = 255 - gray
    h, w = gray.shape
    ink = gray < ink_threshold

    row_ratio = ink.sum(axis=1).astype(np.float64) / max(1, w)
    staff_rows = np.where(row_ratio >= staff_row_ratio)[0]
    if staff_rows.size < 6:
        top, bottom = 0, h - 1
    else:
        top, bottom = int(staff_rows.min()), int(staff_rows.max())

    band_h = bottom - top + 1
    if band_h < 6:
        return []

    col_ink = ink[top:bottom + 1, :].sum(axis=0).astype(np.float64)
    col_ratio = col_ink / band_h
    candidates = np.where(col_ratio >= span_ratio)[0]
    if candidates.size == 0:
        return []

    groups: list[list[int]] = []
    cur = [int(candidates[0])]
    for x in candidates[1:]:
        if int(x) - cur[-1] <= merge_gap:
            cur.append(int(x))
        else:
            groups.append(cur)
            cur = [int(x)]
    groups.append(cur)
    centers = [int(round(sum(g) / len(g))) for g in groups]
    return [x for x in centers if min_margin <= x <= w - min_margin]


def detect_barlines(image) -> list[int]:
    """检测谱面小节线（竖线），返回升序 x 像素坐标。

    优先鲁棒检测；无结果时回退到逐列墨迹启发式。
    """
    bars = detect_barlines_robust(image)
    if bars:
        return bars
    return _heuristic_barlines(image)


# ---------------- 播放光标（高亮竖条）检测 ----------------

# B 站/常见谱面播放器的光标颜色（浅蓝 #ccd8f0 / 蓝绿）
PLAYHEAD_TARGET_RGB = (204, 216, 240)


def _color_mask(image) -> np.ndarray:
    """蓝/青/绿高亮像素掩码（用于播放光标、当前小节高亮）。"""
    if hasattr(image, "convert"):
        rgb = np.array(image.convert("RGB"), dtype=np.uint8)
    else:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    rgb_i32 = rgb.astype(np.int32)
    target = np.array(PLAYHEAD_TARGET_RGB, dtype=np.int32)
    diff = rgb_i32 - target
    dist_sq = np.sum(diff * diff, axis=2)
    mask = (dist_sq <= 48 * 48).astype(np.uint8) * 255

    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    blue = cv2.inRange(hsv, np.array([80, 20, 50]), np.array([145, 255, 255]))
    green = cv2.inRange(hsv, np.array([35, 20, 40]), np.array([90, 255, 255]))
    mask = cv2.bitwise_or(mask, blue)
    mask = cv2.bitwise_or(mask, green)
    return mask


def detect_playhead(image, min_band_pixels: int = 20,
                    smooth_width: int = 31) -> tuple[int | None, float]:
    """检测播放光标竖条的 x 中心（无则 (None, 0)）。"""
    mask = _color_mask(image)
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
    if mask.ndim != 2:
        return None, 0.0
    h, w = mask.shape
    col_scores = np.sum(mask > 0, axis=0).astype(np.float32)
    sw = min(max(3, smooth_width), max(3, w // 2))
    if sw % 2 == 0:
        sw += 1
    kernel = np.ones(sw, dtype=np.float32) / sw
    smoothed = np.convolve(col_scores, kernel, mode="same")
    center = int(np.argmax(smoothed))
    peak = float(smoothed[center])
    if peak < min_band_pixels:
        return None, 0.0
    return center, peak


def mask_playhead(image: np.ndarray, centers: list[int | None],
                  band_half_width: int = 30,
                  fill: tuple[int, int, int] | None = None) -> np.ndarray:
    """把光标竖条区域涂成背景色（用于去重比较，避免光标位置导致误判不同）。

    fill=None 时自动采样图像背景色（亮像素中位数），避免纯白补丁与米色/灰色背景不协调。
    """
    out = image.copy()
    h, w = out.shape[:2]
    if fill is None:
        try:
            gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
            bg_mask = gray > 200
            if int(bg_mask.sum()) > 100:
                fill = tuple(int(v) for v in np.median(out[bg_mask], axis=0))
            else:
                fill = (255, 255, 255)
        except Exception:
            fill = (255, 255, 255)
    for c in centers:
        if c is None:
            continue
        x1 = max(0, c - band_half_width)
        x2 = min(w, c + band_half_width)
        out[:, x1:x2] = fill
    return out


def split_into_measures(image: np.ndarray, bars: list[int]) -> list[np.ndarray]:
    """按小节线（含图片左右边界）把图切成若干竖条。"""
    h, w = image.shape[:2]
    cuts = [0] + sorted({int(x) for x in bars if 0 <= x <= w}) + [w]
    pieces = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        if b - a >= 4:   # 太窄的条忽略（避免切到线本身）
            pieces.append(image[:, a:b])
    return pieces


def count_measures(image) -> int:
    """大概的小节数（小节线条数 - 1，至少 0）。"""
    bars = detect_barlines(image)
    return max(0, len(bars) - 1)
