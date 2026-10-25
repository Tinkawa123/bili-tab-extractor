from pathlib import Path

HERE = Path(__file__).resolve().parent
f = HERE / "film" / "film.py"
s = f.read_text(encoding="utf-8")

# ============================================================ 1) captions never split glyphs
old = '''def caption(base, text, x, y, t, t_in, t_out, color, name="serif", px=90, tracking=1.5, weight=600, rise=24, dur=0.6, align="left"):
    if t < t_in or t > t_out + 0.5:
        return
    p = remap(t, t_in, t_in + dur, ease_out_cubic)
    q = remap(t, t_out, t_out + 0.5, ease_in_cubic)
    spr = text_sprite(text, color, name, px, tracking, weight)
    spr = wipe(spr, p, up=True)
    op = 1 - q
    dy = (1 - p) * rise - q * rise
    if align == "center" and x is None:
        x = (D.W - spr.w) / 2
    if align == "right" and x is None:
        x = D.W - 150 - spr.w
    over(base, spr.with_opacity(op) if op < 1 else spr, x, y + dy)'''
new = '''def caption(base, text, x, y, t, t_in, t_out, color, name="serif", px=90, tracking=1.5, weight=600, rise=24, dur=0.6, align="left"):
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
    over(base, spr.with_opacity(op), x, y + dy)'''
assert old in s
s = s.replace(old, new)

# HUD numbers: fade instead of a hard wipe
s = s.replace("over(img, wipe(v, p, up=False), hx - 2, hy + 20)", "over(img, v.with_opacity(p), hx - 2, hy + 20)")

# ============================================================ 2) flashes: never wash the whole frame
s = s.replace('''    for tc in (4.30, 4.95, 5.60):
        shake_amt += 6.0 * pulse(t, tc, 0.22)''',
              '''    for tc in (4.30, 4.95, 5.60):
        shake_amt += 4.0 * pulse(t, tc, 0.22)''')
s = s.replace('''        fl = pulse(t, tc, 0.26)
        if fl > 0:
            img = img * (1 - fl * 0.55) + fl * 0.55''',
              '''        fl = pulse(t, tc, 0.22)
        if fl > 0:
            # localised flash inside the capture area only
            flash = solid(D.W, D.H, D.WHITE)
            over(img, flash, 0, 0, fl * 0.18)
            glow = glow_field(D.W, 460, (D.W * 0.5, 230), 700, D.WHITE, falloff=1.5, gain=0.5)
            over(img, glow, 0, 740 - 230 + 60, fl * 0.7, blend="add")''')
s = s.replace("    return _flash_cut(img, t, 7.0, 7.2)", "    return _flash_cut(img, t, 7.06, 7.2)")

# ============================================================ 3) the tab strip: warmer, not the brightest thing
s = s.replace("    tab *= np.array([0.80, 0.85, 0.86], F32)",
              "    tab *= np.array([0.86, 0.815, 0.745], F32)")
s = s.replace("    scan = glow_field(D.W, 90, (D.W * 0.5, 45), D.W * 0.6, D.TEAL, falloff=1.8, gain=0.28)",
              "    scan = glow_field(D.W, 90, (D.W * 0.5, 45), D.W * 0.6, D.TEAL, falloff=1.8, gain=0.16)")
s = s.replace("    gg = glow_field(D.W, D.H, (D.W * 0.76, D.H * 0.04), D.W * 1.0, D.TEAL, falloff=2.8, gain=0.22)",
              "    gg = glow_field(D.W, D.H, (D.W * 0.76, D.H * 0.04), D.W * 1.0, D.TEAL, falloff=2.8, gain=0.12)")
# boundary between video and tab gets a soft occlusion so it is not a hard cut
s = s.replace("    scrim(base, D.W, 90, (0, 0), (0, 90), [(0.0, 0.0), (1.0, 0.85)], 0, tab_top - 90)",
              "    scrim(base, D.W, 120, (0, 0), (0, 120), [(0.0, 0.0), (0.55, 0.55), (1.0, 0.92)], 0, tab_top - 120)")

