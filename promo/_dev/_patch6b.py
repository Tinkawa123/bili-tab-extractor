from pathlib import Path

HERE = Path(__file__).resolve().parent
p = HERE / "film" / "film.py"
s = p.read_text(encoding="utf-8")

# start S6 with the page still large (continuity from S5)
s = s.replace("        sc = 0.5 * (1 - out * 0.55)", "        sc = 1.45 * (1 - out * 0.66)")

# centred couplet (x=None) + timing so logo appears after the type clears
s = s.replace('caption(img, "视频会划走，", 0, 300, t, 47.9, 53.2, D.PAPER, "serif", 112, 3.0, 600, rise=28, dur=0.7, align="center")',
              'caption(img, "视频会划走，", None, 352, t, 47.9, 52.35, D.PAPER, "serif", 112, 3.0, 600, rise=28, dur=0.7, align="center")')
s = s.replace('caption(img, "谱子会留下。", 0, 448, t, 49.35, 53.2, D.TEAL, "serif", 112, 3.0, 600, rise=28, dur=0.7, align="center")',
              'caption(img, "谱子会留下。", None, 500, t, 49.35, 52.35, D.TEAL, "serif", 112, 3.0, 600, rise=28, dur=0.7, align="center")')
s = s.replace('caption(img, "一键扒谱 · 专治手截", 0, 748, t, 55.4, 58.6, D.TEAL, "serif", 34, 3.0, 600, rise=14, dur=0.6, align="center")',
              'caption(img, "一键扒谱 · 专治手截", None, 748, t, 55.35, 58.9, D.TEAL, "serif", 34, 4.0, 600, rise=14, dur=0.6, align="center")')

# logo / wordmark timing + size
s = s.replace("    lp = remap(t, 52.85, 53.9, ease_out_cubic)\n    wm = remap(t, 53.6, 54.5, ease_out_cubic)\n    tg = remap(t, 54.4, 55.3, ease_out_cubic)",
              "    lp = remap(t, 52.55, 53.55, ease_out_cubic)\n    wm = remap(t, 53.35, 54.25, ease_out_cubic)\n    tg = remap(t, 54.05, 54.95, ease_out_cubic)")
s = s.replace("    mark = _logo_mark(lp, remap(t, 53.1, 53.9, ease_out_cubic))", "    mark = _logo_mark(lp, remap(t, 52.8, 53.55, ease_out_cubic))")
s = s.replace("        mx = (D.W - ms.w) / 2\n        my = 300", "        mx = (D.W - ms.w) / 2\n        my = 268")
s = s.replace('word = text_sprite("视频扒谱工具", D.PAPER, "sans_bold", 54, tracking=10.0)',
              'word = text_sprite("视频扒谱工具", D.PAPER, "sans_bold", 56, tracking=13.0)')
s = s.replace("        over(img, wipe(word, wm).with_opacity(wm), (D.W - word.w) / 2, 596)",
              "        over(img, wipe(word, wm).with_opacity(wm), (D.W - word.w) / 2, 552)")
s = s.replace('tag = text_sprite("B站教学视频  →  完整吉他谱  /  A4 PDF", D.GREY, "sans", 20, tracking=4.0)',
              'tag = text_sprite("B站教学视频  →  完整吉他谱  /  A4 PDF", D.GREY, "sans", 21, tracking=4.0)')
s = s.replace("        over(img, wipe(tag, tg).with_opacity(0.85 * tg), (D.W - tag.w) / 2, 676)",
              "        over(img, wipe(tag, tg).with_opacity(0.85 * tg), (D.W - tag.w) / 2, 640)")
s = s.replace("        foot = text_sprite(\"BILIBILI  →  PDF   ·   LOCAL  ·  FREE\", D.GREY_DIM, \"sans\", 13, tracking=4.0)",
              "        foot = text_sprite(\"BILIBILI  →  PDF   ·   LOCAL  ·  300 DPI\", D.GREY_DIM, \"sans\", 13, tracking=4.0)")

p.write_text(s, encoding="utf-8")
print("patched S6", len(s))
