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


class ProcessCancelled(Exception):
    """用户请求取消处理（GUI 据此丢弃结果、不弹核验窗口）。"""


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


def _process_horizontal(crop_imgs, api_key, work_dir, p, use_vlm=True,
                        thresholds: dict | None = None,
                        state: dict | None = None) -> list[TabRow]:
    """横向滚动谱带处理。

    优先：VLM 读每帧小节号 → 按小节号去重、按小节号排序（最可靠）。
    回退：像素位移分段拼接 → 切段。
    state: 可选 dict，用于向调用方回传处理方式（state["vlm_ok"] = True/False）。
    """
    from stitch import (crop_screen_top, estimate_shift, is_transition_frame,
                        normalize_heights, split_wide_image, stitch_horizontal)

    # 先裁掉每帧顶部的演奏画面
    cleaned = []
    for img in crop_imgs:
        try:
            cleaned.append(crop_screen_top(img, thresholds=thresholds))
        except Exception:
            cleaned.append(img)

    # 跳过片头淡入/片尾淡出/黑屏等过场帧：它们不含谱面，参与横向拼接会在
    # 长图里留下整块黑色（本视频 frame0、frame89-94 就是纯黑/近黑）。
    filtered = [c for c in cleaned if not is_transition_frame(c)]
    if filtered and len(filtered) < len(cleaned):
        log.info(f"跳过 {len(cleaned) - len(filtered)} 张过场帧（淡入/淡出/黑屏）")
        cleaned = filtered

    # 统一高度：crop_screen_top() 按每帧演奏画面的实际高度裁剪（有的裁 28px、
    # 有的裁 90px），同一视频的帧高会从 137px 到 199px 不等。VLM 读小节号、
    # 相位相关估位移、横向拼接都要求各帧形状一致，否则 numpy 报
    # "could not broadcast input array from shape (199,1270,3) into
    #  shape (137,1270,3)"。这里统一到"多数帧高度"（底部对齐，不缩放内容）。
    cleaned = normalize_heights(cleaned)

    if use_vlm and api_key:
        try:
            from vlm import load_model
            from vlm_recognize import analyze_rows

            p("正在用 VLM 识别每帧小节号…", 50)
            tmp = [TabRow(img, 0, f"f-{i}", i) for i, img in enumerate(cleaned)]
            cache = os.path.join(work_dir or os.getcwd(), "vlm_horizontal_cache.json")
            analyses = analyze_rows(
                tmp, api_key=api_key, model=load_model(), cache_path=cache,
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
                if state is not None:
                    state["vlm_ok"] = True
                return rows
            log.warn("VLM 未识别到小节号，回退像素拼接")
            if state is not None:
                state["vlm_ok"] = False
        except Exception as e:
            log.warn(f"VLM 小节号识别失败，回退像素拼接: {e}")
            if state is not None:
                state["vlm_ok"] = False

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
    # 段数太少（<6）说明这不是"持续滚动的谱带"，更可能是翻页视频被误判：
    # 回退到整屏模式更安全（像素拼接会把翻页内容错位拼在一起）。
    if rows and len(rows) < 6 and state is not None:
        log.warn(f"横向拼接只得到 {len(rows)} 段（偏少），判定为翻页型 → 回退整屏模式")
        state["fallback_screen"] = True
        return []
    return rows


def _is_real_horizontal_scroll(crop_imgs, min_shift: float = 30.0) -> tuple[bool, float]:
    """判断是否"真横向滚动"（连续同向、幅度稳定的位移）。

    翻页/静止型视频也会有零散位移（光标、局部变化），但方向和幅度杂乱；
    真滚动（如 Guitar Pro 谱带）是连续同向、幅度接近的位移。
    返回 (是否真滚动, 位移中位数)。
    """
    from stitch import estimate_shift

    if len(crop_imgs) < 4:
        return False, 0.0
    step = max(1, len(crop_imgs) // 14)
    picks = crop_imgs[::step][:14]
    dxs = []
    for i in range(1, len(picks)):
        try:
            dx, _dy, resp = estimate_shift(picks[i - 1], picks[i])
        except Exception:
            continue
        if abs(dx) >= min_shift and resp > 0.1:
            dxs.append(dx)
    if len(dxs) < 3:
        return False, 0.0
    # 连续同号的最大段长
    best_run = 1
    run = 1
    for i in range(1, len(dxs)):
        if dxs[i] * dxs[i - 1] > 0:
            run += 1
            best_run = max(best_run, run)
        else:
            run = 1
    # 幅度一致性（0.5~1.5 倍中位数）
    mags = [abs(d) for d in dxs]
    med = sorted(mags)[len(mags) // 2]
    consistent = sum(1 for m in mags if 0.5 * med <= m <= 1.5 * med) / len(mags)
    # 同号比例（Guitar Pro 谱带持续同向滚动时该值高）
    signs = [1 if d > 0 else -1 for d in dxs]
    same_ratio = sum(1 for s in signs if s == signs[0]) / len(signs)
    # 判定：
    # ① 连续同向 + 幅度稳定 → 真滚动（理想情形）；
    # ② 位移很大（>=200px，明显在滚动）且同向比例 >=0.5 → 也算真滚动
    #    （抽帧间隔大时相位相关会出现混叠，幅度不稳定，但方向仍以同向为主）
    ok = (best_run >= 3 and consistent >= 0.6) or (same_ratio >= 0.5 and med >= 200)
    return ok, med


def process(url: str = None, video: str = None, title: str = None,
            interval: float = 2.0, sample: int = 6, max_height: int = 720,
            cookies: str = None, box_arg: str = None,
            work_dir: str = None,
            progress: ProgressCb = None, keep_temp: bool = False,
            cleanup: bool = True,
            allow_manual: bool = True,
            api_key: str = None,
            vlm_on_horizontal: bool = True,
            should_stop=None) -> PipelineResult:
    """完整处理流程。

    返回 PipelineResult（all_rows/kept_rows/box/title）。
    使用 work_dir 作为工作目录（GUI 传入持久目录以便"找回"行）。
    allow_manual: 自动检测失败时是否允许弹出手动框选窗口
                  （GUI 后台线程必须为 False）。
    api_key: VLM API Key（横向滚动谱面用 VLM 读小节号去重；为空则用像素拼接）。
    should_stop: 可选回调，返回 True 表示用户已请求取消；在各阶段边界检查，
                 True 时抛 ProcessCancelled（GUI 据此丢弃结果、不弹核验窗口）。
    """
    def _check_stop():
        if should_stop is not None:
            try:
                if should_stop():
                    raise ProcessCancelled("用户取消")
            except ProcessCancelled:
                raise
            except Exception:
                pass

    def p(text: str, frac: float = 0.0):
        if progress:
            progress(text, frac)

    if not work_dir:
        work_dir = os.path.join(os.getcwd(),
                                f"_bili_tab_work_{int(time.time())}_{os.getpid()}")
    os.makedirs(work_dir, exist_ok=True)

    try:
        _check_stop()
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
        _check_stop()

        frames_dir = os.path.join(work_dir, "frames")
        _check_stop()
        p("正在抽帧…", 15)
        frames = extract_frames(video_path, frames_dir, interval)
        _check_stop()
        if len(frames) < 3:
            log.warn("帧数很少，请确认视频包含谱面画面")

        p("正在检测谱面区域…", 25)
        box = detect_tab_box(frames, sample, box_arg, allow_manual=allow_manual)
        _check_stop()

        crops_dir = os.path.join(work_dir, "crops")
        p("正在裁剪谱面区域…", 35)
        crops = crop_frames(frames, box, crops_dir)
        _check_stop()

        # 读裁剪图（供类型检测与后续处理）
        crop_imgs = [imread(c) for c in crops]
        crop_imgs = [i for i in crop_imgs if i is not None]

        # 检测谱面滚动类型：横向滚动 / 上滚 / 逐行（翻页）
        from stitch import (crop_screen_top, detect_scroll_direction,
                            estimate_shift, split_wide_image, stitch_horizontal)

        # 谱面视觉特征分析 → 自适应阈值（不针对某个视频写死"白底=230"这类参数）
        from profile import analyze_profile

        prof = analyze_profile(crop_imgs)
        thresholds = prof["thresholds"]
        log.info(f"谱面特征: {'、'.join(prof['labels'])} | "
                 f"背景灰度 {prof['bg_gray']}、墨迹灰度 {prof['ink_gray']}、"
                 f"对比度 {prof['contrast']}、背景饱和度 {prof['bg_sat']}、"
                 f"内容密度 {prof['content_frac']:.1%}")
        log.info(f"自适应阈值: 亮区>{thresholds['bright']} 墨迹<{thresholds['dark']} "
                 f"肤色饱和度>{thresholds['skin_sat']} 画面亮度<{thresholds['screen_bright']}")

        scroll_type = detect_scroll_direction(crop_imgs)
        log.info(f"谱面类型检测: {scroll_type}")

        all_rows: list[TabRow] = []
        used_horizontal = False

        # 判断谱面是"整屏一行"（和弦图+TAB+数字 = 一条完整谱行，高度通常 <700px）
        # 还是"多行排列"（一屏 2+ 条独立谱行）。
        # 整屏一行不要按"内容行密度"切分，否则会被拆成和弦图行/TAB行/数字行碎片。
        from rows import count_staff_groups

        screen_single_row = False
        if crop_imgs:
            heights = [img.shape[0] for img in crop_imgs[:12]]
            med_h = sorted(heights)[len(heights) // 2]
            groups = [count_staff_groups(img) for img in crop_imgs[:6]]
            med_groups = sorted(groups)[len(groups) // 2]
            # 整屏一行：高度 <=650px（单条谱行，含和弦图+TAB+数字）；
            # 多行排列通常 >650px（一屏 2~3 条独立谱行）。
            # 谱线组数只做记录，不作为硬条件（底部数字行/和弦图会额外成组）。
            screen_single_row = med_h <= 650
            log.info(f"谱面布局: 高度中位数 {med_h}px, 谱线组 {med_groups} → "
                     f"{'整屏一行' if screen_single_row else '多行排列'}")

        # 判断是否"真横向滚动"（连续同向、幅度稳定）
        scroll_significant, med_dx = _is_real_horizontal_scroll(crop_imgs)
        log.info(f"横向滚动判定: {'真滚动' if scroll_significant else '静止/翻页'} "
                 f"（位移中位数 {med_dx:.0f}px）")

        # 记录处理方式（用于末尾"总结"日志，让用户一眼看出走的哪条路）
        mode_state: dict = {}
        mode = "cv_rows"   # 默认：多行排列，纯本地 CV 切分

        if scroll_significant and screen_single_row:
            # 横向滚动谱带：VLM 读小节号去重（优先），像素拼接回退
            all_rows = _process_horizontal(
                crop_imgs, api_key, work_dir, p, vlm_on_horizontal, thresholds,
                state=mode_state)
            if mode_state.get("fallback_screen"):
                # 拼接段数过少 → 实际是翻页型视频，回退整屏模式
                scroll_significant = False
                screen_single_row = True
            else:
                used_horizontal = True
                mode = ("vlm_horizontal" if mode_state.get("vlm_ok") is True
                        else "cv_pixel_horizontal")

        if not all_rows and screen_single_row:
            # 整屏一行（静止/翻页/轻微滚动）：每帧一屏作为一行，后续像素去重
            mode = "cv_screen"
            p("正在整理整屏谱行…", 45)
            n_ph = 0
            for ci, img in enumerate(crop_imgs):
                try:
                    img = crop_screen_top(img, thresholds=thresholds)
                except Exception:
                    pass
                # 检测并涂掉"播放光标"（蓝/青色高亮竖条）：
                # 同一行谱面在光标位置不同时会被误判为不同帧（重复截取），
                # 涂白后指纹/像素比较都不受光标影响，PDF 也更干净。
                # band_half_width 用 30px（只盖光标细线，避免误伤谱面内容）。
                try:
                    from barlines import detect_playhead, mask_playhead
                    center, peak = detect_playhead(img)
                    if center is not None:
                        img = mask_playhead(img, [center], band_half_width=30)
                        n_ph += 1
                except Exception:
                    pass
                all_rows.append(TabRow(img, ci * interval, f"screen-{ci}", ci))
            if n_ph:
                log.info(f"检测并涂除播放光标 {n_ph} 帧（避免光标位置不同导致重复截取）")

        if not all_rows:
            # 行级切分（多行排列）：收集所有行（含被去重的，供人工核验找回）
            from rows import split_crop_rows

            n_crops = len(crops)
            for ci, c in enumerate(crops):
                if ci % 10 == 0:
                    _check_stop()
                img = imread(c)
                if img is None:
                    continue
                t = ci * interval
                for ri, row in enumerate(split_crop_rows(img, thresholds=thresholds)):
                    all_rows.append(TabRow(row, t, c, ri))
                if ci % 20 == 0:
                    p(f"切分行片段 {ci}/{n_crops}…", 40 + 30 * ci / n_crops)

        if len(all_rows) < 3:
            # 兜底：整屏裁剪作为"行"
            log.warn("行片段较少，回退到整屏模式")
            all_rows = []
            for ci, c in enumerate(crops):
                img = imread(c)
                if img is None:
                    continue
                all_rows.append(TabRow(img, ci * interval, c, 0))

        _check_stop()
        p("正在自动排序去重…", 75)
        if used_horizontal:
            # 横向滚动拼接/小节号去重后的段已不重叠，无需行级去重
            kept_rows = list(all_rows)
        else:
            from rows import dedup_rows

            # dedup_rows 输入是 (image, source, index)，输出 (image, source, index)
            kept = dedup_rows([(r.image, r.source, r.index) for r in all_rows],
                              thresholds=thresholds)
            kept_keys = {(k[1], k[2]) for k in kept}
            kept_rows = [r for r in all_rows if (r.source, r.index) in kept_keys]
            # 按时间排序（自动排序 = 按视频出现顺序）
            kept_rows.sort(key=lambda r: (r.time, r.index))

        p("处理完成", 100)

        # ---------- 处理方式总结（一眼看出走的哪条路）----------
        n_kept = len(kept_rows)
        log.step("处理方式总结")
        if mode == "vlm_horizontal":
            log.success(f"谱面类型：横向滚动 → AI（VLM）识别小节号去重成功，{n_kept} 段"
                        f"（模型读小节号，按小节顺序排列）")
        elif mode == "cv_pixel_horizontal":
            log.warn(f"谱面类型：横向滚动 → AI 未成功（或未启用），回退纯本地 CV 像素拼接，{n_kept} 段")
        elif mode == "cv_screen":
            log.success(f"谱面类型：整屏/翻页（单屏一条谱行）→ 纯本地 CV 处理（未使用 AI），"
                        f"{n_kept} 行")
        else:
            log.success(f"谱面类型：多行排列 → 纯本地 CV 切分（未使用 AI），{n_kept} 行")
        log.info("提示：如需语义去重（识别和弦/歌词/残谱），请在核验界面点「AI 识别 + 去重」")

        return PipelineResult(title, box, all_rows, kept_rows)
    finally:
        if cleanup and not keep_temp:
            # 默认保留 work_dir（GUI 需要它来找回行）；CLI 场景由调用方清理
            pass