# ============================================================ 4) S1 seam line must not strike through type
s = s.replace('''    seam = remap(t, 0.05, 0.85, ease_out_cubic)
    if seam > 0:
        lw = int(D.W * 0.72 * seam)
        over(img, solid(lw, 2, D.TEAL), (D.W - lw) / 2, 560, 0.65 * seam, blend="add")
        over(img, glow_field(D.W, 120, (D.W * 0.5, 560), D.W * 0.36 * seam + 2, D.TEAL, falloff=2.0, gain=0.35), 0, 500, seam, blend="add")''',
              '''    seam = remap(t, 0.05, 0.85, ease_out_cubic) * (1 - remap(t, 1.55, 2.3, ease_in_out_cubic))
    if seam > 0:
        lw = int(D.W * 0.72 * seam)
        over(img, solid(lw, 2, D.TEAL), (D.W - lw) / 2, 566, 0.55 * seam, blend="add")
        over(img, glow_field(D.W, 120, (D.W * 0.5, 566), D.W * 0.36 * seam + 2, D.TEAL, falloff=2.0, gain=0.30), 0, 506, seam, blend="add")''')

# ============================================================ 5) S3 ghost frames: soft, rounded, no hard teal rectangles
old_ghost = '''    for k, (gdx, gdy, gsc, ga) in enumerate([(26, 34, 0.965, 0.30), (13, 17, 0.98, 0.45)]):
        gq = pages.page_quad(vx + gdx, vy + gdy, vw * gsc, vh * gsc, rx=6, ry=tilt, rz=-2)
        ghost = solid(int(vw * gsc), int(vh * gsc), np.array([0.10, 0.16, 0.17], F32), alpha=ga)
        blit_perspective(img, ghost, gq)'''
new_ghost = '''    for k, (gdx, gdy, gsc, ga) in enumerate([(30, 40, 0.955, 0.22), (15, 20, 0.978, 0.30)]):
        gq = pages.page_quad(vx + gdx, vy + gdy, vw * gsc, vh * gsc, rx=6, ry=tilt, rz=-2)
        ghost = rounded_rect(int(vw * gsc), int(vh * gsc), 10, np.array([0.06, 0.10, 0.11], F32), alpha=ga)
        ghost = blur(ghost, 18)
        blit_perspective(img, ghost, gq)'''
assert old_ghost in s
s = s.replace(old_ghost, new_ghost)
# contact-sheet backdrop: blur + fade the hard tiles
s = s.replace('''                gm = rounded_rect_mask(tw, th, 5, 3) * 0.5
                gs = mask_to_sprite(gm, D.hexc("#6FA9A2"))
                over(img, gs, tx, ty, sheet_a * (0.10 + 0.05 * rng.uniform(0, 1)))''',
              '''                gm = rounded_rect_mask(tw, th, 6, 3) * 0.5
                gs = blur(mask_to_sprite(gm, D.hexc("#4E8C86")), 10)
                over(img, gs, tx, ty, sheet_a * (0.05 + 0.04 * rng.uniform(0, 1)))''')

# ============================================================ 6) window shadows: soft, two layers (no hard black band)
for win_var in ["win_s"]:
    pass
s = s.replace("        sh = shadow(win_s, 54 + 26 * push, 0.55 * ent, color=np.array([0, 0, 0], F32))\n        over(img, sh, ox + 8, oy + 36)",
              "        sh = shadow(win_s, 92 + 30 * push, 0.34 * ent, color=np.array([0, 0, 0], F32))\n        over(img, sh, ox + 4, oy + 54)\n        sh2 = shadow(win_s, 26, 0.22 * ent, color=np.array([0, 0, 0], F32))\n        over(img, sh2, ox + 2, oy + 16)")
s = s.replace("    over(img, shadow(win_s, 56 + 30 * push, 0.55 * ent, color=np.array([0, 0, 0], F32)), ox + 8, oy + 36)",
              "    over(img, shadow(win_s, 96 + 30 * push, 0.32 * ent, color=np.array([0, 0, 0], F32)), ox + 4, oy + 56)\n    over(img, shadow(win_s, 24, 0.20 * ent, color=np.array([0, 0, 0], F32)), ox + 2, oy + 14)")

# ============================================================ 7) page / paper tone + row backgrounds
old_rows = '''        region = page[y : y + h, x_ink : x_ink + w]
        region *= np.clip(im ** 1.45, 0, 1)'''
new_rows = '''        region = page[y : y + h, x_ink : x_ink + w]
        # normalise each strip's paper white to 1.0 so it melts into the sheet
        hi = float(np.percentile(im, 96)) or 1.0
        im = np.clip(im / max(0.55, hi), 0, 1)
        region *= np.clip(im ** 1.6, 0, 1)'''
pass
pg = HERE / "film" / "pages.py"
ps = pg.read_text(encoding="utf-8")
assert old_rows in ps
ps = ps.replace(old_rows, new_rows)
# slightly warmer, brighter sheet
ps = ps.replace("    page = paper * light[..., None]", "    page = paper * light[..., None] * np.array([1.015, 1.0, 0.975], F32)")
pg.write_text(ps, encoding="utf-8")

