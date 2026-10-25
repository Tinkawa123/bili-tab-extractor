# -*- coding: utf-8 -*-
"""VLM 主导的谱面识别与去重。

思路：每行谱面交给 Qwen-VL 提取结构化内容（和弦序列 / 节奏型 / 歌词 / 小节号），
再基于**语义**判断两行是否重复（替代/补强像素指纹）：

1. 小节号相同（若有）→ 重复（最强信号）
2. 和弦序列相同 且 节奏型相同 → 重复
3. 和弦序列相同但节奏不同 → 不同段落，保留
4. 歌词相同 → 重复（歌词行）
"""

from __future__ import annotations

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from vlm import DEFAULT_MODEL, _array_to_data_url, _call, load_api_key

ROW_ANALYSIS_PROMPT = """你是一个专业的吉他谱识别助手。这张图片是截取的一行吉他谱（可能包含：和弦图、六线谱TAB、五线谱、歌词）。

请精确识别并输出 JSON（只输出 JSON，不要其他文字）：
{
  "is_complete": true/false,
  "row_type": "chord_diagram | tab | lyrics | mixed | other",
  "chords": ["按从左到右出现顺序列出和弦名，如 F, C/E, Dm, Am"],
  "rhythm": "这一行的节奏型/扫弦型，如：下 下上 上下上（x 闷音）",
  "lyrics": "这一行对应的歌词（没有则空字符串）",
  "bar_numbers": [谱面上印着的小节号序号；没有或不确定则空数组],
  "bar_count": 这一行包含的小节数量（整数，估计 0）,
  "content": "一句话概括这一行的音乐内容，如：F-C/E-Dm-Am 和弦图 + 八分扫弦"
}

判断要点：
- **is_complete**：这一行是否**可作为独立谱行收录**。判定标准：
  * true：有完整的谱线结构（TAB 六线谱/五线谱线条横贯整行）并带音符/指法/节奏标记；
    或有完整的和弦图组（多个和弦图 + 下方谱线）；或是一整行**歌词**；
    **没有和弦图的纯 TAB 行也是完整行（true）**，不要因为"没有和弦/没有小节结构"就判 false；
  * false：只有**碎片**——如只有几个孤立数字、只有和弦图一角（谱线缺失）、
    一大片留白、只有一行孤立的节拍说明/水印文字。
- chords 按谱面上和弦出现的顺序列出（和弦图上方标注的和弦名）；
- rhythm 描述扫弦/拨弦的节奏走向（下、上、上下、x 闷音等）；
- bar_numbers 是每小节开头的独立序号（1、2、3…），
  **绝对不要**把 TAB 六线谱上的拨弦数字（如 0-2-3）当作小节号；分不清就留空数组；
- 若这一行是纯歌词，row_type=lyrics，chords 为空。
"""


def _img_hash(img) -> str:
    import cv2

    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    data = buf.tobytes() if ok else img.tobytes()
    return hashlib.md5(data).hexdigest()


def analyze_row(img, api_key: str | None = None, model: str | None = None,
                timeout: float = 90.0) -> dict:
    """分析一行谱面，返回结构化内容。"""
    return _call(api_key, model or DEFAULT_MODEL,
                 ROW_ANALYSIS_PROMPT, _array_to_data_url(img), timeout)


def _normalize_analysis(data: dict) -> dict:
    """规范识别结果（补默认值、清洗）。"""
    if not isinstance(data, dict):
        return {}
    out = {
        "is_complete": bool(data.get("is_complete", True)),
        "row_type": str(data.get("row_type") or "other").strip().lower(),
        "chords": [str(c).strip() for c in (data.get("chords") or []) if str(c).strip()],
        "rhythm": str(data.get("rhythm") or "").strip(),
        "lyrics": str(data.get("lyrics") or "").strip(),
        "bar_numbers": [],
        "bar_count": 0,
        "content": str(data.get("content") or data.get("description") or "").strip(),
    }
    for b in (data.get("bar_numbers") or []):
        try:
            out["bar_numbers"].append(int(b))
        except (TypeError, ValueError):
            pass
    try:
        out["bar_count"] = int(data.get("bar_count") or 0)
    except (TypeError, ValueError):
        out["bar_count"] = 0
    # 若 row_type 缺失但有和弦/歌词，推断
    if out["row_type"] in ("", "other") and out["chords"]:
        out["row_type"] = "mixed"
    return out


