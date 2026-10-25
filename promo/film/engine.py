"""Deterministic 2D motion-graphics engine for the promo film.

Pure Python: numpy + OpenCV + Pillow.  All drawing is a pure function of time,
so any frame can be rendered independently (and in parallel).

Conventions
-----------
* Canvas: RGB float32 in [0,1], shape (H, W, 3), top-left origin, sRGB.
* Sprite: RGBA float32 *premultiplied*, shape (h, w, 4).
* Colours are float32 triplets or '#rrggbb' strings.
"""

from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import os as _os

_t = _os.environ.get("DSH_CV_THREADS")
cv2.setNumThreads(int(_t) if _t else min(8, cv2.getNumberOfCPUs()))

F32 = np.float32
ASSETS = Path(__file__).resolve().parent / "assets"
FONTS = ASSETS / "fonts"

# --------------------------------------------------------------------------- #
# colour & easing
# --------------------------------------------------------------------------- #


def hexc(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4)], F32)


def mix(a, b, t):
    t = float(np.clip(t, 0.0, 1.0))
    return a + (b - a) * t


def mixc(c1, c2, t):
    return mix(c1, c2, t)


def clamp(x, a=0.0, b=1.0):
    return a if x < a else (b if x > b else x)


def clamp01(x):
    return clamp(x, 0.0, 1.0)


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(t):
    t = clamp01(t)
    return t * t * (3 - 2 * t)


def ease_in_quad(t):
    t = clamp01(t)
    return t * t


def ease_out_quad(t):
    t = clamp01(t)
    return 1 - (1 - t) * (1 - t)


def ease_in_cubic(t):
    t = clamp01(t)
    return t * t * t


def ease_out_cubic(t):
    t = clamp01(t)
    u = 1 - t
    return 1 - u * u * u


def ease_in_out_cubic(t):
    t = clamp01(t)
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out_quint(t):
    t = clamp01(t)
    return 1 - (1 - t) ** 5


def ease_in_out_quint(t):
    t = clamp01(t)
    return 16 * t**5 if t < 0.5 else 1 - (-2 * t + 2) ** 5 / 2


def ease_out_expo(t):
    t = clamp01(t)
    return 1.0 if t >= 1 else 1 - 2 ** (-10 * t)


def ease_in_expo(t):
    t = clamp01(t)
    return 0.0 if t <= 0 else 2 ** (10 * t - 10)


def ease_out_back(t, s=1.70158):
    t = clamp01(t)
    return 1 + (s + 1) * (t - 1) ** 3 + s * (t - 1) ** 2


def spring(t, freq=3.2, damp=6.0):
    """0 -> 1 with a soft overshoot."""
    t = clamp01(t)
    return 1 - math.exp(-damp * t) * math.cos(freq * math.pi * t)


def pulse(t, t0, dur, attack=0.2):
    """0->1->0 bump starting at t0."""
    x = (t - t0) / dur
    if x < 0 or x > 1:
        return 0.0
    return math.sin(math.pi * (x ** (attack * 2.2))) * (1 - x) ** 0.4


def remap(t, t0, t1, ease=None, clamp_out=True):
    if t1 == t0:
        return 0.0
    p = (t - t0) / (t1 - t0)
    if clamp_out:
        p = clamp01(p)
    return ease(p) if ease else p


def beat_time(bpm=100.0):
    return 60.0 / bpm


# --------------------------------------------------------------------------- #
# sprite
# --------------------------------------------------------------------------- #


class Sprite:
    __slots__ = ("rgba", "pad")

    def __init__(self, rgba, pad=0):
        arr = np.asarray(rgba, F32)
        if arr.ndim == 2:
            arr = np.dstack([np.zeros_like(arr), np.zeros_like(arr), np.zeros_like(arr), arr])
        self.rgba = arr
        self.pad = pad

    # -- geometry -------------------------------------------------------- #
    @property
    def w(self):
        return self.rgba.shape[1]

    @property
    def h(self):
        return self.rgba.shape[0]

    @property
    def size(self):
        return (self.w, self.h)

    @property
    def alpha(self):
        return self.rgba[..., 3:4]

    @property
    def rgb(self):
        return self.rgba[..., :3]

    def copy(self):
        return Sprite(self.rgba.copy())

    def cropped(self, x0, y0, x1, y1):
        return Sprite(self.rgba[y0:y1, x0:x1].copy())

    def scaled(self, w, h):
        interp = cv2.INTER_AREA if (w < self.w) else cv2.INTER_LINEAR
        return Sprite(cv2.resize(self.rgba, (int(w), int(h)), interpolation=interp))

    def tinted(self, color, strength=1.0):
        out = self.rgba.copy()
        out[..., :3] = self.rgba[..., :3] * (1 - strength) + self.rgba[..., 3:4] * color * strength
        return Sprite(out)

    def with_opacity(self, op):
        out = self.rgba.copy()
        out[..., :3] *= op
        out[..., 3:4] *= op
        return Sprite(out)

    def flood(self, color):
        out = self.rgba.copy()
        out[..., :3] = out[..., 3:4] * color
        return Sprite(out)


