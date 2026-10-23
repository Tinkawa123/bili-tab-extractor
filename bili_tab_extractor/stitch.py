# -*- coding: utf-8 -*-
"""拼接与 PDF 输出模块。

- 滚动拼接：对"平滑滚动"型谱面（谱面像字幕一样持续上滚），用相位相关
  估计的垂直位移把各帧按正确位置贴到一张长图上，得到完整谱。
  长图随后按"内容行间距聚类"切分为一行行谱面（可读性更好）。
- 翻页/逐行型谱面：每帧本身就是完整一行，直接竖排。
- PDF：A4 @300DPI，每页自上而下排多张谱面图（参考 rohin 的
  images_to_pdf_a4：超出页高则翻页）。
"""

from __future__ import annotations

import os

import cv2
import numpy as np
from PIL import Image, ImageFilter

from util import imread, imwrite, log

# A4 @300DPI
A4_WIDTH, A4_HEIGHT = 2480, 3508
MARGIN = 100
GAP = 40  # 同一页内相邻谱图间距
MIN_SEG_HEIGHT = 24     # 切出的片段最小高度


# ---------- 滚动拼接 ----------

def stitch_scrolling(crops: list[str], shifts: list[float],
                     min_shift: float = 4.0) -> list[np.ndarray]:
    """把滚动型谱面按垂直位移拼接为若干段长图（BGR）。

    原理：谱面内容相对窗口持续平移（相位相关给出相邻帧位移 dy），
    把每帧贴到内容空间的绝对位置（画布随需要向顶部/底部扩展），
    重叠区由最新帧覆盖，从而还原出完整谱面长图。

    返回段列表；若位移模式不符合滚动（翻页型），返回 [] 让调用方逐帧处理。
    """
    if len(crops) < 2:
        return []
    # 位移方向一致性检查
    sig = [s for s in shifts[1:] if abs(s) >= min_shift]
    if not sig:
        return []
    mean_dir = np.sign(np.mean(sig))
    consistent = sum(1 for s in sig if np.sign(s) == mean_dir)
    if consistent / len(sig) < 0.6:
        return []

    log.step(f"滚动拼接 {len(crops)} 帧…")

    imgs = [imread(p) for p in crops]
    if any(i is None for i in imgs):
        log.warn("部分裁剪图读取失败，跳过滚动拼接")
        return []
    h, w = imgs[0].shape[:2]

    segments: list[np.ndarray] = []
    canvas = imgs[0].copy()
    top = 0  # 当前帧内容顶部在画布中的 y 坐标

    def flush():
        nonlocal canvas
        dark_rows = (canvas < 128).any(axis=(1, 2))
        if dark_rows.any():
            first = int(np.argmax(dark_rows))
            last = int(len(dark_rows) - 1 - np.argmax(dark_rows[::-1]))
            seg = canvas[max(0, first - 10): last + 11]
            if seg.shape[0] > MIN_SEG_HEIGHT:
                segments.append(seg.copy())

    for i in range(1, len(imgs)):
        dy = shifts[i]
        cur = imgs[i]
        # 位移突变（方向反转或跳跃）=> 翻页/段落切换，结束当前段
        if dy * mean_dir < -2 or abs(dy) > h * 0.4:
            flush()
            canvas = imgs[i].copy()
            top = 0
            continue
        if abs(dy) < 1:
            continue  # 几乎无位移（光标在扫），跳过

        top += dy  # 当前帧顶部在画布中的位置（dy 负 = 内容上滚，顶部上移）
        top_int = int(round(top))

        if top_int < 0:
            ext = np.full((-top_int, w, 3), 255, dtype=np.uint8)
            canvas = np.vstack([ext, canvas])
            top_int = 0
            top = 0.0
        need = top_int + h
        if need > canvas.shape[0]:
            ext = np.full((need - canvas.shape[0] + h, w, 3), 255, dtype=np.uint8)
            canvas = np.vstack([canvas, ext])
        canvas[top_int:top_int + h] = cur

    flush()
    log.success(f"滚动拼接完成：{len(segments)} 段")
    return segments