def analyze_rows(rows, api_key: str | None = None, model: str | None = None,
                 cache_path: str | None = None, progress=None,
                 max_workers: int = 4, stop_flag=None,
                 stats: dict | None = None) -> dict[int, dict]:
    """批量分析所有行（并发 + 缓存）。

    progress: callable(done, total)
    stats: 可选 dict，回填 {"failed": 失败数, "total": 总行数}（GUI 用来提示
           "AI 失败 N/M 行，结果不完整"，避免全失败却显示"分析完成"）。
    返回 {row_index: 规范化分析结果}
    """
    try:
        from vlm import reset_usage

        reset_usage()
    except Exception:
        pass
    cache: dict = {}
    if cache_path and os.path.isfile(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}

    results: dict[int, dict] = {}
    total = len(rows)
    todo: list[tuple[int, str]] = []
    for i, row in enumerate(rows):
        h = _img_hash(row.image)
        if h in cache:
            results[i] = _normalize_analysis(cache[h])
        else:
            todo.append((i, h))

    done = len(results)
    if progress:
        progress(done, total)

    def work(idx: int, h: str) -> tuple[int, dict, bool]:
        try:
            data = analyze_row(rows[idx].image, api_key=api_key, model=model)
            return idx, _normalize_analysis(data), True
        except Exception:
            return idx, {}, False

    if todo:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(work, i, h): (i, h) for i, h in todo}
            for fut in as_completed(futures):
                if stop_flag and stop_flag():
                    break
                idx, norm, ok = fut.result()
                results[idx] = norm
                if ok:
                    cache[futures[fut][1]] = norm
                done += 1
                if progress:
                    progress(done, total)

    # 失败计数（缓存命中不算失败）
    failed = sum(1 for i in range(total) if i in results and not results[i])
    if stats is not None:
        stats["failed"] = failed
        stats["total"] = total

    if cache_path:
        try:
            os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
        except Exception:
            pass
    # 输出本次 AI 用量（估算）
    try:
        from vlm import get_usage

        u = get_usage()
        if u["calls"]:
            models = "、".join(f"{k}×{v}" for k, v in u["by_model"].items())
            log.info(f"AI 用量：调用 {u['calls']} 次（{models}），"
                     f"估算约 {u['calls'] * 1350} token（每张谱面图 ~1350）")
        if u["failed"]:
            log.warn(f"AI 调用失败 {u['failed']} 次（可能额度耗尽，已尝试降级）")
    except Exception:
        pass
    return results


# ---------- 语义去重判断 ----------

def _norm_chords(chords: list[str]) -> tuple:
    """和弦序列规范化（去空格、统一大小写、常见写法归一）。"""
    out = []
    for c in chords or []:
        c = c.strip().upper().replace(" ", "")
        if not c:
            continue
        # 统一 bsus4 -> BSUS4 之类；把 b 前缀、maj7 保留
        out.append(c)
    return tuple(out)


def _norm_rhythm(rt: str) -> str:
    """节奏型规范化（去标点/空格）。"""
    if not rt:
        return ""
    return "".join(ch for ch in rt if ch not in " ，,。.、;；:：()（）")


def is_duplicate(a: dict, b: dict) -> tuple[bool, str]:
    """判断两行是否重复。返回 (是否重复, 理由)。

    判据（保守，宁漏勿误删）：
    1. 歌词相同（>=4 字）—— 最稳
    2. content 完整描述完全一致（>=20 字）—— 能区分"相同和弦进行但细节不同"的段落
    3. 小节号（1~3 个）一致 + 和弦序列一致 —— 辅助

    **不使用**"和弦+节奏相同"：实测会把不同段落（如击弦段 vs 扫弦段）误判成重复。
    小节号单独也不可靠（VLM 常把 TAB 数字误当小节号），必须配合其它判据。
    """
    if not a or not b:
        return False, ""
    # 碎片/非谱行不参与去重（它们本身要被过滤）
    if not a.get("is_complete", True) or not b.get("is_complete", True):
        return False, ""

    la, lb = (a.get("lyrics") or "").strip(), (b.get("lyrics") or "").strip()
    cta, ctb = (a.get("content") or "").strip(), (b.get("content") or "").strip()
    ca, cb = _norm_chords(a.get("chords")), _norm_chords(b.get("chords"))

    # 强否定：两边都有歌词且不同 → 一定是不同内容（哪怕 content 描述碰巧一样）
    if la and lb and la != lb:
        return False, ""

    # 1) 歌词都有且相同（>=4 字）→ 重复
    if la and lb and la == lb and len(la) >= 4:
        return True, f"歌词相同「{la[:12]}」"

    # 2) 两边都没歌词 + content 完整描述完全一致（>=20 字）→ 重复
    if not la and not lb and cta and cta == ctb and len(cta) >= 20:
        return True, f"内容描述一致「{cta[:16]}」"

    # 3) 小节号一致（1~3 个，两边都有）+ 和弦序列一致 → 重复
    ba = set(a.get("bar_numbers") or [])
    bb = set(b.get("bar_numbers") or [])
    if 1 <= len(ba) <= 3 and ba == bb and ca and ca == cb:
        return True, f"小节号一致 {sorted(ba)} 且和弦相同"

    return False, ""


