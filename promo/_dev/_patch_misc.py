"""Consistency + legibility + transition polish fixes from judge feedback."""

from pathlib import Path

HERE = Path(__file__).resolve().parent

# ---------------- engine: dither large gradients to kill banding
e = HERE / "film" / "engine.py"
es = e.read_text(encoding="utf-8")
es = es.replace(
    "    rgba = np.dstack([colors, np.ones((h, w), F32)])\n    return Sprite(rgba)\n\n\ndef radial_sprite",
    "    colors = colors + (np.random.default_rng(3).random((h, w, 3)).astype(F32) - 0.5) * (0.6 / 255.0)\n"
    "    rgba = np.dstack([np.clip(colors, 0, 1), np.ones((h, w), F32)])\n    return Sprite(rgba)\n\n\ndef radial_sprite",
)
e.write_text(es, encoding="utf-8")

f = HERE / "film" / "film.py"
s = f.read_text(encoding="utf-8")

# ---------------- numbers consistent: 48 rows - 12 dup = 36 rows, 8 pages
s = s.replace('        (20.60, 150, 858, "DUPLICATES / 重复", "−12", "", D.AMBER),\n        (24.10, 470, 858, "PAGES / 页", "3", " A4", D.TEAL),',
              '        (20.60, 150, 858, "DUPLICATES / 重复", "−12", "", D.AMBER),\n        (24.10, 470, 858, "PAGES / 页", "8", " A4", D.TEAL),')
s = s.replace('text_sprite("25 行谱面  ·  4 组疑似重复  ·  拖拽排序 / 双击放大", D.INK_SOFT, "sans", 14, tracking=1.2)',
              'text_sprite("36 行谱面  ·  6 组疑似重复  ·  拖拽排序 / 双击放大", D.INK_SOFT, "sans", 15, tracking=1.2)')
s = s.replace('text_sprite("AI 已识别 4 组重复", D.TEAL, "sans", 15, tracking=1.0)',
              'text_sprite("AI 已识别 6 组重复", D.TEAL, "sans", 16, tracking=1.0)')
s = s.replace('pages.build_page(list(range(0, 5)), "Paranoid", "Black Sabbath · 吉他谱", 1, 3)',
              'pages.build_page(list(range(0, 5)), "Paranoid", "Black Sabbath · 吉他谱", 1, 8)')
s = s.replace('pages.build_page(list(range(starts[i], starts[i] + 9)), titles[i][0], titles[i][1], i + 1, 3)',
              'pages.build_page(list(range(starts[i], starts[i] + 5)), titles[i][0], titles[i][1], i + 1, 8)')
s = s.replace('    starts = [0, 5, 10]', '    starts = [0, 5, 10]')

# ---------------- chapter labels + micro type legibility
s = s.replace('lab = text_sprite("02 / 抽取", D.GREY, "sans", 15, tracking=4.0)',
              'lab = text_sprite("02 / 抽取", D.GREY, "sans", 17, tracking=4.0)')
s = s.replace('lab = text_sprite("01 / 输入", D.GREY, "sans", 15, tracking=4.0)',
              'lab = text_sprite("01 / 输入", D.GREY, "sans", 17, tracking=4.0)')
s = s.replace('lab = text_sprite("03 / 核验", D.GREY, "sans", 15, tracking=4.0)',
              'lab = text_sprite("03 / 核验", D.GREY, "sans", 17, tracking=4.0)')
s = s.replace('lab = text_sprite("04 / 成品", D.GREY, "sans", 15, tracking=4.0)',
              'lab = text_sprite("04 / 成品", D.GREY, "sans", 17, tracking=4.0)')
s = s.replace('.with_opacity(0.65 * p * (1 - push))', '.with_opacity(0.8 * p * (1 - push))')
s = s.replace('.with_opacity(0.6 * p * (1 - back * 0.8))', '.with_opacity(0.8 * p * (1 - back * 0.8))')
s = s.replace('.with_opacity(0.6 * p * (1 - remap(t, 25.5, 26.1, ease_in_out_cubic)))',
              '.with_opacity(0.8 * p * (1 - remap(t, 25.5, 26.1, ease_in_out_cubic)))')
s = s.replace('.with_opacity(0.65 * p), 140, 214)', '.with_opacity(0.8 * p), 140, 214)')

# HUD labels / units bigger
s = s.replace('lab = text_sprite(lab_en, D.GREY, "sans", 13, tracking=3.2)', 'lab = text_sprite(lab_en, D.GREY, "sans", 15, tracking=3.2)')
s = s.replace('sf = text_sprite(suf, D.GREY, "sans", 16, tracking=1.6)', 'sf = text_sprite(suf, D.GREY, "sans", 18, tracking=1.6)')

