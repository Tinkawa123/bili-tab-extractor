from pathlib import Path

p = Path(__file__).resolve().parent / "film" / "film.py"
s = p.read_text(encoding="utf-8")

old = '''            crop = row[y0 : y0 + ch, x0 : x0 + cw]
            pad = 14
            cw2, ch2 = cw + 2 * pad, ch + 2 * pad + 30
            card = blank(cw2, ch2)
            # paper-white print border (was reading as a black frame)
            over_sprite(card, solid(cw2, ch2, np.array([0.965, 0.955, 0.93], F32)))
            over_sprite(card, from_float(np.dstack([np.clip(crop * 1.02, 0, 1), np.ones(crop.shape[:2], F32)])), pad, pad)
            over_sprite(card, rounded_border(cw2, ch2, 3, 1, D.INK_SOFT, opacity=0.30))
            tick = text_sprite("CAPTURED", D.TEAL_DEEP, "mono_bold", 11, tracking=2.0)
            over_sprite(card, tick, cw2 - pad - tick.w, ch2 - 26)
            stamp = ellipse_sprite(6, 6, D.TEAL_DEEP)
            over_sprite(card, stamp, pad, ch2 - 24)
            card.rgba *= rounded_rect_mask(cw2, ch2, 4, 3)[..., None]'''
new = '''            crop = row[y0 : y0 + ch, x0 : x0 + cw]
            pad = 14
            cw2, ch2 = cw + 2 * pad, ch + 2 * pad + 30
            # build on an opaque RGB canvas (a print with a paper border + tab crop)
            canvas = np.zeros((ch2, cw2, 3), F32) + np.array([0.965, 0.955, 0.93], F32)
            canvas[pad : pad + ch, pad : pad + cw] = np.clip(crop * 1.02, 0, 1)
            over(canvas, rounded_border(cw2, ch2, 4, 1, D.INK_SOFT, opacity=0.35), 0, 0)
            tick = text_sprite("CAPTURED", D.TEAL_DEEP, "mono_bold", 11, tracking=2.0)
            over(canvas, tick, cw2 - pad - tick.w, ch2 - 26)
            over(canvas, ellipse_sprite(6, 6, D.TEAL_DEEP), pad, ch2 - 24)
            alpha = rounded_rect_mask(cw2, ch2, 5, 3)
            card = Sprite(np.dstack([canvas * alpha[..., None], alpha]))'''
assert old in s
s = s.replace(old, new)
p.write_text(s, encoding="utf-8")
print("polaroid cards v2")
