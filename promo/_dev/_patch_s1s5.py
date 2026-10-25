from pathlib import Path

HERE = Path(__file__).resolve().parent
p = HERE / "film" / "film.py"
s = p.read_text(encoding="utf-8")

# ---------------- S1 stats: top-left, big, readable
old_stats = '''    # ---- stats (top right)
    if t > 4.2:
        scrim(img, 460, 200, (0, 0), (460, 200), [(0.0, 0.55), (1.0, 0.0)], 1440, 90)
        n = 12 if t < 4.9 else (24 if t < 5.55 else 37)
        bx, bw = 1492, 288
        lab = text_sprite("已截图", D.hexc("#A9B4B7"), "sans", 18, tracking=3.0)
        over(img, lab, bx, 152)
        num = text_sprite(f"{n:02d}", D.PAPER, "mono_bold", 46, tracking=1.0)
        over(img, num, bx + bw - num.w, 134)
        over(img, solid(bw, 1, D.GREY_DIM), bx, 202, 0.5)
        av = text_sprite("可用", D.hexc("#A9B4B7"), "sans", 18, tracking=3.0)
        over(img, av, bx, 232)
        z = text_sprite("00", D.RED, "mono_bold", 46, tracking=1.0)
        over(img, z, bx + bw - z.w, 214)'''
new_stats = '''    # ---- stats: top-left, big and unmistakable
    if t > 4.2:
        n = 12 if t < 4.9 else (24 if t < 5.55 else 37)
        bx, bw = 140, 300
        lab = text_sprite("已截图", D.hexc("#B9C4C7"), "sans", 20, tracking=3.0)
        over(img, lab, bx, 132)
        num = text_sprite(f"{n:02d}", D.PAPER, "mono_bold", 58, tracking=1.0)
        over(img, num, bx + bw - num.w, 108)
        over(img, solid(bw, 1, D.GREY_DIM), bx, 186, 0.55)
        av = text_sprite("可用", D.hexc("#B9C4C7"), "sans", 20, tracking=3.0)
        over(img, av, bx, 208)
        z = text_sprite("00", D.RED, "mono_bold", 58, tracking=1.0)
        over(img, z, bx + bw - z.w, 184)'''
assert old_stats in s
s = s.replace(old_stats, new_stats)

# ---------------- S1 polaroids: all shadows first, then all cards
old_pol = '''    for i, f in enumerate(_polaroids()):
        dt = t - f["t0"] - f["delay"]
        if dt < 0:
            continue
        p = remap(dt, 0, 0.42, spring)
        op = remap(dt, 0, 0.16, ease_out_cubic)
        dy = (1 - p) * -70
        sc = f["scale"] * (1.14 - 0.14 * p)
        rot = f["rot"] * (0.5 + 0.5 * p)
        s2, _, _ = affine_sprite(f["spr"], 0, 0, sc, rot)
        x = f["x"] - s2.w / 2
        y = f["y"] - s2.h / 2 + dy
        sh = shadow(s2, 16, 0.22)
        over(img, sh, x - s2.w / 2 + 6, y - s2.h / 2 + 9, op)
        over(img, s2, x, y, op)'''
new_pol = '''    placed = []
    for i, f in enumerate(_polaroids()):
        dt = t - f["t0"] - f["delay"]
        if dt < 0:
            continue
        p = remap(dt, 0, 0.42, spring)
        op = remap(dt, 0, 0.16, ease_out_cubic)
        dy = (1 - p) * -70
        sc = f["scale"] * (1.14 - 0.14 * p)
        rot = f["rot"] * (0.5 + 0.5 * p)
        s2, _, _ = affine_sprite(f["spr"], 0, 0, sc, rot)
        placed.append((s2, f["x"] - s2.w / 2, f["y"] - s2.h / 2 + dy, op))
    # shadows first so they never read as black borders around overlapping cards
    sh_all = blank(D.W, D.H)
    for s2, x, y, op in placed:
        over_sprite(sh_all, shadow(s2, 22, 0.20).with_opacity(op), x + 8, y + 14)
    over(img, sh_all, 0, 0, 1.0)
    for s2, x, y, op in placed:
        over(img, s2, x, y, op)'''
assert old_pol in s
s = s.replace(old_pol, new_pol)

# ---------------- S5 stack shadow: soft, drawn before every page
s = s.replace(
    '''            if k == 0:
                sh = shadow(spr.scaled(w3, h3), 46, 0.5)
                blit_perspective(img, sh, q + np.array([0, 22], F32), back)''',
    '''            if k == 0:
                sh = shadow(spr.scaled(w3, h3), 70, 0.30)
                blit_perspective(img, sh, q + np.array([0, 42], F32), back)''',
)

p.write_text(s, encoding="utf-8")
print("patched S1 stats/polaroids + S5 shadow")
