"""Build A4 'printed tab' pages from the real extracted tab rows."""

from pathlib import Path

import numpy as np
import cv2
from PIL import Image

from engine import (
    F32,
    Sprite,
    blank,
    blur,
    over,
    paper_texture,
    text_sprite,
    vignette_mask,
    gradient_sprite,
)
import design as D

ROWS_DIRS = [
    # 搬运视频素材（非付费谱）：Black Sabbath - Paranoid, BV19f421Q76h
    Path(__file__).resolve().parents[2] / "out" / "测试集" / "Paranoid",
]

_CACHE = {}


def _imread_unicode(path):
    img = Image.open(str(path))
    return np.asarray(img.convert("L"))


def _row_paths():
    rows = []
    for d in ROWS_DIRS:
        if d.exists():
            rows += sorted(d.glob("*.png"))
    return rows


def tab_rows():
    """Real extracted tab rows as uint8 RGB arrays (white bg). ~4x less RAM."""
    if "rows" not in _CACHE:
        out = []
        for p in _row_paths():
            try:
                img = _imread_unicode(p)
            except Exception:
                continue
            out.append(np.dstack([img, img, img]))
        _CACHE["rows"] = out
    return _CACHE["rows"]


def row_f32(i):
    """Float32 [0,1] copy of a cached row."""
    r = tab_rows()[i % len(tab_rows())]
    return r.astype(F32) / 255.0


def _resize_w(img, w):
    h = int(round(img.shape[0] * w / img.shape[1]))
    interp = cv2.INTER_AREA if w < img.shape[1] else cv2.INTER_CUBIC
    return cv2.resize(img, (int(w), max(1, h)), interpolation=interp)


def build_page(
    row_idx,
    title="富士山下",
    subtitle="吉他谱 · 完整版",
    page_no=1,
    page_total=3,
    width=1200,
    height=1697,
    margin=96,
    ink=(0.085, 0.095, 0.105),
    show_numbers=True,
    footer_note="视频扒谱工具 · 自动截谱",
):
    """Compose an A4-ratio page (px) with real tab rows printed on paper."""
    key = (tuple(row_idx), title, subtitle, page_no, page_total, width, height, margin, ink, show_numbers, footer_note)
    if key in _CACHE:
        return _CACHE[key]

    paper = paper_texture(width, height, seed=5 + page_no)
    paper = np.clip(paper * np.array([1.0, 0.996, 0.972], F32), 0, 1)
    # gentle paper shading: cooler at edges, warm light top-left
    ys, xs = np.mgrid[0:height, 0:width].astype(F32)
    nx = xs / width
    ny = ys / height
    light = 1.0 + 0.045 * (1 - nx) * (1 - ny) - 0.06 * (nx**2 + ny**2) ** 0.7
    page = paper * light[..., None] * np.array([1.015, 1.0, 0.975], F32)
    page = np.clip(page, 0, 1)

    rows = tab_rows()
    avail_w = width - margin * 2
    img_w = avail_w - (44 if show_numbers else 0)

    head_h = 122
    foot_h = 76
    y_top = margin + head_h
    y_bot = height - margin - foot_h
    avail_h = y_bot - y_top

    # build row images
    imgs = []
    for i in row_idx:
        if i >= len(rows):
            continue
        imgs.append(_resize_w(rows[i], img_w))
    if not imgs:
        page_s = Sprite(np.dstack([page, np.ones((height, width), F32)]))
        _CACHE[key] = page_s
        return page_s

    spacing = 30
    total = sum(im.shape[0] for im in imgs) + spacing * (len(imgs) - 1)
    if total > avail_h:
        # shrink rows proportionally
        k = avail_h / total
        imgs = [
            cv2.resize(im, (max(1, int(im.shape[1] * k)), max(1, int(im.shape[0] * k))), interpolation=cv2.INTER_AREA)
            for im in imgs
        ]
        spacing = max(12, int(spacing * k))
        total = sum(im.shape[0] for im in imgs) + spacing * (len(imgs) - 1)
    y = y_top + max(0, (avail_h - total) // 2)

    x_ink = margin + (44 if show_numbers else 0)
    for n, im in enumerate(imgs):
        h, w = im.shape[:2]
        region = page[y : y + h, x_ink : x_ink + w]
        # flatten the strip's own background (video lighting / highlights) onto
        # pure white so the notation reads as ink printed on this sheet
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41))
        bg = cv2.morphologyEx(im.astype(np.float32), cv2.MORPH_CLOSE, k)
        bg = np.maximum(bg, 0.35)
        im = np.clip(im / bg, 0, 1)
        im = np.clip((im - 0.06) / 0.94, 0, 1)
        region *= np.clip(im ** 1.9, 0, 1)
        if show_numbers:
            num = text_sprite(f"{n + 1:02d}", D.INK_SOFT * 0.85, "mono", 15, tracking=1.0)
            over(page, num, margin + 6, y + h / 2 - num.h / 2)
        y += h + spacing

    # header
    t = text_sprite(title, D.INK, "serif", 42, tracking=3.0, weight=600)
    over(page, t, margin, margin - 8)
    st = text_sprite(subtitle, D.INK_SOFT, "sans", 16, tracking=2.6)
    over(page, st, margin, margin + 58)
    page[margin + head_h - 34 : margin + head_h - 33, margin : width - margin] *= 0.80
    # right side tiny meta
    meta = text_sprite("A4  ·  300 DPI  ·  PDF", D.INK_SOFT * 0.8, "sans", 12, tracking=1.6)
    over(page, meta, width - margin - meta.w, margin + 58)

    # footer
    page[height - margin - foot_h + 22 : height - margin - foot_h + 23, margin : width - margin] *= 0.82
    fl = text_sprite(footer_note, D.INK_SOFT * 0.9, "sans", 13, tracking=0.8)
    over(page, fl, margin, height - margin + 8)
    ft = text_sprite(f"{page_no} / {page_total}", D.INK_SOFT, "mono", 15, tracking=1.4)
    over(page, ft, width - margin - ft.w, height - margin + 4)

    # print softness + paper grain
    page = cv2.GaussianBlur(page, (0, 0), 0.55)
    page = np.clip(page, 0, 1)

    s = Sprite(np.dstack([page, np.ones((height, width), F32)]))
    _CACHE[key] = s
    return s


def page_quad(cx, cy, w, h, rx=0.0, ry=0.0, rz=0.0, f=2600.0):
    """Return 4 corner points of a page centred at cx,cy with 3D-ish rotation."""
    import math

    pts3 = np.array(
        [[-w / 2, -h / 2, 0], [w / 2, -h / 2, 0], [w / 2, h / 2, 0], [-w / 2, h / 2, 0]], F32
    )
    a, b, c = math.radians(ry), math.radians(rx), math.radians(rz)
    Ry = np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]], F32)
    Rx = np.array([[1, 0, 0], [0, math.cos(b), -math.sin(b)], [0, math.sin(b), math.cos(b)]], F32)
    Rz = np.array([[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]], F32)
    P = pts3 @ Rz.T @ Rx.T @ Ry.T
    z = P[:, 2] + f
    return P[:, :2] * (f / z)[:, None] + np.array([cx, cy], F32)