def mask_to_sprite(mask, color):
    m = mask.astype(F32)
    if m.ndim == 2:
        m = m[..., None]
    rgba = np.concatenate([m * color, m], axis=2)
    return Sprite(rgba)


def blank(w, h):
    return Sprite(np.zeros((h, w, 4), F32))


def solid(w, h, color, alpha=1.0):
    w, h = max(1, int(round(w))), max(1, int(round(h)))
    rgba = np.zeros((h, w, 4), F32)
    rgba[..., :3] = color * alpha
    rgba[..., 3] = alpha
    return Sprite(rgba)


def from_uint8(img, premultiply=True):
    """PIL image / uint8 array (RGB or RGBA) -> Sprite."""
    if isinstance(img, Image.Image):
        img = np.asarray(img.convert("RGBA"))
    arr = np.asarray(img, F32) / 255.0
    if arr.shape[2] == 3:
        arr = np.dstack([arr, np.ones(arr.shape[:2], F32)])
    if premultiply:
        arr[..., :3] *= arr[..., 3:4]
    return Sprite(arr)


def from_float(img):
    return Sprite(img)


def load_image(path, mode="RGBA"):
    img = Image.open(path)
    if mode == "RGB":
        return np.asarray(img.convert("RGB"), F32) / 255.0
    return from_uint8(img)


# --------------------------------------------------------------------------- #
# masks & vector shapes  (rendered supersampled for clean edges)
# --------------------------------------------------------------------------- #


def _down(mask, w, h):
    if mask.shape[1] == w and mask.shape[0] == h:
        return mask.astype(F32) / 255.0
    return cv2.resize(mask.astype(F32), (int(w), int(h)), interpolation=cv2.INTER_AREA) / 255.0


_MASK_CACHE = {}


def rounded_rect_mask(w, h, radius, ss=3):
    w, h = int(round(w)), int(round(h))
    if w <= 0 or h <= 0:
        return np.zeros((max(h, 1), max(w, 1)), F32)
    r = min(float(radius), w / 2, h / 2)
    key = ("rr", w, h, round(r, 2), ss)
    hit = _MASK_CACHE.get(key)
    if hit is not None:
        return hit
    W, H = w * ss, h * ss
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=r * ss, fill=255)
    out = _down(np.asarray(img), w, h)
    if len(_MASK_CACHE) < 400:
        _MASK_CACHE[key] = out
    return out


def rect_mask(w, h, ss=2):
    return rounded_rect_mask(w, h, 0, ss)


def circle_mask(d, ss=3):
    return ellipse_mask(d, d, ss)


def ellipse_mask(w, h, ss=3):
    w, h = int(round(w)), int(round(h))
    img = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(img).ellipse([0, 0, w * ss - 1, h * ss - 1], fill=255)
    return _down(np.asarray(img), w, h)


def ring_mask(d, thickness, ss=3):
    w = int(round(d))
    W = w * ss
    img = Image.new("L", (W, W), 0)
    t = max(1, int(thickness * ss))
    ImageDraw.Draw(img).ellipse([t / 2, t / 2, W - 1 - t / 2, W - 1 - t / 2], outline=255, width=t)
    return _down(np.asarray(img), w, w)


def polygon_mask(w, h, points, ss=3):
    w, h = int(round(w)), int(round(h))
    img = Image.new("L", (w * ss, h * ss), 0)
    pts = [(x * ss, y * ss) for x, y in points]
    ImageDraw.Draw(img).polygon(pts, fill=255)
    return _down(np.asarray(img), w, h)


def line_mask(w, h, p0, p1, thickness, ss=3, cap=True):
    w, h = int(round(w)), int(round(h))
    img = Image.new("L", (w * ss, h * ss), 0)
    d = ImageDraw.Draw(img)
    t = max(1, thickness * ss)
    d.line([p0[0] * ss, p0[1] * ss, p1[0] * ss, p1[1] * ss], fill=255, width=int(t))
    if cap:
        for p in (p0, p1):
            d.ellipse([p[0] * ss - t / 2, p[1] * ss - t / 2, p[0] * ss + t / 2, p[1] * ss + t / 2], fill=255)
    return _down(np.asarray(img), w, h)


