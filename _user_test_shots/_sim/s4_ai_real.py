# -*- coding: utf-8 -*-
"""场景 4：真实 AI 识别（3 行，DeepSeek），观察进度/结果/失败提示。"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import app, pump, shot, load_rows, SHOTS
from pipeline import PipelineResult
from gui_qt import MainWindow, ReviewWindow
from vlm import load_api_key

print("KEY configured:", bool(load_api_key()))
rows = load_rows("富士山下", max_rows=3)
res = PipelineResult("AI真测3行", None, list(rows), list(rows))
mw = MainWindow()
mw.work_dir = os.path.join(SHOTS, "_sim", "_work_ai")
os.makedirs(mw.work_dir, exist_ok=True)
rev = ReviewWindow(mw, res)
rev.resize(1300, 800)
rev.show()
pump(300)
shot(rev, "40_AI_点击前")

t0 = time.time()
rev._on_ai_analyze()
pump(1200)
shot(rev, "41_AI_分析中")
print("status:", rev.status_top.text(), "| btn enabled:", rev.read_bars_btn.isEnabled())

shot_at = [10, 30, 60, 90, 120]
while time.time() - t0 < 150:
    app.processEvents()
    el = time.time() - t0
    if shot_at and el > shot_at[0]:
        shot_at.pop(0)
        shot(rev, f"42_AI_等待{int(el)}s")
        print(f"t={el:.0f}s status:", rev.status_top.text())
    if rev._ai_done:
        break
    if not rev._bar_thread.isRunning() if rev._bar_thread else False:
        break
    time.sleep(0.2)

el = time.time() - t0
print(f"AI finished in {el:.1f}s | done={rev._ai_done} | analyses={len(rev._ai_analyses)} "
      f"| groups={rev._ai_dup_groups} | incomplete={sorted(rev._incomplete_rows)}")
print("status:", rev.status_top.text())
shot(rev, "43_AI_结果")
rev.close()
mw.close()
print("DONE")
