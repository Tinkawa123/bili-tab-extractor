from pathlib import Path

HERE = Path(__file__).resolve().parent
p = HERE / "film" / "film.py"
s = p.read_text(encoding="utf-8")

# S1: cover the video's own burned-in tab completely
s = s.replace("    tab_top = 745\n    tab_bottom = D.H - 52", "    tab_top = 648\n    tab_bottom = D.H - 52")

# S5 macro: opacity must not be the animation progress
s = s.replace(
    "    macro_vis = macro * (1 - remap(t, 42.3, 43.0, ease_in_out_cubic))\n    if macro_vis > 0:",
    "    macro_vis = macro * (1 - remap(t, 42.3, 43.0, ease_in_out_cubic))\n    macro_op = min(1.0, macro_vis * 6.0)\n    if macro_vis > 0:",
)
s = s.replace(
    "over(img, shadow(pg, 60, 0.7, dx=-14, dy=18), px - 10, py + 20, ent * macro_vis)\n        over(img, pg, px, py, ent * macro_vis)",
    "over(img, shadow(pg, 60, 0.7, dx=-14, dy=18), px - 10, py + 20, ent * macro_op)\n        over(img, pg, px, py, ent * macro_op)",
)
s = s.replace(
    "        if macro_vis > 0.2:\n            img = _dof(img, (fx, fy), 620, 0.45 * macro_vis)",
    "        if macro_vis > 0.55:\n            img = _dof(img, (fx, fy), 620, 0.45 * min(1.0, (macro_vis - 0.55) * 4))",
)
p.write_text(s, encoding="utf-8")

# audio: firmer glue compression before loudness normalisation
a = HERE / "audio.py"
t = a.read_text(encoding="utf-8")
t = t.replace("    mix = compress(mix, 0.55, 2.2)\n    mix = soft_clip(mix * 1.15, 1.15)",
              "    mix = compress(mix, 0.30, 3.4)\n    mix = soft_clip(mix * 1.1, 1.1)\n    mix = compress(mix, 0.45, 2.0)")
a.write_text(t, encoding="utf-8")
print("patched round 3")
