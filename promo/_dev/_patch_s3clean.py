from pathlib import Path

p = Path(__file__).resolve().parent / "film" / "film.py"
s = p.read_text(encoding="utf-8")

# the scan-line glow was drawn full-width (a hard rectangle across the whole frame)
old = '''        over(img, glow_field(D.W, 170, (D.W * 0.5, 85), 760, D.TEAL, falloff=1.7, gain=0.45), 0, ly - 85, 0.85, blend="add")
        over(img, solid(D.W, 2, D.TEAL), 0, ly, 0.5, blend="add")'''
new = '''        over(img, glow_field(int(vw + 120), 170, ((vw + 120) * 0.5, 85), vh * 0.75, D.TEAL, falloff=1.7, gain=0.42),
             int(vx - vw / 2 - 60), ly - 85, 0.75, blend="add")
        over(img, solid(int(vw), 2, D.TEAL), int(vx - vw / 2), ly, 0.5, blend="add")'''
assert old in s
s = s.replace(old, new)

# drop the faint contact-sheet tiles (they read as a translucent rectangle over the stage)
old2 = '''    sheet_a = remap(t, 14.9, 15.8, ease_out_cubic) * (1 - remap(t, 21.8, 23.0, ease_in_out_cubic))
    if sheet_a > 0.01:
        rng = np.random.default_rng(9)
        for gy in range(4):
            for gx in range(3):
                tx = 760 + gx * 176 + rng.uniform(-8, 8)
                ty = 170 + gy * 150 + rng.uniform(-8, 8)
                th = 96
                tw = 170
                gm = rounded_rect_mask(tw, th, 6, 3) * 0.5
                gs = blur(mask_to_sprite(gm, D.hexc("#4E8C86")), 10)
                over(img, gs, tx, ty, sheet_a * (0.05 + 0.04 * rng.uniform(0, 1)))
'''
assert old2 in s
s = s.replace(old2, "")

p.write_text(s, encoding="utf-8")
print("S3 scan/backdrop fixed")
