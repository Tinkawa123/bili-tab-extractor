# -*- coding: utf-8 -*-
"""日志工具 + 中文路径兼容的图像 IO。

本模块被所有子模块导入；在其顶部完成 pylibs 注入：沙箱环境无法写系统
site-packages，本地安装的 yt-dlp/img2pdf/imageio-ffmpeg 放在工作区
pylibs/ 下，需手动加入模块搜索路径。
"""

from __future__ import annotations

import os
import sys

_PYLIBS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pylibs")
if os.path.isdir(_PYLIBS) and _PYLIBS not in sys.path:
    sys.path.insert(0, _PYLIBS)

import cv2
import numpy as np


def _color(text: str, code: str) -> str:
    # PyInstaller --windowed 下 sys.stdout 可能为 None
    try:
        if not sys.stdout.isatty():
            return text
    except Exception:
        return text
    return f"\033[{code}m{text}\033[0m"


def step(msg: str) -> None:
    print(_color(f"[步骤] {msg}", "36"), flush=True)


def success(msg: str) -> None:
    print(_color(f"[完成] {msg}", "32"), flush=True)


def warn(msg: str) -> None:
    print(_color(f"[警告] {msg}", "33"), flush=True)


def error(msg: str) -> None:
    print(_color(f"[错误] {msg}", "31"), flush=True)


def info(msg: str) -> None:
    print(f"[信息] {msg}", flush=True)


class _Log:
    """日志命名空间，供 `from util import log` 使用。"""

    step = staticmethod(step)
    success = staticmethod(success)
    warn = staticmethod(warn)
    error = staticmethod(error)
    info = staticmethod(info)


log = _Log()


def imread(path: str, flags: int = cv2.IMREAD_COLOR):
    """cv2.imread 的中文路径兼容版（cv2 底层用 fopen，不支持非 ASCII 路径）。

    文件缺失/不可读时返回 None（与 cv2.imread 约定一致）。
    """
    try:
        data = np.fromfile(path, dtype=np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, flags)


def imwrite(path: str, img, params=None) -> bool:
    """cv2.imwrite 的中文路径兼容版。"""
    ext = os.path.splitext(path)[1] or ".png"
    ok, buf = cv2.imencode(ext, img, params if params is not None else [])
    if ok:
        buf.tofile(path)
    return ok
