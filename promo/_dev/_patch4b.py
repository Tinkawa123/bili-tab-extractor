from pathlib import Path

p = Path(__file__).resolve().parent / "film" / "film.py"
s = p.read_text(encoding="utf-8")

# darker thumbnails with a paper card behind
s = s.replace("    r = np.clip(r * 0.80, 0, 1)\n    spr = from_float(np.dstack([r, np.ones((h, w), F32)]))",
              "    r = np.clip((r - 0.04) * 0.82, 0, 1)\n    spr = from_float(np.dstack([r, np.ones((h, w), F32)]))")

# preview panel: stack three rows instead of one thin strip
old = '''    pv = _rv_preview(2)
    over(B, pv, px0 + 14, 236)
    over(B, rounded_border(196, 40, 8, 1.2, D.UI_LINE), px0 + 14, 452)
    zl = text_sprite("双击全屏", D.GREY_DIM, "sans", 12, tracking=1.0)
    over(B, zl, px0 + 30, 464)'''
new = '''    yy = 236
    for k in (2, 3, 4):
        pv = _rv_preview(k)
        over(B, pv, px0 + 14, yy)
        over(B, solid(w - m - px0 - 28, 1, D.UI_LINE), px0 + 14, yy + pv.h + 6, 0.6)
        yy += pv.h + 14
    over(B, rounded_border(196, 40, 8, 1.2, D.UI_LINE), px0 + 14, 452)
    zl = text_sprite("双击全屏", D.GREY_DIM, "sans", 12, tracking=1.0)
    over(B, zl, px0 + 30, 464)'''
assert old in s
s = s.replace(old, new)
p.write_text(s, encoding="utf-8")
print("patched S4 thumbs", len(s))
