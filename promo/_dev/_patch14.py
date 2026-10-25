from pathlib import Path

HERE = Path(__file__).resolve().parent
p = HERE / "film" / "film.py"
s = p.read_text(encoding="utf-8")

# --- S1: soft scrim behind the stats so they read over the footage
old = "    # ---- stats (top right)\n    if t > 4.2:"
new = '''    # ---- stats (top right)
    if t > 4.2:
        scrim(img, 460, 200, (0, 0), (460, 200), [(0.0, 0.55), (1.0, 0.0)], 1440, 90)'''
assert old in s
s = s.replace(old, new, 1)

# --- S1 polaroids: lighter shadows (they were reading as black frames)
s = s.replace("        sh = shadow(s2, 9, 0.32)\n        over(img, sh, x - s2.w / 2 + 3, y - s2.h / 2 + 4, op)",
              "        sh = shadow(s2, 16, 0.22)\n        over(img, sh, x - s2.w / 2 + 6, y - s2.h / 2 + 9, op)")

# --- S4: the two floating bars must not collide
s = s.replace("        fw2 = 420\n        fx2 = lx + cw - fw2\n        fy2 = 196",
              "        fw2 = 420\n        fx2 = lx + cw - fw2\n        fy2 = 252")

p.write_text(s, encoding="utf-8")
print("patched polish 2")
