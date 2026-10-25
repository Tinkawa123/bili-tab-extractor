from pathlib import Path

p = Path(__file__).resolve().parent / "film" / "film.py"
s = p.read_text(encoding="utf-8")

s = s.replace(
    '''    tag = text_sprite("每一步都可暂停 / 可回退", D.GREY_DIM, "sans", 15, tracking=1.2)
    over(win.rgba[..., :3], tag, w - m - tag.w, sy + 33)
''',
    "",
)
s = s.replace('steps = ["下载视频", "抽帧", "检测谱行", "去重排序", "输出 A4 PDF"]',
              'steps = ["下载视频", "抽取帧", "检测谱行", "去重排序", "输出 PDF"]')
s = s.replace("    sy = 560", "    sy = 540")

old_band = '''    band = remap(t, 13.98, 14.38, ease_in_cubic)
    if band > 0:
        yc = focus_y
        hh = int(band * D.H * 1.25)
        band_img = gradient_sprite(D.W, max(2, hh), [(0, D.hexc("#062019")), (0.5, D.hexc("#0E7C6B")), (1, D.hexc("#062019"))], (0, 0), (0, hh))
        over(img, band_img, 0, int(yc - hh / 2), min(1.0, band * 1.5))
        if band > 0.5:
            u = (band - 0.5) / 0.5
            img = img * (1 - u * 0.9) + u * 0.9
'''
new_band = '''    band = remap(t, 14.00, 14.36, ease_in_cubic)
    if band > 0:
        yc = focus_y
        hh = max(3, int((band ** 1.5) * D.H * 1.25))
        band_img = gradient_sprite(D.W, hh, [(0, D.hexc("#0B4A40")), (0.5, D.TEAL), (1, D.hexc("#0B4A40"))], (0, 0), (0, hh))
        over(img, band_img, 0, int(yc - hh / 2), 1.0)
        if band > 0.62:
            u = (band - 0.62) / 0.38
            img = img * (1 - u * 0.92) + u * 0.92
'''
assert old_band in s
s = s.replace(old_band, new_band)

s = s.replace('    warm = 0.6 if D.S5 <= t < D.S6 else 0.0\n    vig = 0.58 if t < D.S2 else (0.5 if t < D.S5 else 0.55)',
              '    warm = 0.6 if D.S5 <= t < D.S6 else 0.0\n    vig = 0.58 if t < D.S2 else (0.4 if t < D.S5 else 0.55)')

p.write_text(s, encoding="utf-8")
print("patched", len(s))
