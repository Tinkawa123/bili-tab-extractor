# -*- coding: utf-8 -*-
"""谱面区域自动检测模块（纯 CV，无需 LLM API）。

B 站吉他教学视频的谱面形态多变（底部横条 / 角落小窗 / 深色 UI 播放器），
因此采用三级策略：

1. 白纸区域检测 —— 参考 marcelpanse 的 refineBox 思想：乐谱是"浅色低饱和
   背景 + 内部密集暗色内容（线条/数字）"，与彩色演奏画面区分明显。
   用 行/列投影 找出候选白纸矩形，再按"暗内容密度 + 水平线密度 + 位于画面
   下方"评分，取最优。
2. 平行线簇检测 —— 深色 UI 谱面播放器（白纸掩码失效）时，TAB 谱的 6 条
   弦线 / 五线谱的 5 条线是极强的"紧密平行长水平线"特征，用 Hough 直线
   检测 + 聚类定位。
3. 手动框选 fallback —— 前两者失败时用 tkinter 鼠标拖拽（参考 rohin 的
   region_selector），也支持 --box 直接指定。

输出为归一化坐标 Box（0~1000），与 marcelpanse 的 Box 约定一致。
"""

from __future__ import annotations

import cv2
import numpy as np

from util import imread, imwrite, log

# ---------- 阈值（参照 marcelpanse detect.ts） ----------
WHITE_MIN_BRIGHTNESS = 170   # 像素 max(r,g,b) 至少达到此值才可能是纸面
WHITE_MAX_CHROMA = 45        # 且 (max-min) 通道差小于此值（低饱和）
ROW_COL_WHITE_FRAC = 0.45    # 一行/一列被视为"纸"所需的白像素占比
MIN_W_FRAC = 0.25            # 候选矩形最小宽度 = 0.25 * 图宽
MIN_H_FRAC = 0.03            # 候选矩形最小高度 = 0.03 * 图高
BRIDGE_GAP = 5               # 投影桥接：把长度 <= 该值的暗行/暗列缺口视为内容
DARK_CONTENT_MIN = 0.015     # 矩形内非白像素占比下限（排除纯白画面）
DARK_CONTENT_MAX = 0.92      # 上限（排除纯黑画面）
BOTTOM_BIAS = 0.5            # 画面下方候选的加分权重
SCAN_WIDTH = 640             # 检测时缩小到的宽度（加速）
TOP_PAD = 40                 # 检测框顶部向上扩展量（归一化 0~1000）

# 平行线检测参数（深色 UI 场景）
HOUGH_MIN_LEN_FRAC = 0.35    # 直线最小长度 = 0.35 * 图宽
HOUGH_THRESHOLD = 80
LINE_GAP_MAX = 14            # 同一簇内相邻线最大间距（px，按扫描宽度归一化前）
CLUSTER_MIN_LINES = 4        # 一簇最少平行线数


class Box:
    """归一化包围盒，坐标 0~1000（原点左上），与 marcelpanse 约定一致。"""

    __slots__ = ("x0", "y0", "x1", "y1")

    def __init__(self, x0: float, y0: float, x1: float, y1: float):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1

    def __repr__(self) -> str:
        return f"Box(x {self.x0:.0f}–{self.x1:.0f}, y {self.y0:.0f}–{self.y1:.0f} of 1000)"

    def to_pixels(self, w: int, h: int) -> tuple[int, int, int, int]:
        left = int(round(self.x0 / 1000 * w))
        top = int(round(self.y0 / 1000 * h))
        right = int(round(self.x1 / 1000 * w))
        bottom = int(round(self.y1 / 1000 * h))
        return left, top, right, bottom


# ---------- 工具函数 ----------

def _contiguous_segments(ok: np.ndarray, min_len: int) -> list[tuple[int, int]]:
    """把布尔数组为 True 的连续段找出来，返回 [(start, end), ...]。"""
    segs: list[tuple[int, int]] = []
    start = None
    for i, v in enumerate(ok):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start >= min_len:
                segs.append((start, i - 1))
            start = None
    if start is not None and len(ok) - start >= min_len:
        segs.append((start, len(ok) - 1))
    return segs


def _bridge_gaps(ok: np.ndarray, max_gap: int) -> np.ndarray:
    """1D 闭运算：把长度 <= max_gap 的 False 缺口桥接为 True。

    谱面内部的暗色弦线/小节线会让投影出现短缺口，若不桥接，
    白色行段会被切成许多小段而无法形成候选矩形。
    """
    result = ok.copy()
    n = len(ok)
    i = 0
    while i < n:
        if ok[i]:
            i += 1
            continue
        j = i
        while j < n and not ok[j]:
            j += 1
        if (j - i <= max_gap and i > 0 and j < n
                and ok[i - 1] and ok[j]):
            result[i:j] = True
        i = j
    return result


