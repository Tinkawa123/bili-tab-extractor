# -*- coding: utf-8 -*-
"""探针：真实调用一次 VLM，看失败时返回什么（不打印 Key）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_rows
from vlm_recognize import analyze_row
from vlm import load_api_key, load_model, DEFAULT_MODEL

key = load_api_key()
print("provider model:", load_model(), "| default:", DEFAULT_MODEL, "| key?", bool(key))
rows = load_rows("富士山下", max_rows=1)
try:
    data = analyze_row(rows[0].image, api_key=key)
    print("RESULT keys:", list(data)[:12] if isinstance(data, dict) else type(data))
    print("RESULT preview:", str(data)[:300])
except Exception as e:
    print("EXCEPTION:", type(e).__name__, str(e)[:600])
