from pathlib import Path

p = Path(__file__).resolve().parent / "film" / "film.py"
s = p.read_text(encoding="utf-8")

# streak: narrower + softer
s = s.replace('''        band = gradient_sprite(700, D.H + 200, [(0.0, np.zeros(3, F32)), (0.5, D.WHITE), (1.0, np.zeros(3, F32))], (0, 0), (700, 0))
        bx = int(-700 + (D.W + 1400) * u)
        over(img, band, bx, 0, 0.55 * (1 - u))''',
              '''        band = gradient_sprite(380, D.H + 200, [(0.0, np.zeros(3, F32)), (0.5, D.WHITE), (1.0, np.zeros(3, F32))], (0, 0), (380, 0))
        bx = int(-380 + (D.W + 760) * u)
        over(img, band, bx, 0, 0.30 * (1 - u))''')

# faster entrances after the cuts
s = s.replace("    ent = remap(t, 26.4, 26.95, ease_out_cubic)", "    ent = remap(t, 26.4, 26.8, ease_out_quint)")
s = s.replace("    ent = remap(t, 7.2, 7.78, ease_out_cubic)", "    ent = remap(t, 7.2, 7.62, ease_out_quint)")
s = s.replace("    ent = remap(t, 35.98, 36.55, ease_out_cubic)", "    ent = remap(t, 35.96, 36.4, ease_out_quint)")

# brighter hero line 1
s = s.replace('caption(img, "视频会划走，", None, 340, t, 47.55, 51.35, D.PAPER, "serif", 112, 3.0, 600, rise=26, dur=0.7, align="center")',
              'caption(img, "视频会划走，", None, 340, t, 47.55, 51.35, D.WHITE, "serif", 112, 3.0, 600, rise=26, dur=0.7, align="center")')
p.write_text(s, encoding="utf-8")
print("tweaks applied")
