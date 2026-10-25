from pathlib import Path

HERE = Path(__file__).resolve().parent
p = HERE / "film" / "film.py"
s = p.read_text(encoding="utf-8")

# ---- S6 layout: give the logo room above the wordmark
s = s.replace("        ms = mark.scaled(int(mark.w * 0.90 * bw), int(mark.h * 0.90 * bw))\n        mx = (D.W - ms.w) / 2\n        my = 250",
              "        ms = mark.scaled(int(mark.w * 0.86 * bw), int(mark.h * 0.86 * bw))\n        mx = (D.W - ms.w) / 2\n        my = 208")
s = s.replace('_stagger_text(img, "视频扒谱工具", 512, t, 52.55, 0.6, D.PAPER, "sans_bold", 56, 13.0, stagger=0.07, rise=20)',
              '_stagger_text(img, "视频扒谱工具", 536, t, 52.55, 0.6, D.PAPER, "sans_bold", 56, 13.0, stagger=0.07, rise=20)')
s = s.replace('_stagger_text(img, "B站教学视频  →  完整吉他谱  /  A4 PDF", 596, t, 53.35, 0.5, D.GREY, "sans", 21, 3.4, stagger=0.008, rise=12, opacity=0.9)',
              '_stagger_text(img, "B站教学视频  →  完整吉他谱  /  A4 PDF", 620, t, 53.35, 0.5, D.GREY, "sans", 21, 3.4, stagger=0.008, rise=12, opacity=0.9)')
s = s.replace("        over(img, solid(lw, 2, D.TEAL), (D.W - lw) / 2, 664, 0.55 * dv, blend=\"add\")",
              "        over(img, solid(lw, 2, D.TEAL), (D.W - lw) / 2, 690, 0.55 * dv, blend=\"add\")")
s = s.replace('_stagger_text(img, "一键扒谱 · 专治手残", 700, t, 54.45, 0.6, D.TEAL, "serif", 36, 4.0, weight=600, stagger=0.06, rise=14)',
              '_stagger_text(img, "一键扒谱 · 专治手残", 724, t, 54.45, 0.6, D.TEAL, "serif", 36, 4.0, weight=600, stagger=0.06, rise=14)')
# CTA: Chinese must not use the mono font (no CJK glyphs)
s = s.replace('l1 = text_sprite("WINDOWS · 免安装 · 免费", D.GREY_DIM, "mono", 15, tracking=3.0)',
              'l1 = text_sprite("WINDOWS · 免安装 · 免费", D.GREY_DIM, "sans", 16, tracking=3.0)')
s = s.replace("        over(img, l1.with_opacity(0.7 * p), (D.W - l1.w) / 2, 800 + (1 - p) * 12)",
              "        over(img, l1.with_opacity(0.7 * p), (D.W - l1.w) / 2, 806 + (1 - p) * 12)")
s = s.replace("        over(img, l2.with_opacity(0.92 * p), (D.W - l2.w) / 2, 834 + (1 - p) * 12)",
              "        over(img, l2.with_opacity(0.92 * p), (D.W - l2.w) / 2, 840 + (1 - p) * 12)")
s = s.replace("        over(img, l3.with_opacity(0.9 * p), (D.W - l3.w) / 2, 878 + (1 - p) * 14)",
              "        over(img, l3.with_opacity(0.9 * p), (D.W - l3.w) / 2, 884 + (1 - p) * 14)")

# ---- S4 push-in: less aggressive so the frame stays composed
s = s.replace("    scale = 1.0 + push * 0.55\n    fx, fy = _RV_W - _RV_M - 100, _RV_H - 50\n    focus_x = lerp(_RV_X + _RV_M + 320, 1080, push)\n    focus_y = lerp(_RV_Y + 380, 640, push)",
              "    scale = 1.0 + push * 0.34\n    fx, fy = _RV_W - _RV_M - 110, _RV_H - 40\n    focus_x = lerp(_RV_X + _RV_M + 260, 1010, push)\n    focus_y = lerp(_RV_Y + 330, 600, push)")

# ---- S5 macro DOF: gentler, keep more of the print sharp
s = s.replace("blur = cv2.GaussianBlur(img, (0, 0), 6)", "blur = cv2.GaussianBlur(img, (0, 0), 5)")
s = s.replace("            img = _dof(img, (fx, fy), 760, 0.32 * min(1.0, (macro_vis - 0.55) * 4))",
              "            img = _dof(img, (fx, fy), 900, 0.24 * min(1.0, (macro_vis - 0.55) * 4))")

p.write_text(s, encoding="utf-8")
print("patched end card + push + dof")
