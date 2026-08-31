# -*- coding: utf-8 -*-
"""行级处理模块：把裁剪图切成一行行谱，按行内容做全局去重。

针对"一屏显示多行谱 + 播放光标扫动"的真实 B 站教学视频：
整屏级去重无法区分"光标扫过同一行"（会重复保留）与"真正翻页"，
因此改为：
1. split_crop_rows: 按内容行密度聚类，把一屏切成一行行谱（行内
   五线谱/TAB 线距小且均匀，行间空白更大，可区分）；
2. row_fingerprint: 每行缩放为统一尺寸后分网格统计暗像素占比，
   得到 128 维内容指纹（比 9x8 dHash 能区分"同线不同数字"）；
3. dedup_rows: 全局去重——与所有已保留的行比较，指纹距离小于
   阈值视为同一行（光标扫过的重复帧），只保留第一次出现；
4. is_tab_row: 行片段谱面特征检查（水平线密度），过滤演奏画面等
   非谱面内容。
"""

from __future__ import annotations

import cv2
import numpy as np

from util import log

# 行切分参数
CONTENT_ROW_DARK = 8      # 内容行判定：暗像素数 > 该值（含歌词/和弦名等稀疏文字）
INNER_GAP = 8             # 行内聚类间隙（五线谱线距约 10-12px）
MIN_ROW_HEIGHT = 14       # 行片段最小高度
MAX_PARTIAL = 100         # 半行判定：段高低于此值视为不完整行
MERGE_GAP = 30            # 半行段与相邻段的最大合并空隙
ABSORB_MAX = 60           # 行顶部向上吸收的最大像素数
ABSORB_MIN_DARK = 4       # 吸收判定：行暗像素 >= 此值视为"稀疏内容"
ABSORB_MAX_DARK = 150     # 暗像素 > 此值视为密集内容（演奏画面），不吸收

# 指纹参数
FP_W, FP_H = 320, 56      # 行指纹归一化尺寸
FP_ROWS, FP_COLS = 8, 16  # 网格数
FP_DIST_THRESH = 6.0      # 指纹 L1 距离阈值（< 视为候选重复）
SAME_FRAC = 0.008         # 像素差异占比低于此值 => 几乎相同（重复）；
                          # "大致相同但不同"的行（前奏两段/相邻小节）
                          # 差异常为 1~3%，应保留（宁多勿缺）


def _dense_fraction(gray: np.ndarray, y0: int, y1: int) -> float:
    """段内暗像素（<100）占比：演奏画面等深色内容 > 0.5。"""
    seg = gray[y0:y1 + 1]
    return float((seg < 100).mean())


def _skin_fraction(bgr: np.ndarray, y0: int, y1: int) -> float:
    """段内肤色占比（HSV 肤色范围）。演奏画面（手/脸）肤色占比高，
    谱面墨迹/蓝色标记条不会被误判。"""
    seg = bgr[y0:y1 + 1]
    hsv = cv2.cvtColor(seg, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 30, 60), (25, 255, 255))
    mask |= cv2.inRange(hsv, (165, 30, 60), (180, 255, 255))
    return float(mask.mean())


SKIN_MERGE_FRAC = 0.15   # 段肤色占比高于此值视为演奏画面，不参与合并
SKIN_ROW_FRAC = 0.05     # 行片段肤色占比高于此值判为非谱面（演奏画面）


def _has_staff_lines(gray: np.ndarray, y0: int, y1: int,
                  min_lines: int = 3, span_frac: float = 0.5) -> bool:
    """段内是否含谱线（横向跨度大的暗行 >= min_lines）。

    用于合并判定：只有含谱线的段（五线谱/TAB 半行）才与相邻段合并，
    纯歌词段（无谱线）保持独立，避免"两行歌词+一行谱"被叠成一个大行。
    """
    seg = gray[y0:y1 + 1]
    dark = seg < 150
    w = gray.shape[1]
    n = 0
    for y in range(dark.shape[0]):
        cols = np.where(dark[y])[0]
        if len(cols) > 15:
            span = cols.max() - cols.min()
            if span > span_frac * w:
                n += 1
    return n >= min_lines


def _absorb_above(gray: np.ndarray, y0: int) -> int:
    """把行片段顶部向上扩展，吸收上方的"稀疏内容"（如和弦名/标记）。

    和弦名等短文字每行暗像素只有几个到几十个（稀疏），切行时因阈值/高度
    不足被丢弃；而演奏画面是密集内容（暗像素数百）。逐行向上扫描：
    - 稀疏内容行（ABSORB_MIN_DARK..ABSORB_MAX_DARK）：吸收
    - 空白行：短暂容忍（<=3 行）后停止
    - 密集内容行（> ABSORB_MAX_DARK）：立即停止（不吸收演奏画面）
    """
    dark = (gray < 150).sum(axis=1)
    ext = 0
    blank = 0
    while ext < ABSORB_MAX and y0 - ext - 1 >= 0:
        d = int(dark[y0 - ext - 1])
        if d > ABSORB_MAX_DARK:
            break  # 密集内容（演奏画面/谱面主体），不吸收
        if d >= ABSORB_MIN_DARK:
            ext += 1
            blank = 0
        else:
            blank += 1
            if blank > 3:
                break
            ext += 1
    return max(0, y0 - ext)


