from pathlib import Path

HERE = Path(__file__).resolve().parent

# ================= 1) engine.shadow(): pad by 3 sigma so the blur has room
e = HERE / "film" / "engine.py"
es = e.read_text(encoding="utf-8")
old = '''def shadow(spr, sigma, opacity=0.55, color=None, dx=0.0, dy=0.0):
    a = _blur_alpha(spr.rgba[..., 3:4], sigma) * opacity
    col = np.array([0.0, 0.0, 0.0], F32) if color is None else color
    return Sprite(np.dstack([a * col, a]))'''
new = '''def shadow(spr, sigma, opacity=0.55, color=None, dx=0.0, dy=0.0):
    # pad the alpha by 3 sigma first: otherwise the blur is clipped at the
    # sprite border and every drop shadow ends up with a hard black edge
    pad = int(math.ceil(sigma * 3)) + 2
    alpha = spr.rgba[..., 3:4]
    padded = cv2.copyMakeBorder(alpha, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
    a = cv2.GaussianBlur(padded, (0, 0), sigma) * opacity
    if a.ndim == 2:
        a = a[..., None]
    col = np.array([0.0, 0.0, 0.0], F32) if color is None else color
    return Sprite(np.dstack([a * col, a]), pad=pad)'''
assert old in es
es = es.replace(old, new)
# Sprite needs to know its padding for correct placement
es = es.replace('''class Sprite:
    __slots__ = ("rgba",)

    def __init__(self, rgba):
        arr = np.asarray(rgba, F32)
        if arr.ndim == 2:
            arr = np.dstack([np.zeros_like(arr), np.zeros_like(arr), np.zeros_like(arr), arr])
        self.rgba = arr''',
'''class Sprite:
    __slots__ = ("rgba", "pad")

    def __init__(self, rgba, pad=0):
        arr = np.asarray(rgba, F32)
        if arr.ndim == 2:
            arr = np.dstack([np.zeros_like(arr), np.zeros_like(arr), np.zeros_like(arr), arr])
        self.rgba = arr
        self.pad = pad''')
e.write_text(es, encoding="utf-8")

f = HERE / "film" / "film.py"
s = f.read_text(encoding="utf-8")

# ================= 2) S5: remove the stray full-size shadow drawn over the page
s = s.replace("        # base shadow under the page\n        over(img, shadow(p1, 50, 0.55, dx=0, dy=26), cx - pw / 2, cy - ph / 2 + 26, ent * (1 - macro))\n", "")

# ================= 3) S4: the "found rows" toast must fade out (it stayed 5.6 s)
s = s.replace("    fr = remap(t, 30.35, 30.95, ease_out_cubic)",
              "    fr = remap(t, 30.35, 30.95, ease_out_cubic) * (1 - remap(t, 31.85, 32.35, ease_in_out_cubic))")

# ================= 4) S6: line is a full-height glow (no 1920x200 hard rectangle) and exits at 52.55
old_line = '''    pl = remap(t, 46.35, 52.55, ease_in_out_cubic)
    if t > 46.35:
        ly = lerp(D.H * 0.63, 318.0, pl)
        lw = int(lerp(D.W * 0.62, 396.0, pl))
        dim = 0.95 * (1.0 - 0.66 * remap(t, 47.45, 48.05) * (1.0 - remap(t, 51.15, 51.75, ease_in_out_cubic)))
        over(img, solid(lw, 2, D.TEAL), (D.W - lw) / 2, ly, dim, blend="add")
        over(img, glow_field(D.W, 200, (D.W * 0.5, 100), D.W * 0.42, D.TEAL, falloff=2.0, gain=0.34), 0, ly - 100, 0.7 * dim, blend="add")'''
new_line = '''    pl = remap(t, 46.35, 52.4, ease_in_out_cubic)
    if 46.35 < t < 52.55:
        ly = lerp(D.H * 0.63, 318.0, pl)
        lw = int(lerp(D.W * 0.62, 396.0, pl))
        dim = 0.95 * (1.0 - 0.66 * remap(t, 47.45, 48.05) * (1.0 - remap(t, 51.15, 51.75, ease_in_out_cubic)))
        dim *= 1.0 - remap(t, 52.3, 52.55, ease_in_out_cubic)
        over(img, solid(lw, 2, D.TEAL), (D.W - lw) / 2, ly, dim, blend="add")
        # full-height soft glow: a fixed-size rect would show its own edges
        over(img, glow_field(D.W, D.H, (D.W * 0.5, ly), D.W * 0.42, D.TEAL, falloff=2.0, gain=0.30), 0, 0, 0.75 * dim, blend="add")'''
assert old_line in s
s = s.replace(old_line, new_line)

# ================= 5) S3 labels move off the guitar (into the top margin)
s = s.replace('over(img, lab.with_opacity(0.55 * p), 150, 176)', 'over(img, lab.with_opacity(0.55 * p), 150, 112)')
s = s.replace('over(img, lab.with_opacity(0.8 * p * (1 - remap(t, 25.5, 26.1, ease_in_out_cubic))), 150, 238)',
              'over(img, lab.with_opacity(0.8 * p * (1 - remap(t, 25.5, 26.1, ease_in_out_cubic))), 150, 146)')