def _paper_mask(bgr: np.ndarray) -> np.ndarray:
    """白纸掩码：高亮度 + 低饱和。"""
    mx = bgr.max(axis=2).astype(np.int16)
    mn = bgr.min(axis=2).astype(np.int16)
    return (mx > WHITE_MIN_BRIGHTNESS) & ((mx - mn) < WHITE_MAX_CHROMA)


def _horizontal_edge_density(gray: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> float:
    """矩形区域内"水平边缘"的密度：对每行统计水平差分超阈值的像素占比。"""
    sub = gray[y0:y1, x0:x1].astype(np.int16)
    if sub.size == 0:
        return 0.0
    diff = np.abs(sub[:, 1:] - sub[:, :-1]) > 24
    return float(diff.mean())


def _find_paper_rects(mask: np.ndarray, min_w: int, min_h: int) -> list[tuple[int, int, int, int]]:
    """在掩码上用行/列投影找候选纸面矩形 [(x0,y0,x1,y1)]。"""
    h, w = mask.shape
    row_white = mask.sum(axis=1)
    row_ok = _bridge_gaps(row_white > w * ROW_COL_WHITE_FRAC, BRIDGE_GAP)
    rects: list[tuple[int, int, int, int]] = []
    for y0, y1 in _contiguous_segments(row_ok, min_h):
        sub = mask[y0:y1 + 1]
        col_white = sub.sum(axis=0)
        col_ok = _bridge_gaps(col_white > (y1 - y0 + 1) * ROW_COL_WHITE_FRAC, BRIDGE_GAP)
        for x0, x1 in _contiguous_segments(col_ok, min_w):
            rects.append((x0, y0, x1, y1))
    return rects


def _score_rect(rect, w: int, h: int, gray: np.ndarray, mask: np.ndarray) -> float:
    """候选矩形评分：暗内容密度、水平线密度、位置（下方加分）、宽扁程度。"""
    x0, y0, x1, y1 = rect
    rw, rh = x1 - x0 + 1, y1 - y0 + 1
    if rw <= 0 or rh <= 0:
        return -1.0

    region = mask[y0:y1 + 1, x0:x1 + 1]
    white_frac = float(region.mean())
    dark_frac = 1.0 - white_frac
    # 排除纯白/纯黑画面
    if not (DARK_CONTENT_MIN < dark_frac < DARK_CONTENT_MAX):
        return -1.0

    # 水平边缘密度（谱面 = 大量长水平线）
    edge_density = _horizontal_edge_density(gray, x0, y0, x1, y1)
    if edge_density < 0.004:
        return -1.0

    # 位置：越靠下越好（B 站教学视频谱面通常在下方）
    center_y = (y0 + y1) / 2 / h
    pos_bonus = BOTTOM_BIAS * center_y

    # 宽扁程度：宽度占比高、高度适中更可能是谱面条带
    width_frac = rw / w
    aspect_bonus = min(width_frac / 0.7, 1.0) * 0.15

    # 暗内容太少（如只有少量数字）或太多都减分
    content_score = min(dark_frac / 0.25, 1.0)

    return edge_density * 8.0 + content_score * 0.6 + pos_bonus + aspect_bonus


def _dedup_overlap(rects, overlap_frac: float = 0.5) -> list:
    """合并高度重叠的矩形（保留面积大的）。"""
    rects = sorted(rects, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]), reverse=True)
    kept = []
    for r in rects:
        x0, y0, x1, y1 = r
        inter = False
        for k in kept:
            ix0, iy0, ix1, iy1 = k
            ow = max(0, min(x1, ix1) - max(x0, ix0))
            oh = max(0, min(y1, iy1) - max(y0, iy0))
            if ow * oh > overlap_frac * min((x1 - x0) * (y1 - y0), (ix1 - ix0) * (iy1 - iy0)):
                inter = True
                break
        if not inter:
            kept.append(r)
    return kept


# ---------- 策略 1：白纸区域 ----------