def mask_gradient(mask, stops, p0, p1):
    """Fill a 2D mask with a linear gradient along p0->p1. stops: [(t, color), ...]."""
    h, w = mask.shape
    ys, xs = np.mgrid[0:h, 0:w].astype(F32)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    denom = dx * dx + dy * dy
    if denom < 1e-9:
        g = np.zeros((h, w, 3), F32) + stops[0][1]
    else:
        g = ((xs - p0[0]) * dx + (ys - p0[1]) * dy) / denom
        g = np.clip(g, 0, 1)
        g = g[..., None]
        out = np.zeros((h, w, 3), F32)
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]
            t1, c1 = stops[i + 1]
            seg = np.clip((g - t0) / max(t1 - t0, 1e-6), 0, 1)
            wgt = (g >= t0) & (g <= t1)
            out += (c0 + (c1 - c0) * seg) * wgt
        return out.astype(F32)
    return np.broadcast_to(g, (h, w, 3)).astype(F32)


def gradient_sprite(w, h, stops, p0, p1):
    h, w = int(h), int(w)
    xs = np.linspace(0, 1, w, dtype=F32)[None, :]
    ys = np.linspace(0, 1, h, dtype=F32)[:, None]
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    denom = dx * dx + dy * dy
    g = ((xs * w - p0[0]) * dx + (ys * h - p0[1]) * dy) / max(denom, 1e-9)
    g = np.clip(g, 0, 1)
    colors = np.zeros((h, w, 3), F32)
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        seg = np.clip((g - t0) / max(t1 - t0, 1e-6), 0, 1)[..., None]
        wgt = ((g >= t0) & (g <= t1))[..., None]
        colors += (c0 + (c1 - c0) * seg) * wgt
    rgba = np.dstack([colors, np.ones((h, w), F32)])
    return Sprite(rgba)


def alpha_scrim(w, h, p0, p1, stops, color=(0, 0, 0)):
    """Directional darkening scrim with alpha gradient (stops: [(t, alpha)])."""
    w, h = int(w), int(h)
    xs = np.linspace(0, 1, w, dtype=F32)[None, :] * w
    ys = np.linspace(0, 1, h, dtype=F32)[:, None] * h
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    denom = dx * dx + dy * dy
    g = np.clip(((xs - p0[0]) * dx + (ys - p0[1]) * dy) / max(denom, 1e-9), 0, 1)
    a = np.zeros((h, w), F32)
    for i in range(len(stops) - 1):
        t0, a0 = stops[i]
        t1, a1 = stops[i + 1]
        seg = np.clip((g - t0) / max(t1 - t0, 1e-6), 0, 1)
        wgt = (g >= t0) & (g <= t1)
        a += (a0 + (a1 - a0) * seg) * wgt
    a = np.clip(a, 0, 1)[..., None]
    return Sprite(np.dstack([a * np.asarray(color, F32), a]))


def radial_sprite(w, h, stops, center, radius, aspect=1.0):
    h, w = int(h), int(w)
    ys, xs = np.mgrid[0:h, 0:w].astype(F32)
    dx = (xs - center[0]) / max(radius, 1e-6)
    dy = (ys - center[1]) / max(radius * aspect, 1e-6)
    g = np.clip(np.sqrt(dx * dx + dy * dy), 0, 1)
    colors = np.zeros((h, w, 3), F32)
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        seg = np.clip((g - t0) / max(t1 - t0, 1e-6), 0, 1)[..., None]
        wgt = ((g >= t0) & (g <= t1))[..., None]
        colors += (c0 + (c1 - c0) * seg) * wgt
    rgba = np.dstack([colors, np.ones((h, w), F32)])
    return Sprite(rgba)


