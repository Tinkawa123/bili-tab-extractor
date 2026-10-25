from pathlib import Path

HERE = Path(__file__).resolve().parent
p = HERE / "film" / "film.py"
s = p.read_text(encoding="utf-8")

# --- darker print ink on pages
pg = HERE / "film" / "pages.py"
ps = pg.read_text(encoding="utf-8")
ps = ps.replace("region *= np.clip(im * 0.955, 0, 1)", "region *= np.clip((im - 0.03) * 0.80, 0, 1)")
pg.write_text(ps, encoding="utf-8")

# --- flip shading: replace the dark solid block with a gradient scrim
old = '''            if f > 0.02:
                q1 = _page_turn_quad(spine, top, pw, ph, f)
                shade = 0.55 + 0.45 * abs(f)
                spr = p1
                blit_perspective(img, spr, q1, ent * min(1, abs(f) * 1.6))
                over(img, solid(int(pw * abs(f) + 2), ph, np.array([0.06, 0.04, 0.03], F32), alpha=0.30 * (1 - abs(f))), spine, top, 1.0)'''
new = '''            if f > 0.02:
                q1 = _page_turn_quad(spine, top, pw, ph, f)
                blit_perspective(img, p1, q1, ent * min(1, abs(f) * 1.6))
                shade_w = int(pw * abs(f)) + 2
                sc = alpha_scrim(shade_w, ph, (0, 0), (shade_w, 0), [(0.0, 0.0), (0.6, 0.18 * (1 - abs(f))), (1.0, 0.5 * (1 - abs(f)))])
                over(img, sc, int(spine), int(top), ent)'''
assert old in s
s = s.replace(old, new)

# --- macro fades out when we pull back; softer DOF
s = s.replace("    if macro > 0:\n        z = 1 + macro * 1.15",
              "    macro_vis = macro * (1 - remap(t, 42.3, 43.0, ease_in_out_cubic))\n    if macro_vis > 0:\n        z = 1 + macro_vis * 1.15")
s = s.replace("over(img, shadow(pg, 60, 0.7, dx=-14, dy=18), px - 10, py + 20, ent * macro)\n        over(img, pg, px, py, ent * macro)",
              "over(img, shadow(pg, 60, 0.7, dx=-14, dy=18), px - 10, py + 20, ent * macro_vis)\n        over(img, pg, px, py, ent * macro_vis)")
s = s.replace("        if macro > 0.25:\n            img = _dof(img, (fx, fy), 520, 0.75)",
              "        if macro_vis > 0.2:\n            img = _dof(img, (fx, fy), 620, 0.45 * macro_vis)")
s = s.replace("    if macro <= 0.001:", "    if macro_vis <= 0.001:")

# --- caption readability
s = s.replace('caption(img, "可以直接打印。", 140, 424, t, 38.5, 40.4, D.hexc("#C9B9A0"), "sans", 26, tracking=2.0, rise=14, dur=0.5)',
              'caption(img, "可以直接打印。", 140, 424, t, 38.5, 40.4, D.hexc("#D8C7AE"), "sans", 30, tracking=2.4, rise=14, dur=0.5)')

p.write_text(s, encoding="utf-8")
print("patched S5 + ink", len(s))