def _detect_by_paper(path: str) -> Box | None:
    img = imread(path)
    if img is None:
        return None
    h0, w0 = img.shape[:2]
    scale = SCAN_WIDTH / w0
    small = cv2.resize(img, (SCAN_WIDTH, max(1, int(h0 * scale))),
                       interpolation=cv2.INTER_AREA)
    h, w = small.shape[:2]

    mask = _paper_mask(small)
    if mask.sum() < w * h * 0.01:
        return None

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    min_w = int(w * MIN_W_FRAC)
    min_h = int(h * MIN_H_FRAC)
    rects = _find_paper_rects(mask, min_w, min_h)
    if not rects:
        return None

    scored = [(r, _score_rect(r, w, h, gray, mask)) for r in rects]
    scored = [(r, s) for r, s in scored if s > 0]
    if not scored:
        return None
    scored.sort(key=lambda t: t[1], reverse=True)

    # 取前 5 个高分候选去重，保留最佳
    top = [r for r, _ in scored[:5]]
    top = _dedup_overlap(top)
    if not top:
        return None
    x0, y0, x1, y1 = top[0]
    # 转归一化坐标
    box = Box(x0 / w * 1000, y0 / h * 1000, x1 / w * 1000, y1 / h * 1000)
    if (box.x1 - box.x0) < 50 or (box.y1 - box.y0) < 20:
        return None
    return box


# ---------- 策略 2：平行线簇（深色 UI） ----------

def _detect_by_lines(path: str) -> Box | None:
    img = imread(path)
    if img is None:
        return None
    h0, w0 = img.shape[:2]
    scale = SCAN_WIDTH / w0
    small = cv2.resize(img, (SCAN_WIDTH, max(1, int(h0 * scale))),
                       interpolation=cv2.INTER_AREA)
    h, w = small.shape[:2]
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

    edges = cv2.Canny(gray, 50, 150)
    min_len = int(w * HOUGH_MIN_LEN_FRAC)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, HOUGH_THRESHOLD,
                            minLineLength=min_len, maxLineGap=6)
    if lines is None:
        return None

    ys: list[float] = []
    for line in lines:
        # OpenCV 4.x 返回 (N,1,4)，OpenCV 5.x 返回 (N,4)
        if line.ndim == 2 and line.shape[0] == 1:
            x1_, y1_, x2_, y2_ = line[0]
        else:
            x1_, y1_, x2_, y2_ = line
        dx, dy = x2_ - x1_, y2_ - y1_
        length = np.hypot(dx, dy)
        if length == 0:
            continue
        # 近似水平：角度 < 6°
        if abs(dy) / length > 0.105:
            continue
        ys.append((y1_ + y2_) / 2)

    if len(ys) < CLUSTER_MIN_LINES:
        return None

    # 按 y 聚类（贪心：排序后相邻间距 < LINE_GAP 归为一簇）
    ys.sort()
    clusters: list[list[float]] = []
    for y in ys:
        if clusters and y - clusters[-1][-1] <= LINE_GAP_MAX:
            clusters[-1].append(y)
        else:
            clusters.append([y])

    best = max(clusters, key=len, default=[])
    if len(best) < CLUSTER_MIN_LINES:
        return None

    y_top, y_bot = best[0], best[-1]
    # 谱面区域 = 线簇上下各扩展 1.6 倍簇高（容纳五线谱/数字），x 取全宽
    cluster_h = max(y_bot - y_top, 1)
    y0 = max(0, y_top - cluster_h * 0.8)
    y1 = min(h - 1, y_bot + cluster_h * 0.8)
    return Box(0, y0 / h * 1000, 1000, y1 / h * 1000)


# ---------- 策略 3：手动框选 ----------

def _manual_select(path: str) -> Box | None:
    """tkinter 鼠标拖拽框选。返回归一化 Box。"""
    try:
        import tkinter as tk
        from PIL import Image, ImageTk
    except Exception as e:  # pragma: no cover
        log.error(f"无法打开图形窗口（{e}），请用 --box 手动指定区域")
        return None

    img = imread(path)
    if img is None:
        return None
    h0, w0 = img.shape[:2]
    # 缩到屏幕可显示
    max_w = 1100
    scale = min(1.0, max_w / w0)
    disp = cv2.resize(img, (int(w0 * scale), int(h0 * scale)))
    dh, dw = disp.shape[:2]

    root = tk.Tk()
    root.title("拖拽框选谱面区域（左上→右下），按 Enter 确认 / Esc 取消")
    canvas = tk.Canvas(root, width=dw, height=dh, cursor="crosshair")
    canvas.pack()

    rgb = cv2.cvtColor(disp, cv2.COLOR_BGR2RGB)
    photo = ImageTk.PhotoImage(Image.fromarray(rgb))
    canvas.create_image(0, 0, image=photo, anchor="nw")

    state = {"x0": 0, "y0": 0, "x1": 0, "y1": 0, "rect": None, "done": False, "ok": False}

    def on_press(e):
        state["x0"], state["y0"] = e.x, e.y

    def on_drag(e):
        if state["rect"]:
            canvas.delete(state["rect"])
        state["x1"], state["y1"] = e.x, e.y
        state["rect"] = canvas.create_rectangle(
            state["x0"], state["y0"], e.x, e.y, outline="red", width=2)

    def on_enter(_e=None):
        state["done"], state["ok"] = True, True
        root.quit()

    def on_esc(_e=None):
        state["done"], state["ok"] = True, False
        root.quit()

    # 无 GUI/无人值守环境防卡死：90 秒未操作自动放弃
    root.after(90_000, on_esc)

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_drag)
    root.bind("<Return>", on_enter)
    root.bind("<Escape>", on_esc)
    root.protocol("WM_DELETE_WINDOW", on_esc)

    root.mainloop()
    root.destroy()

    if not state["ok"]:
        return None
    x0, y0 = min(state["x0"], state["x1"]), min(state["y0"], state["y1"])
    x1, y1 = max(state["x0"], state["x1"]), max(state["y0"], state["y1"])
    if x1 - x0 < 10 or y1 - y0 < 5:
        return None
    # 显示坐标 → 原图坐标 → 归一化
    return Box(x0 / dw * 1000, y0 / dh * 1000, x1 / dw * 1000, y1 / dh * 1000)


