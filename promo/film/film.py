"""「视频扒谱工具」60s promo film — deterministic render(t).

Timeline (100 BPM, BAR = 2.4 s):
  S1  0.0-7.2   the tab keeps scrolling, 37 screenshots, none of them usable
  S2  7.2-14.4  paste the link, hit start
  S3 14.4-26.4  extraction: scan -> strips -> stack -> dedupe -> page
  S4 26.4-36.0  review: drag, dedupe, AI
  S5 36.0-45.6  paper: A4 pages, flip, macro
  S6 45.6-60.0  brand: the line becomes the logo
"""

from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

import design as D
import pages
from engine import *
from engine import F32

ASSET_VIDEO = Path(__file__).resolve().parent / "assets" / "video"

_C = {}


# --------------------------------------------------------------------------- #
# shared assets
# --------------------------------------------------------------------------- #


def _resize_fit(img, w, h, interp=None):
    ih, iw = img.shape[:2]
    s = max(w / iw, h / ih)
    nw, nh = int(round(iw * s)), int(round(ih * s))
    if interp is None:
        interp = cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC
    r = cv2.resize(img, (nw, nh), interpolation=interp)
    x0, y0 = (nw - w) // 2, (nh - h) // 2
    return r[y0 : y0 + h, x0 : x0 + w]


def video_sprite(name, crop, w, h):
    key = ("vid", name, crop, w, h)
    if key in _C:
        return _C[key]
    img = load_image(ASSET_VIDEO / name, "RGB")
    if crop:
        x0, y0, x1, y1 = crop
        img = img[y0:y1, x0:x1]
    img = _resize_fit(img, w, h)
    _C[key] = from_float(np.dstack([img, np.ones(img.shape[:2], F32)]))
    return _C[key]


def tab_strip_texture(width=1500, n=16):
    key = ("strip", width, n)
    if key in _C:
        return _C[key]
    rows = pages.tab_rows()
    parts = []
    for i in range(min(n, len(rows))):
        im = rows[i]
        h = int(round(im.shape[0] * width / im.shape[1]))
        r = cv2.resize(im, (width, max(1, h)), interpolation=cv2.INTER_AREA).astype(F32) / 255.0
        parts.append(r)
        parts.append(np.ones((12, width, 3), F32))
    tex = np.clip(np.concatenate(parts, axis=0) * 0.99, 0, 1)
    _C[key] = from_float(np.dstack([tex, np.ones(tex.shape[:2], F32)]))
    return _C[key]


def studio_bg(variant="dark"):
    """Dark studio stage: key light, floor falloff, dust."""
    key = ("bg", variant)
    if key in _C:
        return _C[key]
    if variant == "dark":
        base = radial_sprite(D.W, D.H, [(0.0, D.hexc("#101A1B")), (0.5, D.hexc("#070B0C")), (1.0, D.hexc("#020303"))], (D.W * 0.52, D.H * 0.30), D.W * 0.9)
        img = base.rgb.copy()
        warm = glow_field(D.W, D.H, (D.W * 0.18, D.H * 0.92), D.W * 0.75, D.hexc("#3A2414"), falloff=2.4, gain=0.55)
        over(img, warm, 0, 0, 1.0, blend="add")
    elif variant == "warm":
        base = radial_sprite(D.W, D.H, [(0.0, D.hexc("#2A1A10")), (0.45, D.hexc("#140C07")), (1.0, D.hexc("#050302"))], (D.W * 0.42, D.H * 0.42), D.W * 0.9)
        img = base.rgb.copy()
        warm = glow_field(D.W, D.H, (D.W * 0.30, D.H * 0.85), D.W * 0.8, D.hexc("#5A3418"), falloff=2.2, gain=0.6)
        over(img, warm, 0, 0, 1.0, blend="add")
    else:
        base = radial_sprite(D.W, D.H, [(0.0, D.hexc("#0B1B1E")), (0.5, D.hexc("#061011")), (1.0, D.hexc("#020505"))], (D.W * 0.5, D.H * 0.35), D.W * 0.9)
        img = base.rgb.copy()
        teal = glow_field(D.W, D.H, (D.W * 0.5, D.H * 0.55), D.W * 0.7, D.TEAL_DARK, falloff=2.6, gain=0.8)
        over(img, teal, 0, 0, 1.0, blend="add")
    _C[key] = img
    return img


def dust(img, t, n=34, seed=5, gain=1.0):
    rng = np.random.default_rng(seed)
    xs = rng.uniform(0, D.W, n)
    ys = rng.uniform(0, D.H, n)
    rs = rng.uniform(0.6, 2.2, n)
    ph = rng.uniform(0, 6.28, n)
    sp = rng.uniform(0.15, 0.5, n)
    for i in range(n):
        x = xs[i] + math.sin(t * sp[i] + ph[i]) * 26
        y = (ys[i] - t * (6 + 10 * sp[i])) % D.H
        a = 0.05 + 0.05 * (0.5 + 0.5 * math.sin(t * 0.9 + ph[i] * 2))
        d = int(round(rs[i] * 2)) + 1
        spr = ellipse_sprite(d, d, D.WHITE if i % 5 else D.TEAL, opacity=a * gain)
        over(img, spr, x, y, 1.0, blend="add")


def cursor_sprite(scale=1.0):
    key = ("cursor", round(scale, 2))
    if key in _C:
        return _C[key]
    w, h = int(28 * scale), int(40 * scale)
    pts = [(2, 2), (2, 32), (9.5, 24.5), (15, 38), (20.5, 35), (15, 22.5), (25, 23.5)]
    pts = [(x * scale, y * scale) for x, y in pts]
    m = polygon_mask(w, h, pts, ss=4)
    body = mask_to_sprite(m, np.array([0.99, 0.99, 0.99], F32))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    dil = cv2.dilate(m, k, iterations=1)
    outline = mask_to_sprite(np.clip(dil - m, 0, 1), np.array([0.02, 0.02, 0.03], F32))
    spr = blank(w, h)
    over_sprite(spr, outline)
    over_sprite(spr, body)
    _C[key] = spr
    return spr


def finish(img, t, grain_amt=0.024, vig=0.52, warm=0.0, lift=0.0, contrast=1.03, sat=1.0, bloom_amt=0.13, halo_amt=0.05):
    img = np.clip(img, 0, 1)
    img = (img - 0.42) * contrast + 0.42
    img = np.clip(img, 0, 1)
    if sat != 1.0:
        lum = img @ np.array([0.2126, 0.7152, 0.0722], F32)
        img = lum[..., None] + (img - lum[..., None]) * sat
    if warm > 0:
        img = img * np.array([1 + 0.045 * warm, 1 + 0.012 * warm, 1 - 0.05 * warm], F32)
    if lift > 0:
        img = img * (1 - lift) + lift * np.array([0.02, 0.03, 0.032], F32)
    img = light_pass(img, threshold=0.70, sigma=28, bloom_gain=bloom_amt, halo_gain=halo_amt, halo_tint=(1.0, 0.58, 0.42))
    img = grain(img, t, grain_amt)
    img = img * vignette_mask(D.W, D.H, vig)
    img = img * 0.985 + np.array([0.008, 0.010, 0.011], F32)
    return np.clip(img, 0, 1)


# --------------------------------------------------------------------------- #
# text helpers
# --------------------------------------------------------------------------- #


def wipe(spr, p, up=True, feather=0.18):
    if p >= 0.999:
        return spr
    if p <= 0.001:
        return spr.with_opacity(0.0)
    h = spr.h
    yy = np.linspace(0, 1, h, dtype=F32)[:, None]
    edge = p * (1 + feather)
    if up:
        a = np.clip((edge - yy) / feather, 0, 1)
    else:
        a = np.clip((yy - (1 - edge)) / feather, 0, 1)
    a = np.clip(a, 0, 1)
    a = (a * a * (3 - 2 * a))[..., None]
    out = spr.rgba.copy()
    out[..., :3] *= a
    out[..., 3:4] *= a
    return Sprite(out)


def caption(base, text, x, y, t, t_in, t_out, color, name="serif", px=90, tracking=1.5, weight=600, rise=24, dur=0.6, align="left"):
    """Fade + rise reveal (a hard wipe cuts CJK glyphs in half)."""
    if t < t_in or t > t_out + 0.5:
        return
    p = remap(t, t_in, t_in + dur, ease_out_cubic)
    q = remap(t, t_out, t_out + 0.5, ease_in_cubic)
    spr = text_sprite(text, color, name, px, tracking, weight)
    op = (p ** 0.8) * (1 - q)
    dy = (1 - p) * rise - q * rise
    if align == "center":
        x = (D.W - spr.w) / 2
    elif align == "right" and x is None:
        x = D.W - 140 - spr.w
    over(base, spr.with_opacity(op), x, y + dy)


def scrim(img, w, h, p0, p1, stops, x=0, y=0):
    over(img, alpha_scrim(w, h, p0, p1, stops), x, y)


# --------------------------------------------------------------------------- #
# S1 — pain (0.0 - 7.2)
# --------------------------------------------------------------------------- #


def _closeup_tab(t, z=1.0, speed=1500.0, width=2600):
    tex = tab_strip_texture(width=width, n=16)
    th = tex.h
    need_h = int(D.H * z) + 24
    off = (t * speed * z) % max(1, th - need_h)
    sub = tex.rgba[int(off) : int(off) + need_h]
    img = sub[..., :3].copy()
    sigma = 5.0 + 7.0 * clamp(speed / 2200.0)
    img = cv2.GaussianBlur(img, (0, 0), 1.4, sigma)
    ch, cw = img.shape[:2]
    cw2, ch2 = min(cw, int(D.W / z)), min(ch, int(D.H / z))
    x0, y0 = (cw - cw2) // 2, (ch - ch2) // 2
    img = cv2.resize(img[y0 : y0 + ch2, x0 : x0 + cw2], (D.W, D.H), interpolation=cv2.INTER_AREA)
    # video-grade: darker, cooler, glowing screen
    img *= np.array([0.46, 0.52, 0.55], F32)
    gg = glow_field(D.W, D.H, (D.W * 0.76, D.H * 0.04), D.W * 1.0, D.TEAL, falloff=2.8, gain=0.12)
    over(img, gg, 0, 0, 1.0, blend="add")
    return img


def _video_world(t):
    """Full-bleed 'the tutorial video' frame with the scrolling tab region."""
    key = ("vworld", round(t, 3))
    hit = _C.get(key)
    if hit is not None:
        return hit
    base = _video_base().copy()
    # ---- scrolling tab region (replaces the burned-in tab in the video)
    tab_top = 596
    tab_bottom = D.H - 52
    tab_h = tab_bottom - tab_top
    tex = tab_strip_texture(width=D.W, n=16)
    speed = 640.0 + 380.0 * (1.0 - remap(t, 0.8, 3.4, ease_out_cubic))
    off = int((t * speed) % max(1, tex.h - tab_h - 4))
    tab = tex.rgba[off : off + tab_h][..., :3].copy()
    sigma = 2.0 + 3.0 * clamp((speed - 600) / 500.0)
    tab = cv2.GaussianBlur(tab, (0, 0), 1.1, sigma)
    tab *= np.array([0.86, 0.815, 0.745], F32)
    over(base, from_float(np.dstack([tab, np.ones((tab_h, D.W), F32)])), 0, tab_top)
    # boundary shadow above the tab
    scrim(base, D.W, 170, (0, 0), (0, 170), [(0.0, 0.0), (0.35, 0.30), (0.75, 0.76), (1.0, 0.95)], 0, tab_top - 170)
    # scan line inside the tab
    sp = (t * 0.42) % 1.0
    ly = int(tab_top + 8 + sp * (tab_h - 16))
    scan = glow_field(D.W, 90, (D.W * 0.5, 45), D.W * 0.6, D.TEAL, falloff=1.8, gain=0.16)
    over(base, scan, 0, ly - 45, 1.0, blend="add")
    over(base, mask_to_sprite(rect_mask(D.W, 1), D.TEAL), 0, ly, 0.55, blend="add")
    # detection edge
    over(base, mask_to_sprite(rect_mask(D.W, 2), D.TEAL_DEEP), 0, tab_top, 0.5)
    # ---- player chrome
    over(base, alpha_scrim(D.W, 90, (0, 0), (0, 90), [(0.0, 0.9), (1.0, 0.0)]), 0, D.H - 90)
    p = clamp(0.18 + t * 0.045, 0, 0.42)
    over(base, solid(D.W - 96, 3, D.hexc("#3A4446")), 48, D.H - 30)
    fw = int((D.W - 96) * p)
    over(base, solid(fw, 3, D.TEAL), 48, D.H - 30)
    over(base, ellipse_sprite(11, 11, D.TEAL), 48 + fw - 5, D.H - 34)
    tc = text_sprite("02:14 / 06:38", D.hexc("#C9D2D4"), "mono", 15, tracking=1.2)
    over(base, tc, D.W - 48 - tc.w, D.H - 44)
    _C[key] = base
    return base


