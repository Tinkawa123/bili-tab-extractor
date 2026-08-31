# -*- coding: utf-8 -*-
"""B站视频下载模块：基于 yt-dlp（Python API，兼容源码运行与 PyInstaller 打包）。

参考开源项目 rohin-garg/youtube-guitar-tab-parser 的 download_frames.py，
针对 B 站做适配，并**使用 yt-dlp 的 Python API 而非子进程**：
- PyInstaller 打包后无法 `exe -m yt_dlp`，Python API 直接 import 即用；
- ffmpeg 合并通过 imageio_ffmpeg 定位（打包后也在包内）。
"""

from __future__ import annotations

import os
import re
import shutil

# 模块级 import：确保 PyInstaller 打包时收集 yt_dlp 包本体
import yt_dlp  # noqa: F401

from util import log


def resolve_ffmpeg() -> str:
    """返回可用的 ffmpeg 可执行文件路径。"""
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:  # pragma: no cover
        raise SystemExit(
            "未找到 ffmpeg。请安装 ffmpeg 并加入 PATH，或执行: pip install imageio-ffmpeg"
        ) from e


def _ffmpeg_exe_path() -> str | None:
    """返回 ffmpeg 可执行文件完整路径（供 yt-dlp 的 ffmpeg_location）。

    yt-dlp 的 ffmpeg_location 既接受目录也接受可执行文件本身的路径。
    直接传 imageio-ffmpeg 的 exe 路径（名字带版本号）即可，无需创建
    ffmpeg.exe 别名（避免打包后 _MEI 临时目录不可写导致别名失败）。
    兼容源码运行与 PyInstaller 打包。
    """
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.isfile(exe):
            return exe
    except Exception:
        pass
    p = shutil.which("ffmpeg")
    if p:
        return p
    return None


def download_video(url: str, out_path: str, max_height: int = 720,
                   cookies: str | None = None,
                   progress_hook=None) -> str:
    """用 yt-dlp Python API 下载 B 站视频到 out_path，返回视频标题。

    progress_hook: 可选回调 dict -> None（yt-dlp 进度事件）。
    """
    url = url.replace("\\", "").strip()
    if not re.match(r"^https?://", url):
        raise ValueError(f'"{url}" 不是合法的 URL')

    import yt_dlp  # noqa: F401  (模块顶部已导入；此处仅为语义清晰)

    ff_exe = _ffmpeg_exe_path()
    ydl_opts = {
        "format": (
            f"bestvideo[height<={max_height}]+bestaudio/"
            f"best[height<={max_height}]/best"
        ),
        "outtmpl": out_path,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "overwrites": True,
    }
    if ff_exe:
        # yt-dlp 的 ffmpeg_location 支持可执行文件路径
        ydl_opts["ffmpeg_location"] = ff_exe
    if cookies:
        ydl_opts["cookiefile"] = cookies
    if progress_hook:
        ydl_opts["progress_hooks"] = [progress_hook]

    log.step(f"下载视频 (≤{max_height}p)…")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as e:
        raise RuntimeError(f"yt-dlp 下载失败: {e}") from e

    if not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
        raise RuntimeError("yt-dlp 未生成视频文件，下载可能失败")

    title = (info or {}).get("title") or "tab"
    log.success(f'视频已下载: "{title}"')
    return title
