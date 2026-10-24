# -*- coding: utf-8 -*-
"""VLM 谱面识别模块（通义千问 Qwen-VL，OpenAI 兼容接口）。

用途：
- 识别一行谱面图片中的：小节号、和弦名、歌词、TAB 数字
- 返回结构化 JSON，供去重判断 / 文本谱生成使用

配置：
- API Key 从环境变量 DASHSCOPE_API_KEY 读取，
  或从本地配置文件 bili_tab_extractor/vlm_config.json 读取（已 gitignore）
"""

from __future__ import annotations

import base64
import json
import os
import threading

import requests  # yt-dlp 的既有依赖，打包零额外体积

# DashScope OpenAI 兼容接口
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3-vl-plus"   # 视觉能力最强；额度耗尽时自动降级

# 推荐模型列表（GUI 下拉展示）：(model, 说明)
RECOMMENDED_MODELS = [
    ("qwen3-vl-plus", "视觉最强（默认，免费额度可能有限）"),
    ("qwen-vl-ocr-2025-11-20", "OCR 专用（免费额度通常可用）"),
    ("qwen-vl-ocr", "OCR 专用（稳定）"),
    ("qwen-vl-max-latest", "视觉旗舰（需开通）"),
    ("qwen-vl-plus-latest", "视觉增强（需开通）"),
    ("qwen2.5-vl-72b-instruct", "旧版视觉（需开通）"),
]

# 降级链：主模型失败（额度/权限问题）时依次尝试
MODEL_FALLBACKS = ["qwen3-vl-plus", "qwen-vl-ocr-2025-11-20", "qwen-vl-ocr"]

# 本次运行用量统计（估算，供日志/界面显示）
_USAGE = {
    "calls": 0,          # 成功调用次数
    "failed": 0,         # 失败次数
    "by_model": {},      # 各模型成功次数
    "est_tokens": 0,     # 估算消耗 token（输入+输出）
}

# 降级前的确认回调（GUI 注册；返回 True=允许降级，False=中止）
# 签名：asker(failed_model: str, error_msg: str, use_model: str) -> bool
_fallback_asker = None
# 并发保护：多个线程同时遇到 403 时，只询问一次
_fallback_lock = threading.Lock()
_fallback_asked = False
_fallback_denied = False


def set_fallback_asker(fn) -> None:
    """注册"降级前询问用户"的回调（None 表示不询问、静默降级）。

    每轮分析开始时调用一次，会重置"已询问"状态。
    """
    global _fallback_asker, _fallback_asked, _fallback_denied
    _fallback_asker = fn
    _fallback_asked = False
    _fallback_denied = False


def get_usage() -> dict:
    """返回本次运行的用量统计（副本）。"""
    return {"calls": _USAGE["calls"], "failed": _USAGE["failed"],
            "by_model": dict(_USAGE["by_model"]),
            "est_tokens": _USAGE["est_tokens"]}


def reset_usage() -> None:
    """重置用量统计（每次处理开始时调用）。"""
    _USAGE.update({"calls": 0, "failed": 0, "by_model": {}, "est_tokens": 0})


def estimate_image_tokens(width: int, height: int) -> int:
    """粗略估算一张图编码后的 token 数（按面积 / 750 像素² 逐块计）。"""
    tiles = max(1, (width * height) // (750 * 750))
    return tiles * 1000 + 200

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vlm_config.json")


def load_api_key() -> str | None:
    """读取 API Key：环境变量优先，其次本地配置文件。"""
    key = os.environ.get("DASHSCOPE_API_KEY")
    if key:
        return key.strip()
    return load_config_key()


def load_config_key() -> str | None:
    """只从本地配置文件读取 Key（GUI 设置用）。"""
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return (json.load(f).get("api_key") or "").strip() or None
        except Exception:
            pass
    return None


def save_api_key(key: str, model: str | None = None) -> None:
    """保存 API Key（及可选模型）到本地配置文件。"""
    data = {}
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data["api_key"] = key.strip()
    if model:
        data["model"] = model.strip()
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_model() -> str:
    """读取配置的模型名（默认 qwen3-vl-plus）。"""
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                m = (json.load(f).get("model") or "").strip()
                if m:
                    return m
        except Exception:
            pass
    return DEFAULT_MODEL


def _require_key(api_key: str | None) -> str:
    """校验并返回 API Key。"""
    key = api_key or load_api_key()
    if not key:
        raise RuntimeError(
            "未配置 API Key：请设置环境变量 DASHSCOPE_API_KEY，"
            "或在 bili_tab_extractor/vlm_config.json 写入 {\"api_key\": \"sk-...\"}")
    return key


def _image_to_data_url(path: str) -> str:
    """图片文件 → data URL（base64）。"""
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


ROW_PROMPT = """你是一个乐谱识别助手。这张图片是一行吉他谱（可能是五线谱/TAB 六线谱 + 和弦名 + 歌词）。

请仔细识别并输出 JSON（不要输出其他内容）：
{
  "bar_numbers": [识别到的小节号数字，如 5, 6, 7；没有则空数组],
  "chords": [从上到下、从左到右的和弦名，如 "C", "G", "Am", "Fmaj7"],
  "lyrics": "这一行对应的歌词（没有则空字符串）",
  "tab_lines": [TAB 六线谱的数字行，从左到右，如 "0-2-3", "1-3-5"],
  "description": "用一句话描述这一行的音乐内容"
}

注意：
- 只识别谱面上实际印有的内容，不要编造；
- 如果图片不是谱面（是乐器/演奏画面），返回 {"error": "not_tab"}。
"""


BAR_PROMPT = """你是一个乐谱识别助手。这张图片是一行吉他谱（五线谱/TAB + 和弦 + 歌词）。

只做一件事：**找出这一行谱面上印的小节号数字**。

关键区分（非常重要）：
- **小节号**：每个小节开头的一个独立小编号（通常是 1, 2, 3, 4…依次递增），
  一般印在行首或小节起始位置的上方/旁边，是**孤立的数字**；
- **TAB 数字**：六线谱线条上横向排列的拨弦指法数字（如 0-2-3-5、3-3-3），
  它们是**谱线的一部分**，不是小节号，**绝对不要**把它们当作小节号报告！

判断标准：小节号是"每小节标一次的序号"，TAB 数字是"具体弹哪个品的指法"。
如果分不清，宁可返回空数组，也不要乱报。

输出 JSON（不要输出其他内容）：
{"bar_numbers": [真正的小节号序号列表；不确定或没有则空数组], "has_tab": true/false}

注意：
- 只报谱面上实际印着的小节号，不要编造；
- 如果图片不是谱面（演奏画面/乐器），返回 {"error": "not_tab"}。
"""


def _extract_json(text: str) -> dict:
    """从模型回复中提取 JSON（容忍 ```json 代码块）。"""
    text = (text or "").strip()
    if "```" in text:
        parts = text.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                text = p
                break
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text, "error": "json_parse_failed"}


