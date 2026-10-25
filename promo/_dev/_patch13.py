from pathlib import Path

HERE = Path(__file__).resolve().parent
p = HERE / "film" / "film.py"
s = p.read_text(encoding="utf-8")

# ============ S1: the killer info gets its own beat and proper size
old = '''    # couplet
    caption(img, "谱面在滚。", 140, 306, t, 0.90, 5.95, D.PAPER, "serif", 104, 2.0, 600, rise=26)
    caption(img, "截图在追。", 140, 470, t, 2.92, 5.95, D.AMBER, "serif", 96, 2.0, 600, rise=26)
    # final line
    if t > 6.05:
        q = remap(t, 6.05, 6.6, ease_out_cubic)
        msg = text_sprite("37 张截图，拼不成一首歌。", D.hexc("#B9C4C6"), "sans", 26, tracking=1.4)
        over(img, wipe(msg, q).with_opacity(0.92), 144, 640)'''
new = '''    # couplet -> the real number
    caption(img, "谱面在滚。", 140, 300, t, 0.90, 4.95, D.PAPER, "serif", 104, 2.0, 600, rise=26)
    caption(img, "截图在追。", 140, 452, t, 2.92, 4.95, D.AMBER, "serif", 96, 2.0, 600, rise=26)
    caption(img, "37 张截图。", 140, 300, t, 5.12, 7.2, D.PAPER, "serif", 96, 2.0, 600, rise=24)
    caption(img, "0 张能用。", 140, 452, t, 5.85, 7.2, D.RED, "serif", 96, 2.0, 600, rise=24)'''
assert old in s
s = s.replace(old, new)

# stats block bigger / clearer
s = s.replace('lab = text_sprite("已截图", D.hexc("#8D999C"), "sans", 16, tracking=3.0)\n        over(img, lab, bx, 156)\n        num = text_sprite(f"{n:02d}", D.PAPER, "mono_bold", 38, tracking=1.0)',
              'lab = text_sprite("已截图", D.hexc("#A9B4B7"), "sans", 18, tracking=3.0)\n        over(img, lab, bx, 152)\n        num = text_sprite(f"{n:02d}", D.PAPER, "mono_bold", 46, tracking=1.0)')
s = s.replace('over(img, num, bx + bw - num.w, 140)', 'over(img, num, bx + bw - num.w, 134)')
s = s.replace('av = text_sprite("可用", D.hexc("#8D999C"), "sans", 16, tracking=3.0)\n        over(img, av, bx, 222)\n        z = text_sprite("00", D.RED, "mono_bold", 38, tracking=1.0)\n        over(img, z, bx + bw - z.w, 206)',
              'av = text_sprite("可用", D.hexc("#A9B4B7"), "sans", 18, tracking=3.0)\n        over(img, av, bx, 232)\n        z = text_sprite("00", D.RED, "mono_bold", 46, tracking=1.0)\n        over(img, z, bx + bw - z.w, 214)')

# ============ S3: human language, four short lines
old_s3 = '''    # small statement
    if t > 24.35:
        p = remap(t, 24.35, 24.95, ease_out_cubic)
        st = text_sprite("抽帧 → 拼接 → 去重 → 成页", D.GREY, "sans", 19, tracking=2.0)
        over(img, wipe(st, p).with_opacity(0.85), 148, 966)'''
new_s3 = '''    # human commentary (the section must not be 13 s of silence)
    for t_in, t_out, line in [
        (15.55, 17.05, "386 帧里，"),
        (17.15, 20.35, "挑出 48 行谱。"),
        (20.55, 23.95, "12 行重复，自动去掉。"),
        (24.15, 26.2, "拼成一整份。"),
    ]:
        caption(img, line, 148, 604, t, t_in, t_out, D.PAPER, "serif", 46, 1.5, 600, rise=16, dur=0.45)'''
assert old_s3 in s
s = s.replace(old_s3, new_s3)

# ============ S4: show "find back discarded rows" actually happening
old_toast = '''    # ---------- toast
    ta = remap(t, 31.0, 31.5, ease_out_cubic) * (1 - remap(t, 32.5, 33.0, ease_in_out_cubic))
    if ta > 0:
        tw2 = 320
        tx = lx + (cw - tw2) / 2
        over(B, rounded_rect(tw2, 44, 11, D.hexc("#0F1A18"), opacity=0.92 * ta), tx, 196)
        tt = text_sprite("AI 已识别 6 组重复", D.TEAL, "sans", 16, tracking=1.0)
        over(B, tt.with_opacity(ta), tx + 20, 209)'''
