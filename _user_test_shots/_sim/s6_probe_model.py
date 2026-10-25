# -*- coding: utf-8 -*-
"""探针 2：显式传当前配置的模型，验证是不是"模型没传导致 400"。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_rows
from vlm_recognize import analyze_row
from vlm import load_api_key, load_model

key = load_api_key()
model = load_model()
print("provider model:", model, "| key?", bool(key))
rows = load_rows("富士山下", max_rows=1)
try:
    data = analyze_row(rows[0].image, api_key=key, model=model, timeout=200)
    print("RESULT:", {k: (str(v)[:60]) for k, v in data.items()})
except Exception as e:
    print("EXCEPTION:", type(e).__name__, str(e)[:400])