def estimate_shift(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float]:
    """相位相关估计 b 相对 a 的位移 (dx, dy) 与响应强度。

    返回 (dx, dy, response)：dx>0 表示内容向右移动，dy>0 表示向下移动。
    """
    ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.float32)
    # 加 Hann 窗减少边缘效应
    h, w = ga.shape
    win = np.outer(np.hanning(h), np.hanning(w)).astype(np.float32)
    ga = (ga - ga.mean()) * win
    gb = (gb - gb.mean()) * win
    (dx, dy), response = cv2.phaseCorrelate(ga, gb)
    return float(dx), float(dy), float(response)


def detect_scroll_direction(images: list[np.ndarray], sample: int = 12) -> str:
    """判断视频谱面滚动类型：'horizontal'（横向滚动）/ 'vertical'（上滚）/ 'rows'（逐行/翻页）。

    采样比较相邻帧的位移方向：横向位移显著大于纵向 → horizontal；
    纵向位移显著 → vertical；都没有明显位移（整行切换）→ rows。
    """
    if len(images) < 3:
        return "rows"
    step = max(1, len(images) // sample)
    picks = images[::step][:sample]
    dxs, dys = [], []
    for i in range(1, len(picks)):
        try:
            dx, dy, resp = estimate_shift(picks[i - 1], picks[i])
        except Exception:
            continue
        if resp < 0.02:  # 相关性太低（内容完全变化）→ 忽略
            continue
        dxs.append(abs(dx))
        dys.append(abs(dy))
    if not dxs:
        return "rows"
    med_dx = float(np.median(dxs))
    med_dy = float(np.median(dys))
    if med_dx >= 8 and med_dx > med_dy * 2:
        return "horizontal"
    if med_dy >= 8 and med_dy > med_dx * 2:
        return "vertical"
    return "rows"


def crop_screen_top(img: np.ndarray, max_frac: float = 0.4,
                    thresholds: dict | None = None) -> np.ndarray:
    """裁掉图片顶部的演奏画面残留。

    判断依据（谱面是亮底，演奏画面是深色/高饱和）：
    - 行平均亮度 < screen_bright（画面偏暗，默认 170），或
    - 行平均饱和度 > screen_sat（画面彩色，谱面近灰白，默认 60）
    thresholds 来自 profile.analyze_profile（自适应到该视频的亮度/色调）。
    max_frac 限制最多裁掉的比例，避免误裁。
    """
    h, w = img.shape[:2]
    if h < 40:
        return img
    if thresholds:
        screen_bright = int(thresholds.get("screen_bright", 170))
        screen_sat = int(thresholds.get("screen_sat", 60))
    else:
        screen_bright, screen_sat = 170, 60
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    row_bright = gray.mean(axis=1)
    row_sat = hsv[:, :, 1].mean(axis=1)
    is_screen = (row_bright < screen_bright) | (row_sat > screen_sat)
    limit = int(h * max_frac)
    cut = 0
    for y in range(min(h, limit)):
        if is_screen[y]:
            cut = y + 1
        elif cut > 0 and y > cut + 5:
            break
    if cut >= 5:
        return img[cut:]
    return img


def stitch_horizontal(images: list[np.ndarray], shifts: list[float],
                      min_shift: float = 20.0,
                      max_seg_width: int = 60000) -> list[np.ndarray]:
    """横向滚动型谱面拼接（支持回滚：按位移方向分段拼接）。

    images: 各帧裁剪图（同尺寸）
    shifts: shifts[i] = 第 i 帧相对第 i-1 帧的水平位移（>0 内容右移）
    返回拼接段列表（每段是一张横向长图）；无有效位移时返回 []。
    """
    if len(images) < 2:
        return []
    h, w = images[0].shape[:2]

    # 清理位移：无位移帧跳过；混叠修正（|dx| 接近整幅宽度时取等价短位移）
    valid: list[float | None] = [None]
    for i in range(1, len(images)):
        s = shifts[i] if i < len(shifts) else 0.0
        if abs(s) < min_shift:
            valid.append(None)
            continue
        if abs(s) > w * 0.6:
            alt = s - np.sign(s) * w
            if abs(alt) < abs(s):
                s = alt
        valid.append(float(s))

    sig = [(i, s) for i, s in enumerate(valid) if s is not None]
    if len(sig) < 2:
        return []

    # 按位移方向分段（方向反转 = 回滚，新起一段）
    segments: list[tuple[float, list[int]]] = []
    cur: list[int] = [0]
    cur_sign: float | None = None
    for idx, s in sig:
        sign = float(np.sign(s))
        if cur_sign is None or sign == cur_sign:
            cur.append(idx)
            cur_sign = sign
        else:
            segments.append((cur_sign, cur))
            cur = [idx]
            cur_sign = sign
    if cur:
        segments.append((cur_sign or 0.0, cur))

    out: list[np.ndarray] = []
    for sign, frames in segments:
        frames = sorted(set(frames))
        if len(frames) < 2:
            continue
        # 段内累计绝对偏移
        offsets = {frames[0]: 0.0}
        acc = 0.0
        for k in range(1, len(frames)):
            for j in range(frames[k - 1] + 1, frames[k] + 1):
                sv = valid[j]
                if sv is not None:
                    acc += sv
            offsets[frames[k]] = acc
        xs = list(offsets.values())
        base = -min(xs)
        total_w = int(max(xs) - min(xs)) + w
        if total_w > max_seg_width:
            log.warn(f"横向段过长（{total_w}px），跳过")
            continue
        canvas = np.full((h, total_w, 3), 255, dtype=np.uint8)
        for i in frames:
            x = int(round(base + offsets[i]))
            x2 = min(total_w, x + w)
            if 0 <= x < total_w and x2 > x:
                canvas[:, x:x2] = images[i][:, :x2 - x]
        out.append(canvas)

    if out:
        log.success(f"横向拼接完成：{len(segments)} 段 → {len(out)} 张长图")
    return out


def split_wide_image(img: np.ndarray, max_section_w: int = 2400,
                     blank_ratio: float = 0.02) -> list[np.ndarray]:
    """把超宽长图按"小节间隙"（空白竖列）切段，避免切断谱线。

    max_section_w: 每段最大宽度（超过则强制切）
    blank_ratio: 空白列判定（该列内容像素占比低于此值算空白）
    """
    h, w = img.shape[:2]
    if w <= max_section_w:
        return [img]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    content = (gray < 150).mean(axis=0)  # 每列内容占比
    sections = []
    start = 0
    while start < w:
        end = min(w, start + max_section_w)
        if end >= w:
            sections.append(img[:, start:end])
            break
        # 在 [start+max_section_w*0.6, end] 区间找最空的列作为切点
        lo = start + int(max_section_w * 0.6)
        best_x, best_score = end, 1e9
        for x in range(lo, end):
            score = content[x]
            if score < blank_ratio and score < best_score:
                best_score = score
                best_x = x
        sections.append(img[:, start:best_x])
        start = best_x
    return [s for s in sections if s.shape[1] > 20]


def split_long_image(img: np.ndarray, max_inner_gap: int = 25,
                     dark_thresh: int = 30) -> list[np.ndarray]:
    """把长图按"内容行间距聚类"切分为一行行谱面（BGR -> 列表）。

    原理：每行谱 = 五线谱（5 条密排线）+ TAB 块（6 条密排线），其内部
    线间距小且均匀（8~12px）；行与行之间是更大的垂直空白。因此对"内容
    行"（暗像素数 > dark_thresh）做相邻间距分析，间距 > max_inner_gap
    的位置即行间分界，在分界空白的中点切开。

    若整图找不到分界（单行或排版紧凑），返回空列表，由调用方兜底。
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    dark_count = (gray < 128).sum(axis=1)
    content_rows = np.where(dark_count > dark_thresh)[0]
    if len(content_rows) < 2:
        return []

    gaps = np.diff(content_rows)
    cut_positions: list[int] = []
    for i, g in enumerate(gaps):
        if g > max_inner_gap:
            mid = (content_rows[i] + content_rows[i + 1]) // 2
            cut_positions.append(mid)
    if not cut_positions:
        return []

    segments: list[np.ndarray] = []
    prev = 0
    for cut in cut_positions:
        seg = img[prev:cut]
        if seg.shape[0] >= MIN_SEG_HEIGHT:
            segments.append(seg)
        prev = cut
    tail = img[prev:]
    if tail.shape[0] >= MIN_SEG_HEIGHT:
        segments.append(tail)
    return segments


# ---------- PDF ----------

def _fit_width(img: Image.Image, target_w: int) -> Image.Image:
    w, h = img.size
    if w == target_w:
        return img
    scale = target_w / w
    return img.resize((target_w, max(1, int(h * scale))), Image.LANCZOS)


def images_to_pdf(images: list[Image.Image], out_path: str, title: str,
                  lines_per_page: int = 0) -> int:
    """把谱面图竖排为 A4 多页 PDF。

    lines_per_page=0 时自动：能放几张放几张；>0 时每页固定张数。
    返回页数。
    """
    if not images:
        raise RuntimeError("没有可输出的谱面图像")

    content_w = A4_WIDTH - 2 * MARGIN
    content_h = A4_HEIGHT - 2 * MARGIN

    pages: list[Image.Image] = []
    page = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), "white")
    cursor_y = MARGIN

    # 标题（第一页顶部）
    if title:
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(page)
        try:
            font = ImageFont.truetype("msyh.ttc", 64)  # 微软雅黑
        except Exception:
            font = ImageFont.load_default()
        draw.text((MARGIN, 40), title, fill="black", font=font)
        cursor_y = MARGIN + 110

    def new_page():
        nonlocal page, cursor_y
        pages.append(page)
        page = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), "white")
        cursor_y = MARGIN

    count_on_page = 0
    for img in images:
        img = _fit_width(img, content_w)
        iw, ih = img.size
        # 超高图（如未切分的滚动长图）等比缩到一页高
        if ih > content_h:
            scale = content_h / ih
            img = img.resize((max(1, int(iw * scale)), content_h), Image.LANCZOS)
            iw, ih = img.size
        # 锐化：放大后谱面线条更清晰（USM，半径 2 不影响笔画）
        if iw > 300:
            img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=80, threshold=2))
        if cursor_y + ih > A4_HEIGHT - MARGIN:
            new_page()
            count_on_page = 0
        if lines_per_page > 0 and count_on_page >= lines_per_page:
            new_page()
            count_on_page = 0
        page.paste(img, (MARGIN, cursor_y))
        cursor_y += ih + GAP
        count_on_page += 1

    pages.append(page)

    # 去掉末尾的空页（new_page 在换页时已把旧页入列；若最后一页无任何
    # 内容则丢弃——例如刚好填满一页后多出的空白页）
    if pages and _page_is_blank(pages[-1]):
        pages.pop()

    pages[0].save(out_path, "PDF", save_all=True, append_images=pages[1:],
                  resolution=300)
    return len(pages)


def _page_is_blank(page: Image.Image, dark_thresh: float = 0.002) -> bool:
    """判断一页是否基本空白（除标题外无谱面内容）。"""
    import numpy as _np

    arr = _np.asarray(page.convert("L"))
    return float((arr < 128).mean()) < dark_thresh


def verify_and_clean_pdf(out_path: str, skin_thresh: float = 0.05) -> int:
    """PDF 生成后的最终检查：渲染每页，删除混入演奏画面（肤色特征）的页。

    这是第二道防线——行级过滤（PDF 前）漏网的演奏画面在此被拦截。
    用 pypdf 提取页面嵌入图片做肤色检测（演奏者手/脸的强特征），
    肤色占比超过阈值的页面直接从 PDF 中移除。返回清理后的页数。
    """
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        return 0
    import io
    from PIL import Image

    reader = PdfReader(out_path)
    if len(reader.pages) <= 1:
        return len(reader.pages)

    writer = PdfWriter()
    removed = 0
    for i, page in enumerate(reader.pages):
        res = page.get("/Resources")
        skin_frac = 0.0
        if res and "/XObject" in res:
            for obj in res["/XObject"].values():
                try:
                    img = Image.open(io.BytesIO(obj.get_data())).convert("RGB")
                    arr = np.asarray(img)
                    hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)
                    skin = cv2.inRange(hsv, (0, 30, 60), (25, 255, 255))
                    skin |= cv2.inRange(hsv, (165, 30, 60), (180, 255, 255))
                    # 注意：skin 是 0/255 的 uint8，必须换算成 0~1 比例
                    skin_frac = max(skin_frac, float((skin > 0).mean()))
                except Exception:
                    continue
        if skin_frac > skin_thresh:
            removed += 1
            log.warn(f"PDF 后检查：第{i + 1}页含演奏画面（肤色 {skin_frac:.1%}），已移除")
        else:
            writer.add_page(page)

    if removed:
        with open(out_path, "wb") as f:
            writer.write(f)
        log.warn(f"PDF 后检查完成：共移除 {removed} 页演奏画面")
    else:
        log.success("PDF 后检查：所有页面均为纯净谱面")
    return len(writer.pages)


def make_pdf(crops: list[str], shifts: list[float], out_path: str, title: str,
             use_scroll: bool = True) -> int:
    """编排最终 PDF：滚动拼接（若适用）→ 切行 → A4 竖排。返回页数。"""
    log.step(f"生成 PDF（{len(crops)} 张谱面图）…")

    pil_images: list[Image.Image] = []
    if use_scroll:
        segs = stitch_scrolling(crops, shifts)
        for seg in segs:
            parts = split_long_image(seg)
            if not parts:
                # 排版紧凑无空白带：按滚动窗口高度切段，避免整图缩太小
                h = seg.shape[0]
                win = min(h, 320)
                for y in range(0, h, win):
                    parts.append(seg[y:y + win])
            for p in parts:
                pil_images.append(Image.fromarray(cv2.cvtColor(p, cv2.COLOR_BGR2RGB)))
    if not pil_images:
        # 翻页/逐行模式：每帧一行
        for p in crops:
            img = imread(p)
            if img is not None:
                pil_images.append(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))

    if not pil_images:
        raise RuntimeError("没有可输出的谱面图像")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    n_pages = images_to_pdf(pil_images, out_path, title)
    log.success(f"PDF 已生成 → {out_path}（{n_pages} 页）")
    return n_pages


def make_pdf_from_rows(rows: list[tuple[np.ndarray, str, int]],
                       out_path: str, title: str,
                       rows_per_page: int = 0) -> int:
    """把去重后的行片段直接竖排为 A4 PDF（行级管线）。

    rows: [(行BGR图, 来源, 行序号), ...]，已按视频出现顺序排列。
    """
    if not rows:
        raise RuntimeError("没有可输出的谱面行")
    log.step(f"生成 PDF（{len(rows)} 行谱面）…")

    pil_images = [Image.fromarray(cv2.cvtColor(r[0], cv2.COLOR_BGR2RGB)) for r in rows]
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    n_pages = images_to_pdf(pil_images, out_path, title,
                            lines_per_page=rows_per_page)
    log.success(f"PDF 已生成 → {out_path}（{n_pages} 页，{len(rows)} 行）")
    return n_pages
