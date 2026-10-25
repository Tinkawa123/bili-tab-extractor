from pathlib import Path

p = Path(__file__).resolve().parent / "film" / "film.py"
s = p.read_text(encoding="utf-8")

old = '''            crop = row[y0 : y0 + ch, x0 : x0 + cw]
            pad = 14
            card = blank(cw + 2 * pad, ch + 2 * pad + 30)
            over_sprite(card, from_float(np.dstack([crop, np.ones(crop.shape[:2], F32)])), pad, pad)
            # teal capture tick top-right
            tick = text_sprite("CAPTURED", D.TEAL_DEEP, "mono_bold", 11, tracking=2.0)
            over(card.rgba[..., :3], tick, card.w - pad - tick.w, card.h - 26)
            stamp = ellipse_sprite(6, 6, D.TEAL_DEEP)
            over(card.rgba[..., :3], stamp, pad, card.h - 24)
            mask = rounded_rect_mask(card.w, card.h, 3, 3)
            card.rgba[..., :3] *= mask[..., None]
            card.rgba[..., 3:4] = mask[..., None]'''
new = '''            crop = row[y0 : y0 + ch, x0 : x0 + cw]
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
assert old in s
s = s.replace(old, new)
p.write_text(s, encoding="utf-8")
print("polaroid cards fixed")
