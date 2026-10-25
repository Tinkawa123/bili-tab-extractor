# -*- coding: utf-8 -*-
"""生成合成测试视频：模拟 B 站吉他教学视频的典型画面。

画面 = 彩色背景（模拟演奏者/演播室）+ 底部白色谱面条带 + 播放光标。
谱面内容分 4 行（每行：五线谱 5 线 + TAB 6 线 + 音符数字），
前 5 秒显示行 1-2，后 5 秒翻页显示行 3-4；光标在每行上扫过。
"""

import numpy as np
import cv2
import os

W, H = 1280, 720
FPS = 30
SECONDS = 10
BAR_Y, BAR_H = 460, 250  # 谱面条带位置（画面下方），容纳 2 行谱


def make_tab_row(text: str, top: int) -> np.ndarray:
    """在白色条带内画一行谱（五线谱 + TAB），返回该区域图像。"""
    img = np.full((BAR_H, W, 3), 250, dtype=np.uint8)
    y = top
    # 五线谱 5 条
    for i in range(5):
        cv2.line(img, (40, y + 12 * i), (W - 40, y + 12 * i), (40, 40, 40), 2)
    # TAB 6 条
    for i in range(6):
        cv2.line(img, (40, y + 70 + 10 * i), (W - 40, y + 70 + 10 * i), (40, 40, 40), 2)
    cv2.putText(img, text, (50, y + 45), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (40, 40, 40), 2)
    return img


def render_frame(page_rows, cursor_pos) -> np.ndarray:
    """渲染一帧：彩色背景 + 底部谱面条带 + 光标。"""
    frame = np.full((H, W, 3), 30, dtype=np.uint8)
    # 模拟演奏画面的彩色渐变
    for x in range(W):
        frame[:, x] = (20 + x // 60, 25, 35 + x // 40)
    # 装饰
    cv2.circle(frame, (1000, 200), 90, (200, 120, 60), -1)
    cv2.rectangle(frame, (150, 150), (400, 350), (90, 130, 200), -1)

    # 谱面条带
    bar = np.full((BAR_H, W, 3), 250, dtype=np.uint8)
    for text, top in page_rows:
        row = make_tab_row(text, top)
        bar = np.where(row < 250, row, bar)
    frame[BAR_Y:BAR_Y + BAR_H] = bar

    # 播放光标（红色三角，位于当前行）
    if cursor_pos is not None:
        cx, cy = cursor_pos
        cv2.drawMarker(frame, (cx, BAR_Y + cy), (255, 0, 0),
                       cv2.MARKER_TRIANGLE_DOWN, 26, 5)
    return frame


def main():
    rows_page1 = [("1 3 5 7 9 12 15", 15), ("2 4 6 8 10 13 16", 150)]
    rows_page2 = [("3 5 7 9 11 14 17", 15), ("4 6 8 10 12 15 18", 150)]

    out = "test_video.mp4"
    if os.path.exists(out):
        os.remove(out)
    writer = cv2.VideoWriter(out, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    if not writer.isOpened():
        print("VideoWriter 打开失败（可能缺少编码器），尝试用 imageio-ffmpeg")
        import imageio_ffmpeg
        # fallback: 用 ffmpeg 逐帧写太麻烦，直接报错
        raise SystemExit("无法创建测试视频")

    t = 0
    while t < SECONDS * FPS:
        if t < 4 * FPS:
            rows, base = rows_page1, 0
        elif t < 6 * FPS:
            rows, base = rows_page2, 0  # 翻页过渡
        else:
            rows, base = rows_page2, 0
        # 光标在行 1 上从左到右扫（周期 4 秒）
        phase = (t % (4 * FPS)) / (4 * FPS)
        cursor = (int(80 + phase * 1100), 40) if phase < 1 else None
        frame = render_frame(rows, cursor)
        writer.write(frame)
        t += 1
    writer.release()
    print(f"测试视频已生成: {out} ({SECONDS}s, {FPS}fps, {W}x{H})")


if __name__ == "__main__":
    main()