def cv_is_likely_fragment(img) -> bool:
    """CV 层面判断是否疑似碎片（配合 VLM 的 is_complete 复核）。

    碎片特征：
    - 行很矮（<70px），或
    - 内容极少（暗像素 <2%）—— 只有几个孤立数字/几乎空白。
    注意：谱面本身就是"白底+少量墨迹"（暗像素 3~8% 很正常），
    阈值不能太高，否则正常谱行会被误判成碎片。
    """
    import cv2

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    dark = gray < 150
    frac = float(dark.mean())
    if h < 70:
        return True
    if frac < 0.02:
        return True
    return False


def find_incomplete_rows(analyses: dict[int, dict], rows=None) -> list[int]:
    """找出碎片/空谱行（VLM is_complete + CV 内容量双向校验）。

    - VLM 判不完整：若 CV 显示内容充足（行高 >=70 且暗像素 >=2%）则**救回**；
    - VLM 判完整：若 CV 显示内容极少（<2%）且不是歌词行，仍判为碎片。
    注意：谱面天然"白底+少墨迹"，CV 只做兜底，不能过严（否则正常谱成碎片）。
    """
    out = []
    for i, a in sorted(analyses.items()):
        vlm_incomplete = not a.get("is_complete", True)
        is_lyrics = a.get("row_type") == "lyrics"
        cv_frag = False
        if rows is not None and i < len(rows):
            try:
                cv_frag = cv_is_likely_fragment(rows[i].image)
            except Exception:
                cv_frag = False
        if vlm_incomplete:
            # CV 复核救回（避免误删纯 TAB/简谱/歌词行）
            if rows is not None and not cv_frag:
                continue
            out.append(i)
        else:
            # VLM 判完整时，只有 CV 也确认"几乎空白"才兜底判碎片
            if rows is not None and cv_frag and not is_lyrics:
                out.append(i)
    return out


def find_duplicate_groups(analyses: dict[int, dict]) -> list[list[int]]:
    """找出重复组（按行索引）。每组内成员两两互相重复（连通分量）。"""
    idxs = sorted(analyses)
    n = len(idxs)
    adj: dict[int, set[int]] = {i: set() for i in idxs}
    reasons: list[tuple[int, int, str]] = []
    for a_i in range(n):
        for b_i in range(a_i + 1, n):
            i, j = idxs[a_i], idxs[b_i]
            dup, why = is_duplicate(analyses[i], analyses[j])
            if dup:
                adj[i].add(j)
                adj[j].add(i)
                reasons.append((i, j, why))

    # 连通分量（只保留 >=2 的分量）
    seen = set()
    groups = []
    for i in idxs:
        if i in seen or not adj[i]:
            continue
        stack = [i]
        comp = []
        while stack:
            k = stack.pop()
            if k in seen:
                continue
            seen.add(k)
            comp.append(k)
            stack.extend(adj[k] - seen)
        if len(comp) >= 2:
            groups.append(sorted(comp))
    groups.sort()
    return groups


def duplicate_reasons(analyses: dict[int, dict]) -> dict[tuple[int, int], str]:
    """返回重复对及理由（供界面展示）。"""
    out = {}
    idxs = sorted(analyses)
    for a_i in range(len(idxs)):
        for b_i in range(a_i + 1, len(idxs)):
            i, j = idxs[a_i], idxs[b_i]
            dup, why = is_duplicate(analyses[i], analyses[j])
            if dup:
                out[(i, j)] = why
    return out