new_toast = '''    # ---------- toast (AI dedupe)
    ta = remap(t, 31.0, 31.5, ease_out_cubic) * (1 - remap(t, 32.4, 32.9, ease_in_out_cubic))
    if ta > 0:
        tw2 = 330
        tx = lx + (cw - tw2) / 2
        over(B, rounded_rect(tw2, 44, 11, D.hexc("#0F1A18"), opacity=0.92 * ta), tx, 196)
        tt = text_sprite("AI 已识别 6 组重复", D.TEAL, "sans", 16, tracking=1.0)
        over(B, tt.with_opacity(ta), tx + 20, 209)

    # ---------- "discarded rows can be found again" micro-beat
    fr = remap(t, 30.35, 30.95, ease_out_cubic)
    if fr > 0:
        fw2 = 420
        fx2 = lx + cw - fw2
        fy2 = 196
        over(B, rounded_rect(fw2, 44, 11, D.hexc("#101A18"), opacity=0.94 * fr), fx2, fy2)
        ft = text_sprite("已丢弃 3 行", D.hexc("#C9D4D2"), "sans", 15, tracking=1.0)
        over(B, ft.with_opacity(fr), fx2 + 18, fy2 + 13)
        over(B, rounded_rect(86, 30, 8, D.TEAL_DEEP, opacity=fr), fx2 + fw2 - 104, fy2 + 7)
        bl = text_sprite("找回", D.WHITE, "sans", 14, tracking=1.0)
        over(B, bl.with_opacity(fr), fx2 + fw2 - 104 + (86 - bl.w) / 2, fy2 + 14)
    # the recovered row slides back into the list
    rc = remap(t, 31.15, 31.85, ease_out_cubic)
    if rc > 0:
        rec = cards[6] if len(cards) > 6 else None
        if rec is None:
            rec = dict(id="r7", name="第 7 行", meta="1917×379 · t=12s", st="找回", thumb=6, y=slot * 4, op=1.0)
        ry2 = ly + slot * 3 + (1 - rc) * 46
        over(B, rounded_rect(cw, chh, 11, D.UI_PANEL, opacity=rc), lx, ry2)
        over(B, rounded_border(cw, chh, 11, 1.6, D.TEAL, opacity=rc), lx, ry2)
        spr = _rv_thumb(6)
        tw = int(spr.w * 52 / spr.h)
        over(B, spr.scaled(tw, 52), lx + 20, ry2 + 13, rc)
        nm = text_sprite("第 7 行", D.UI_TEXT, "sans_bold", 19, tracking=0.6)
        over(B, nm, lx + 334, ry2 + 14, rc)
        mt = text_sprite("1917×379 · t=12s", D.GREY_DIM, "mono", 12, tracking=0.8)
        over(B, mt, lx + 334, ry2 + 44, rc)
        chip = text_sprite("已找回", D.hexc("#1F6B45"), "sans", 13, tracking=1.0)
        over(B, rounded_rect(chip.w + 22, 26, 7, D.GREEN, opacity=0.3 * rc), lx + cw - 104, ry2 + 26)
        over(B, chip, lx + cw - 93, ry2 + 29, rc)'''
assert old_toast in s
s = s.replace(old_toast, new_toast)

# caption swap for the trust beat
s = s.replace('caption(img, "重复的，", 138, 620, t, 29.9, 32.3, D.TEAL, "serif", 44, 1.0, 600, rise=16, dur=0.5)\n    caption(img, "删掉。", 138, 680, t, 30.15, 32.3, D.TEAL, "serif", 44, 1.0, 600, rise=16, dur=0.5)',
              'caption(img, "丢了的，", 138, 606, t, 29.9, 32.3, D.TEAL, "serif", 44, 1.0, 600, rise=16, dur=0.5)\n    caption(img, "还能捡回来。", 138, 666, t, 30.15, 32.3, D.TEAL, "serif", 44, 1.0, 600, rise=16, dur=0.5)')

# ============ S5: the one spec that matters becomes a claim
s = s.replace('caption(img, "300 DPI · 整页排版", 140, 900, t, 41.4, 43.6, D.hexc("#C9B9A0"), "sans", 19, tracking=2.4, rise=12, dur=0.5)',
              'caption(img, "放大 4 倍，", 140, 856, t, 41.35, 43.6, D.PAPER, "serif", 44, 1.5, 600, rise=16, dur=0.5)\n    caption(img, "谱线不虚。", 140, 912, t, 41.7, 43.6, D.TEAL, "serif", 44, 1.5, 600, rise=16, dur=0.5)\n    if t > 42.2:\n        p = remap(t, 42.2, 42.8, ease_out_cubic)\n        spec = text_sprite("300 DPI · 整页排版", D.hexc("#9A8C72"), "sans", 16, tracking=2.0)\n        over(img, spec.with_opacity(0.75 * p), 142, 976)')

# ============ end card: product name is the hero, not a caption
s = s.replace('_stagger_text(img, "视频扒谱工具", 536, t, 52.55, 0.6, D.PAPER, "sans_bold", 56, 13.0, stagger=0.07, rise=20)',
              '_stagger_text(img, "视频扒谱工具", 528, t, 52.55, 0.6, D.PAPER, "sans_bold", 68, 14.0, stagger=0.07, rise=22)')
s = s.replace('_stagger_text(img, "B站教学视频  →  完整吉他谱  /  A4 PDF", 620, t, 53.35, 0.5, D.GREY, "sans", 21, 3.4, stagger=0.008, rise=12, opacity=0.9)',
              '_stagger_text(img, "B站教学视频  →  完整吉他谱  /  A4 PDF", 626, t, 53.35, 0.5, D.GREY, "sans", 23, 3.4, stagger=0.008, rise=12, opacity=0.92)')
s = s.replace('l2 = text_sprite("B站 / GitHub 搜索：视频扒谱工具", D.PAPER, "sans", 25, tracking=2.0)',
              'l2 = text_sprite("B站 / GitHub 搜索：视频扒谱工具", D.PAPER, "sans", 27, tracking=2.0)')

# ============ S2: keep the frame alive with a slow drift
s = s.replace("    scale = 1.0 + push * 0.95", "    scale = 1.0 + push * 0.95 + 0.012 * remap(t, 7.2, 13.2, ease_in_out_cubic)")

p.write_text(s, encoding="utf-8")
print("patched per judge C")
