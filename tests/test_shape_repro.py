# -*- coding: utf-8 -*-
"""形状安全回归测试（最小复现 + 断言）。

复现的真实 bug：BV1nU4y1r7xJ 的视频谱面是"整屏一行 + 横向滚动"，
crop_screen_top() 按每帧演奏画面实际高度裁顶部（有的裁 28px、有的裁 90px），
同一视频的裁剪帧高度变成 199px / 137px 不等；stitch_horizontal() 用
images[0] 的高度建画布后逐帧贴图：

    canvas[:, x:x2] = images[i][:, :x2 - x]
    ValueError: could not broadcast input array from shape (199,1270,3)
                into shape (137,1270,3)

同类隐患：estimate_shift（相位相关窗口按 a 的形状算）、stitch_scrolling
（vstack + canvas[y:y+h]=cur）、rows.dedup_rows / GUI 相似度（逐像素差）。

运行：python test_shape_repro.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
import numpy as np

from rows import dedup_rows
from stitch import (crop_screen_top, estimate_shift, is_transition_frame,
                    make_pdf_from_rows, normalize_heights, normalize_shapes,
                    split_long_image, split_wide_image, stitch_horizontal,
                    stitch_scrolling)
from util import imwrite

W = 1270          # 真实视频的裁剪宽度
SHORT, TALL = 137, 199   # 真实视频里出现的不等高度
PASS, FAIL = [], []


def check(name: str, fn):
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        FAIL.append(name)
        print(f"[FAIL] {name}: {type(e).__name__}: {e}")
        traceback.print_exc()
    else:
        PASS.append(name)
        print(f"[OK]   {name}")


# ---------- 合成帧 ----------

def make_global(h: int = TALL, width: int = W * 3) -> np.ndarray:
    """造一张宽 3W 的"完整谱面"：白底 + TAB 谱线 + 小节线/数字 + 噪点。"""
    rng = np.random.default_rng(7)
    img = np.full((h, width, 3), 255, np.uint8)
    base = h - 20                      # 谱面底边（内容底部对齐）
    for k in range(6):                 # TAB 六条线
        y = base - k * 10
        cv2.line(img, (0, y), (width - 1, y), (0, 0, 0), 2)
    for bx in range(60, width, 300):   # 小节线 + 小节号
        cv2.line(img, (bx, base - 52), (bx, base), (0, 0, 0), 2)
        cv2.putText(img, str(bx // 300 + 1), (bx + 8, base - 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    img[rng.integers(0, 2, size=(h, width), dtype=np.uint8).astype(bool)] = 0
    return img


def cut_top(img: np.ndarray, cut: int) -> np.ndarray:
    """模拟 crop_screen_top：只裁掉顶部 cut 行（内容底部对齐）。"""
    return np.ascontiguousarray(img[cut:]) if cut else img.copy()


# ---------- 1. 最小复现：stitch_horizontal 混合高度 ----------

def t_stitch_horizontal_mixed():
    g = make_global()
    # 五帧、横向位置 0/200/400/600/800；第 0、4 帧多裁 62px（多数帧=199px，
    # 与真实视频一致：88 帧 199px、6 帧 137px）。
    x0s = [0, 200, 400, 600, 800]
    cuts = [62, 0, 0, 0, 62]
    frames = [cut_top(g[:, x:x + W], c) for x, c in zip(x0s, cuts)]
    assert [f.shape[0] for f in frames] == [SHORT, TALL, TALL, TALL, SHORT], \
        [f.shape[0] for f in frames]

    shifts = [0.0] + [float(x0s[i - 1] - x0s[i]) for i in range(1, len(x0s))]
    segs = stitch_horizontal(frames, shifts)
    assert segs, "混合高度帧应能拼接出至少一段"
    seg = segs[0]
    assert seg.ndim == 3 and seg.shape[2] == 3, seg.shape
    # 画布高度 = 多数帧高度（199），宽度覆盖 800 + W
    assert seg.shape[0] == TALL, (seg.shape, TALL)
    assert seg.shape[1] == 800 + W, seg.shape
    # 内容对齐：修正方向后 canvas 坐标 == 全局坐标，底部 137 行逐像素一致
    got = seg[TALL - SHORT:, :]
    want = g[TALL - SHORT:, :seg.shape[1]]
    diff = float((got != want).mean())
    assert diff < 0.001, f"拼接内容与全局参考不一致 diff={diff:.4f}"
    # 顶部（只有 199px 高帧最后覆盖的区域）不能被白边覆盖：
    # 第 1 帧（cut=0，完整 199px）在 canvas x=200..400 处是最后写入者
    assert np.array_equal(seg[:TALL - SHORT, 200:400], g[:TALL - SHORT, 200:400]), \
        "高帧顶部内容被白边覆盖"


# ---------- 2. estimate_shift 不同高度 ----------

def t_estimate_shift_mixed():
    a = cut_top(make_global(), 0)
    b = cut_top(make_global(), 62)[:, 200:200 + W]
    b = np.ascontiguousarray(b)
    dx, dy, resp = estimate_shift(a[:, :W], b)
    assert np.isfinite(dx) and np.isfinite(dy) and np.isfinite(resp)
    assert resp > 0.05, f"相关性过低 resp={resp}"
    assert abs(dy) < 3, f"纵向位移应接近 0，实际 {dy}"


# ---------- 3. stitch_scrolling 混合高度（读盘 → 纵向拼接） ----------

def t_stitch_scrolling_mixed(tmp: str):
    # 全局长图：每 40px 一条带编号的横线，便于验证纵向拼接的顺序与对齐
    gh, gw = 700, W
    g = np.full((gh, gw, 3), 255, np.uint8)
    for k, y in enumerate(range(20, gh, 40)):
        cv2.line(g, (0, y), (gw - 1, y), (0, 0, 0), 3)
        cv2.putText(g, str(k), (30, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                    (0, 0, 0), 2)
    rng = np.random.default_rng(3)
    g[rng.integers(0, 2, size=g.shape[:2]).astype(bool)] = 0

    paths, frames = [], []
    for i, cut in enumerate([62, 0, 62, 0, 0, 62]):   # 混合高度
        top = i * 40
        frame = cut_top(g[top:top + TALL], cut)
        p = os.path.join(tmp, f"scroll-{i}.png")
        imwrite(p, frame)
        paths.append(p)
        frames.append(frame)
    shifts = [0.0] + [estimate_shift(frames[i - 1], frames[i])[1]
                      for i in range(1, len(frames))]
    segs = stitch_scrolling(paths, shifts)
    assert segs, "滚动拼接应产出至少一段"
    seg = segs[0]
    assert seg.ndim == 3 and seg.shape[2] == 3 and seg.shape[0] > 0, seg.shape
    # 内容顺序/对齐：与全局参考在某个偏移处几乎逐像素相等（flush 会裁掉
    # 段首尾空白，所以偏移不固定）；帧序颠倒时差异会 >100，能明显区分
    best = min(
        ((int(off), float(np.abs(seg.astype(np.int16)
                                - g[off:off + seg.shape[0]].astype(np.int16)).mean()))
         for off in range(0, gh - seg.shape[0] + 1)),
        key=lambda t: t[1])
    assert best[1] < 8.0, f"纵向拼接错位: {best}"


# ---------- 4. crop_screen_top 调用链 ----------

def t_crop_screen_top():
    img = np.full((240, W, 3), 255, np.uint8)
    img[:60] = 30                       # 顶部 60 行为深色演奏画面
    out = crop_screen_top(img)
    assert out.ndim == 3 and out.shape[2] == 3
    assert out.shape[0] < 240 and out.shape[0] > 0, out.shape


# ---------- 4b. 过场帧（黑屏/淡入淡出）识别 ----------

def t_transition_frame():
    black = np.zeros((199, W, 3), np.uint8)
    assert is_transition_frame(black), "纯黑帧应判为过场帧"
    fade = np.full((199, W, 3), 40, np.uint8)
    assert is_transition_frame(fade), "近黑低反差帧应判为过场帧"
    tab = make_global(width=W)
    assert not is_transition_frame(tab), "正常谱面帧不应被误判"
    # 暗色主题（低亮度但高反差）不应被误判
    dark_tab = np.full((199, W, 3), 20, np.uint8)
    cv2.line(dark_tab, (0, 100), (W - 1, 100), (255, 255, 255), 3)
    cv2.putText(dark_tab, "3 5 7 3 5 7", (100, 140),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
    assert not is_transition_frame(dark_tab), "暗色主题谱面不应被误判"


# ---------- 5. normalize_heights / normalize_shapes ----------

def t_normalize():
    g = make_global()
    frames = [cut_top(g[:, :W], c) for c in (62, 0, 62, 0)]
    out = normalize_heights(frames)
    assert {f.shape[0] for f in out} == {TALL}, [f.shape[0] for f in out]
    # 底部对齐：底部 100 行内容不得改变
    for src, dst in zip(frames, out):
        assert np.array_equal(src[-100:], dst[-100:]), "底部内容被改动"
    # 宽度统一
    out2 = normalize_shapes([f[:, :600] for f in frames[:2]] + [g[:, :600]])
    assert len({f.shape for f in out2}) == 1, [f.shape for f in out2]


# ---------- 6. 行级去重：高度/宽度不等 ----------

def t_dedup_rows_mixed():
    g = make_global(width=W)
    row_same_tall = g.copy()
    row_same_short = cut_top(g, 62)          # 同一行，高度不同
    row_other = np.full((SHORT, W, 3), 255, np.uint8)
    cv2.line(row_other, (0, 60), (W - 1, 60), (0, 0, 0), 3)
    rows = [(row_same_tall, "a", 0), (row_same_short, "a", 1),
            (row_other, "a", 2)]
    kept = dedup_rows(rows)                  # 修复前：广播错误
    assert isinstance(kept, list)
    assert all(k[0].ndim == 3 for k in kept)


# ---------- 7. split_wide_image / split_long_image ----------

def t_splits():
    g = make_global(width=W * 4)
    parts = split_wide_image(g, 2400)
    assert parts and all(p.shape[0] == g.shape[0] for p in parts), \
        [p.shape for p in parts]
    # 退化输入不应崩
    assert split_wide_image(np.zeros((0, 10, 3), np.uint8)) == []
    assert split_long_image(np.zeros((0, 10, 3), np.uint8)) == []


# ---------- 8. PDF：混合高度 + 灰度/RGBA 行 ----------

def t_pdf_mixed(tmp: str):
    g = make_global(width=W)
    rows = [
        (g.copy(), "a", 0),                              # 199px BGR
        (cut_top(g, 62), "a", 1),                        # 137px BGR
        (cv2.cvtColor(cut_top(g, 62), cv2.COLOR_BGR2GRAY), "a", 2),  # 灰度
        (cv2.cvtColor(g[:150], cv2.COLOR_BGR2BGRA), "a", 3),         # RGBA
    ]
    out = os.path.join(tmp, "mixed.pdf")
    n = make_pdf_from_rows(rows, out, "形状安全测试")
    assert os.path.isfile(out) and os.path.getsize(out) > 1000
    assert n >= 1, n


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="shape_test_")
    try:
        print("输入帧高度：", [SHORT, TALL])
        check("stitch_horizontal(137/199 混合高度)", t_stitch_horizontal_mixed)
        check("estimate_shift(137 vs 199)", t_estimate_shift_mixed)
        check("stitch_scrolling(混合高度)", lambda: t_stitch_scrolling_mixed(tmp))
        check("crop_screen_top", t_crop_screen_top)
        check("is_transition_frame(黑屏/暗色主题)", t_transition_frame)
        check("normalize_heights/normalize_shapes", t_normalize)
        check("dedup_rows(高度不等)", t_dedup_rows_mixed)
        check("split_wide_image/split_long_image", t_splits)
        check("make_pdf_from_rows(混合高度/灰度/RGBA)", lambda: t_pdf_mixed(tmp))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        print("失败项：", FAIL)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
