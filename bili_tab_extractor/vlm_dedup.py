# -*- coding: utf-8 -*-
"""VLM 小节号去重辅助：批量读每行谱面小节号，找出"同一小节"的重复行。

用途（人工核验窗口）：
- 后台批量调用 Qwen-VL 读小节号（带缓存，同一图片只调一次）
- 相同小节号的行 → 判定为重复，标黄供人工确认（或自动删除）
"""

from __future__ import annotations

import hashlib
import json
import os

from vlm import DEFAULT_MODEL, read_bar_numbers


def _img_hash(img) -> str:
    """图片内容哈希（缓存 key）。"""
    import cv2

    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    data = buf.tobytes() if ok else img.tobytes()
    return hashlib.md5(data).hexdigest()


def read_bars_batch(rows, api_key: str | None = None,
                    cache_path: str | None = None,
                    progress=None, model: str | None = None,
                    stop_flag=None) -> dict[int, list[int]]:
    """批量读每行的小节号。

    rows: list[TabRow]
    progress: callable(done, total, row_index, bars) 进度回调
    stop_flag: 可选 callable() -> bool，返回 True 时中止
    返回: {row_index: [bar_numbers]}
    """
    cache: dict = {}
    if cache_path and os.path.isfile(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}

    results: dict[int, list[int]] = {}
    total = len(rows)
    dirty = False
    for i, row in enumerate(rows):
        if stop_flag and stop_flag():
            break
        h = _img_hash(row.image)
        if h in cache:
            results[i] = cache[h]
        else:
            try:
                data = read_bar_numbers(row.image, api_key=api_key,
                                        model=model or DEFAULT_MODEL)
            except Exception:
                data = {"bar_numbers": []}
            bars = data.get("bar_numbers") or []
            # 规范化：只保留整数
            clean = []
            for b in bars:
                try:
                    clean.append(int(b))
                except (TypeError, ValueError):
                    pass
            results[i] = clean
            cache[h] = clean
            dirty = True
        if progress:
            progress(i + 1, total, i, results[i])

    if cache_path and dirty:
        try:
            os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
        except Exception:
            pass
    return results


def find_duplicate_groups(bars_map: dict[int, list[int]]) -> list[list[int]]:
    """按小节号分组，返回"存在重复"的组（每组成员行索引，按小节号排序）。

    规则：同一小节号出现在多行 → 这些行疑似重复。
    只有至少 2 行共享同一个小节号才成组。
    """
    groups: dict[int, list[int]] = {}
    for idx, bars in bars_map.items():
        for b in set(bars):
            groups.setdefault(b, []).append(idx)
    dup_groups = []
    seen_sets = set()
    for b in sorted(groups):
        idxs = sorted(groups[b])
        if len(idxs) < 2:
            continue
        key = tuple(idxs)
        if key in seen_sets:  # 同一批行共享多个小节号时只记一次
            continue
        seen_sets.add(key)
        dup_groups.append(idxs)
    return dup_groups


def bar_label(bars: list[int]) -> str:
    """小节号列表 → 显示文本。"""
    if not bars:
        return ""
    if len(bars) == 1:
        return f"小节 {bars[0]}"
    return "小节 " + "-".join(str(b) for b in bars)