def _absorb_below(gray: np.ndarray, y1: int, h: int) -> int:
    """把行片段底部向下扩展，吸收下方的"稀疏内容"（歌词/标记行）。

    与 _absorb_above 对称：歌词等文字行常印在谱线下方，逐行向下扫描，
    稀疏内容行吸收，空白容忍 <=3 行，密集内容（下一行谱线）立即停止。
    """
    dark = (gray < 150).sum(axis=1)
    ext = 0
    blank = 0
    while ext < ABSORB_MAX and y1 + ext + 1 < h:
        d = int(dark[y1 + ext + 1])
        if d > ABSORB_MAX_DARK:
            break  # 密集内容（下一行谱面），不吸收
        if d >= ABSORB_MIN_DARK:
            ext += 1
            blank = 0
        else:
            blank += 1
            if blank > 3:
                break
            ext += 1
    return min(h - 1, y1 + ext)


def split_crop_rows(img: np.ndarray) -> list[np.ndarray]:
    """把裁剪图按"内容行密度聚类"切成一行行谱（BGR -> 列表）。

    内容行 = 暗像素数 > CONTENT_ROW_DARK 的行；对内容行做相邻间距
    聚类，间隙 <= INNER_GAP 的行合并（行内五线谱/TAB 密排），
    间隙更大处即行间分界。
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    dark = (gray < 150).sum(axis=1)

    # 每行肤色占比（演奏画面 = 肤色密集行，从内容行中排除）
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    skin_mask = cv2.inRange(hsv, (0, 30, 60), (25, 255, 255))
    skin_mask |= cv2.inRange(hsv, (165, 30, 60), (180, 255, 255))
    skin_row_frac = (skin_mask > 0).sum(axis=1) / w

    # 内容行段（允许 2px 内的小断裂）；肤色密集行视为演奏画面，不参与
    segs: list[tuple[int, int]] = []
    start = None
    for y in range(h):
        is_content = dark[y] > CONTENT_ROW_DARK and skin_row_frac[y] < 0.3
        if is_content and start is None:
            start = y
        elif not is_content and start is not None:
            if y - start >= 2:
                segs.append((start, y - 1))
            start = None
    if start is not None:
        segs.append((start, h - 1))

    # 聚类合并（间隙 <= INNER_GAP）
    rows: list[tuple[int, int]] = []
    for s0, s1 in segs:
        if rows and s0 - rows[-1][1] <= INNER_GAP:
            rows[-1] = (rows[-1][0], s1)
        else:
            rows.append((s0, s1))

    # 合并"半行"段：段高 < MAX_PARTIAL 且与相邻段空隙 <= MERGE_GAP 时
    # 合并（五线谱段 + TAB 段凑成完整一行；避免一行被切成两半）
    merged_rows: list[tuple[int, int]] = []
    i = 0
    while i < len(rows):
        y0, y1 = rows[i]
        while i + 1 < len(rows):
            ny0, ny1 = rows[i + 1]
            if (y1 - y0 + 1) < MAX_PARTIAL and (ny0 - y1) <= MERGE_GAP:
                # 演奏画面段（密集暗色 或 肤色密集）不参与合并，避免混入谱面行
                if _dense_fraction(gray, y0, y1) > 0.5:
                    break
                if _skin_fraction(img, y0, y1) > SKIN_MERGE_FRAC:
                    break
                # 纯歌词段（无谱线）不与相邻段合并，避免歌词/谱线叠加
                if not _has_staff_lines(gray, y0, y1):
                    break
                y1 = ny1
                i += 1
            else:
                break
        merged_rows.append((y0, y1))
        i += 1

    out = []
    for y0, y1 in merged_rows:
        if y1 - y0 + 1 >= MIN_ROW_HEIGHT:
            ny0 = _absorb_above(gray, y0)
            ny1 = _absorb_below(gray, y1, h)
            out.append(img[max(0, ny0 - 2):min(h, ny1 + 3)])
    return out


def row_fingerprint(row: np.ndarray) -> np.ndarray:
    """行内容指纹：缩放归一化后分网格统计暗像素占比（128 维）。"""
    gray = cv2.cvtColor(row, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (FP_W, FP_H), interpolation=cv2.INTER_AREA)
    dark = resized < 128
    fp = np.zeros(FP_ROWS * FP_COLS, dtype=np.float32)
    for r in range(FP_ROWS):
        y0, y1 = r * FP_H // FP_ROWS, (r + 1) * FP_H // FP_ROWS
        for c in range(FP_COLS):
            x0, x1 = c * FP_W // FP_COLS, (c + 1) * FP_W // FP_COLS
            fp[r * FP_COLS + c] = dark[y0:y1, x0:x1].mean()
    return fp


def _fp_dist(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.abs(a - b).sum())


def is_tab_row(row: np.ndarray, min_lines: int = 3,
               span_frac: float = 0.6) -> bool:
    """行片段是否像谱面（白底谱/歌词谱）。

    谱面行特征：浅色(白)背景 + 稀疏暗内容。
    两种形态都接受：
    - 谱线行：横贯弦线/五线谱线 >= min_lines
    - 歌词/和弦名行：文字特征（垂直笔画多，如"16-21 小节只有歌词"的段落）
    演奏画面（肤色/复杂纹理）先被剔除。
    判定：
    - 白底：亮像素占比 > 0.35
    - 内容稀疏：暗像素占比 < 0.35
    - 肤色占比 < SKIN_ROW_FRAC
    - 且（长线 >= min_lines 或 文本特征显著）
    """
    gray = cv2.cvtColor(row, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    white_frac = float((gray > 230).mean())
    dark_frac = float((gray < 100).mean())
    if white_frac < 0.35 or dark_frac > 0.35:
        return False
    # 肤色检查：演奏画面（手/脸）的强特征
    hsv = cv2.cvtColor(row, cv2.COLOR_BGR2HSV)
    skin = cv2.inRange(hsv, (0, 30, 60), (25, 255, 255))
    skin |= cv2.inRange(hsv, (165, 30, 60), (180, 255, 255))
    if float(skin.mean()) > SKIN_ROW_FRAC:
        return False
    dark = gray < 150
    n_long = 0
    for y in range(h):
        cols = np.where(dark[y])[0]
        if len(cols) > 15:
            span = cols.max() - cols.min()
            if span > span_frac * w:
                n_long += 1
    if n_long >= min_lines:
        return True
    # 文本行判定（歌词/和弦名）：垂直笔画显著，且非纯水平线
    # （演奏画面已被肤色检查拦截，此处阈值可放宽）
    gx = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3))
    gy = np.abs(cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3))
    ve = float((gx > 40).mean())
    he = float((gy > 40).mean())
    if ve > 0.02 and ve > he * 0.15:
        return True
    return False


def dedup_rows(rows: list[tuple[np.ndarray, str, int]]) -> list[tuple[np.ndarray, str, int]]:
    """行级全局去重。

    输入: [(行BGR图, 来源裁剪图路径, 行序号), ...]
    输出: 去重后的子集（同一行谱只保留第一次出现）。
    保留顺序 = 视频中第一次出现的顺序。

    判定：指纹距离 < FP_DIST_THRESH 时再做像素级确认
    （content_changed：仅光标移动 = 重复丢弃；内容确实变化 = 保留），
    兼顾"重复行去重"与"高度相似但不同的行保留"。
    """
    if not rows:
        return []
    log.step(f"行级去重 {len(rows)} 行片段（指纹阈值 {FP_DIST_THRESH}）…")

    kept_fps_mat: list[np.ndarray] = []   # 已保留行的指纹
    kept_rows_arr: list[np.ndarray] = []  # 已保留行的图像
    kept: list[tuple[np.ndarray, str, int]] = []
    dropped_dup = 0
    dropped_notab = 0

    for row, src, idx in rows:
        if not is_tab_row(row):
            dropped_notab += 1
            continue
        fp = row_fingerprint(row)
        dup = False
        if kept_fps_mat:
            # 批量距离计算：与所有已保留行比较（O(n) 向量化）
            mat = np.stack(kept_fps_mat)          # (K, D)
            dists = np.abs(mat - fp[None, :]).sum(axis=1)
            near = np.where(dists < FP_DIST_THRESH)[0]
            for ki in near:
                krow = kept_rows_arr[ki]
                # 像素级确认：只有"几乎完全相同"才判重复。
                # 注意：不使用 content_changed（光标免疫）——它对"相似但
                # 不同"的歌词/小节行不适用（前奏两段、不同小节的和弦变化
                # 差异集中但确属不同内容），宁多勿缺。
                h0, w0 = krow.shape[:2]
                h1, w1 = row.shape[:2]
                if h0 != h1:
                    a = cv2.resize(krow, (w0, h1), interpolation=cv2.INTER_AREA)
                    b = row
                else:
                    a, b = krow, row
                diff = np.abs(a.astype(np.int16) - b.astype(np.int16)) > 40
                diff_frac = float(diff.mean())
                if diff_frac < SAME_FRAC:
                    dup = True
                    break
        if dup:
            dropped_dup += 1
            continue
        kept_fps_mat.append(fp)
        kept_rows_arr.append(row)
        kept.append((row, src, idx))

    log.success(
        f"行级去重完成：保留 {len(kept)} 行 "
        f"（丢弃 {dropped_dup} 重复行, {dropped_notab} 非谱面片段）")
    return kept
