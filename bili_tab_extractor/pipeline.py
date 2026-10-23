# -*- coding: utf-8 -*-
"""可复用的处理流程：URL/视频 → 谱行数据（供 CLI 和 GUI 共用）。

把 main.py 的核心流程抽出来，返回结构化结果：
- all_rows: 所有截取的谱行（含被去重的，供人工核验"找回"）
- kept_rows: 自动排序 + 去重后的谱行（初始排序）
- title/box 等元信息

GUI 在此基础上做人工核验（拖动/增删），确认后调用
stitch.make_pdf_from_rows / 保存图片。
"""

from __future__ import annotations

import os
import shutil
import sys
import time

import numpy as np

# 沙箱/打包环境下 pylibs 注入（与 main.py 一致）
_PYLIBS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pylibs")
if os.path.isdir(_PYLIBS) and _PYLIBS not in sys.path:
    sys.path.insert(0, _PYLIBS)

import cv2

from detect import Box, detect_tab_box
from download import download_video
from frames import extract_frames
from util import imread, imwrite, log


class TabRow:
    """一行谱面。"""

    __slots__ = ("image", "time", "source", "index", "bars")

    def __init__(self, image: np.ndarray, time: float, source: str, index: int,
                 bars: list[int] | None = None):
        self.image = image      # BGR ndarray
        self.time = time        # 视频时间（秒）
        self.source = source    # 来源（crop 文件名 / 本地文件）
        self.index = index      # 行序号
        self.bars = bars        # VLM 读出的小节号（None=未识别）

    def __repr__(self) -> str:
        return f"TabRow(t={self.time:.0f}s, h={self.image.shape[0]})"


class PipelineResult:
    """处理结果。"""

    def __init__(self, title: str, box: Box,
                 all_rows: list[TabRow], kept_rows: list[TabRow]):
        self.title = title
        self.box = box
        self.all_rows = all_rows       # 全部原始行（按时间）
        self.kept_rows = kept_rows     # 自动去重排序后的行


ProgressCb = "callable[[str, float], None]"  # (阶段文本, 0~100)


def crop_frames(frames: list[str], box: Box, crops_dir: str) -> list[str]:
    """把每帧裁剪到谱面区域，返回裁剪图路径列表（与 main.py 一致）。"""
    os.makedirs(crops_dir, exist_ok=True)
    first = imread(frames[0])
    if first is None:
        raise RuntimeError(f"无法读取帧: {frames[0]}")
    h, w = first.shape[:2]
    left, top, right, bottom = box.to_pixels(w, h)
    if right - left < 10 or bottom - top < 5:
        raise RuntimeError(f"谱面区域过小: ({left},{top})-({right},{bottom})，请检查 --box")
    paths: list[str] = []
    for i, f in enumerate(frames):
        img = imread(f)
        if img is None:
            continue
        crop = img[top:bottom, left:right]
        out = os.path.join(crops_dir, f"crop-{i:05d}.png")
        imwrite(out, crop)
        paths.append(out)
    return paths


def _process_horizontal(crop_imgs, api_key, work_dir, p, use_vlm=True) -> list[TabRow]:
    """横向滚动谱带处理。

    优先：VLM 读每帧小节号 → 按小节号去重、按小节号排序（最可靠）。
    回退：像素位移分段拼接 → 切段。
    """
    from stitch import crop_screen_top, estimate_shift, split_wide_image, stitch_horizontal

    # 先裁掉每帧顶部的演奏画面
    cleaned = []
    for img in crop_imgs:
        try:
            cleaned.append(crop_screen_top(img))
        except Exception:
            cleaned.append(img)

    if use_vlm and api_key:
        try:
            from vlm_recognize import analyze_rows

            p("正在用 VLM 识别每帧小节号…", 50)
            tmp = [TabRow(img, 0, f"f-{i}", i) for i, img in enumerate(cleaned)]
            cache = os.path.join(work_dir or os.getcwd(), "vlm_horizontal_cache.json")
            analyses = analyze_rows(
                tmp, api_key=api_key, cache_path=cache,
                progress=lambda d, t: p(
                    f"VLM 识别小节号 {d}/{t}…", 50 + 30 * d / max(1, t)),
                max_workers=4)
            # 按小节号去重排序（相同小节范围只保留一帧）
            seen = set()
            rows: list[TabRow] = []
            for i in sorted(analyses):
                bars = analyses[i].get("bar_numbers") or []
                if not bars:
                    continue
                key = tuple(bars)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(TabRow(cleaned[i], 0, f"frame-{i}", min(bars)))
            if rows:
                rows.sort(key=lambda r: r.index)  # 按起始小节号排序
                log.success(f"VLM 小节号去重：{len(cleaned)} 帧 → {len(rows)} 段")
                return rows
            log.warn("VLM 未识别到小节号，回退像素拼接")
        except Exception as e:
            log.warn(f"VLM 小节号识别失败，回退像素拼接: {e}")

    # 回退：像素位移分段拼接
    p("正在横向拼接谱带…", 50)
    shifts = [0.0]
    for i in range(1, len(cleaned)):
        try:
            dx, _dy, _resp = estimate_shift(cleaned[i - 1], cleaned[i])
        except Exception:
            dx = 0.0
        shifts.append(dx)
    segs = stitch_horizontal(cleaned, shifts)
    rows: list[TabRow] = []
    if segs:
        idx = 0
        for seg in segs:
            for sec in split_wide_image(seg):
                rows.append(TabRow(sec, 0, f"section-{idx}", idx))
                idx += 1
    return rows


