from pathlib import Path

HERE = Path(__file__).resolve().parent
p = HERE / "film" / "film.py"
s = p.read_text(encoding="utf-8")

# ============ 1) S2: breathing camera + a light sweep so 8–13 s is never dead
old = '''    push = remap(t, 13.2, 14.32, ease_in_out_cubic)
    fx, fy = _UI_M + 150, _UI_BTN_Y + 44
    scale = 1.0 + push * 0.95 + 0.012 * remap(t, 7.2, 13.2, ease_in_out_cubic)
    focus_x = lerp(WIN_X + fx, 760, push)
    focus_y = lerp(WIN_Y + fy, 560, push)
    ox = focus_x - fx * scale
    oy = focus_y - fy * scale
    ent = remap(t, 7.22, 8.05, ease_out_cubic)
    oy += (1 - ent) * 50'''
new = '''    push = remap(t, 13.2, 14.32, ease_in_out_cubic)
    fx, fy = _UI_M + 150, _UI_BTN_Y + 44
    breathe = 0.010 * remap(t, 7.2, 13.2, ease_in_out_cubic) + 0.0045 * math.sin((t - 7.2) * 0.9)
    scale = 1.0 + push * 0.95 + breathe
    focus_x = lerp(WIN_X + fx, 760, push)
    focus_y = lerp(WIN_Y + fy, 560, push)
    ox = focus_x - fx * scale
    oy = focus_y - fy * scale
    oy += 4.0 * math.sin((t - 7.2) * 0.62)
    ent = remap(t, 7.2, 7.78, ease_out_cubic)
    oy += (1 - ent) * 50'''
assert old in s
s = s.replace(old, new)

# light sweep across the window (keeps the frame alive, reads as a screen reflection)
old2 = '''    # captions (left column)
    caption(img, "粘贴链接，", 140, 300, t, 7.55, 9.55, D.PAPER, "serif", 58, 1.0, 600, rise=18, dur=0.5)'''
new2 = '''    # slow screen-reflection sweep
    sw = ((t - 7.2) / 2.6) % 1.0
    if t > 7.4:
        band = gradient_sprite(360, D.H, [(0.0, np.zeros(3, F32)), (0.5, D.WHITE), (1.0, np.zeros(3, F32))], (0, 0), (360, 0))
        bx = int(-360 + (D.W + 720) * sw)
        over(img, band, bx, 0, 0.035)
    # captions (left column)
    caption(img, "粘贴链接，", 140, 300, t, 7.55, 9.55, D.PAPER, "serif", 58, 1.0, 600, rise=18, dur=0.5)'''
assert old2 in s
s = s.replace(old2, new2)

# ============ 2) S4: continuous drift (9.5 s static was the worst offender)
old = '''    push = remap(t, 33.2, 34.9, ease_in_out_cubic)
    scale = 1.0 + push * 0.22
    # interpolate the window position directly so it stays framed while pushing in
    ox = lerp(_RV_X, 196.0, push)
    oy = lerp(_RV_Y, 128.0, push)
    ent = remap(t, 26.4, 27.2, ease_out_cubic)'''
new = '''    push = remap(t, 33.2, 34.9, ease_in_out_cubic)
    drift = remap(t, 26.4, 34.0, ease_in_out_cubic)
    scale = 1.0 + push * 0.22 + 0.014 * drift + 0.0035 * math.sin((t - 26.4) * 0.8)
    # interpolate the window position directly so it stays framed while pushing in
    ox = lerp(_RV_X, 196.0, push) - 16.0 * drift
    oy = lerp(_RV_Y, 128.0, push) - 8.0 * drift + 3.5 * math.sin((t - 26.4) * 0.55)
    ent = remap(t, 26.4, 26.95, ease_out_cubic)'''
assert old in s
s = s.replace(old, new)
# screen-reflection sweep for S4 too
old3 = '''    # captions (left column)
    caption(img, "错一行？", 138, 300, t, 26.9, 28.9, D.PAPER, "serif", 56, 1.0, 600, rise=18, dur=0.5)'''
new3 = '''    sw4 = ((t - 26.4) / 2.9) % 1.0
    if t > 26.5:
        band = gradient_sprite(420, D.H, [(0.0, np.zeros(3, F32)), (0.5, D.WHITE), (1.0, np.zeros(3, F32))], (0, 0), (420, 0))
        bx = int(-420 + (D.W + 840) * sw4)
        over(img, band, bx, 0, 0.03)
    # captions (left column)
    caption(img, "错一行？", 138, 300, t, 26.9, 28.9, D.PAPER, "serif", 56, 1.0, 600, rise=18, dur=0.5)'''
