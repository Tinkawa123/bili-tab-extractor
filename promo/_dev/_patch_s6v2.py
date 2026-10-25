"""S6 v2 — hero couplet -> logo -> wordmark -> CTA, with continuous motion."""

from pathlib import Path

HERE = Path(__file__).resolve().parent
p = HERE / "film" / "film.py"
s = p.read_text(encoding="utf-8")

start = s.index("def scene6(t):")
end = s.index("def _placeholder(t, name):")

new = '''def _logo_mark(p, line_p):
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
        lp = remap(t, 46.35, 47.5, ease_in_out_cubic)
        if lp > 0:
            ly = D.H * 0.5 - 40 * out + h * 0.06
            lw = int((D.W * 0.62) * lp)
            over(img, solid(lw, 2, D.TEAL), (D.W - lw) / 2, ly, lp * 0.9, blend="add")
            over(img, glow_field(D.W, 220, (D.W * 0.5, 110), D.W * 0.42, D.TEAL, falloff=2.0, gain=0.38), 0, ly - 110, lp * 0.8, blend="add")

    # ---------------- hero couplet
    caption(img, "视频会划走，", None, 340, t, 47.55, 51.35, D.PAPER, "serif", 112, 3.0, 600, rise=26, dur=0.7, align="center")
    caption(img, "谱子会留下。", None, 488, t, 48.85, 51.35, D.TEAL, "serif", 112, 3.0, 600, rise=26, dur=0.7, align="center")

    # ---------------- end card
    lp = remap(t, 51.45, 52.5, ease_out_cubic)
    if lp > 0:
        mark = _logo_mark(lp, remap(t, 51.75, 52.55, ease_out_cubic)).with_opacity(lp)
        bw = 1 + 0.025 * math.sin((t - 51.5) * 2.0)
        ms = mark.scaled(int(mark.w * 0.90 * bw), int(mark.h * 0.90 * bw))
        mx = (D.W - ms.w) / 2
        my = 250
        over(img, glow(ms, 30, 0.30, D.TEAL), mx, my, 0.9, blend="add")
        over(img, ms, mx, my, 1.0)

    _stagger_text(img, "视频扒谱工具", 512, t, 52.55, 0.6, D.PAPER, "sans_bold", 56, 13.0, stagger=0.07, rise=20)
    _stagger_text(img, "B站教学视频  →  完整吉他谱  /  A4 PDF", 596, t, 53.35, 0.5, D.GREY, "sans", 21, 3.4, stagger=0.008, rise=12, opacity=0.9)

    # divider
    dv = remap(t, 53.9, 54.5, ease_out_cubic)
    if dv > 0:
        lw = int(120 * dv)
        over(img, solid(lw, 2, D.TEAL), (D.W - lw) / 2, 664, 0.55 * dv, blend="add")

    # slogan
    _stagger_text(img, "一键扒谱 · 专治手残", 700, t, 54.45, 0.6, D.TEAL, "serif", 36, 4.0, weight=600, stagger=0.06, rise=14)

    # CTA block
    if t > 55.3:
        p = remap(t, 55.3, 56.0, ease_out_cubic)
        l1 = text_sprite("WINDOWS · 免安装 · 免费", D.GREY_DIM, "mono", 15, tracking=3.0)
        over(img, l1.with_opacity(0.7 * p), (D.W - l1.w) / 2, 800 + (1 - p) * 12)
        l2 = text_sprite("B站 / GitHub 搜索：视频扒谱工具", D.PAPER, "sans", 25, tracking=2.0)
        over(img, l2.with_opacity(0.92 * p), (D.W - l2.w) / 2, 834 + (1 - p) * 12)
        l3 = text_sprite("github.com/Tinkawa123/bili-tab-extractor", D.TEAL, "mono", 18, tracking=1.2)
        over(img, l3.with_opacity(0.9 * p), (D.W - l3.w) / 2, 878 + (1 - p) * 14)

    if t > 56.2:
        p = remap(t, 56.2, 56.9, ease_out_cubic)
        foot = text_sprite("BILIBILI  →  PDF   ·   LOCAL  ·   300 DPI", D.GREY_DIM, "sans", 13, tracking=4.0)
        over(img, foot.with_opacity(0.5 * p), (D.W - foot.w) / 2, 1000)

    # continuous slow push + fade out
    drift = remap(t, 51.0, 59.2, ease_in_out_cubic)
    if drift > 0:
        img = _camera(img, 1.0 + 0.03 * drift, D.W * 0.5, D.H * 0.52)
    end = remap(t, 58.85, 60.0, ease_in_out_cubic)
    if end > 0:
        img = img * (1 - end)
    return img


'''

s = s[:start] + new + s[end:]
p.write_text(s, encoding="utf-8")
print("patched S6 v2", len(s))