# ================= 6) nav block count label matches what is drawn
s = s.replace('text_sprite("48 块 · 点一下跳转", D.GREY_DIM, "sans", 12, tracking=1.0)',
              'text_sprite("30 块 · 点一下跳转", D.GREY_DIM, "sans", 14, tracking=1.0)')

# ================= 7) CTA block: bigger, brighter, on screen longer
s = s.replace('l1 = text_sprite("WINDOWS · 免安装 · 免费", D.GREY_DIM, "sans", 16, tracking=3.0)',
              'l1 = text_sprite("WINDOWS  ·  免安装  ·  免费", D.hexc("#C9D2D4"), "sans", 21, tracking=3.0)')
s = s.replace('l2 = text_sprite("B站 / GitHub 搜索：视频扒谱工具", D.PAPER, "sans", 27, tracking=2.0)',
              'l2 = text_sprite("B站 / GitHub 搜索：视频扒谱工具", D.PAPER, "sans", 40, tracking=2.0)')
s = s.replace('l3 = text_sprite("github.com/Tinkawa123/bili-tab-extractor", D.TEAL, "mono", 18, tracking=1.2)',
              'l3 = text_sprite("github.com/Tinkawa123/bili-tab-extractor", D.TEAL, "mono", 24, tracking=1.2)')
s = s.replace("        over(img, l1.with_opacity(0.75 * p), (D.W - l1.w) / 2, 812 + (1 - p) * 12)",
              "        over(img, l1.with_opacity(0.92 * p), (D.W - l1.w) / 2, 806 + (1 - p) * 12)")
s = s.replace("        over(img, l2.with_opacity(0.95 * p), (D.W - l2.w) / 2, 846 + (1 - p) * 12)",
              "        over(img, l2.with_opacity(0.97 * p), (D.W - l2.w) / 2, 844 + (1 - p) * 12)")
s = s.replace("        over(img, l3.with_opacity(0.92 * p), (D.W - l3.w) / 2, 890 + (1 - p) * 14)",
              "        over(img, l3.with_opacity(0.95 * p), (D.W - l3.w) / 2, 904 + (1 - p) * 14)")
s = s.replace("    drift = remap(t, 51.0, 59.2, ease_in_out_cubic)\n    if drift > 0:\n        img = _camera(img, 1.0 + 0.03 * drift, D.W * 0.5, D.H * 0.52)",
              "    drift = remap(t, 51.0, 59.4, ease_in_out_cubic)\n    if drift > 0:\n        img = _camera(img, 1.0 + 0.055 * drift, D.W * 0.5, D.H * 0.52)")
s = s.replace("    end = remap(t, 58.85, 60.0, ease_in_out_cubic)", "    end = remap(t, 59.3, 60.0, ease_in_out_cubic)")

# ================= 8) S1: softer, thicker top edge on the tab strip
s = s.replace("    scrim(base, D.W, 120, (0, 0), (0, 120), [(0.0, 0.0), (0.55, 0.55), (1.0, 0.92)], 0, tab_top - 120)",
              "    scrim(base, D.W, 170, (0, 0), (0, 170), [(0.0, 0.0), (0.35, 0.30), (0.75, 0.76), (1.0, 0.95)], 0, tab_top - 170)")

# ================= 9) S3 rows: trim the cut right edge so the stack looks complete
s = s.replace('''    for i in idx:
        im = src[i % len(src)].astype(F32) / 255.0
        h = max(18, int(round(im.shape[0] * w / im.shape[1])))
        r = cv2.resize(im, (w, h), interpolation=cv2.INTER_AREA)''',
              '''    for i in idx:
        im = src[i % len(src)].astype(F32) / 255.0
        ih, iw = im.shape[:2]
        im = im[:, int(iw * 0.012) : int(iw * 0.985)]
        h = max(18, int(round(im.shape[0] * w / im.shape[1])))
        r = cv2.resize(im, (w, h), interpolation=cv2.INTER_AREA)''')

# ================= 10) pages: pick non-adjacent rows (no duplicate-looking rows on the sheet)
s = s.replace("    starts = [0, 5, 10]", "    starts = [0, 7, 15]")
s = s.replace('pages.build_page(list(range(0, 5)), "Paranoid", "Black Sabbath · 吉他谱", 1, 8)',
              'pages.build_page([0, 4, 9, 15, 21], "Paranoid", "Black Sabbath · 吉他谱", 1, 8)')
s = s.replace("    pg = pages.build_page(list(range(starts[i], starts[i] + 5)), titles[i][0], titles[i][1], i + 1, 8)",
              "    picks = [[0, 4, 9, 15, 21], [3, 8, 13, 19, 25], [6, 11, 17, 23, 29]][i]\n    pg = pages.build_page(picks, titles[i][0], titles[i][1], i + 1, 8)")

f.write_text(s, encoding="utf-8")
print("P0 fixes from round 2 applied")
