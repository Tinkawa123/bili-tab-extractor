# -*- coding: utf-8 -*-
"""抽帧模块：用 ffmpeg 从视频中每隔 interval 秒抽取一帧。

参考开源项目 marcelpanse/youtube-guitar-tab-parser 的 steps/frames.ts，
使用 ffmpeg 的 fps 滤镜（等价于 fps=1/interval），输出按序号命名的 PNG。
"""

from __future__ import annotations

import os
import subprocess

from download import resolve_ffmpeg
from util import log


def extract_frames(video_path: str, frames_dir: str, interval: float = 2.0) -> list[str]:
    """抽取帧到 frames_dir，返回排序后的帧文件路径列表（按时间顺序）。"""
    os.makedirs(frames_dir, exist_ok=True)
    ffmpeg = resolve_ffmpeg()
    pattern = os.path.join(frames_dir, "frame-%05d.png")

    log.step(f"用 ffmpeg 抽帧（每 {interval} 秒一帧）…")
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error",
         "-i", video_path, "-vf", f"fps=1/{interval}", pattern],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg 抽帧失败: {(proc.stderr or '').strip()[-1500:]}")

    files = sorted(
        f for f in os.listdir(frames_dir)
        if f.startswith("frame-") and f.endswith(".png")
    )
    if not files:
        raise RuntimeError("ffmpeg 未生成任何帧，请检查视频文件是否有效")
    paths = [os.path.join(frames_dir, f) for f in files]
    log.success(f"抽帧完成，共 {len(paths)} 帧")
    return paths
