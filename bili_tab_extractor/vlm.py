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

import requests  # yt-dlp 的既有依赖，打包零额外体积

# DashScope OpenAI 兼容接口
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3-vl-plus"   # 也可用 qwen-vl-ocr（文字/数字识别更强）

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


def _call(api_key: str | None, model: str, prompt: str, image_data_url: str,
          timeout: float) -> dict:
    """调用 DashScope OpenAI 兼容接口（requests，零额外依赖）。"""
    key = _require_key(api_key)
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
    resp.raise_for_status()
    data = resp.json()
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"接口返回格式异常: {str(data)[:300]}") from e
    return _extract_json(text)


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