# ============================================================ 8) end card hierarchy: mark + wordmark bigger
s = s.replace("        ms = mark.scaled(int(mark.w * 0.86 * bw), int(mark.h * 0.86 * bw))\n        mx = (D.W - ms.w) / 2\n        my = 208",
              "        ms = mark.scaled(int(mark.w * 1.12 * bw), int(mark.h * 1.12 * bw))\n        mx = (D.W - ms.w) / 2\n        my = 150")
s = s.replace('_stagger_text(img, "视频扒谱工具", 528, t, 52.55, 0.6, D.PAPER, "sans_bold", 68, 14.0, stagger=0.07, rise=22)',
              '_stagger_text(img, "视频扒谱工具", 536, t, 52.55, 0.6, D.PAPER, "sans_bold", 84, 14.0, stagger=0.07, rise=22)')
s = s.replace('_stagger_text(img, "B站教学视频  →  完整吉他谱  /  A4 PDF", 626, t, 53.35, 0.5, D.GREY, "sans", 23, 3.4, stagger=0.008, rise=12, opacity=0.92)',
              '_stagger_text(img, "B站教学视频  →  完整吉他谱  /  A4 PDF", 650, t, 53.35, 0.5, D.GREY, "sans", 24, 3.4, stagger=0.008, rise=12, opacity=0.92)')
s = s.replace("        over(img, solid(lw, 2, D.TEAL), (D.W - lw) / 2, 690, 0.55 * dv, blend=\"add\")",
              "        over(img, solid(lw, 2, D.TEAL), (D.W - lw) / 2, 712, 0.55 * dv, blend=\"add\")")
s = s.replace('_stagger_text(img, "一键扒谱 · 不用手截", 724, t, 54.45, 0.6, D.TEAL, "serif", 36, 4.0, weight=600, stagger=0.06, rise=14)',
              '_stagger_text(img, "一键扒谱 · 不用手截", 742, t, 54.45, 0.6, D.TEAL, "serif", 38, 4.0, weight=600, stagger=0.06, rise=14)')
s = s.replace("        over(img, l1.with_opacity(0.7 * p), (D.W - l1.w) / 2, 806 + (1 - p) * 12)",
              "        over(img, l1.with_opacity(0.75 * p), (D.W - l1.w) / 2, 812 + (1 - p) * 12)")
s = s.replace("        over(img, l2.with_opacity(0.92 * p), (D.W - l2.w) / 2, 840 + (1 - p) * 12)",
              "        over(img, l2.with_opacity(0.95 * p), (D.W - l2.w) / 2, 846 + (1 - p) * 12)")
s = s.replace("        over(img, l3.with_opacity(0.9 * p), (D.W - l3.w) / 2, 884 + (1 - p) * 14)",
              "        over(img, l3.with_opacity(0.92 * p), (D.W - l3.w) / 2, 890 + (1 - p) * 14)")
# footer removed (it was 2:1 contrast noise)
s = s.replace('''    if t > 56.2:
        p = remap(t, 56.2, 56.9, ease_out_cubic)
        foot = text_sprite("BILIBILI  →  PDF   ·   LOCAL  ·   300 DPI", D.GREY_DIM, "sans", 13, tracking=4.0)
        over(img, foot.with_opacity(0.5 * p), (D.W - foot.w) / 2, 1000)
''', "")

# ============================================================ 9) black floor: nothing is true 0,0,0
s = s.replace("    img = grain(img, t, grain_amt)\n    img = img * vignette_mask(D.W, D.H, vig)\n    return np.clip(img, 0, 1)",
              "    img = grain(img, t, grain_amt)\n    img = img * vignette_mask(D.W, D.H, vig)\n    img = img * 0.985 + np.array([0.008, 0.010, 0.011], F32)\n    return np.clip(img, 0, 1)")
s = s.replace("    vig = 0.58 if t < D.S2 else (0.4 if t < D.S5 else 0.55)",
              "    vig = 0.46 if t < D.S2 else (0.34 if t < D.S5 else 0.46)")

# ============================================================ 10) consistent page margins (500 / 140)
s = s.replace("WIN_X, WIN_Y = 470, 148", "WIN_X, WIN_Y = 500, 150")
s = s.replace("_RV_X, _RV_Y = 470, 168", "_RV_X, _RV_Y = 500, 168")

f.write_text(s, encoding="utf-8")
print("final polish pass applied")
