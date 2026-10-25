# -*- coding: utf-8 -*-
"""端到端验证：URL/本地视频 → pipeline.process → PDF（不启动 GUI）。

用法:
    python test_e2e.py --url https://www.bilibili.com/video/BV1nU4y1r7xJ/
    python test_e2e.py --video ..\test_bv19f.mp4
    python test_e2e.py --url ... --api-key        # 用 DASHSCOPE_API_KEY 走 VLM 路径

检查项：处理不抛异常、有谱行输出、PDF 生成、PDF 页数/大小合理、
行高度分布（确认没有混合形状导致的崩溃）。
"""
from __future__ import annotations

import argparse
import collections
import os
import sys
import time
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import cv2

from pipeline import process
from stitch import make_pdf_from_rows, verify_and_clean_pdf
from util import imwrite, log


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=None)
    ap.add_argument("--video", default=None)
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--work", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--api-key", action="store_true",
                    help="使用环境变量 DASHSCOPE_API_KEY 走 VLM 识别路径")
    args = ap.parse_args()

    tag = "url" if args.url else "local"
    stamp = time.strftime("%H%M%S")
    work = args.work or os.path.join(os.path.dirname(_HERE),
                                     f"_e2e_work_{tag}_{stamp}")
    out_dir = args.out or os.path.join(os.path.dirname(_HERE),
                                       f"_e2e_out_{tag}_{stamp}")
    os.makedirs(work, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)

    key = os.environ.get("DASHSCOPE_API_KEY") if args.api_key else None

    def prog(text, frac=0.0):
        print(f"  [{frac:3.0f}%] {text}", flush=True)

    t0 = time.time()
    try:
        result = process(url=args.url, video=args.video,
                         interval=args.interval, work_dir=work,
                         progress=prog, api_key=key, allow_manual=False)
    except Exception:
        print("=== pipeline.process 失败 ===")
        traceback.print_exc()
        return 1

    rows = result.kept_rows
    print(f"\n处理完成：all_rows={len(result.all_rows)} kept={len(rows)} "
          f"耗时 {time.time() - t0:.1f}s")
    if not rows:
        print("没有保留任何谱行 → PDF 无法生成")
        return 2
    print("行尺寸分布:", collections.Counter(
        (r.image.shape[1], r.image.shape[0]) for r in rows).most_common(6))

    # 保存谱行图片（与 main.py 一致）
    img_dir = os.path.join(out_dir, "谱行图片")
    os.makedirs(img_dir, exist_ok=True)
    for i, r in enumerate(rows):
        imwrite(os.path.join(img_dir, f"行{i + 1:03d}.png"), r.image)

    pdf = os.path.join(out_dir, f"{tag}.pdf")
    pages = make_pdf_from_rows([(r.image, r.source, r.index) for r in rows],
                               pdf, result.title or tag)
    try:
        pages = verify_and_clean_pdf(pdf)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] PDF 后检查跳过: {e}")
    size = os.path.getsize(pdf)
    print(f"PDF: {pdf} 页数={pages} 大小={size / 1024:.0f}KB")
    if pages < 1 or size < 5000:
        print("PDF 输出异常")
        return 3
    print("端到端通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