# ---------- 主入口 ----------

def _median(nums: list[float]) -> float:
    s = sorted(nums)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def _pick_sample(frames: list[str], n: int) -> list[str]:
    if len(frames) <= n:
        return frames
    step = len(frames) / n
    return [frames[int(i * step + step / 2)] for i in range(n)]


def detect_tab_box(frames: list[str], sample: int = 6,
                   box_arg: str | None = None,
                   allow_manual: bool = True) -> Box:
    """在采样帧上检测谱面区域，多帧结果取中位数。

    - box_arg: 形如 "100,200,900,800"（归一化 0~1000），直接指定跳过检测
    - allow_manual: 自动检测失败时是否弹出手动框选窗口；
       GUI 后台线程中必须为 False（线程内不能建 tk.Tk()）
    """
    if box_arg:
        try:
            parts = [float(v) for v in box_arg.replace(" ", "").split(",")]
            if len(parts) != 4:
                raise ValueError
            x0, y0, x1, y1 = parts
            # 范围校验：坐标在 0~1000 且 x0<x1, y0<y1
            if not (0 <= x0 < x1 <= 1000 and 0 <= y0 < y1 <= 1000):
                raise ValueError
            box = Box(x0, y0, x1, y1)
            log.success(f"使用手动指定的区域: {box}")
            return box
        except ValueError:
            raise SystemExit(
                "--box 格式应为 x0,y0,x1,y1（0~1000 归一化坐标，且 x0<x1, y0<y1）")

    picks = _pick_sample(frames, sample)
    log.step(f"检测谱面区域（采样 {len(picks)} 帧，策略：白纸→平行线→手动）…")

    paper_boxes: list[Box] = []
    line_boxes: list[Box] = []
    for i, p in enumerate(picks):
        box = _detect_by_paper(p)
        if box:
            paper_boxes.append(box)
            log.info(f"  帧 {i + 1}/{len(picks)}: 白纸策略 -> {box}")
            continue
        box = _detect_by_lines(p)
        if box:
            line_boxes.append(box)
            log.info(f"  帧 {i + 1}/{len(picks)}: 平行线策略 -> {box}")

    # 白纸策略结果优先；只有全部失败才退到平行线结果
    chosen = paper_boxes or line_boxes
    if not chosen:
        if not allow_manual:
            raise RuntimeError(
                "未自动检测到谱面区域。该视频可能需要 --box 手动指定区域，"
                "或调整抽帧间隔后重试")
        log.warn("自动检测失败，请在弹出的窗口手动框选谱面区域…")
        med_path = picks[len(picks) // 2]
        box = _manual_select(med_path)
        if box is None:
            raise SystemExit("未获得谱面区域。可尝试: 1) 重新运行并用 --box 指定 2) 调整抽帧间隔")
        log.success(f"手动框选区域: {box}")
        return box

    # 每边取中位数（marcelpanse 的鲁棒做法）
    box = Box(
        _median([b.x0 for b in chosen]),
        _median([b.y0 for b in chosen]),
        _median([b.x1 for b in chosen]),
        _median([b.y1 for b in chosen]),
    )
    # 顶部向上扩展：谱面主体上方常印有和弦名/标题等附属内容，
    # 白纸掩码检测到的是纸面主体，会把这些截掉（实测首行内容被拦腰切断）。
    # 扩展 40/1000（约 4% 画面高），行级过滤会剔除混入的非谱面片段。
    box.y0 = max(0.0, box.y0 - TOP_PAD)
    strategy = "白纸掩码" if paper_boxes else "平行线簇"
    log.success(f"谱面区域（{strategy}策略，多帧中位数，顶部扩展）: {box}")
    return box
