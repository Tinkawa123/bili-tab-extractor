# -*- coding: utf-8 -*-
"""生成 App 图标候选方案（4x 超采样，输出多尺寸 PNG/ICO）。

用法：python promo/gen_icon.py
输出：promo/icons/ 下 icon_a/b/c_256.png + 选定方案的 icon.ico
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
os.makedirs(OUT_DIR, exist_ok=True)

# 配色（与 GUI 一致）
BLACK = (26, 26, 26)
WHITE = (255, 255, 255)
TEAL = (0, 121, 107)
TEAL_LIGHT = (0, 150, 136)
YELLOW = (255, 213, 79)
GREY = (128, 128, 128)

SS = 4          # 超采样倍数
SIZE = 256      # 目标尺寸
BIG = SIZE * SS


def _rounded_rect(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def scheme_a() -> Image.Image:
    """方案 A：深色圆角块 + 六线谱（青绿）+ TAB 数字点 + 右下白色播放三角。"""
    img = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = int(BIG * 0.10)
    _rounded_rect(d, (pad, pad, BIG - pad, BIG - pad), int(BIG * 0.22), BLACK)
    # 六线谱
    x0, x1 = int(BIG * 0.20), int(BIG * 0.80)
    y_top = int(BIG * 0.22)
    gap = int(BIG * 0.085)
    lw = max(2, int(BIG * 0.010))
    for k in range(6):
        y = y_top + k * gap
        d.line([(x0, y), (x1, y)], fill=TEAL_LIGHT, width=lw)
    # 小节线
    d.line([(int(BIG * 0.62), y_top), (int(BIG * 0.62), y_top + 5 * gap)],
           fill=TEAL, width=lw)
    # TAB 数字点：对齐到谱线上（像谱面上的数字）
    rx = int(BIG * 0.020)
    for (cx, line_idx) in [(0.28, 1), (0.39, 3), (0.50, 2), (0.55, 4)]:
        px = int(BIG * cx)
        py = y_top + line_idx * gap
        _rounded_rect(d, (px - rx, py - rx, px + rx, py + rx), rx, WHITE)
    # 右下播放三角
    tri = [(int(BIG * 0.68), int(BIG * 0.70)),
           (int(BIG * 0.68), int(BIG * 0.86)),
           (int(BIG * 0.83), int(BIG * 0.78))]
    d.polygon(tri, fill=WHITE)
    return img.resize((SIZE, SIZE), Image.LANCZOS)


def scheme_b() -> Image.Image:
    """方案 B：白底文档 + 谱线 + 青绿 PDF 折角（亮色版）。"""
    img = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = int(BIG * 0.12)
    _rounded_rect(d, (pad, pad, BIG - pad, BIG - pad), int(BIG * 0.20), WHITE)
    # 文档折角（右上）
    fx, fy = int(BIG * 0.72), int(BIG * 0.12)
    fs = int(BIG * 0.16)
    d.polygon([(fx, fy), (fx + fs, fy), (fx + fs, fy + fs)], fill=TEAL)
    # 谱线
    x0, x1 = int(BIG * 0.24), int(BIG * 0.72)
    y0 = int(BIG * 0.32)
    gap = int(BIG * 0.075)
    lw = max(2, int(BIG * 0.012))
    for k in range(5):
        y = y0 + k * gap
        d.line([(x0, y), (x1, y)], fill=BLACK, width=lw)
    # 播放三角（青绿）
    tri = [(int(BIG * 0.30), int(BIG * 0.66)),
           (int(BIG * 0.30), int(BIG * 0.80)),
           (int(BIG * 0.42), int(BIG * 0.73))]
    d.polygon(tri, fill=TEAL)
    return img.resize((SIZE, SIZE), Image.LANCZOS)


def scheme_c() -> Image.Image:
    """方案 C：极简——圆角方块 + 三条粗谱线 + 青绿播放键（最简洁）。"""
    img = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = int(BIG * 0.08)
    _rounded_rect(d, (pad, pad, BIG - pad, BIG - pad), int(BIG * 0.26), BLACK)
    # 三条粗线
    x0, x1 = int(BIG * 0.24), int(BIG * 0.76)
    for k, yf in enumerate((0.34, 0.48, 0.62)):
        y = int(BIG * yf)
        lw = int(BIG * 0.035)
        color = TEAL_LIGHT if k != 1 else WHITE
        d.line([(x0, y), (x1, y)], fill=color, width=lw)
    # 播放三角（青绿）
    tri = [(int(BIG * 0.40), int(BIG * 0.70)),
           (int(BIG * 0.40), int(BIG * 0.86)),
           (int(BIG * 0.58), int(BIG * 0.78))]
    d.polygon(tri, fill=TEAL_LIGHT)
    return img.resize((SIZE, SIZE), Image.LANCZOS)


def main():
    schemes = {"a": scheme_a, "b": scheme_b, "c": scheme_c}
    for name, fn in schemes.items():
        icon = fn()
        p256 = os.path.join(OUT_DIR, f"icon_{name}_256.png")
        icon.save(p256)
        # 小尺寸预览（检查可读性）
        for sz in (16, 32, 48, 64, 128):
            icon.resize((sz, sz), Image.LANCZOS).save(
                os.path.join(OUT_DIR, f"icon_{name}_{sz}.png"))
        print(f"生成: {p256}")

    # 默认用方案 A 生成 ICO（多尺寸，Windows 图标）
    ico_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    base = schemes["a"]()
    ico_path = os.path.join(OUT_DIR, "icon.ico")
    base.save(ico_path, format="ICO", sizes=ico_sizes)
    print(f"生成: {ico_path}")


if __name__ == "__main__":
    main()