def _post_once(key: str, model: str, prompt: str, image_data_url: str,
               timeout: float) -> dict:
    """单次请求（不做降级），失败抛 RuntimeError。"""
    resp = requests.post(
        f"{DASHSCOPE_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }],
            "temperature": 0.1,
        },
        timeout=timeout,
    )
    if resp.status_code == 401:
        raise RuntimeError("API Key 无效或已过期（HTTP 401）")
    if resp.status_code == 429:
        raise RuntimeError("调用频率过高或额度用尽（HTTP 429）")
    if resp.status_code == 403:
        code = ""
        try:
            code = str(resp.json().get("error", {}).get("code", ""))
        except Exception:
            pass
        if "FreeTierOnly" in code or "AllocationQuota" in code:
            raise RuntimeError(f"模型 {model} 免费额度已用尽（403 {code}）")
        raise RuntimeError(f"模型 {model} 无权访问（403 {code}）")
    resp.raise_for_status()
    data = resp.json()
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"接口返回格式异常: {str(data)[:300]}") from e
    return _extract_json(text)


def _call(api_key: str | None, model: str, prompt: str, image_data_url: str,
          timeout: float) -> dict:
    """调用 DashScope OpenAI 兼容接口，失败自动降级到备选模型。

    降级链：指定模型 → MODEL_FALLBACKS 中其它模型。
    只有"额度/权限/格式"错误才降级；Key 无效（401）直接抛错。
    """
    key = _require_key(api_key)
    candidates = [model]
    for fb in MODEL_FALLBACKS:
        if fb not in candidates:
            candidates.append(fb)

    last_err: Exception | None = None
    global _fallback_asked, _fallback_denied
    for m in candidates:
        try:
            result = _post_once(key, m, prompt, image_data_url, timeout)
            _USAGE["calls"] += 1
            _USAGE["by_model"][m] = _USAGE["by_model"].get(m, 0) + 1
            return result
        except RuntimeError as e:
            msg = str(e)
            if "401" in msg or "API Key 无效" in msg:
                raise
            last_err = e
            # 找下一个可降级模型
            nxt = next((c for c in candidates[candidates.index(m) + 1:]), None)
            if not nxt:
                continue
            # 降级前询问用户：并发线程下只问一次（全局锁 + 标志）
            with _fallback_lock:
                if _fallback_asked:
                    if _fallback_denied:
                        raise RuntimeError(
                            f"已中止：模型 {m} 额度/权限不足（{msg}），用户未允许降级")
                    # 已确认过：静默降级（日志只在第一次询问时打印）
                    continue
                _fallback_asked = True
                try:
                    from util import log as _log
                    _log.warn(f"模型 {m} 调用失败：{msg}")
                except Exception:
                    pass
                if _fallback_asker is not None:
                    try:
                        allowed = _fallback_asker(m, msg, nxt)
                    except Exception:
                        allowed = True
                    if not allowed:
                        _fallback_denied = True
                        raise RuntimeError(
                            f"已中止：模型 {m} 额度/权限不足（{msg}），用户未允许降级")
                try:
                    from util import log as _log
                    _log.warn(f"→ 自动切换到备用模型 {nxt} 继续")
                except Exception:
                    pass
            continue
    _USAGE["failed"] += 1
    raise RuntimeError(f"所有模型均调用失败（最后错误：{last_err}）")


def _array_to_data_url(img) -> str:
    """numpy BGR 数组 → data URL（base64 PNG）。"""
    import cv2

    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise RuntimeError("无法编码图片")
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def recognize_row(image_path: str, api_key: str | None = None,
                  model: str = DEFAULT_MODEL, timeout: float = 120.0) -> dict:
    """识别一行谱面图片（文件路径），返回结构化 dict。"""
    return _call(api_key, model, ROW_PROMPT, _image_to_data_url(image_path), timeout)


def recognize_row_array(img, api_key: str | None = None,
                        model: str = DEFAULT_MODEL, timeout: float = 120.0) -> dict:
    """识别一行谱面图片（numpy 数组，免存盘），返回结构化 dict。"""
    return _call(api_key, model, ROW_PROMPT, _array_to_data_url(img), timeout)


def read_bar_numbers(img, api_key: str | None = None,
                     model: str = DEFAULT_MODEL, timeout: float = 90.0) -> dict:
    """只读一行谱面上的小节号（轻量提示词，降低 token 成本）。

    返回 {"bar_numbers": [...], "has_tab": bool} 或 {"error": ...}。
    """
    return _call(api_key, model, BAR_PROMPT, _array_to_data_url(img), timeout)