assert old3 in s
s = s.replace(old3, new3)

# ============ 3) S3: rows opaque while flying (no "paper-through-paper")
s = s.replace("        op = p * (1 - page_fade) * (1 - dup_die)",
              "        op = min(1.0, p * 2.6) * (1 - page_fade) * (1 - dup_die)")

# ============ 4) S4: selection survives through the dedupe beat
s = s.replace("    sel = 27.5 < t < 30.3", "    sel = 27.5 < t < 30.55")

# ============ 5) S5: page 2 fades in instead of popping in one frame
s = s.replace("                blit_perspective(img, p2, q2, ent)", "                blit_perspective(img, p2, q2, ent * min(1.0, flip * 7.0))")

# ============ 6) shutter flash leads its sound by ~40 ms
s = s.replace('''        fl = pulse(t, tc, 0.22)
        if fl > 0:''', '''        fl = pulse(t, tc - 0.042, 0.22)
        if fl > 0:''')

# ============ 7) S6: the line survives from the page all the way into the logo
old_line = '''        lp = remap(t, 46.35, 47.5, ease_in_out_cubic)
        if lp > 0:
            ly = D.H * 0.5 - 40 * out + h * 0.06
            lw = int((D.W * 0.62) * lp)
            over(img, solid(lw, 2, D.TEAL), (D.W - lw) / 2, ly, lp * 0.9, blend="add")
            over(img, glow_field(D.W, 220, (D.W * 0.5, 110), D.W * 0.42, D.TEAL, falloff=2.0, gain=0.38), 0, ly - 110, lp * 0.8, blend="add")'''
new_line = '''        lp = remap(t, 46.35, 47.3, ease_in_out_cubic)'''
assert old_line in s
s = s.replace(old_line, new_line)

old_couplet = '''    # ---------------- hero couplet
    caption(img, "视频会划走，", None, 340, t, 47.55, 51.35, D.PAPER, "serif", 112, 3.0, 600, rise=26, dur=0.7, align="center")'''
new_couplet = '''    # ---------------- the protagonist line: page -> logo bar
    pl = remap(t, 46.35, 52.55, ease_in_out_cubic)
    if t > 46.35:
        ly = lerp(D.H * 0.63, 318.0, pl)
        lw = int(lerp(D.W * 0.62, 396.0, pl))
        dim = 0.95 * (1.0 - 0.66 * remap(t, 47.45, 48.05) * (1.0 - remap(t, 51.15, 51.75, ease_in_out_cubic)))
        over(img, solid(lw, 2, D.TEAL), (D.W - lw) / 2, ly, dim, blend="add")
        over(img, glow_field(D.W, 200, (D.W * 0.5, 100), D.W * 0.42, D.TEAL, falloff=2.0, gain=0.34), 0, ly - 100, 0.7 * dim, blend="add")

    # ---------------- hero couplet
    caption(img, "视频会划走，", None, 340, t, 47.55, 51.35, D.PAPER, "serif", 112, 3.0, 600, rise=26, dur=0.7, align="center")'''
assert old_couplet in s
s = s.replace(old_couplet, new_couplet)

# ============ 8) vary the three hard cuts with different light signatures
old_frame = '''def frame(t):
    t = float(np.clip(t, 0, D.DURATION - 1e-6))'''
new_frame = '''def _transition_fx(img, t):
    """Give each hard cut its own light signature instead of the same flash."""
    # S3 -> S4 : fast diagonal streak
    if 26.28 < t < 26.66:
        u = remap(t, 26.28, 26.66, ease_out_cubic)
        band = gradient_sprite(700, D.H + 200, [(0.0, np.zeros(3, F32)), (0.5, D.WHITE), (1.0, np.zeros(3, F32))], (0, 0), (700, 0))
        bx = int(-700 + (D.W + 1400) * u)
        over(img, band, bx, 0, 0.55 * (1 - u))
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
    t = float(np.clip(t, 0, D.DURATION - 1e-6))'''
assert old_frame in s
s = s.replace(old_frame, new_frame)

# call the transition overlay right before finishing
s = s.replace('''    warm = 0.6 if D.S5 <= t < D.S6 else 0.0''',
              '''    img = _transition_fx(img, t)
    warm = 0.6 if D.S5 <= t < D.S6 else 0.0''')

p.write_text(s, encoding="utf-8")
print("motion/transition pass applied")
