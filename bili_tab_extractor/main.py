# -*- coding: utf-8 -*-
"""B站吉他谱视频 → PDF 提取工具（CLI 入口，复用 pipeline 流程）。

用法:
    python main.py <bilibili_url> [选项]
    python main.py --video 本地视频.mp4 [选项]

流程: 下载(B站) → 抽帧 → 谱面区域检测 → 裁剪 → 行级切分去重 → 拼接PDF
与 GUI（gui.py）共用 pipeline.py，保证行为一致。
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys

# 沙箱/打包环境下 pylibs 注入
_PYLIBS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pylibs")
if os.path.isdir(_PYLIBS) and _PYLIBS not in sys.path:
    sys.path.insert(0, _PYLIBS)

from pipeline import process
from stitch import make_pdf_from_rows, verify_and_clean_pdf
from util import log


def _safe(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    # 防目录穿越与 Windows 保留名
    if name in ("", ".", ".."):
        return "tab"
    if name.upper() in ("CON", "PRN", "AUX", "NUL") or name[1:2] == ":":
        return "tab_" + name
    return name[:80] or "tab"


def _unique_path(path: str) -> str:
    """同名文件自动重命名：xxx.pdf -> xxx(1).pdf -> xxx(2).pdf ..."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    n = 1
    while os.path.exists(f"{base}({n}){ext}"):
        n += 1
    return f"{base}({n}){ext}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="把 B 站吉他教学视频中的实时谱面提取并拼接为完整 PDF")
    parser.add_argument("url", nargs="?", default=None,
                        help="B 站视频 URL（支持 https://www.bilibili.com/video/BV…）")
    parser.add_argument("--video", default=None,
                        help="本地视频文件路径（跳过下载，直接处理）")
    parser.add_argument("--title", default=None,
                        help="PDF 标题（默认用视频标题/文件名）")
    parser.add_argument("--interval", type=float, default=2.0,
                        help="抽帧间隔秒数（默认 2；滚动快的视频可调小到 1）")
    parser.add_argument("--sample", type=int, default=6,
                        help="谱面区域检测的采样帧数（默认 6）")
    parser.add_argument("--max-height", type=int, default=0,
                        help="下载分辨率上限（默认 0=最高清晰度；越小越快）")
    parser.add_argument("--cookies", default=None,
                        help="B 站 cookies 文件路径（部分视频需登录）")
    parser.add_argument("--box", default=None,
                        help="直接指定谱面区域 x0,y0,x1,y1（归一化 0~1000），跳过自动检测")
    parser.add_argument("--rows-per-page", type=int, default=0,
                        help="每页谱面行数（默认 0 = 自动填满一页）")
    parser.add_argument("--out", default=None,
                        help="输出目录（默认 out/<视频标题>/）")
    args = parser.parse_args()

    if not args.url and not args.video:
        parser.print_help()
        return

    import tempfile

    work = tempfile.mkdtemp(prefix="bili_tab_", dir=os.getcwd())
    try:
        result = process(
            url=args.url,
            video=args.video,
            title=args.title,
            interval=args.interval,
            sample=args.sample,
            max_height=args.max_height if args.max_height > 0 else 720,
            cookies=args.cookies,
            box_arg=args.box,
            work_dir=work,
        )
        title = result.title
        kept_rows = result.kept_rows
        if not kept_rows:
            raise RuntimeError("没有保留任何谱面行，请调整参数重试")

        out_dir = args.out or os.path.join("out", _safe(title))
        os.makedirs(out_dir, exist_ok=True)
        pdf_path = _unique_path(os.path.join(out_dir, f"{_safe(title)}.pdf"))
        if pdf_path != os.path.join(out_dir, f"{_safe(title)}.pdf"):
            log.info(f"检测到同名文件，输出重命名为: {os.path.basename(pdf_path)}")

        # 图片文件夹
        img_dir = os.path.join(out_dir, "谱行图片")
        os.makedirs(img_dir, exist_ok=True)
        for i, row in enumerate(kept_rows):
            from util import imwrite

            imwrite(os.path.join(img_dir, f"行{i + 1:03d}.png"), row.image)
        log.success(f"谱行图片: {img_dir}")

        make_pdf_from_rows([(r.image, r.source, r.index) for r in kept_rows],
                           pdf_path, title, rows_per_page=args.rows_per_page)
        verify_and_clean_pdf(pdf_path)
        log.success(f"PDF: {pdf_path}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
