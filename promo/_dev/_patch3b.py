from pathlib import Path

p = Path(__file__).resolve().parent / "film" / "film.py"
s = p.read_text(encoding="utf-8")

# --- bigger source card
s = s.replace("    vx, vy = 424, 350 - 10 * cam\n    vw, vh = 640, 360",
              "    vx, vy = 430, 356 - 10 * cam\n    vw, vh = 720, 405")
s = s.replace('    vw, vh = 640, 360\n    if key in _C:', '    vw, vh = 720, 405\n    if key in _C:')

# --- stack geometry
s = s.replace("    stack_x = 1288\n    stack_top = 196", "    stack_x = 1300\n    stack_top = 172")
s = s.replace("        t_in = 15.35 + i * 0.30", "        t_in = 15.25 + i * 0.265")
s = s.replace("        p = remap(t, t_in, t_in + 0.66, ease_out_cubic)", "        p = remap(t, t_in, t_in + 0.82, ease_out_cubic)")

# --- backdrop: sampled-frame contact sheet + glow behind stack
old = '''    # ---------------- source card (left) ----------------'''
new = '''    # ---------------- backdrop: sampled frames + stack glow ----------------
    sg = glow_field(D.W, D.H, (stack_x, 520), 620, D.hexc("#0E4B41"), falloff=2.6, gain=0.55)
    over(img, sg, 0, 0, 1.0, blend="add")
    sheet_a = remap(t, 14.9, 15.8, ease_out_cubic) * (1 - remap(t, 21.8, 23.0, ease_in_out_cubic))
    if sheet_a > 0.01:
        rng = np.random.default_rng(9)
        for gy in range(4):
            for gx in range(3):
                tx = 760 + gx * 176 + rng.uniform(-8, 8)
                ty = 170 + gy * 150 + rng.uniform(-8, 8)
                th = 96
                tw = 170
                gm = rounded_rect_mask(tw, th, 5, 3) * 0.5
                gs = mask_to_sprite(gm, D.hexc("#6FA9A2"))
                over(img, gs, tx, ty, sheet_a * (0.10 + 0.05 * rng.uniform(0, 1)))
    # ---------------- source card (left) ----------------'''
assert old in s
s = s.replace(old, new, 1)

# --- HUD with units, larger numbers
old_hud = '''    hud = [
        (15.05, 150, AD := 760, "FRAMES / 帧", "386", D.PAPER),
        (17.30, 456, AD, "TAB ROWS / 行", "+48", D.PAPER),
        (20.60, 150, AD + 118, "DUPLICATES / 重复", "−12", D.AMBER),
        (24.10, 456, AD + 118, "PAGES / 页", "3", D.TEAL),
    ]
    for (t_in, hx, hy, lab_en, val, col) in hud:
        p = remap(t, t_in, t_in + 0.45, ease_out_cubic)
        if p <= 0:
            continue
        lab = text_sprite(lab_en, D.GREY, "sans", 13, tracking=3.2)
        over(img, lab.with_opacity(0.5 * p), hx, hy)
        v = text_sprite(val, col, "mono_bold", 54, tracking=1.5)
        over(img, wipe(v, p, up=False), hx - 2, hy + 20)'''
new_hud = '''    hud = [
        (15.05, 150, 736, "FRAMES / 帧", "386", "", D.PAPER),
        (17.30, 470, 736, "TAB ROWS / 行", "+48", "", D.PAPER),
        (20.60, 150, 858, "DUPLICATES / 重复", "−12", "", D.AMBER),
        (24.10, 470, 858, "PAGES / 页", "3", " A4", D.TEAL),
    ]
    for (t_in, hx, hy, lab_en, val, suf, col) in hud:
        p = remap(t, t_in, t_in + 0.45, ease_out_cubic)
        if p <= 0:
            continue
        lab = text_sprite(lab_en, D.GREY, "sans", 13, tracking=3.2)
        over(img, lab.with_opacity(0.5 * p), hx, hy)
        v = text_sprite(val, col, "mono_bold", 64, tracking=1.5)
        over(img, wipe(v, p, up=False), hx - 2, hy + 20)
        if suf:
            sf = text_sprite(suf, D.GREY, "sans", 16, tracking=1.6)
            over(img, sf.with_opacity(0.7 * p), hx + v.w + 6, hy + 72)'''
assert old_hud in s
s = s.replace(old_hud, new_hud)

p.write_text(s, encoding="utf-8")
print("patched S3 tweaks", len(s))