def process(url: str = None, video: str = None, title: str = None,
            interval: float = 2.0, sample: int = 6, max_height: int = 720,
            cookies: str = None, box_arg: str = None,
            work_dir: str = None,
            progress: ProgressCb = None, keep_temp: bool = False,
            cleanup: bool = True,
            allow_manual: bool = True,
            api_key: str = None,
            vlm_on_horizontal: bool = True) -> PipelineResult:
    """完整处理流程。

    返回 PipelineResult（all_rows/kept_rows/box/title）。
    使用 work_dir 作为工作目录（GUI 传入持久目录以便"找回"行）。
    allow_manual: 自动检测失败时是否允许弹出手动框选窗口
                  （GUI 后台线程必须为 False）。
    api_key: VLM API Key（横向滚动谱面用 VLM 读小节号去重；为空则用像素拼接）。
    """
    def p(text: str, frac: float = 0.0):
        if progress:
            progress(text, frac)

    if not work_dir:
        work_dir = os.path.join(os.getcwd(),
                                f"_bili_tab_work_{int(time.time())}_{os.getpid()}")
    os.makedirs(work_dir, exist_ok=True)

    try:
        video_path = os.path.join(work_dir, "video.mp4")
        if video:
            if not os.path.isfile(video):
                raise RuntimeError(f"本地视频不存在: {video}")
            title = title or os.path.splitext(os.path.basename(video))[0]
            shutil.copy2(video, video_path)
            p(f"使用本地视频: {video}")
        else:
            if not url:
                raise RuntimeError("请提供 B 站 URL 或本地视频路径")
            p("正在下载视频…", 5)
            title = download_video(url, video_path, max_height, cookies)

        frames_dir = os.path.join(work_dir, "frames")
        p("正在抽帧…", 15)
        frames = extract_frames(video_path, frames_dir, interval)
        if len(frames) < 3:
            log.warn("帧数很少，请确认视频包含谱面画面")

        p("正在检测谱面区域…", 25)
        box = detect_tab_box(frames, sample, box_arg, allow_manual=allow_manual)

        crops_dir = os.path.join(work_dir, "crops")
        p("正在裁剪谱面区域…", 35)
        crops = crop_frames(frames, box, crops_dir)

        # 读裁剪图（供类型检测与后续处理）
        crop_imgs = [imread(c) for c in crops]
        crop_imgs = [i for i in crop_imgs if i is not None]

        # 检测谱面滚动类型：横向滚动 / 上滚 / 逐行（翻页）
        from stitch import (crop_screen_top, detect_scroll_direction,
                            estimate_shift, split_wide_image, stitch_horizontal)
        scroll_type = detect_scroll_direction(crop_imgs)
        log.info(f"谱面类型检测: {scroll_type}")

        all_rows: list[TabRow] = []
        if scroll_type == "horizontal":
            # 横向滚动谱带：优先用 VLM 读小节号去重（可靠）；
            # 无 API Key 时回退到像素分段拼接。
            all_rows = _process_horizontal(
                crop_imgs, api_key, work_dir, p, vlm_on_horizontal)

        if not all_rows:
            # 行级切分：收集所有行（含被去重的，供人工核验找回）
            from rows import split_crop_rows, dedup_rows

            n_crops = len(crops)
            for ci, c in enumerate(crops):
                img = imread(c)
                if img is None:
                    continue
                t = ci * interval
                for ri, row in enumerate(split_crop_rows(img)):
                    all_rows.append(TabRow(row, t, c, ri))
                if ci % 20 == 0:
                    p(f"切分行片段 {ci}/{n_crops}…", 40 + 30 * ci / n_crops)

        if len(all_rows) < 3:
            # 行级切分失败（滚动型/无行结构），用整屏裁剪作为"行"
            log.warn("行片段较少，回退到整屏模式")
            all_rows = []
            for ci, c in enumerate(crops):
                img = imread(c)
                if img is None:
                    continue
                all_rows.append(TabRow(img, ci * interval, c, 0))

        p("正在自动排序去重…", 75)
        if scroll_type == "horizontal":
            # 横向拼接后的段已经是不重叠内容，无需行级去重
            kept_rows = list(all_rows)
        else:
            from rows import dedup_rows

            # dedup_rows 输入是 (image, source, index)，输出 (image, source, index)
            kept = dedup_rows([(r.image, r.source, r.index) for r in all_rows])
            kept_keys = {(k[1], k[2]) for k in kept}
            kept_rows = [r for r in all_rows if (r.source, r.index) in kept_keys]
            # 按时间排序（自动排序 = 按视频出现顺序）
            kept_rows.sort(key=lambda r: (r.time, r.index))

        p("处理完成", 100)
        return PipelineResult(title, box, all_rows, kept_rows)
    finally:
        if cleanup and not keep_temp:
            # 默认保留 work_dir（GUI 需要它来找回行）；CLI 场景由调用方清理
            pass