def _video_base():
    key = ("vbase",)
    if key in _C:
        return _C[key]
    v = video_sprite("bv19f_20.png", (0, 0, 1920, 1080), D.W, D.H)
    img = v.rgb.copy()
    lum = img @ np.array([0.2126, 0.7152, 0.0722], F32)
    img = lum[..., None] + (img - lum[..., None]) * 0.55
    img = img * np.array([0.42, 0.47, 0.50], F32)
    img = np.clip((img - 0.08) * 1.30, 0, 1)
    # teal + warm mixed ambience
    g = glow_field(D.W, D.H, (D.W * 0.85, D.H * 0.08), D.W * 0.75, D.TEAL, falloff=2.6, gain=0.12)
    over(img, g, 0, 0, 1.0, blend="add")
    w = glow_field(D.W, D.H, (D.W * 0.10, D.H * 0.75), D.W * 0.6, D.hexc("#5A3418"), falloff=2.4, gain=0.25)
    over(img, w, 0, 0, 1.0, blend="add")
    _C[key] = img
    return img


def _camera(img, zoom=1.0, cx=D.W / 2, cy=D.H / 2, shake=(0.0, 0.0)):
    if abs(zoom - 1.0) < 1e-4 and abs(shake[0]) < 0.2 and abs(shake[1]) < 0.2:
        return img
    M = np.array(
        [[zoom, 0, (1 - zoom) * cx + shake[0]], [0, zoom, (1 - zoom) * cy + shake[1]]], F32
    )
    return cv2.warpAffine(img, M, (D.W, D.H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def scene1(t):
    world = _video_world(t)
    # camera: gentle drift, then a push into the tab for the cut
    push = remap(t, 6.35, 7.15, ease_in_cubic)
    zoom = 1.03 + 0.02 * math.sin(t * 0.55) + 0.16 * push
    shake_amt = 0.0
    for tc in (4.30, 4.95, 5.60):
        shake_amt += 4.0 * pulse(t, tc, 0.22)
    shake = (math.sin(t * 90) * shake_amt, math.cos(t * 77) * shake_amt)
    img = _camera(world.copy(), zoom, D.W * 0.5, 860, shake)

    # fade in from black + the protagonist line draws in
    fade = remap(t, 0.0, 0.35, ease_out_cubic)
    img = img * fade
    seam = remap(t, 0.05, 0.85, ease_out_cubic) * (1 - remap(t, 1.55, 2.3, ease_in_out_cubic))
    if seam > 0:
        lw = int(D.W * 0.72 * seam)
        over(img, solid(lw, 2, D.TEAL), (D.W - lw) / 2, 566, 0.55 * seam, blend="add")
        over(img, glow_field(D.W, 120, (D.W * 0.5, 566), D.W * 0.36 * seam + 2, D.TEAL, falloff=2.0, gain=0.30), 0, 506, seam, blend="add")

    # left scrim for type
    scrim(img, 1080, 760, (0, 0), (1080, 760), [(0.0, 0.86), (0.55, 0.42), (1.0, 0.0)], 0, 240)
    # couplet -> the real number
    caption(img, "谱面在滚。", 140, 300, t, 0.90, 4.95, D.PAPER, "serif", 104, 2.0, 600, rise=26)
    caption(img, "截图在追。", 140, 452, t, 2.92, 4.95, D.AMBER, "serif", 96, 2.0, 600, rise=26)
    caption(img, "37 张截图。", 140, 300, t, 5.12, 7.2, D.PAPER, "serif", 96, 2.0, 600, rise=24)
    caption(img, "0 张能用。", 140, 452, t, 5.85, 7.2, D.RED, "serif", 96, 2.0, 600, rise=24)

    # ---- capture reticle + flashes
    for tc in (4.30, 4.95, 5.60):
        p = remap(t, tc - 0.16, tc, ease_out_cubic)
        out = remap(t, tc + 0.02, tc + 0.4, ease_in_cubic)
        if 0 < p and out < 1:
            op = p * (1 - out)
            _reticle(img, 62, 738, D.W - 124, 300, op, tc, t)
        fl = pulse(t, tc - 0.042, 0.22)
        if fl > 0:
            # localised flash inside the capture area only
            flash = solid(D.W, D.H, D.WHITE)
            over(img, flash, 0, 0, fl * 0.18)
            glow = glow_field(D.W, 460, (D.W * 0.5, 230), 700, D.WHITE, falloff=1.5, gain=0.5)
            over(img, glow, 0, 740 - 230 + 60, fl * 0.7, blend="add")
            # horizontal glitch slices
            for k in range(3):
                yy = int(D.H * (0.55 + 0.14 * k)) + int(math.sin(tc * 13 + k) * 30)
                hh = 2 + k * 2
                sl = img[yy : yy + hh].copy()
                img[yy : yy + hh] = np.roll(sl, int(24 * fl), axis=1)

    # ---- stats: top-left, big and unmistakable
    if t > 4.2:
        n = 12 if t < 4.9 else (24 if t < 5.55 else 37)
        bx, bw = 140, 300
        lab = text_sprite("已截图", D.hexc("#BCC7CA"), "sans", 20, tracking=3.0)
        over(img, lab, bx, 130)
        num = text_sprite(f"{n:02d}", D.PAPER, "mono_bold", 60, tracking=1.0)
        over(img, num, bx + bw - num.w, 104)
        over(img, solid(bw, 1, D.GREY_DIM), bx, 184, 0.55)
        av = text_sprite("可用", D.hexc("#BCC7CA"), "sans", 20, tracking=3.0)
        over(img, av, bx, 206)
        z = text_sprite("00", D.RED, "mono_bold", 60, tracking=1.0)
        over(img, z, bx + bw - z.w, 180)

    # ---- polaroid pile
    _s1_polaroids(img, t)
    return _flash_cut(img, t, 7.09, 7.2)


def _reticle(img, x, y, w, h, op, tc, t):
    col = D.hexc("#EFFFFA")
    cl = 34
    th = 2.2
    for (px, py, dx, dy) in [(x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)]:
        hx = px + dx * cl
        vy = py + dy * cl
        over(img, solid(cl, th, col), min(px, hx), min(py, py + dy * th), op * 0.9, blend="add")
        over(img, solid(th, cl, col), min(px, px + dx * th), min(py, vy), op * 0.9, blend="add")
    # crosshair centre label
    lab = text_sprite("CAPTURE", D.hexc("#EFFFFA"), "mono_bold", 12, tracking=3.0)
    over(img, lab, x + 8, y - 26, op * 0.75)


def _flash_cut(img, t, t0, t1):
    """White flash used at hard cuts."""
    fl = 0.0
    if t0 <= t <= t1:
        u = (t - t0) / (t1 - t0)
        fl = math.sin(math.pi * u) ** 0.8
    if fl > 0:
        img = img * (1 - fl * 0.86) + fl * 0.86
    return img


def _player_card(t):
    key = ("pcard", round(t, 3))
    hit = _C.get(key)
    if hit is not None:
        return hit
    Wc, Hc = 1400, 788
    card = blank(Wc, Hc)
    vid_h = 452
    # video (guitar + hands, cinematic crop)
    vid = video_sprite("fuji_20.png", (0, 40, 1280, 440), Wc, vid_h)
    v = vid.rgb * np.array([0.62, 0.68, 0.70], F32)
    # teal rim light from the left
    g = glow_field(Wc, vid_h, (Wc * 0.05, vid_h * 0.55), Wc * 0.55, D.TEAL, falloff=2.2, gain=0.12)
    over(v, g, 0, 0, 1.0, blend="add")
    over(card.rgba[..., :3], from_float(np.dstack([v, np.ones((vid_h, Wc), F32)])), 0, 0)

    # tab window
    tab_top = vid_h
    chrome_h = 46
    tab_h = Hc - vid_h - chrome_h
    tex = tab_strip_texture(width=Wc, n=16)
    off = int((t * 780) % max(1, tex.h - tab_h - 4))
    tab = tex.rgba[off : off + tab_h][..., :3].copy()
    tab = cv2.GaussianBlur(tab, (0, 0), 1.0, 3.6)
    tab *= np.array([0.88, 0.93, 0.94], F32)
    over(card.rgba[..., :3], from_float(np.dstack([tab, np.ones((tab_h, Wc), F32)])), 0, tab_top)
    # detection frame over tab region
    bx, by, bw2, bh2 = 26, tab_top + 16, Wc - 52, tab_h - 32
    border = rounded_border(bw2, bh2, 8, 1.6, D.TEAL_DEEP, opacity=0.75)
    over(card.rgba[..., :3], border, bx, by)
    # corner brackets
    cl = 22
    for (px, py, dx, dy) in [(bx, by, 1, 1), (bx + bw2, by, -1, 1), (bx, by + bh2, 1, -1), (bx + bw2, by + bh2, -1, -1)]:
        lm = line_mask(cl + 8, cl + 8, (4, 4 + (cl if dy > 0 else 0)), (4 + (cl if dx > 0 else 0), 4), 2.4, ss=3)
        if dx < 0 or dy < 0:
            lm = line_mask(cl + 8, cl + 8, (cl + 4, 4 if dy < 0 else 4), (4 if dx < 0 else 4, 4 + (cl if dy < 0 else 0)), 2.4, ss=3)
        over(card.rgba[..., :3], mask_to_sprite(lm, D.TEAL_DEEP), px - 4, py - 4)
    # scan line inside tab
    sp = ((t * 0.55) % 1.0)
    ly = int(by + sp * bh2)
    scan = glow_field(Wc, 120, (Wc * 0.5, 60), Wc * 0.7, D.TEAL, falloff=1.7, gain=0.25)
    over(card.rgba[..., :3], scan, 0, ly - 60, 1.0, blend="add")
    over(card.rgba[..., :3], mask_to_sprite(rect_mask(Wc, 1), D.TEAL), 0, ly, 0.5, blend="add")

    # chrome
    chrome = np.zeros((chrome_h, Wc, 3), F32) + np.array([0.045, 0.05, 0.052], F32)
    over(card.rgba[..., :3], from_float(np.dstack([chrome, np.ones((chrome_h, Wc), F32)])), 0, Hc - chrome_h)
    # progress
    p = clamp((t - 1.9) * 0.045, 0, 0.42)
    over(card.rgba[..., :3], solid(Wc - 64, 3, D.hexc("#2A3234")), 32, Hc - 24)
    fw = int((Wc - 64) * p)
    if fw > 2:
        over(card.rgba[..., :3], solid(fw, 3, D.TEAL), 32, Hc - 24)
        over(card.rgba[..., :3], ellipse_sprite(9, 9, D.TEAL), 32 + fw - 4, Hc - 27)
    tc = text_sprite("02:14 / 06:38", D.GREY, "mono", 13, tracking=1.0)
    over(card.rgba[..., :3], tc, Wc - 32 - tc.w, Hc - 34)
    # top fade inside video
    scrim(card.rgba[..., :3], Wc, 180, (0, 0), (0, 180), [(0.0, 0.85), (1.0, 0.0)], 0, 0)
    # glass reflection
    refl = gradient_sprite(Wc, 240, [(0, D.WHITE * 1.4), (1, np.zeros(3, F32))], (0, 0), (Wc * 0.7, 240))
    over(card.rgba[..., :3], refl, 0, 0, 0.05, blend="add")
    # rounded
    mask = rounded_rect_mask(Wc, Hc, 16, 4)
    card.rgba[..., :3] *= mask[..., None]
    card.rgba[..., 3:4] = mask[..., None]
    if len(_C) < 260:
        _C[key] = card
    return card


_FRAGS = None


def _fragments():
    global _FRAGS
    if _FRAGS is not None:
        return _FRAGS
    rng = np.random.default_rng(42)
    rows = [r for r in pages.tab_rows() if r.shape[0] > 120]
    frags = []
    t0s = [4.30, 4.90, 5.50]
    for gi, t0 in enumerate(t0s):
        for k in range(5):
            row = rows[(gi * 5 + k) % len(rows)]
            h, w = row.shape[:2]
            cw = min(w, int(rng.integers(380, 560)))
            x0 = int(rng.integers(0, max(1, w - cw)))
            ch = min(h, int(cw * rng.uniform(0.38, 0.52)))
            y0 = int(rng.integers(0, max(1, h - ch)))
            crop = row[y0 : y0 + ch, x0 : x0 + cw]
            spr = from_float(np.dstack([np.clip(crop * 0.96, 0, 1), np.ones(crop.shape[:2], F32)]))
            pad = 11
            frame = blank(cw + pad * 2, ch + pad * 2)
            over_sprite(frame, spr, pad, pad)
            # soft shadow baked as border
            over_sprite(frame, rounded_border(cw + pad * 2, ch + pad * 2, 3, 1, D.INK_SOFT, opacity=0.25))
            for (mx, my, dx, dy) in [
                (0, 0, 1, 1),
                (cw + pad * 2, 0, -1, 1),
                (0, ch + pad * 2, 1, -1),
                (cw + pad * 2, ch + pad * 2, -1, -1),
            ]:
                lm = line_mask(20, 20, (10 - 8 * dx, 10 - 8 * dy), (10 + 8 * dx, 10 + 8 * dy), 1.5, ss=3)
                over_sprite(frame, mask_to_sprite(lm, D.INK_SOFT), mx - 10, my - 10)
            frags.append(
                {
                    "spr": frame,
                    "t0": t0,
                    "sx": float(rng.uniform(0.12, 0.9)),
                    "sy": float(rng.uniform(0.18, 0.62)),
                    "scale": float(rng.uniform(0.42, 0.66)),
                    "rot": float(rng.uniform(-8, 8)),
                    "delay": float(rng.uniform(0, 0.10)),
                    "phase": float(rng.uniform(0, 6.28)),
                }
            )
    _FRAGS = frags
    return frags


def _s1_fragments(img, t):
    if t < 4.3:
        return
    for f in _fragments():
        dt = t - f["t0"] - f["delay"]
        if dt < 0:
            continue
        p = remap(dt, 0, 0.5, ease_out_cubic)
        start = (960, 300)
        end = (f["sx"] * 1700 + 110, 120 + f["sy"] * 700)
        x = lerp(start[0], end[0], p) + math.sin(t * 1.2 + f["phase"]) * 7
        y = lerp(start[1], end[1], p) + math.cos(t * 1.0 + f["phase"]) * 7
        a = remap(t, 5.6, 6.4, ease_in_cubic)
        sc = f["scale"] * (0.55 + 0.45 * p) * (1 + a * 1.1)
        op = (1 - a) * p
        if op <= 0.01:
            continue
        ang = f["rot"] * p + a * 14
        s2, _, _ = affine_sprite(f["spr"], 0, 0, sc, ang)
        sh = shadow(s2, 16, 0.22)
        over(img, sh, x - s2.w / 2 + 6, y - s2.h / 2 + 9, op)
        over(img, s2, x - s2.w / 2, y - s2.h / 2, op)


# --------------------------------------------------------------------------- #
# S1 polaroid pile
# --------------------------------------------------------------------------- #

_POLAS = None


def _polaroids():
    global _POLAS
    if _POLAS is not None:
        return _POLAS
    rng = np.random.default_rng(17)
    rows = [r for r in pages.tab_rows() if 120 < r.shape[0] < 520]
    groups = [4.30, 4.95, 5.60]
    polas = []
    for gi, t0 in enumerate(groups):
        for k in range(5):
            row = rows[(gi * 5 + k * 3) % len(rows)].astype(F32) / 255.0
            h, w = row.shape[:2]
            cw = 470
            ch = min(h, 250)
            x0 = int(rng.integers(0, max(1, w - cw)))
            y0 = int(rng.integers(0, max(1, h - ch)))
            crop = row[y0 : y0 + ch, x0 : x0 + cw]
            pad = 14
            cw2, ch2 = cw + 2 * pad, ch + 2 * pad + 30
            # build on an opaque RGB canvas (a print with a paper border + tab crop)
            canvas = np.zeros((ch2, cw2, 3), F32) + np.array([0.965, 0.955, 0.93], F32)
            canvas[pad : pad + ch, pad : pad + cw] = np.clip(crop * 1.02, 0, 1)
            over(canvas, rounded_border(cw2, ch2, 4, 1, D.INK_SOFT, opacity=0.35), 0, 0)
            tick = text_sprite("CAPTURED", D.TEAL_DEEP, "mono_bold", 11, tracking=2.0)
            over(canvas, tick, cw2 - pad - tick.w, ch2 - 26)
            over(canvas, ellipse_sprite(6, 6, D.TEAL_DEEP), pad, ch2 - 24)
            alpha = rounded_rect_mask(cw2, ch2, 5, 3)
            card = Sprite(np.dstack([canvas * alpha[..., None], alpha]))
            polas.append(
                {
                    "spr": card,
                    "t0": t0,
                    "delay": float(rng.uniform(0, 0.14)),
                    "x": float(rng.uniform(1080, 1690)),
                    "y": float(rng.uniform(600, 900)),
                    "rot": float(rng.uniform(-22, 22)),
                    "scale": float(rng.uniform(0.58, 0.86)),
                }
            )
    _POLAS = polas
    return polas


def _s1_polaroids(img, t):
    placed = []
    for i, f in enumerate(_polaroids()):
        dt = t - f["t0"] - f["delay"]
        if dt < 0:
            continue
        p = remap(dt, 0, 0.42, spring)
        op = remap(dt, 0, 0.16, ease_out_cubic)
        dy = (1 - p) * -70
        sc = f["scale"] * (1.14 - 0.14 * p)
        rot = f["rot"] * (0.5 + 0.5 * p)
        s2, _, _ = affine_sprite(f["spr"], 0, 0, sc, rot, shear=(0.14 * math.sin(f["rot"]), 0.0))
        placed.append((s2, f["x"] - s2.w / 2, f["y"] - s2.h / 2 + dy, op))
    sh_all = blank(D.W, D.H)
    for s2, x, y, op in placed:
        over_sprite(sh_all, shadow(s2, 24, 0.18).with_opacity(op), x + 9, y + 16)
    over(img, sh_all, 0, 0, 1.0)
    for s2, x, y, op in placed:
        over(img, s2, x, y, op)


# --------------------------------------------------------------------------- #
# S2 — input (7.2 - 14.4)
# --------------------------------------------------------------------------- #

URL = "bilibili.com/video/BV19f421Q76h"
LOGS = ["下载视频  100%", "抽取帧  386 张", "检测谱面区域", "识别谱行  48 行"]

_UI_W, _UI_H = 1280, 740
_UI_M = 68
_UI_FIELD_Y = 202
_UI_BTN_Y = 438

# screen placement of the window (before the end push-in)
WIN_X, WIN_Y = 500, 150


def _ui_base():
    key = ("uibase",)
    if key in _C:
        return _C[key]
    w, h, m = _UI_W, _UI_H, _UI_M
    win = blank(w, h)
    base = np.zeros((h, w, 3), F32) + D.UI_BG
    over(win.rgba[..., :3], from_float(np.dstack([base, np.ones((h, w), F32)])), 0, 0)

    title = text_sprite("视频扒谱工具", D.UI_TEXT, "sans_bold", 38, tracking=1.2)
    over(win.rgba[..., :3], title, m, 32)
    sub = text_sprite("B站教学视频  →  完整吉他谱  /  A4 PDF", D.INK_SOFT, "sans", 18, tracking=1.8)
    over(win.rgba[..., :3], sub, m, 84)
    over(win.rgba[..., :3], ellipse_sprite(10, 10, D.GREEN), w - m - 110, 44)
    st = text_sprite("就绪", D.INK_SOFT, "sans", 16, tracking=1.4)
    over(win.rgba[..., :3], st, w - m - 92, 37)
    over(win.rgba[..., :3], solid(w - 2 * m, 1, D.UI_LINE), m, 130)

    lbl = text_sprite("B站视频链接", D.INK_SOFT, "sans", 19, tracking=2.4)
    over(win.rgba[..., :3], lbl, m, 164)
    fw, fh = w - 2 * m, 86
    over(win.rgba[..., :3], rounded_rect(fw, fh, 15, D.UI_PANEL), m, _UI_FIELD_Y)
    over(win.rgba[..., :3], rounded_border(fw, fh, 15, 1.5, D.UI_LINE), m, _UI_FIELD_Y)

    lbl2 = text_sprite("输出标题（可选）", D.INK_SOFT, "sans", 19, tracking=2.4)
    over(win.rgba[..., :3], lbl2, m, 322)
    over(win.rgba[..., :3], rounded_rect(fw, 66, 13, D.UI_PANEL), m, 358)
    over(win.rgba[..., :3], rounded_border(fw, 66, 13, 1.3, D.UI_LINE), m, 358)
    ph = text_sprite("留空自动用视频标题", D.GREY_DIM, "sans", 20, tracking=1.2)
    over(win.rgba[..., :3], ph, m + 26, 376)

    # pipeline stepper (fills the lower half, explains the product)
    sy = 540
    over(win.rgba[..., :3], solid(w - 2 * m, 1, D.UI_LINE), m, sy - 28, 0.8)
    steps = ["下载视频", "抽取帧", "检测谱行", "去重排序", "输出 PDF"]
    xs = [m + 4 + i * 224 for i in range(len(steps))]
    over(win.rgba[..., :3], solid(xs[-1] - xs[0] - 40, 1, D.UI_LINE), xs[0], sy + 12, 0.9)
    for i, s in enumerate(steps):
        teal = i in (0, 1, 2)
        over(win.rgba[..., :3], ellipse_sprite(13, 13, D.TEAL_DEEP if teal else D.UI_LINE), xs[i], sy + 6)
        cap = text_sprite(s, D.UI_TEXT if teal else D.GREY_DIM, "sans", 17, tracking=0.8)
        over(win.rgba[..., :3], cap, xs[i], sy + 32)

    hint = text_sprite("本地处理 · 不上传视频 · 可随时中断", D.GREY_DIM, "sans", 16, tracking=1.2)
    over(win.rgba[..., :3], hint, m, h - 62)
    over(win.rgba[..., :3], solid(w, 1, D.WHITE), 0, 0, 0.8)
    mask = rounded_rect_mask(w, h, 18, 4)
    win.rgba[..., :3] *= mask[..., None]
    win.rgba[..., 3:4] = mask[..., None]
    _C[key] = win
    return win


def _draw_options(base, t, alpha):
    w, m = _UI_W, _UI_M
    if alpha <= 0.01:
        return
    for i, (k, v) in enumerate([("抽帧间隔", "2.0 s"), ("分辨率", "原始"), ("核验", "开启")]):
        bx = m + i * 270
        over(base, rounded_rect(244, 60, 10, D.UI_PANEL, opacity=alpha), bx, _UI_BTN_Y + 4)
        over(base, rounded_border(244, 60, 10, 1.2, D.UI_LINE, opacity=alpha), bx, _UI_BTN_Y + 4)
        kt = text_sprite(k, D.INK_SOFT, "sans", 17, tracking=1.4)
        over(base, kt.with_opacity(alpha), bx + 20, _UI_BTN_Y + 22)
        vt = text_sprite(v, D.UI_TEXT, "sans", 18, tracking=0.6)
        over(base, vt.with_opacity(alpha), bx + 244 - 20 - vt.w, _UI_BTN_Y + 20)
    bw, bh = 258, 86
    bx, by = w - m - bw, _UI_BTN_Y - 6
    press = remap(t, 9.90, 9.97, ease_out_cubic) * (1 - remap(t, 10.05, 10.40, ease_out_cubic))
    sc = 1 - 0.025 * press
    bw2, bh2 = int(bw * sc), int(bh * sc)
    over(base, rounded_rect(bw2, bh2, 16, D.TEAL_DEEP, opacity=alpha), bx + (bw - bw2) / 2, by + (bh - bh2) / 2)
    bt = text_sprite("开始处理", D.WHITE, "sans_bold", 27, tracking=2.6)
    over(base, bt.with_opacity(alpha), bx + (bw - bt.w) / 2, by + (bh - bt.h) / 2 - 4)


def _ui_window(t):
    win = _ui_base().copy()
    w, h, m = _UI_W, _UI_H, _UI_M
    base = win.rgba[..., :3]

    # typed url
    n = int(clamp((t - 7.95) / 1.05) * len(URL))
    typed = URL[:n]
    fx, fy = m + 28, _UI_FIELD_Y + 26
    if typed:
        over(base, text_sprite(typed, D.UI_TEXT, "mono", 30, tracking=0.4), fx, fy)
    caret_x = fx + (measure_text(typed, "mono", 30, 0.4) if typed else 0)
    typing = 7.95 <= t <= 9.18
    if typing or (int(t * 2.2) % 2 == 0):
        over(base, solid(2, 34, D.UI_TEXT), caret_x + 3, fy + 2, 0.95 if typing else 0.5)

    # processing panel replaces the options row
    pa = remap(t, 10.42, 11.0, ease_out_cubic)
    _draw_options(base, t, 1 - pa)
    if pa > 0:
        over(base, solid(w - 2 * m, 232, D.UI_BG), m, 430, pa)
        yy = _UI_BTN_Y + 8
        over(base, rounded_rect(w - 2 * m, 10, 5, D.hexc("#DCD4C6"), opacity=pa), m, yy + 40)
        prog = clamp((t - 10.7) / 3.0) * 0.62
        fw2 = int((w - 2 * m) * prog)
        if fw2 > 4:
            over(base, rounded_rect(fw2, 10, 5, D.TEAL_DEEP, opacity=pa), m, yy + 40)
        pc = text_sprite(f"{int(prog*100):02d}%", D.UI_TEXT, "mono_bold", 22, tracking=1.0)
        over(base, pc.with_opacity(pa), m, yy - 2)
        status = text_sprite("正在检测谱面区域…", D.INK_SOFT, "sans", 20, tracking=1.4)
        over(base, status.with_opacity(pa), m + 84, yy - 3)
        for i, lab in enumerate(LOGS):
            lt = 10.9 + i * 0.55
            lp = remap(t, lt, lt + 0.4, ease_out_cubic) * pa
            if lp <= 0:
                continue
            ly = yy + 86 + i * 38
            over(base, ellipse_sprite(8, 8, D.TEAL_DEEP), m + 4, ly + 8, lp)
            ls = text_sprite(lab, D.UI_TEXT, "sans", 21, tracking=0.8)
            over(base, ls.with_opacity(lp), m + 28, ly)
            if i == 0:
                done = text_sprite("完成", D.GREEN, "sans", 14, tracking=1.0)
                over(base, done.with_opacity(lp * 0.9), m + 28 + ls.w + 14, ly + 4)

    # cursor + ripple (hidden once the click happens)
    bw, bh = 258, 86
    bx, by = w - m - bw, _UI_BTN_Y - 6
    tgt = (bx + bw * 0.52, by + bh * 0.58)
    p = remap(t, 9.12, 9.84, ease_in_out_cubic)
    cur = cursor_sprite(1.05)
    cur_x = lerp(1160, tgt[0], p)
    cur_y = lerp(760, tgt[1], p)
    if t < 9.96:
        over(base, cur, cur_x, cur_y, 0.98)
    for k in range(2):
        pr = remap(t, 9.94 + k * 0.13, 10.85 + k * 0.13, ease_out_cubic)
        if 0.02 < pr < 1:
            r = int(26 + pr * 320)
            over(base, mask_to_sprite(ring_mask(r * 2, 2.8), D.TEAL_DEEP), bx + bw / 2 - r, by + bh / 2 - r, (1 - pr) * 0.42)
    return win


def scene2(t):
    img = studio_bg("dark").copy()
    dust(img, t, gain=0.5)
    key = glow_field(D.W, D.H, (D.W * 0.62, D.H * 0.66), 1120, D.hexc("#4A2E12"), falloff=2.3, gain=0.6)
    over(img, key, 0, 0, 1.0, blend="add")

    win = _ui_window(t)
    # end push-in toward the progress bar
    push = remap(t, 13.2, 14.32, ease_in_out_cubic)
    fx, fy = _UI_M + 150, _UI_BTN_Y + 44
    breathe = 0.010 * remap(t, 7.2, 13.2, ease_in_out_cubic) + 0.0045 * math.sin((t - 7.2) * 0.9)
    scale = 1.0 + push * 0.95 + breathe
    focus_x = lerp(WIN_X + fx, 760, push)
    focus_y = lerp(WIN_Y + fy, 560, push)
    ox = focus_x - fx * scale
    oy = focus_y - fy * scale
    oy += 4.0 * math.sin((t - 7.2) * 0.62)
    ent = remap(t, 7.2, 7.62, ease_out_quint)
    oy += (1 - ent) * 50
    if ent > 0.02:
        w = int(win.w * scale)
        h = int(win.h * scale)
        win_s = win.scaled(w, h)
        sh = shadow(win_s, 92 + 30 * push, 0.34 * ent, color=np.array([0, 0, 0], F32))
        over(img, sh, ox + 4, oy + 54)
        sh2 = shadow(win_s, 26, 0.22 * ent, color=np.array([0, 0, 0], F32))
        over(img, sh2, ox + 2, oy + 16)
        over(img, win_s, ox, oy, ent)
        over(img, rounded_border(w, h, int(18 * scale), max(1, int(1.7 * scale)), D.WHITE, opacity=0.32), ox, oy, ent)
    # slow screen-reflection sweep
    sw = ((t - 7.2) / 2.6) % 1.0
    if t > 7.4:
        band = gradient_sprite(360, D.H, [(0.0, np.zeros(3, F32)), (0.5, D.WHITE), (1.0, np.zeros(3, F32))], (0, 0), (360, 0))
        bx = int(-360 + (D.W + 720) * sw)
        over(img, band, bx, 0, 0.035)
    # captions (left column)
    caption(img, "粘贴链接，", 140, 300, t, 7.55, 9.55, D.PAPER, "serif", 58, 1.0, 600, rise=18, dur=0.5)
    caption(img, "点一下。", 140, 386, t, 9.85, 12.05, D.PAPER, "serif", 58, 1.0, 600, rise=18, dur=0.5)
    caption(img, "剩下的，", 140, 660, t, 12.25, 13.55, D.TEAL, "serif", 46, 1.0, 600, rise=16, dur=0.5)
    caption(img, "交给它。", 140, 722, t, 12.52, 13.55, D.TEAL, "serif", 46, 1.0, 600, rise=16, dur=0.5)
    if t > 7.4:
        p = remap(t, 7.4, 8.0, ease_out_cubic)
        lab = text_sprite("01 / 输入", D.GREY, "sans", 17, tracking=4.0)
        over(img, lab.with_opacity(0.8 * p * (1 - push)), 140, 214)
    # teal band wipes up into S3
    band = remap(t, 14.02, 14.36, ease_in_cubic)
    if band > 0:
        yc = focus_y
        hh = max(2, int((band ** 2.2) * D.H * 1.3))
        over(img, solid(D.W, hh, D.TEAL), 0, int(yc - hh / 2), 1.0)
        if hh > 4:
            over(img, glow_field(D.W, min(D.H, hh + 200), (D.W * 0.5, min(D.H, hh + 200) / 2), D.W * 0.7, D.TEAL, falloff=1.4, gain=0.5), 0, int(yc - (hh + 200) / 2), 0.9, blend="add")
        if band > 0.75:
            u = (band - 0.75) / 0.25
            img = img * (1 - u * 0.95) + u * 0.95
    return img


# --------------------------------------------------------------------------- #
# stubs for S3-S6 (implemented below, kept separate for iteration)
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# S3 — extraction (14.4 - 26.4)
# --------------------------------------------------------------------------- #

_S3 = {}


def _s3_rows():
    """Real tab rows scaled for the stack, paper-tinted."""
    if "rows" in _S3:
        return _S3["rows"]
    src = pages.tab_rows()
    idx = [0, 4, 9, 14, 19, 24, 29, 34]
    out = []
    w = 470
    for i in idx:
        im = src[i % len(src)].astype(F32) / 255.0
        ih, iw = im.shape[:2]
        im = im[:, int(iw * 0.012) : int(iw * 0.985)]
        h = max(18, int(round(im.shape[0] * w / im.shape[1])))
        r = cv2.resize(im, (w, h), interpolation=cv2.INTER_AREA)
        rgb = np.clip(r * np.array([0.955, 0.945, 0.915], F32), 0, 1)
        spr = from_float(np.dstack([rgb, np.ones((h, w), F32)]))
        mask = rounded_rect_mask(w, h, 3, 3)
        spr.rgba[..., :3] *= mask[..., None]
        spr.rgba[..., 3:4] = mask[..., None]
        out.append({"spr": spr, "h": h, "dup": i in (9, 24), "idx": len(out)})
    _S3["rows"] = out
    return out


def _row_stack_layout(rows, collapse=0.0):
    gap = 13
    y = 0.0
    layout = []
    for r in rows:
        layout.append(y)
        appear = r["h"] + gap
        y += appear * (1 - collapse) if r["dup"] else appear
    return layout, y - gap


def _s3_video_card(t):
    """Source video card with depth ghosts + scan line."""
    key = ("s3vid",)
    vw, vh = 720, 405
    if key in _C:
        return _C[key]
    v = video_sprite("bv19f_20.png", (0, 0, 1920, 1080), vw, vh).rgb.copy()
    lum = v @ np.array([0.2126, 0.7152, 0.0722], F32)
    v = lum[..., None] + (v - lum[..., None]) * 0.45
    v = np.clip(v * np.array([0.50, 0.57, 0.61], F32), 0, 1)
    v = np.clip((v - 0.06) * 1.25, 0, 1)
    spr = from_float(np.dstack([v, np.ones((vh, vw), F32)]))
    m = rounded_rect_mask(vw, vh, 8, 3)
    spr.rgba[..., :3] *= m[..., None]
    spr.rgba[..., 3:4] = m[..., None]
    _C[key] = spr
    return spr


def scene3(t):
    img = studio_bg("cold").copy()
    dust(img, t, gain=0.8)

    # entrance: teal band from S2 shrinks to a line
    ent = remap(t, 14.38, 14.98, ease_out_cubic)
    if ent < 1:
        hh = max(2, int((1 - ent) ** 1.6 * D.H * 1.25))
        band = gradient_sprite(D.W, hh, [(0, D.hexc("#0B4A40")), (0.5, D.TEAL), (1, D.hexc("#0B4A40"))], (0, 0), (0, hh))
        over(img, band, 0, int(560 - hh / 2), 1.0)
        if ent > 0.3:
            over(img, solid(D.W, 2, D.TEAL), 0, 560, (1 - ent) * 0.9, blend="add")

    # ---------------- backdrop: sampled frames + stack glow ----------------
    sg = glow_field(D.W, D.H, (1300, 520), 620, D.hexc("#0E4B41"), falloff=2.6, gain=0.55)
    over(img, sg, 0, 0, 1.0, blend="add")
    # ---------------- source card (left) ----------------
    cam = remap(t, 14.8, 26.2, ease_in_out_cubic)
    vx, vy = 430, 356 - 10 * cam
    vw, vh = 720, 405
    tilt = -7 + 3 * cam
    # ghost frames behind (sampled moments)
    for k, (gdx, gdy, gsc, ga) in enumerate([(30, 40, 0.955, 0.22), (15, 20, 0.978, 0.30)]):
        gq = pages.page_quad(vx + gdx, vy + gdy, vw * gsc, vh * gsc, rx=6, ry=tilt, rz=-2)
        ghost = rounded_rect(int(vw * gsc), int(vh * gsc), 10, np.array([0.06, 0.10, 0.11], F32), opacity=ga)
        ghost = blur(ghost, 18)
        blit_perspective(img, ghost, gq)
    vid = _s3_video_card(t)
    vq = pages.page_quad(vx, vy, vw, vh, rx=6, ry=tilt, rz=-2)
    blit_perspective(img, shadow(vid, 42, 0.72), vq + np.array([0, 22], F32))
    blit_perspective(img, vid, vq)
    # teal edge + scan line
    blit_perspective(img, rounded_border(vw, vh, 8, 2, D.hexc("#2FE3B8"), opacity=0.20), vq)
    sp = remap(t, 14.9, 16.9, ease_in_out_cubic)
    if 0 < sp < 1:
        ly = int(vy - vh / 2 + sp * vh)
        over(img, glow_field(int(vw + 120), 170, ((vw + 120) * 0.5, 85), vh * 0.75, D.TEAL, falloff=1.7, gain=0.42),
             int(vx - vw / 2 - 60), ly - 85, 0.75, blend="add")
        over(img, solid(int(vw), 2, D.TEAL), int(vx - vw / 2), ly, 0.5, blend="add")
    # label
    if t > 14.9:
        p = remap(t, 14.9, 15.5, ease_out_cubic)
        lab = text_sprite("SOURCE  ·  BILIBILI TUTORIAL", D.GREY, "sans", 14, tracking=3.6)
        over(img, lab.with_opacity(0.55 * p), 150, 112)

    # ---------------- rows fly into the stack ----------------
    rows = _s3_rows()
    collapse = remap(t, 20.95, 21.75, ease_in_out_cubic)
    layout, total_h = _row_stack_layout(rows, collapse)
    stack_x = 1300
    stack_top = 172
    page_fade = remap(t, 23.55, 24.45, ease_in_out_cubic)
    for i, r in enumerate(rows):
        t_in = 15.25 + i * 0.30
        p = remap(t, t_in, t_in + 0.82, ease_out_cubic)
        if p <= 0:
            continue
        target_x = stack_x - r["spr"].w / 2
        target_y = stack_top + layout[i]
        sx, sy = vx + 90, vy + 80
        arc = math.sin(math.pi * p) * (90 + 34 * (i % 4))
        x = lerp(sx, target_x, p)
        y = lerp(sy, target_y, p) - arc
        rot = (1 - p) * (18 - (i % 5) * 9)
        sc = 0.66 + 0.34 * p
        dup_die = remap(t, 20.15, 20.95, ease_in_cubic) if r["dup"] else 0.0
        op = min(1.0, p * 2.6) * (1 - page_fade) * (1 - dup_die)
        if op <= 0.01:
            continue
        s2, _, _ = affine_sprite(r["spr"], 0, 0, sc, rot)
        px = x + (s2.w - r["spr"].w * sc) / 2
        py = y + (s2.h - r["spr"].h * sc) / 2
        over(img, shadow(s2, 13, 0.42), px + 4, py + 6, op * 0.85)
        over(img, glow(s2, 18, 0.07, D.hexc("#CFEFE6")), px, py, op, blend="add")
        over(img, s2, px, py, op)
        if r["dup"] and dup_die < 0.5:
            pulse_a = 0.5 + 0.5 * math.sin(t * 7.0 + i)
            over(img, solid(4, s2.h, D.AMBER), px - 16, py, op * pulse_a * (1 - dup_die))
            lab = text_sprite("重复", D.AMBER, "sans", 15, tracking=2.0)
            over(img, lab.with_opacity(op * 0.9), px - 16 - lab.w - 12, py + s2.h / 2 - lab.h / 2)
        if t > 22.2:
            hit = remap(t, 22.2 + i * 0.05, 22.4 + i * 0.05, ease_out_cubic) * (1 - page_fade)
            if hit > 0.01:
                cy = py + s2.h / 2
                over(img, solid(2, 15, D.TEAL), px + s2.w + 16, cy - 8, hit * 0.9, blend="add")
                over(img, solid(11, 2, D.TEAL), px + s2.w + 16, cy + 5, hit * 0.9, blend="add")
    # ai sweep band
    sw = remap(t, 22.05, 23.2, ease_in_out_cubic)
    if 0 < sw < 1:
        sy2 = stack_top + sw * total_h
        over(img, glow_field(D.W, 160, (D.W * 0.5, 80), 760, D.TEAL, falloff=1.9, gain=0.38), 0, sy2 - 80, 0.9, blend="add")
        over(img, solid(700, 2, D.TEAL), stack_x - 350, sy2, 0.55, blend="add")

    # ---------------- page ----------------
    if t > 23.55:
        page = pages.build_page([0, 4, 9, 15, 21], "Paranoid", "Black Sabbath · 吉他谱", 1, 8)
        pw = 560
        ph = int(page.h * pw / page.w)
        pg = page.scaled(pw, ph)
        pp = remap(t, 23.55, 24.55, ease_out_cubic)
        cx, cy = stack_x, stack_top + total_h / 2
        push2 = remap(t, 24.85, 26.35, ease_in_cubic)
        sc2 = 1 + push2 * 1.6
        cx = lerp(cx, D.W * 0.40, push2)
        cy = lerp(cy, D.H * 0.48, push2)
        w2, h2 = int(pg.w * sc2), int(pg.h * sc2)
        pg2 = pg.scaled(w2, h2)
        over(img, shadow(pg2, 46 + push2 * 46, 0.68, color=np.array([0, 0, 0], F32)), cx - w2 / 2 + 12, cy - h2 / 2 + 28, pp)
        over(img, pg2, cx - w2 / 2, cy - h2 / 2, pp)
        over(img, glow(pg2, 44, 0.09, D.PAPER), cx - w2 / 2, cy - h2 / 2, pp, blend="add")

    # ---------------- HUD: 2 x 2 data block (bottom left) ----------------
    hud = [
        (15.05, 150, 736, "FRAMES / 帧", "386", "", D.PAPER),
        (17.30, 470, 736, "TAB ROWS / 行", "+48", "", D.PAPER),
        (20.60, 150, 858, "DUPLICATES / 重复", "−12", "", D.AMBER),
        (24.10, 470, 858, "PAGES / 页", "8", " A4", D.TEAL),
    ]
    for (t_in, hx, hy, lab_en, val, suf, col) in hud:
        p = remap(t, t_in, t_in + 0.45, ease_out_cubic)
        if p <= 0:
            continue
        lab = text_sprite(lab_en, D.GREY, "sans", 15, tracking=3.2)
        over(img, lab.with_opacity(0.5 * p), hx, hy)
        v = text_sprite(val, col, "mono_bold", 64, tracking=1.5)
        over(img, v.with_opacity(p), hx - 2, hy + 20)
        if suf:
            sf = text_sprite(suf, D.GREY, "sans", 18, tracking=1.6)
            over(img, sf.with_opacity(0.7 * p), hx + v.w + 6, hy + 72)
    # section label
    if t > 14.8:
        p = remap(t, 14.8, 15.4, ease_out_cubic)
        lab = text_sprite("02 / 抽取", D.GREY, "sans", 17, tracking=4.0)
        over(img, lab.with_opacity(0.8 * p * (1 - remap(t, 25.5, 26.1, ease_in_out_cubic))), 150, 146)
    # human commentary (the section must not be 13 s of silence)
    for t_in, t_out, line in [
        (15.55, 17.05, "386 帧里，"),
        (17.15, 20.35, "挑出 48 行谱。"),
        (20.55, 23.95, "12 行重复，自动去掉。"),
        (24.15, 26.2, "拼成一整份。"),
    ]:
        caption(img, line, 148, 604, t, t_in, t_out, D.PAPER, "serif", 46, 1.5, 600, rise=16, dur=0.45)
    return _flash_cut(img, t, 26.22, 26.4)


# --------------------------------------------------------------------------- #
# S4 — review UI (26.4 - 36.0)
# --------------------------------------------------------------------------- #

_RV_W, _RV_H = 1280, 720
_RV_M = 56
_RV_X, _RV_Y = 500, 168


def _rv_thumb(i):
    key = ("rvthumb", i)
    if key in _S3:
        return _S3[key]
    src = pages.tab_rows()
    im = src[[1, 5, 9, 14, 19, 23, 28, 32][i % 8] % len(src)].astype(F32) / 255.0
    w = 250
    h = max(26, int(round(im.shape[0] * w / im.shape[1])))
    r = cv2.resize(im, (w, h), interpolation=cv2.INTER_AREA)
    r = np.clip(r * 0.80, 0, 1)
    spr = from_float(np.dstack([r, np.ones((h, w), F32)]))
    _S3[key] = spr
    return spr


_RV_PREVIEW = None


def _rv_preview(i=2):
    global _RV_PREVIEW
    key = ("rvprev", i)
    if key in _S3:
        return _S3[key]
    src = pages.tab_rows()
    im = src[[1, 5, 9, 14, 19, 23, 28, 32][i % 8] % len(src)].astype(F32) / 255.0
    w = 330
    h = int(round(im.shape[0] * w / im.shape[1]))
    r = cv2.resize(im, (w, h), interpolation=cv2.INTER_AREA)
    r = np.clip(r * 0.86, 0, 1)
    spr = from_float(np.dstack([r, np.ones((h, w), F32)]))
    _S3[key] = spr
    return spr


def _review_window(t):
    w, h, m = _RV_W, _RV_H, _RV_M
    win = blank(w, h)
    B = win.rgba[..., :3]
    base = np.zeros((h, w, 3), F32) + D.UI_BG
    over(B, from_float(np.dstack([base, np.ones((h, w), F32)])), 0, 0)

    # ---------- header
    title = text_sprite("核验  ·  Paranoid", D.UI_TEXT, "sans_bold", 32, tracking=1.0)
    over(B, title, m, 26)
    sub = text_sprite("36 行谱面  ·  6 组疑似重复  ·  拖拽排序 / 双击放大", D.INK_SOFT, "sans", 16, tracking=1.2)
    over(B, sub, m, 68)
    for i, lab in enumerate(["撤销", "重做"]):
        bx = w - m - (2 - i) * 90
        over(B, rounded_border(78, 34, 9, 1.2, D.UI_LINE), bx, 38)
        lt = text_sprite(lab, D.GREY_DIM, "sans", 14, tracking=1.0)
        over(B, lt, bx + (78 - lt.w) / 2, 46)

    # ---------- nav blocks
    over(B, solid(w - 2 * m, 1, D.UI_LINE), m, 110, 0.8)
    rng = np.random.default_rng(4)
    ai = remap(t, 30.8, 31.7, ease_in_out_cubic)
    for i in range(30):
        col = 15
        bx = m + (i % 15) * (col + 5)
        by = 124 + (i // 15) * (col + 5)
        r = rng.random()
        c = D.GREEN if r > 0.2 else (D.AMBER if r > 0.06 else D.RED)
        c = mixc(c, D.GREEN, clamp(ai * 1.5 - i * 0.02))
        over(B, rounded_rect(col, col, 4, c, opacity=0.9), bx, by)
    lab = text_sprite("导航", D.INK_SOFT, "sans", 13, tracking=2.0)
    over(B, lab, m + 15 * 20 + 14, 130)
    cnt = text_sprite("30 块 · 点一下跳转", D.GREY_DIM, "sans", 14, tracking=1.0)
    over(B, cnt, m + 15 * 20 + 14, 150)

    # ---------- list
    keep = remap(t, 28.45, 29.10, ease_in_out_cubic)
    drag = remap(t, 29.35, 30.15, ease_in_out_cubic)
    lx, ly = m, 262
    cw, chh, gap = 764, 78, 8
    slot = chh + gap

    cards = [
        dict(id="r1", name="第 1 行", meta="1917×166 · t=0s", st="正常", thumb=0),
        dict(id="r2", name="第 2 行", meta="1917×471 · t=2s", st="正常", thumb=1),
        dict(id="r3", name="第 3 行", meta="1917×458 · t=4s", st="疑似重复", thumb=2),
        dict(id="r4", name="第 4 行", meta="1917×474 · t=6s", st="疑似重复", thumb=3),
        dict(id="r5", name="第 5 行", meta="1917×473 · t=8s", st="正常", thumb=4),
        dict(id="r6", name="第 6 行", meta="1917×262 · t=10s", st="正常", thumb=5),
    ]
    # slots per phase
    for c in cards:
        c["y"] = None
        c["op"] = 1.0
    cards[0]["y"] = 0
    cards[1]["y"] = slot
    cards[2]["y"] = slot * 2
    cards[3]["y"] = slot * 3
    cards[4]["y"] = slot * 2
    cards[5]["y"] = slot * 3
    # phase: remove duplicates 2,3 -> 4,5 rise
    cards[2]["op"] = 1 - keep
    cards[3]["op"] = 1 - keep
    cards[4]["op"] = keep
    cards[5]["op"] = keep
    # drag: swap r2 (slot1) with r5 (slot2)
    y1 = slot * (1 + drag)
    y2 = slot * (2 - drag)
    if keep > 0.01:
        cards[1]["y"] = lerp(slot, slot, 1) * 1 * (1 - drag) + y1 * drag if False else y1
        cards[4]["y"] = y2
    sel = 27.5 < t < 30.55

    for idx, c in enumerate(cards):
        if c["op"] <= 0.01:
            continue
        cy = ly + c["y"]
        if cy > ly + slot * 3.55:
            continue
        op = c["op"]
        is_dup = c["st"] == "疑似重复"
        is_sel = sel and is_dup
        over(B, rounded_rect(cw, chh, 11, D.UI_PANEL, opacity=op), lx, cy)
        over(B, rounded_border(cw, chh, 11, 1.2, D.UI_LINE, opacity=op), lx, cy)
        if is_sel:
            over(B, rounded_rect(cw, chh, 11, D.hexc("#FFF4D8"), opacity=0.92 * op), lx, cy)
            over(B, rounded_border(cw, chh, 11, 2.0, D.AMBER, opacity=op), lx, cy)
        # thumb with paper backing
        th = 52
        spr = _rv_thumb(c["thumb"])
        tw = int(spr.w * th / spr.h)
        t2 = spr.scaled(tw, th)
        over(B, rounded_rect(tw + 16, th + 12, 5, np.array([1, 1, 1], F32), opacity=op), lx + 12, cy + (chh - th) / 2 - 6)
        over(B, t2, lx + 20, cy + (chh - th) / 2, op)
        num = text_sprite(f"{idx+1:02d}", D.GREY_DIM, "mono", 14, tracking=1.0)
        over(B, num, lx + 304, cy + 18, op)
        nm = text_sprite(c["name"], D.UI_TEXT, "sans_bold", 21, tracking=0.6)
        over(B, nm, lx + 334, cy + 14, op)
        mt = text_sprite(c["meta"], D.GREY_DIM, "mono", 13, tracking=0.8)
        over(B, mt, lx + 334, cy + 44, op)
        if is_dup:
            chip = text_sprite("疑似重复", D.hexc("#7A5A12"), "sans", 13, tracking=1.0)
            over(B, rounded_rect(chip.w + 22, 26, 7, D.AMBER, opacity=0.4 * op), lx + cw - 142, cy + 26)
            over(B, chip, lx + cw - 131, cy + 29, op)
        else:
            chip = text_sprite("正常", D.hexc("#1F6B45"), "sans", 13, tracking=1.0)
            over(B, rounded_rect(chip.w + 22, 26, 7, D.GREEN, opacity=0.28 * op), lx + cw - 100, cy + 26)
            over(B, chip, lx + cw - 89, cy + 29, op)

    # ---------- floating bar
    fb = remap(t, 27.55, 28.1, ease_out_cubic)
    if fb > 0 and t < 30.35:
        bw = 690
        bx = lx + (cw - bw) / 2
        by = 206
        over(B, rounded_rect(bw, 46, 12, D.hexc("#1C2022"), opacity=0.95 * fb), bx, by)
        msg = text_sprite("已选 2 行  ·  疑似重复", D.hexc("#F1F4F4"), "sans", 15, tracking=1.0)
        over(B, msg.with_opacity(fb), bx + 20, by + 13)
        for j, lab in enumerate(["保留第一个", "删除选中"]):
            pw = 118
            px = bx + bw - 20 - (2 - j) * (pw + 8)
            over(B, rounded_rect(pw, 32, 9, D.hexc("#2E3A3D") if j == 0 else D.hexc("#3D2C2C"), opacity=fb), px, by + 7)
            lt = text_sprite(lab, D.WHITE, "sans", 14, tracking=0.6)
            over(B, lt.with_opacity(fb), px + (pw - lt.w) / 2, by + 15)

    # ---------- preview panel
    px0 = 852
    over(B, rounded_rect(w - m - px0, 330, 11, D.UI_PANEL), px0, 190)
    over(B, rounded_border(w - m - px0, 330, 11, 1.2, D.UI_LINE), px0, 190)
    plab = text_sprite("第 3 行  ·  双击可放大", D.INK_SOFT, "sans", 15, tracking=1.0)
    over(B, plab, px0 + 14, 204)
    pv = _rv_preview(2)
    over(B, pv, px0 + 14, 236)
    over(B, rounded_border(196, 40, 8, 1.2, D.UI_LINE), px0 + 14, 452)
    zl = text_sprite("双击全屏", D.GREY_DIM, "sans", 12, tracking=1.0)
    over(B, zl, px0 + 30, 464)

    # ---------- bottom actions
    by2 = h - 74
    over(B, solid(w - 2 * m, 1, D.UI_LINE), m, by2 - 16, 0.8)
    for i, lab in enumerate(["删除选中行", "找回被丢弃的行", "导入本地图片"]):
        bw2 = 160 if i == 0 else 190
        bx2 = m + (0 if i == 0 else (172 + (i - 1) * 202))
        over(B, rounded_border(bw2, 46, 10, 1.2, D.UI_LINE), bx2, by2)
        lt = text_sprite(lab, D.INK_SOFT, "sans", 15, tracking=0.6)
        over(B, lt, bx2 + (bw2 - lt.w) / 2, by2 + 14)
    bw3 = 200
    bx3 = w - m - bw3
    over(B, rounded_rect(bw3, 48, 11, D.hexc("#15191A")), bx3, by2 - 1)
    pt = text_sprite("确认输出 PDF", D.WHITE, "sans_bold", 16, tracking=0.8)
    over(B, pt, bx3 + (bw3 - pt.w) / 2, by2 + 13)
    over(B, rounded_border(186, 48, 11, 1.2, D.UI_LINE), bx3 - 202, by2 - 1)
    at = text_sprite("全自动输出", D.GREY_DIM, "sans", 15, tracking=0.6)
    over(B, at, bx3 - 202 + (186 - at.w) / 2, by2 + 14)

    # ---------- toast (AI dedupe)
    ta = remap(t, 31.0, 31.5, ease_out_cubic) * (1 - remap(t, 32.4, 32.9, ease_in_out_cubic))
    if ta > 0:
        tw2 = 330
        tx = lx + (cw - tw2) / 2
        over(B, rounded_rect(tw2, 44, 11, D.hexc("#0F1A18"), opacity=0.92 * ta), tx, 196)
        tt = text_sprite("AI 已识别 6 组重复", D.TEAL, "sans", 17, tracking=1.0)
        over(B, tt.with_opacity(ta), tx + 20, 209)

    # ---------- "discarded rows can be found again" micro-beat
    fr = remap(t, 30.35, 30.95, ease_out_cubic) * (1 - remap(t, 31.85, 32.35, ease_in_out_cubic))
    if fr > 0:
        fw2 = 420
        fx2 = lx + cw - fw2
        fy2 = 252
        over(B, rounded_rect(fw2, 44, 11, D.hexc("#101A18"), opacity=0.94 * fr), fx2, fy2)
        ft = text_sprite("已丢弃 3 行", D.hexc("#C9D4D2"), "sans", 15, tracking=1.0)
        over(B, ft.with_opacity(fr), fx2 + 18, fy2 + 13)
        over(B, rounded_rect(86, 30, 8, D.TEAL_DEEP, opacity=fr), fx2 + fw2 - 104, fy2 + 7)
        bl = text_sprite("找回", D.WHITE, "sans", 14, tracking=1.0)
        over(B, bl.with_opacity(fr), fx2 + fw2 - 104 + (86 - bl.w) / 2, fy2 + 14)
    # the recovered row slides back into the list
    rc = remap(t, 31.15, 31.85, ease_out_cubic)
    if rc > 0:
        rec = cards[6] if len(cards) > 6 else None
        if rec is None:
            rec = dict(id="r7", name="第 7 行", meta="1917×379 · t=12s", st="找回", thumb=6, y=slot * 4, op=1.0)
        ry2 = ly + slot * 3 + (1 - rc) * 46
        over(B, rounded_rect(cw, chh, 11, D.UI_PANEL, opacity=rc), lx, ry2)
        over(B, rounded_border(cw, chh, 11, 1.6, D.TEAL, opacity=rc), lx, ry2)
        spr = _rv_thumb(6)
        tw = int(spr.w * 52 / spr.h)
        over(B, spr.scaled(tw, 52), lx + 20, ry2 + 13, rc)
        nm = text_sprite("第 7 行", D.UI_TEXT, "sans_bold", 19, tracking=0.6)
        over(B, nm, lx + 334, ry2 + 14, rc)
        mt = text_sprite("1917×379 · t=12s", D.GREY_DIM, "mono", 12, tracking=0.8)
        over(B, mt, lx + 334, ry2 + 44, rc)
        chip = text_sprite("已找回", D.hexc("#1F6B45"), "sans", 13, tracking=1.0)
        over(B, rounded_rect(chip.w + 22, 26, 7, D.GREEN, opacity=0.3 * rc), lx + cw - 104, ry2 + 26)
        over(B, chip, lx + cw - 93, ry2 + 29, rc)

    # ---------- cursor
    cur = cursor_sprite(1.0)
    r3c = (lx + 300, ly + slot * 2 + chh / 2)
    keepb = (lx + (cw - 690) / 2 + 690 - 20 - 118 - 8 + 59, 206 + 23)
    r2c = (lx + 300, ly + slot + chh / 2)
    confb = (bx3 + bw3 / 2, by2 + 24)
    p1 = remap(t, 26.85, 27.4, ease_in_out_cubic)
    p2 = remap(t, 27.62, 28.28, ease_in_out_cubic)
    p3 = remap(t, 29.05, 29.4, ease_in_out_cubic)
    p3b = remap(t, 29.4, 30.15, ease_in_out_cubic)
    p4 = remap(t, 32.15, 32.9, ease_in_out_cubic)
    if t < 28.3:
        cx = lerp(900, r3c[0], p1)
        cy = lerp(560, r3c[1], p1)
    elif t < 29.05:
        cx = lerp(r3c[0], keepb[0], p2)
        cy = lerp(r3c[1], keepb[1], p2)
    elif t < 30.4:
        cx = lerp(keepb[0], r2c[0], p3)
        cy = lerp(keepb[1], r2c[1] + slot * drag, p3b)
    else:
        cx = lerp(r2c[0], confb[0], p4)
        cy = lerp(r2c[1] + slot, confb[1], p4)
    over(B, cur, cx, cy, 0.98)
    # click ripples
    for tc, x, y in [(27.45, r3c[0], r3c[1]), (28.45, keepb[0], keepb[1]), (33.2, confb[0], confb[1])]:
        pr = remap(t, tc, tc + 0.5, ease_out_cubic)
        if 0.02 < pr < 1:
            r = int(16 + pr * 80)
            over(B, mask_to_sprite(ring_mask(r * 2, 2.2), D.TEAL_DEEP), x - r, y - r, (1 - pr) * 0.5)

    mask = rounded_rect_mask(w, h, 18, 4)
    win.rgba[..., :3] *= mask[..., None]
    win.rgba[..., 3:4] = mask[..., None]
    return win


def scene4(t):
    img = studio_bg("dark").copy()
    dust(img, t, gain=0.45)
    key = glow_field(D.W, D.H, (D.W * 0.6, D.H * 0.6), 1100, D.hexc("#4A2E12"), falloff=2.3, gain=0.55)
    over(img, key, 0, 0, 1.0, blend="add")

    push = remap(t, 33.2, 34.9, ease_in_out_cubic)
    drift = remap(t, 26.4, 34.0, ease_in_out_cubic)
    scale = 1.0 + push * 0.22 + 0.014 * drift + 0.0035 * math.sin((t - 26.4) * 0.8)
    # interpolate the window position directly so it stays framed while pushing in
    ox = lerp(_RV_X, 196.0, push) - 16.0 * drift
    oy = lerp(_RV_Y, 128.0, push) - 8.0 * drift + 3.5 * math.sin((t - 26.4) * 0.55)
    ent = remap(t, 26.4, 26.8, ease_out_quint)
    oy += (1 - ent) * 54
    win = _review_window(t)
    w = int(win.w * scale)
    h = int(win.h * scale)
    win_s = win.scaled(w, h)
    over(img, shadow(win_s, 96 + 30 * push, 0.32 * ent, color=np.array([0, 0, 0], F32)), ox + 4, oy + 56)
    over(img, shadow(win_s, 24, 0.20 * ent, color=np.array([0, 0, 0], F32)), ox + 2, oy + 14)
    over(img, win_s, ox, oy, ent)
    over(img, rounded_border(w, h, int(18 * scale), max(1, int(1.7 * scale)), D.WHITE, opacity=0.3), ox, oy, ent)

    sw4 = ((t - 26.4) / 2.9) % 1.0
    if t > 26.5:
        band = gradient_sprite(420, D.H, [(0.0, np.zeros(3, F32)), (0.5, D.WHITE), (1.0, np.zeros(3, F32))], (0, 0), (420, 0))
        bx = int(-420 + (D.W + 840) * sw4)
        over(img, band, bx, 0, 0.03)
    # captions (left column)
    caption(img, "错一行？", 138, 300, t, 26.9, 28.9, D.PAPER, "serif", 56, 1.0, 600, rise=18, dur=0.5)
    caption(img, "拖一下。", 138, 382, t, 27.5, 29.4, D.PAPER, "serif", 56, 1.0, 600, rise=18, dur=0.5)
    caption(img, "丢了的，", 138, 606, t, 29.9, 32.3, D.TEAL, "serif", 44, 1.0, 600, rise=16, dur=0.5)
    caption(img, "还能捡回来。", 138, 666, t, 30.15, 32.3, D.TEAL, "serif", 44, 1.0, 600, rise=16, dur=0.5)
    caption(img, "确认输出。", 138, 620, t, 32.7, 34.7, D.PAPER, "serif", 46, 1.0, 600, rise=18, dur=0.5)
    if t > 26.6:
        p = remap(t, 26.6, 27.2, ease_out_cubic)
        lab = text_sprite("03 / 核验", D.GREY, "sans", 17, tracking=4.0)
        over(img, lab.with_opacity(0.8 * p * (1 - push)), 138, 220)

    fl = pulse(t, 35.72, 0.34)
    if fl > 0:
        img = img * (1 - fl * 0.9) + fl * 0.9
    return img


# --------------------------------------------------------------------------- #
# S5 — paper (36.0 - 45.6)
# --------------------------------------------------------------------------- #

_PG = {}


def _page(i):
    key = ("pg", i)
    if key in _PG:
        return _PG[key]
    titles = [("Paranoid", "Black Sabbath · 吉他谱"), ("Paranoid", "Black Sabbath · 吉他谱"), ("Paranoid", "Black Sabbath · 吉他谱")]
    starts = [0, 7, 15]
    picks = [[0, 4, 9, 15, 21], [3, 8, 13, 19, 25], [6, 11, 17, 23, 29]][i]
    pg = pages.build_page(picks, titles[i][0], titles[i][1], i + 1, 8)
    _PG[key] = pg
    return pg


def _page_turn_quad(spine_x, top, w, h, f):
    """Quad for a page hinged at its left spine, horizontal compression f (1 flat, 0 edge-on)."""
    c = max(-1.0, min(1.0, f))
    s = math.sin(math.acos(abs(c))) * (1 if c >= 0 else -1)
    xr = spine_x + w * c
    dy = h * 0.06 * abs(s)
    return np.array(
        [[spine_x, top], [xr, top + dy], [xr, top + h - dy], [spine_x, top + h]], F32
    )


def _dof(img, focus, radius, strength=0.9):
    blur = cv2.GaussianBlur(img, (0, 0), 5)
    yy, xx = np.mgrid[0 : img.shape[0], 0 : img.shape[1]].astype(F32)
    d = np.sqrt((xx - focus[0]) ** 2 + (yy - focus[1]) ** 2) / radius
    m = np.clip(1 - d * d, 0, 1)[..., None] ** 0.8
    return np.clip(img * m + blur * (1 - m) * strength, 0, 1)


def scene5(t):
    img = studio_bg("warm").copy()
    dust(img, t, gain=0.5)
    # table light pool
    lamp = glow_field(D.W, D.H, (D.W * 0.44, D.H * 0.22), 900, D.hexc("#6A4218"), falloff=2.0, gain=0.75)
    over(img, lamp, 0, 0, 1.0, blend="add")

    p1 = _page(0)
    p2 = _page(1)
    scale = 0.56
    pw, ph = int(p1.w * scale), int(p1.h * scale)
    cx, cy = 1010, 566

    # entrance
    ent = remap(t, 35.96, 36.4, ease_out_quint)
    lift = remap(t, 35.98, 37.1, ease_out_cubic)
    macro = remap(t, 40.45, 42.3, ease_in_out_cubic)
    back = remap(t, 42.35, 43.6, ease_in_out_cubic)

    # ---------------- macro zoom on the printed notation
    macro_vis = macro * (1 - remap(t, 42.3, 43.0, ease_in_out_cubic))
    macro_op = min(1.0, macro_vis * 6.0)
    if macro_vis > 0:
        z = 1 + macro_vis * 1.15
        # focus on a notation area of the page
        fx = cx + pw * 0.18
        fy = cy - ph * 0.10
        scale2 = scale * z
        w2, h2 = int(p1.w * scale2), int(p1.h * scale2)
        pg = p2.scaled(w2, h2)
        px = fx - (fx - cx + pw / 2) * z
        py = fy - (fy - cy + ph / 2) * z
        over(img, shadow(pg, 60, 0.7, dx=-14, dy=18), px - 10, py + 20, ent * macro_op)
        over(img, pg, px, py, ent * macro_op)
        if macro_vis > 0.55:
            img = _dof(img, (fx, fy), 900, 0.24 * min(1.0, (macro_vis - 0.55) * 4))

    # ---------------- single page + turn
    flip = remap(t, 38.75, 40.05, ease_in_out_cubic)
    if macro_vis <= 0.001:
        # back pages in stack
        for k, (ox, oy, rot) in enumerate([(26, -20, 2.2), (13, -10, 1.1)]):
            q = pages.page_quad(cx + ox, cy + oy, pw, ph, rz=rot, ry=-6)
            blit_perspective(img, shadow(p1, 30, 0.5), q + np.array([0, 14], F32), ent * 0.7)
            blit_perspective(img, p1, q, ent * 0.9)
        # main page / turn
        frontal = remap(t, 37.7, 38.5, ease_out_cubic) * (1 - remap(t, 38.72, 39.1, ease_in_out_cubic))
        q = pages.page_quad(cx, cy, pw, ph, ry=-6 + 6 * frontal)
        if flip <= 0:
            blit_perspective(img, shadow(p1, 44, 0.72, dx=-12, dy=16), q + np.array([0, 18], F32), ent)
            blit_perspective(img, p1, q, ent)
            # warm light sweep across the paper
            sw = remap(t, 37.2, 38.5, ease_in_out_cubic)
            if 0 < sw < 1:
                sy = cy - ph / 2 + sw * ph
                over(img, glow_field(D.W, 180, (D.W * 0.5, 90), 820, D.hexc("#FFD9A0"), falloff=1.8, gain=0.35), 0, sy - 90, 0.8, blend="add")
        else:
            # page turning around its left spine
            f = math.cos(math.pi * flip)
            spine = cx - pw / 2
            top = cy - ph / 2
            if f > 0.02:
                q1 = _page_turn_quad(spine, top, pw, ph, f)
                blit_perspective(img, p1, q1, ent * min(1, abs(f) * 1.6))
                shade_w = int(pw * abs(f)) + 2
                sc = alpha_scrim(shade_w, ph, (0, 0), (shade_w, 0), [(0.0, 0.0), (0.6, 0.18 * (1 - abs(f))), (1.0, 0.5 * (1 - abs(f)))])
                over(img, sc, int(spine), int(top), ent)
            if f < 0.98:
                f2 = abs(f)
                q2 = _page_turn_quad(spine, top, pw, ph, max(0.02, f2))
                blit_perspective(img, shadow(p2, 30, 0.4), q2 + np.array([6, 10], F32), ent)
                blit_perspective(img, p2, q2, ent * min(1.0, flip * 7.0))

    # ---------------- pull back to a printed stack
    if back > 0:
        sc3 = 0.5
        w3, h3 = int(p1.w * sc3), int(p1.h * sc3)
        # stack of three pages: only the bottom page casts a soft shadow
        for k, (ox, oy, rot, spr) in enumerate([(34, 26, 3.0, _page(2)), (17, 13, 1.5, p2), (0, 0, 0.0, p1)]):
            q = pages.page_quad(cx + ox, cy + oy + 10, w3, h3, rz=rot, ry=-8)
            if k == 0:
                sh = shadow(spr.scaled(w3, h3), 72, 0.28)
                blit_perspective(img, sh, q + np.array([0, 44], F32), back)
            blit_perspective(img, spr.scaled(w3, h3), q, back)
            # thin darker edge to read as stacked paper
            if k > 0:
                blit_perspective(img, rounded_border(w3, h3, 3, 2, D.hexc("#8A7F6C"), opacity=0.35), q, back)
        # top page lifts toward camera at the end
        lift2 = remap(t, 43.9, 45.5, ease_in_cubic)
        if lift2 > 0:
            q = pages.page_quad(cx, cy - lift2 * 90, w3 * (1 + lift2 * 0.5), h3 * (1 + lift2 * 0.5), rz=-2.0 * lift2, ry=-8 - 10 * lift2)
            blit_perspective(img, shadow(p1.scaled(w3, h3), 40, 0.55), q + np.array([0, 22], F32), back * (1 - lift2 * 0.6))
            blit_perspective(img, p1.scaled(w3, h3), q, back)

    # ---------------- captions
    caption(img, "A4 PDF。", 140, 320, t, 37.9, 40.4, D.PAPER, "serif", 74, 1.5, 600, rise=20, dur=0.55)
    caption(img, "可以直接打印。", 140, 424, t, 38.5, 40.4, D.hexc("#D8C7AE"), "sans", 30, tracking=2.4, rise=14, dur=0.5)
    caption(img, "放大 4 倍，", 140, 856, t, 41.35, 43.6, D.PAPER, "serif", 44, 1.5, 600, rise=16, dur=0.5)
    caption(img, "谱线不虚。", 140, 912, t, 41.7, 43.6, D.TEAL, "serif", 44, 1.5, 600, rise=16, dur=0.5)
    if t > 42.2:
        p = remap(t, 42.2, 42.8, ease_out_cubic)
        spec = text_sprite("300 DPI · 整页排版", D.hexc("#9A8C72"), "sans", 16, tracking=2.0)
        over(img, spec.with_opacity(0.75 * p), 142, 976)
    if t > 36.4:
        p = remap(t, 36.4, 37.1, ease_out_cubic)
        lab = text_sprite("04 / 成品", D.GREY, "sans", 17, tracking=4.0)
        over(img, lab.with_opacity(0.8 * p * (1 - back * 0.8)), 140, 238)
    return img


# --------------------------------------------------------------------------- #
# S6 — brand (45.6 - 60.0)
# --------------------------------------------------------------------------- #


def _logo_mark(p, line_p):
    """Viewfinder brackets + a tab line. p: 0..1 draw-on."""
    w, h = 260, 260
    spr = blank(w, h)
    B = spr.rgba[..., :3]
    line_col = D.TEAL
    # brackets
    arm = 62 * ease_out_cubic(p)
    th = 5
    pad = 26
    for (x, y, dx, dy) in [(pad, pad, 1, 1), (w - pad, pad, -1, 1), (pad, h - pad, 1, -1), (w - pad, h - pad, -1, -1)]:
        if arm < 2:
            continue
        over(B, solid(arm, th, D.PAPER), min(x, x + dx * arm), min(y, y + dy * th) - th / 2 + th / 2, 0.92)
        over(B, solid(th, arm, D.PAPER), min(x, x + dx * th) - th / 2 + th / 2, min(y, y + dy * arm), 0.92)
    # staff line across
    if line_p > 0:
        lw = int((w - 2 * pad + 40) * line_p)
        x0 = (w - lw) / 2
        over(B, solid(lw, 3, line_col), x0, h / 2 - 1.5, 1.0)
        over(B, glow(ellipse_sprite(8, 8, line_col), 8, 0.0), x0 + lw - 6, h / 2 - 4, 0.9, blend="add")
    return spr


def _logo_mark(p, line_p):
    """Viewfinder brackets + a tab line that runs past the frame."""
    w, h = 300, 300
    spr = blank(w, h)
    B = spr.rgba[..., :3]
    arm = 74 * ease_out_cubic(p)
    th = 5
    pad = 22
    for (x, y, dx, dy) in [(pad, pad, 1, 1), (w - pad, pad, -1, 1), (pad, h - pad, 1, -1), (w - pad, h - pad, -1, -1)]:
        if arm < 2:
            continue
        over(B, solid(arm, th, D.PAPER), min(x, x + dx * arm), y - th / 2, 0.94)
        over(B, solid(th, arm, D.PAPER), x - th / 2, min(y, y + dy * arm), 0.94)
    if line_p > 0:
        lw = int((w - 2 * pad + 96) * line_p)
        x0 = (w - lw) / 2
        y0 = h / 2 - 1.5
        over(B, solid(lw, 3, D.TEAL), x0, y0, 1.0)
        # travelling highlight
        over(B, glow(ellipse_sprite(16, 16, D.TEAL), 10, 0.0), x0 + lw - 18, y0 - 12, 0.9, blend="add")
        over(B, solid(lw, 3, D.TEAL), x0, y0, 1.0)
    return spr


def _stagger_text(base, text, y, t, t0, dur, color, name="sans_bold", px=54, tracking=12.0, weight=None,
                  stagger=0.055, rise=18.0, opacity=1.0):
    """Per-character reveal (no glyph gets cut in half)."""
    f = load_font(name, px * 3, weight)
    adv = [f.getlength(ch) / 3.0 for ch in text]
    total = sum(adv) + tracking * (len(text) - 1)
    cx = (D.W - total) / 2
    for i, ch in enumerate(text):
        p = remap(t, t0 + i * stagger, t0 + i * stagger + dur, ease_out_cubic)
        if p > 0.001:
            spr = text_sprite(ch, color, name, px, tracking=0.0, weight=weight, pad=0)
            x = cx + (adv[i] - spr.w) / 2
            op = p * opacity
            over(base, spr.with_opacity(op), x, y + (1 - p) * rise)
        cx += adv[i] + tracking


def scene6(t):
    img = studio_bg("dark").copy()
    dust(img, t, gain=0.85)
    g = glow_field(D.W, D.H, (D.W * 0.5, D.H * 0.40), 860, D.hexc("#0B3D36"), falloff=2.4, gain=0.5)
    over(img, g, 0, 0, 1.0, blend="add")

    # ---------------- the page recedes, the line remains
    if t < 47.9:
        p1 = _page(0)
        out = remap(t, 45.55, 46.9, ease_in_cubic)
        sc = 1.45 * (1 - out * 0.66)
        w, h = int(p1.w * sc), int(p1.h * sc)
        spr = p1.scaled(w, h)
        q = pages.page_quad(D.W * 0.5, D.H * 0.5 - out * 40, w, h, rz=-2 * out, ry=-8 - 12 * out)
        blit_perspective(img, shadow(spr, 50, 0.6), q + np.array([0, 18], F32), 1 - out)
        blit_perspective(img, spr, q, 1 - out)
        lp = remap(t, 46.35, 47.3, ease_in_out_cubic)

    # ---------------- the protagonist line: page -> logo bar
    pl = remap(t, 46.35, 52.4, ease_in_out_cubic)
    if 46.35 < t < 52.55:
        ly = lerp(D.H * 0.63, 318.0, pl)
        lw = int(lerp(D.W * 0.62, 396.0, pl))
        dim = 0.95 * (1.0 - 0.66 * remap(t, 47.45, 48.05) * (1.0 - remap(t, 51.15, 51.75, ease_in_out_cubic)))
        dim *= 1.0 - remap(t, 51.95, 52.35, ease_in_out_cubic)
        over(img, solid(lw, 2, D.TEAL), (D.W - lw) / 2, ly, dim, blend="add")
        # full-height soft glow: a fixed-size rect would show its own edges
        over(img, glow_field(D.W, D.H, (D.W * 0.5, ly), D.W * 0.42, D.TEAL, falloff=2.0, gain=0.30), 0, 0, 0.75 * dim, blend="add")

    # ---------------- hero couplet
    caption(img, "视频会划走，", None, 340, t, 47.55, 51.35, D.WHITE, "serif", 112, 3.0, 600, rise=26, dur=0.7, align="center")
    caption(img, "谱子会留下。", None, 488, t, 48.85, 51.35, D.TEAL, "serif", 112, 3.0, 600, rise=26, dur=0.7, align="center")

    # ---------------- end card
    lp = remap(t, 51.45, 52.5, ease_out_cubic)
    if lp > 0:
        mark = _logo_mark(lp, remap(t, 51.75, 52.55, ease_out_cubic)).with_opacity(lp)
        bw = 1 + 0.025 * math.sin((t - 51.5) * 2.0)
        ms = mark.scaled(int(mark.w * 1.12 * bw), int(mark.h * 1.12 * bw))
        mx = (D.W - ms.w) / 2
        my = 150
        over(img, glow(ms, 30, 0.30, D.TEAL), mx, my, 0.9, blend="add")
        over(img, ms, mx, my, 1.0)

    _stagger_text(img, "视频扒谱工具", 536, t, 52.55, 0.6, D.PAPER, "sans_bold", 84, 14.0, stagger=0.07, rise=22)
    _stagger_text(img, "B站教学视频  →  完整吉他谱  /  A4 PDF", 650, t, 53.35, 0.5, D.GREY, "sans", 24, 3.4, stagger=0.008, rise=12, opacity=0.92)

    # divider
    dv = remap(t, 53.9, 54.5, ease_out_cubic)
    if dv > 0:
        lw = int(120 * dv)
        over(img, solid(lw, 2, D.TEAL), (D.W - lw) / 2, 712, 0.55 * dv, blend="add")

    # slogan
    _stagger_text(img, "一键扒谱 · 不用手截", 742, t, 54.45, 0.6, D.TEAL, "serif", 38, 4.0, weight=600, stagger=0.06, rise=14)

    # CTA block
    if t > 55.3:
        p = remap(t, 55.3, 56.0, ease_out_cubic)
        l1 = text_sprite("WINDOWS  ·  免安装  ·  免费", D.hexc("#C9D2D4"), "sans", 21, tracking=3.0)
        over(img, l1.with_opacity(0.92 * p), (D.W - l1.w) / 2, 806 + (1 - p) * 12)
        l2 = text_sprite("B站 / GitHub 搜索：视频扒谱工具", D.PAPER, "sans", 40, tracking=2.0)
        over(img, l2.with_opacity(0.97 * p), (D.W - l2.w) / 2, 844 + (1 - p) * 12)
        l3 = text_sprite("github.com/Tinkawa123/bili-tab-extractor", D.TEAL, "mono", 24, tracking=1.2)
        over(img, l3.with_opacity(0.95 * p), (D.W - l3.w) / 2, 904 + (1 - p) * 14)


    # continuous slow push + fade out
    drift = remap(t, 51.0, 59.4, ease_in_out_cubic)
    if drift > 0:
        img = _camera(img, 1.0 + 0.055 * drift, D.W * 0.5, D.H * 0.52)
    end = remap(t, 59.3, 60.0, ease_in_out_cubic)
    if end > 0:
        img = img * (1 - end)
    return img


def _placeholder(t, name):
    img = studio_bg("dark").copy()
    lab = text_sprite(f"{name}  @ {t:.1f}s", D.PAPER, "sans", 40, tracking=4)
    over(img, lab, 200, 480)
    return img


# --------------------------------------------------------------------------- #
# dispatch
# --------------------------------------------------------------------------- #


def _transition_fx(img, t):
    """Give each hard cut its own light signature instead of the same flash."""
    # S3 -> S4 : fast diagonal streak
    if 26.28 < t < 26.66:
        u = remap(t, 26.28, 26.66, ease_out_cubic)
        band = gradient_sprite(380, D.H + 200, [(0.0, np.zeros(3, F32)), (0.5, D.WHITE), (1.0, np.zeros(3, F32))], (0, 0), (380, 0))
        bx = int(-380 + (D.W + 760) * u)
        over(img, band, bx, 0, 0.30 * (1 - u))
    # S4 -> S5 : warm table-light bloom
    if 35.94 < t < 36.5:
        u = pulse(t, 35.94, 0.56)
        warm = glow_field(D.W, D.H, (D.W * 0.5, D.H * 0.45), 900, D.hexc("#FFD9A0"), falloff=2.2, gain=0.55)
        over(img, warm, 0, 0, 0.55 * u, blend="add")
    # S5 -> S6 : cool teal rim
    if 45.52 < t < 46.1:
        u = pulse(t, 45.52, 0.58)
        cool = glow_field(D.W, D.H, (D.W * 0.5, D.H * 0.5), 1000, D.hexc("#2FE3B8"), falloff=2.4, gain=0.5)
        over(img, cool, 0, 0, 0.4 * u, blend="add")
    return img


def frame(t):
    t = float(np.clip(t, 0, D.DURATION - 1e-6))
    if t < D.S2:
        img = scene1(t)
    elif t < D.S3:
        img = scene2(t)
    elif t < D.S4:
        img = scene3(t)
    elif t < D.S5:
        img = scene4(t)
    elif t < D.S6:
        img = scene5(t)
    else:
        img = scene6(t)
    img = _transition_fx(img, t)
    warm = 0.6 if D.S5 <= t < D.S6 else 0.0
    vig = 0.46 if t < D.S2 else (0.34 if t < D.S5 else 0.46)
    bloom_amt = 0.07 if D.S5 <= t < D.S6 else 0.13
    halo_amt = 0.03 if D.S5 <= t < D.S6 else 0.05
    return finish(img, t, grain_amt=0.023, vig=vig, warm=warm, bloom_amt=bloom_amt, halo_amt=halo_amt)


render = frame