# S2 app labels a touch bigger
s = s.replace('text_sprite("抽帧间隔", D.INK_SOFT, "sans", 16, tracking=1.4)', 'text_sprite("抽帧间隔", D.INK_SOFT, "sans", 17, tracking=1.4)')
s = s.replace('kt = text_sprite(k, D.INK_SOFT, "sans", 16, tracking=1.4)', 'kt = text_sprite(k, D.INK_SOFT, "sans", 17, tracking=1.4)')
s = s.replace('vt = text_sprite(v, D.UI_TEXT, "sans", 17, tracking=0.6)', 'vt = text_sprite(v, D.UI_TEXT, "sans", 18, tracking=0.6)')
s = s.replace('hint = text_sprite("本地处理 · 不上传视频 · 可随时中断", D.GREY_DIM, "sans", 15, tracking=1.2)',
              'hint = text_sprite("本地处理 · 不上传视频 · 可随时中断", D.GREY_DIM, "sans", 16, tracking=1.2)')
s = s.replace('cap = text_sprite(s, D.UI_TEXT if teal else D.GREY_DIM, "sans", 16, tracking=0.8)',
              'cap = text_sprite(s, D.UI_TEXT if teal else D.GREY_DIM, "sans", 17, tracking=0.8)')

# ---------------- S4 push-in should end on the confirm button, not off-frame
s = s.replace(
    "    push = remap(t, 33.2, 34.9, ease_in_out_cubic)\n    scale = 1.0 + push * 0.9\n    fx, fy = _RV_M + 300, 430\n    focus_x = lerp(_RV_X + fx, 880, push)\n    focus_y = lerp(_RV_Y + fy, 600, push)",
    "    push = remap(t, 33.2, 34.9, ease_in_out_cubic)\n    scale = 1.0 + push * 0.55\n    fx, fy = _RV_W - _RV_M - 100, _RV_H - 50\n    focus_x = lerp(_RV_X + _RV_M + 320, 1080, push)\n    focus_y = lerp(_RV_Y + 380, 640, push)",
)

# ---------------- S5 macro: less blur, keeps the print legible
s = s.replace("blur = cv2.GaussianBlur(img, (0, 0), 9)", "blur = cv2.GaussianBlur(img, (0, 0), 6)")
s = s.replace("            img = _dof(img, (fx, fy), 620, 0.45 * min(1.0, (macro_vis - 0.55) * 4))",
              "            img = _dof(img, (fx, fy), 760, 0.32 * min(1.0, (macro_vis - 0.55) * 4))")

# ---------------- S2->S3 transition: crisp line that opens, not a soft band
old_band = '''    band = remap(t, 14.00, 14.36, ease_in_cubic)
    if band > 0:
        yc = focus_y
        hh = max(3, int((band ** 1.5) * D.H * 1.25))
        band_img = gradient_sprite(D.W, hh, [(0, D.hexc("#0B4A40")), (0.5, D.TEAL), (1, D.hexc("#0B4A40"))], (0, 0), (0, hh))
        over(img, band_img, 0, int(yc - hh / 2), 1.0)
        if band > 0.62:
            u = (band - 0.62) / 0.38
            img = img * (1 - u * 0.92) + u * 0.92'''
new_band = '''    band = remap(t, 14.02, 14.36, ease_in_cubic)
    if band > 0:
        yc = focus_y
        hh = max(2, int((band ** 2.2) * D.H * 1.3))
        over(img, solid(D.W, hh, D.TEAL), 0, int(yc - hh / 2), 1.0)
        if hh > 4:
            over(img, glow_field(D.W, min(D.H, hh + 200), (D.W * 0.5, min(D.H, hh + 200) / 2), D.W * 0.7, D.TEAL, falloff=1.4, gain=0.5), 0, int(yc - (hh + 200) / 2), 0.9, blend="add")
        if band > 0.75:
            u = (band - 0.75) / 0.25
            img = img * (1 - u * 0.95) + u * 0.95'''
assert old_band in s
s = s.replace(old_band, new_band)

# ---------------- S1 polaroids: more depth (shear + slight blur on far ones)
s = s.replace('            "scale": float(rng.uniform(0.62, 0.82)),', '            "scale": float(rng.uniform(0.58, 0.86)),')
s = s.replace('        s2, _, _ = affine_sprite(f["spr"], 0, 0, sc, rot)',
              '        s2, _, _ = affine_sprite(f["spr"], 0, 0, sc, rot, shear=(0.14 * math.sin(f["rot"]), 0.0))')

f.write_text(s, encoding="utf-8")
print("patched misc fixes")