def glow_field(w, h, center, radius, color, falloff=2.2, gain=1.0, aspect=1.0, down=4):
    """Full-canvas radial light field, premultiplied, no clipping edges.

    Computed at reduced resolution and upscaled — it is a low-frequency field,
    so this is visually identical and much cheaper.
    """
    w, h = int(w), int(h)
    dw, dh = max(8, w // down), max(8, h // down)
    ys, xs = np.mgrid[0:dh, 0:dw].astype(F32)
    xs = xs * (w / dw)
    ys = ys * (h / dh)
    dx = (xs - center[0]) / max(radius, 1e-6)
    dy = (ys - center[1]) / max(radius * aspect, 1e-6)
    r = np.sqrt(dx * dx + dy * dy)
    a = (np.clip(1.0 - r, 0, 1) ** falloff) * gain
    a = a[..., None]
    small = np.dstack([a * np.asarray(color, F32), a]).astype(F32)
    big = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
    return Sprite(big)


# --------------------------------------------------------------------------- #
# compositing
# --------------------------------------------------------------------------- #


def over(base, spr, x=0, y=0, opacity=1.0, blend="over"):
    """Composite premultiplied RGBA sprite onto RGB float canvas (in place)."""
    if opacity <= 0:
        return base
    h, w = spr.rgba.shape[:2]
    bh, bw = base.shape[:2]
    x, y = int(round(x)), int(round(y))
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(bw, x + w), min(bh, y + h)
    if x1 <= x0 or y1 <= y0:
        return base
    sx0, sy0 = x0 - x, y0 - y
    sub = spr.rgba[sy0 : sy0 + (y1 - y0), sx0 : sx0 + (x1 - x0)]
    rgb, a = sub[..., :3], sub[..., 3:4]
    if opacity != 1.0:
        rgb = rgb * opacity
        a = a * opacity
    dst = base[y0:y1, x0:x1]
    if blend == "over":
        dst *= 1.0 - a
        dst += rgb
    elif blend == "add":
        dst += rgb
    elif blend == "screen":
        dst[:] = 1 - (1 - dst) * (1 - rgb)
    elif blend == "multiply":
        dst *= (1 - a) + rgb
    elif blend == "overlay":
        dst[:] = dst * (1 - a) + (dst * (1 + rgb - a) + rgb * (1 - dst)) * a
    return base


def over_sprite(dst, src, x=0, y=0, opacity=1.0):
    """Composite sprite onto another sprite (premultiplied RGBA)."""
    if opacity <= 0:
        return dst
    h, w = src.rgba.shape[:2]
    bh, bw = dst.rgba.shape[:2]
    x, y = int(round(x)), int(round(y))
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(bw, x + w), min(bh, y + h)
    if x1 <= x0 or y1 <= y0:
        return dst
    sx0, sy0 = x0 - x, y0 - y
    sub = src.rgba[sy0 : sy0 + (y1 - y0), sx0 : sx0 + (x1 - x0)]
    rgb, a = sub[..., :3], sub[..., 3:4]
    if opacity != 1.0:
        rgb = rgb * opacity
        a = a * opacity
    d = dst.rgba[y0:y1, x0:x1]
    d[..., :3] += rgb * (1.0 - d[..., 3:4])
    d[..., 3:4] += a * (1.0 - d[..., 3:4])
    return dst


def affine_sprite(spr, cx, cy, scale=1.0, rot=0.0, shear=(0.0, 0.0)):
    """Return (sprite, dx, dy) transformed about its own centre with new canvas size."""
    h, w = spr.h, spr.w
    M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), rot, scale)
    M[0, 1] += shear[0]
    M[1, 0] += shear[1]
    # transformed bounding box of the source rect
    corners = np.array([[0, 0], [w, 0], [w, h], [0, h]], F32)
    pts = (corners @ M[:, :2].T) + M[:, 2]
    x0, y0 = np.floor(pts.min(axis=0)).astype(int)
    x1, y1 = np.ceil(pts.max(axis=0)).astype(int) + 1
    M2 = M.copy()
    M2[0, 2] -= x0
    M2[1, 2] -= y0
    out = cv2.warpAffine(
        spr.rgba,
        M2,
        (max(1, x1 - x0), max(1, y1 - y0)),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    return Sprite(out), x0, y0


def blit_affine(base, spr, x, y, scale=1.0, rot=0.0, opacity=1.0, anchor="center", blend="over"):
    """Place sprite at (x, y) being the centre (or 'topleft') after scale/rotate."""
    h, w = spr.h, spr.w
    if abs(scale - 1.0) < 1e-4 and abs(rot) < 1e-4:
        if anchor == "center":
            return over(base, spr, x - w / 2, y - h / 2, opacity, blend)
        return over(base, spr, x, y, opacity, blend)
    s2, ox, oy = affine_sprite(spr, 0, 0, scale, rot)
    if anchor == "center":
        return over(base, s2, x - s2.w / 2, y - s2.h / 2, opacity, blend)
    return over(base, s2, x, y, opacity, blend)


def perspective_sprite(spr, quad):
    """Map sprite corners onto quad (4x2 float, TL,TR,BR,BL). Returns sprite + offset."""
    w, h = spr.w, spr.h
    src = np.array([[0, 0], [w, 0], [w, h], [0, h]], F32)
    dst = np.array(quad, F32)
    H = cv2.getPerspectiveTransform(src, dst)
    pts = np.array([[0, 0], [w, 0], [w, h], [0, h]], F32)
    pts = pts @ H[:, :2].T + H[:, 2]
    pts = pts / pts[:, 2:3]
    pts = pts[:, :2]
    x0, y0 = np.floor(pts.min(axis=0)).astype(int)
    x1, y1 = np.ceil(pts.max(axis=0)).astype(int) + 1
    H2 = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1]], F32) @ H
    out = cv2.warpPerspective(
        spr.rgba,
        H2,
        (max(1, x1 - x0), max(1, y1 - y0)),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    return Sprite(out), int(x0), int(y0)


def blit_perspective(base, spr, quad, opacity=1.0, blend="over"):
    s2, x, y = perspective_sprite(spr, quad)
    return over(base, s2, x, y, opacity, blend)


# --------------------------------------------------------------------------- #
# filters
# --------------------------------------------------------------------------- #


def blur(spr, sigma):
    if sigma <= 0.01:
        return spr
    out = cv2.GaussianBlur(spr.rgba, (0, 0), sigma)
    return Sprite(out)


def blur_rgb(img, sigma):
    if sigma <= 0.01:
        return img
    return cv2.GaussianBlur(img, (0, 0), sigma)


def _blur_alpha(alpha, sigma):
    a = cv2.GaussianBlur(alpha, (0, 0), sigma)
    if a.ndim == 2:
        a = a[..., None]
    return a


def glow(spr, sigma, gain=1.0, tint=None):
    """Additive glow derived from the sprite's alpha (or rgb when tint is None)."""
    a = _blur_alpha(spr.rgba[..., 3:4], sigma) * gain
    if tint is None:
        rgb = cv2.GaussianBlur(spr.rgba[..., :3], (0, 0), sigma) * gain
    else:
        rgb = a * tint
    return Sprite(np.dstack([rgb, a]))


def shadow(spr, sigma, opacity=0.55, color=None, dx=0.0, dy=0.0):
    # pad the alpha by 3 sigma first: otherwise the blur is clipped at the
    # sprite border and every drop shadow ends up with a hard black edge
    pad = int(math.ceil(sigma * 3)) + 2
    alpha = spr.rgba[..., 3:4]
    padded = cv2.copyMakeBorder(alpha, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
    a = cv2.GaussianBlur(padded, (0, 0), sigma) * opacity
    if a.ndim == 2:
        a = a[..., None]
    col = np.array([0.0, 0.0, 0.0], F32) if color is None else color
    return Sprite(np.dstack([a * col, a]), pad=pad)


def drop_shadow(base, spr, x, y, sigma, opacity=0.5, dy=0, dx=0, spread=1.0, color=None):
    sh = shadow(spr, sigma, opacity, color)
    if spread != 1.0:
        sh = Sprite(cv2.resize(sh.rgba, (int(sh.w * spread), int(sh.h * spread)), interpolation=cv2.INTER_LINEAR))
    return over(base, sh, x + dx - (sh.w - spr.w) / 2, y + dy - (sh.h - spr.h) / 2)


def sharpen(img, amount=0.35, sigma=1.0):
    b = cv2.GaussianBlur(img, (0, 0), sigma)
    return img + (img - b) * amount


# --------------------------------------------------------------------------- #
# text
# --------------------------------------------------------------------------- #

FONT_FILES = {
    "serif": "NotoSerifSC-VF.ttf",
    "serif_bold": "NotoSerifSC-VF.ttf",
    "sans": "HarmonyOS_Sans_SC_Regular.ttf",
    "sans_bold": "HarmonyOS_Sans_SC_Bold.ttf",
    "mono": "consola.ttf",
    "mono_bold": "consolab.ttf",
    "hei": "simhei.ttf",
}
_FONT_CACHE: dict = {}


def font_path(name):
    p = FONTS / FONT_FILES[name]
    if not p.exists():
        raise FileNotFoundError(p)
    return str(p)


def load_font(name, px, weight=None):
    key = (name, int(round(px)), weight)
    f = _FONT_CACHE.get(key)
    if f is None:
        f = ImageFont.truetype(font_path(name), int(round(px)))
        if weight is not None:
            try:
                f.set_variation_by_axes([weight])
            except Exception:
                pass
        _FONT_CACHE[key] = f
    return f


def _font_metrics(name, px, weight, ss):
    f = load_font(name, px * ss, weight)
    asc, desc = f.getmetrics()
    return f, asc, desc


def measure_text(text, name="sans", px=24, tracking=0.0, weight=None):
    f = load_font(name, px * 3, weight)
    adv = sum(f.getlength(ch) for ch in text) / 3.0
    return adv + tracking * max(0, len(text) - 1)


def text_mask(text, name="sans", px=24, tracking=0.0, weight=None, ss=3, pad=None):
    """Alpha mask (h, w) of a single line, supersampled then reduced."""
    f, asc, desc = _font_metrics(name, px, weight, ss)
    if pad is None:
        pad = int(px * 0.10) + 2
    advances = [f.getlength(ch) for ch in text]
    total = sum(advances) + tracking * ss * max(0, len(text) - 1)
    W = int(math.ceil(total)) + pad * ss * 2
    H = int(math.ceil(asc + desc)) + pad * ss * 2
    img = Image.new("L", (max(W, 1), max(H, 1)), 0)
    d = ImageDraw.Draw(img)
    x = pad * ss
    for ch, adv in zip(text, advances):
        if ch != " ":
            d.text((x, pad * ss), ch, font=f, fill=255)
        x += adv + tracking * ss
    mask = _down(np.asarray(img), W / ss, H / ss)
    return mask


_TEXT_CACHE = {}


def _cache_key(*args):
    return tuple(a if isinstance(a, (int, float, str, tuple, type(None))) else str(a) for a in args)


def text_sprite(text, color=(1, 1, 1), name="sans", px=24, tracking=0.0, weight=None, ss=3, opacity=1.0, pad=None):
    key = ("t", text, tuple(np.asarray(color, F32).round(4)), name, px, tracking, weight, ss, opacity, pad)
    hit = _TEXT_CACHE.get(key)
    if hit is not None:
        return hit
    m = text_mask(text, name, px, tracking, weight, ss, pad)
    spr = mask_to_sprite(m, np.asarray(color, F32))
    if opacity != 1.0:
        spr = spr.with_opacity(opacity)
    if len(_TEXT_CACHE) < 900:
        _TEXT_CACHE[key] = spr
    return spr


def gradient_text_sprite(text, stops, p0, p1, name="sans", px=24, tracking=0.0, weight=None, ss=3):
    key = ("g", text, tuple((t, tuple(c)) for t, c in stops), p0, p1, name, px, tracking, weight, ss)
    hit = _TEXT_CACHE.get(key)
    if hit is not None:
        return hit
    m = text_mask(text, name, px, tracking, weight, ss)
    g = mask_gradient(m, stops, p0, p1)
    rgba = np.dstack([g * m[..., None], m])
    spr = Sprite(rgba)
    if len(_TEXT_CACHE) < 900:
        _TEXT_CACHE[key] = spr
    return spr


def rounded_rect(w, h, r, color, opacity=1.0, ss=3):
    m = rounded_rect_mask(w, h, r, ss)
    spr = mask_to_sprite(m, np.asarray(color, F32))
    return spr.with_opacity(opacity) if opacity != 1 else spr


def rounded_border(w, h, r, thickness, color, opacity=1.0, ss=4):
    w, h = int(round(w)), int(round(h))
    t = max(1, int(round(thickness)))
    outer = rounded_rect_mask(w, h, r, ss)
    inner = rounded_rect_mask(max(1, w - 2 * t), max(1, h - 2 * t), max(0.0, r - t), ss)
    mask = outer.copy()
    ih, iw = inner.shape
    ox = max(0, (w - iw) // 2)
    oy = max(0, (h - ih) // 2)
    x1, y1 = min(w, ox + iw), min(h, oy + ih)
    mask[oy:y1, ox:x1] -= inner[: y1 - oy, : x1 - ox]
    np.clip(mask, 0, 1, out=mask)
    spr = mask_to_sprite(mask, np.asarray(color, F32))
    return spr.with_opacity(opacity) if opacity != 1 else spr


def line_sprite(w, h, p0, p1, thickness, color, opacity=1.0, ss=3):
    m = line_mask(w, h, p0, p1, thickness, ss)
    spr = mask_to_sprite(m, np.asarray(color, F32))
    return spr.with_opacity(opacity) if opacity != 1 else spr


def ellipse_sprite(w, h, color, opacity=1.0, ss=3):
    m = ellipse_mask(w, h, ss)
    spr = mask_to_sprite(m, np.asarray(color, F32))
    return spr.with_opacity(opacity) if opacity != 1 else spr


def stroke_text_sprite(text, color, stroke_color=(0, 0, 0), width=1.0, name="sans", px=24, tracking=0.0, ss=3):
    f = load_font(name, px * ss, None)
    pad = int(px * 0.35) * ss
    advances = [f.getlength(ch) for ch in text]
    total = sum(advances) + tracking * ss * max(0, len(text) - 1)
    W = int(math.ceil(total)) + pad * 2
    H = int(math.ceil(sum(f.getmetrics()))) + pad * 2
    img = Image.new("RGBA", (max(W, 1), max(H, 1)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = pad
    for ch, adv in zip(text, advances):
        if ch != " ":
            d.text(
                (x, pad),
                ch,
                font=f,
                fill=tuple(int(c * 255) for c in color) + (255,),
                stroke_width=int(width * ss),
                stroke_fill=tuple(int(c * 255) for c in stroke_color) + (255,),
            )
        x += adv + tracking * ss
    arr = np.asarray(img, F32) / 255.0
    arr[..., :3] *= arr[..., 3:4]
    return Sprite(_down_rgba(arr, W / ss, H / ss))


def _down_rgba(arr, w, h):
    w, h = int(round(w)), int(round(h))
    return cv2.resize(arr, (w, h), interpolation=cv2.INTER_AREA)


def wrap_text(text, name="sans", px=24, max_width=800, tracking=0.0, weight=None):
    """Greedy wrap for CJK + latin. Returns list of lines."""
    f = load_font(name, px * 3, weight)
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        trial = cur + ch
        wd = sum(f.getlength(c) for c in trial) / 3.0 + tracking * max(0, len(trial) - 1)
        if wd > max_width and cur:
            lines.append(cur)
            cur = ch
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def paragraph_sprite(
    text,
    color=(1, 1, 1),
    name="sans",
    px=24,
    max_width=800,
    line_height=1.4,
    tracking=0.0,
    weight=None,
    align="left",
):
    lines = wrap_text(text, name, px, max_width, tracking, weight)
    sprites = [text_sprite(l, color, name, px, tracking, weight) for l in lines]
    lh = px * line_height
    W = max(s.w for s in sprites)
    H = int(lh * (len(sprites) - 1) + sprites[-1].h)
    out = blank(W, H)
    y = 0
    for s in sprites:
        x = 0 if align == "left" else (W - s.w if align == "right" else (W - s.w) / 2)
        over_sprite(out, s, x, y + (lh - s.h) / 2)
        y += lh
    return out


# --------------------------------------------------------------------------- #
# textures & fields
# --------------------------------------------------------------------------- #

_TEX_CACHE = {}


def noise_texture(size=512, seed=7, octaves=4, blur_amount=0.0, contrast=1.0):
    key = (size, seed, octaves, blur_amount, contrast)
    if key in _TEX_CACHE:
        return _TEX_CACHE[key]
    rng = np.random.default_rng(seed)
    acc = np.zeros((size, size), F32)
    amp = 1.0
    tot = 0.0
    for o in range(octaves):
        n = rng.random((size, size)).astype(F32)
        n = cv2.GaussianBlur(n, (0, 0), 1.6 * (2**o))
        acc += (n - n.mean()) * amp
        tot += amp
        amp *= 0.55
    acc /= max(tot, 1e-6)
    acc = 0.5 + (acc - acc.mean()) * contrast
    if blur_amount:
        acc = cv2.GaussianBlur(acc, (0, 0), blur_amount)
    acc = np.clip(acc, 0, 1).astype(F32)
    _TEX_CACHE[key] = acc
    return acc


def paper_texture(w, h, seed=3):
    key = ("paper", w, h, seed)
    if key in _TEX_CACHE:
        return _TEX_CACHE[key]
    rng = np.random.default_rng(seed)
    base = np.ones((h, w, 3), F32)
    # fine grain
    n = rng.normal(0, 1, (h, w)).astype(F32)
    n = cv2.GaussianBlur(n, (0, 0), 0.7)
    base += n[..., None] * 0.012
    # broad mottling
    m = rng.normal(0, 1, (h // 4 + 1, w // 4 + 1)).astype(F32)
    m = cv2.resize(m, (w, h), interpolation=cv2.INTER_CUBIC)
    m = cv2.GaussianBlur(m, (0, 0), 18)
    base += m[..., None] * 0.022
    # fibres
    fib = np.zeros((h, w), F32)
    for _ in range(int(w * h / 9000)):
        y = rng.integers(0, h - 1)
        x0 = rng.integers(0, w - 1)
        ln = int(rng.integers(8, 60))
        x1 = min(w, x0 + ln)
        fib[y : y + 1, x0:x1] += rng.uniform(0.3, 1.0)
    fib = cv2.GaussianBlur(fib, (0, 0), 0.6)
    base += fib[..., None] * 0.02
    base = np.clip(base, 0, 1)
    _TEX_CACHE[key] = base
    return base


def tiled(tex, w, h, ox=0, oy=0):
    th, tw = tex.shape[:2]
    oy = int(oy) % th
    ox = int(ox) % tw
    reps_y = int(math.ceil((h + oy) / th))
    reps_x = int(math.ceil((w + ox) / tw))
    big = np.tile(tex, (reps_y, reps_x) + (1,) * (tex.ndim - 2))
    return big[oy : oy + h, ox : ox + w]


# --------------------------------------------------------------------------- #
# film look
# --------------------------------------------------------------------------- #

_VIG_CACHE = {}


def vignette_mask(w, h, strength=0.55, power=2.3):
    key = (w, h, strength, power)
    if key in _VIG_CACHE:
        return _VIG_CACHE[key]
    ys, xs = np.mgrid[0:h, 0:w].astype(F32)
    nx = (xs - w / 2) / (w / 2)
    ny = (ys - h / 2) / (h / 2)
    r = np.sqrt(nx * nx * 0.85 + ny * ny) / 1.35
    v = np.clip(1.0 - strength * np.clip(r, 0, 1.4) ** power, 0, 1)
    v = v[..., None].astype(F32)
    _VIG_CACHE[key] = v
    return v


def apply_grade(img, lift=(0.006, 0.008, 0.012), gamma=1.0, gain=(1.0, 1.0, 1.0), contrast=1.03, saturation=1.0):
    out = img.copy()
    # contrast around 0.42 pivot
    out = (out - 0.42) * contrast + 0.42
    out = np.clip(out, 0, 1)
    out = out**gamma
    out = out * np.asarray(gain, F32) + np.asarray(lift, F32)
    if saturation != 1.0:
        lum = out @ np.array([0.2126, 0.7152, 0.0722], F32)
        out = lum[..., None] + (out - lum[..., None]) * saturation
    return np.clip(out, 0, 1)


def halation(img, threshold=0.72, sigma=26, gain=0.10, tint=(1.0, 0.55, 0.42)):
    lum = img @ np.array([0.2126, 0.7152, 0.0722], F32)
    hi = np.clip((lum - threshold) / (1 - threshold), 0, 1) ** 1.4
    hi = cv2.GaussianBlur(hi, (0, 0), sigma)
    return np.clip(img + hi[..., None] * np.asarray(tint, F32) * gain, 0, 1)


def grain(img, t, amount=0.035, size=512, seed=11):
    tex = noise_texture(size, seed, octaves=3, contrast=0.9)
    h, w = img.shape[:2]
    ox = int(137 * t * 60) % size
    oy = int(91 * t * 60) % size
    g = tiled(tex, w, h, ox, oy)[..., None] - 0.5
    return np.clip(img + g * amount, 0, 1)


def bloom(img, threshold=0.6, sigma=18, gain=0.35):
    lum = img @ np.array([0.2126, 0.7152, 0.0722], F32)
    hi = np.clip((lum - threshold) / (1 - threshold), 0, 1)
    hi = cv2.GaussianBlur(hi, (0, 0), sigma)
    return np.clip(img + (hi[..., None] * img) * gain, 0, 1)


def light_pass(
    img,
    threshold=0.68,
    sigma=26,
    bloom_gain=0.14,
    halo_gain=0.06,
    halo_tint=(1.0, 0.55, 0.40),
    down=4,
):
    """Single low-frequency highlight pass: bloom + halation, computed cheaply."""
    h, w = img.shape[:2]
    lum = img @ np.array([0.2126, 0.7152, 0.0722], F32)
    dw, dh = max(8, w // down), max(8, h // down)
    small = cv2.resize(lum, (dw, dh), interpolation=cv2.INTER_AREA)
    hi = np.clip((small - threshold) / max(1e-3, 1 - threshold), 0, 1) ** 1.25
    hi = cv2.GaussianBlur(hi, (0, 0), max(0.8, sigma / down))
    hi = cv2.resize(hi, (w, h), interpolation=cv2.INTER_LINEAR)[..., None]
    out = img + hi * img * bloom_gain + hi * np.asarray(halo_tint, F32) * halo_gain
    return np.clip(out, 0, 1)


def to_uint8(img):
    return (np.clip(img, 0, 1) * 255.0 + 0.5).astype(np.uint8)


def save_png(img, path):
    u8 = img if img.dtype == np.uint8 else to_uint8(img)
    if u8.ndim == 3 and u8.shape[2] == 3:
        u8 = cv2.cvtColor(u8, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(".png", u8)
    if not ok:
        raise RuntimeError(f"png encode failed: {path}")
    Path(path).write_bytes(buf.tobytes())


def save_jpg(img, path, quality=95):
    u8 = img if img.dtype == np.uint8 else to_uint8(img)
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(u8, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError(f"jpg encode failed: {path}")
    Path(path).write_bytes(buf.tobytes())


def hstack_imgs(imgs, gap=0):
    h = max(i.shape[0] for i in imgs)
    outs = []
    for i in imgs:
        if i.shape[0] < h:
            i = cv2.copyMakeBorder(i, 0, h - i.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(0, 0, 0))
        outs.append(i)
    if gap:
        sep = np.zeros((h, gap, 3), F32)
        inter = []
        for o in outs:
            inter += [o, sep]
        outs = inter[:-1]
    return np.concatenate(outs, axis=1)


def grid_imgs(imgs, cols, gap=6, bg=(0.05, 0.05, 0.06)):
    rows = (len(imgs) + cols - 1) // cols
    ih, iw = imgs[0].shape[:2]
    W = cols * iw + (cols - 1) * gap
    H = rows * ih + (rows - 1) * gap
    out = np.zeros((H, W, 3), F32) + np.asarray(bg, F32)
    for idx, im in enumerate(imgs):
        r, c = divmod(idx, cols)
        y, x = r * (ih + gap), c * (iw + gap)
        out[y : y + ih, x : x + iw] = im
    return out
