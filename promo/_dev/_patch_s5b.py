from pathlib import Path

HERE = Path(__file__).resolve().parent
p = HERE / "film" / "film.py"
s = p.read_text(encoding="utf-8")

# S5: faster entrance so the sheet is already paper-white by 36.8 s
s = s.replace("    ent = remap(t, 35.98, 37.05, ease_out_cubic)", "    ent = remap(t, 35.98, 36.55, ease_out_cubic)")

# S5: a clean, frontal, full-page hero moment before the page turns
s = s.replace(
    "        q = pages.page_quad(cx, cy, pw, ph, ry=-6)",
    "        frontal = remap(t, 37.7, 38.5, ease_out_cubic) * (1 - remap(t, 38.72, 39.1, ease_in_out_cubic))\n        q = pages.page_quad(cx, cy, pw, ph, ry=-6 + 6 * frontal)",
)
p.write_text(s, encoding="utf-8")
print("patched S5 hero moment")
