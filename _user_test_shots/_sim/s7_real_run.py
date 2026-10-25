# -*- coding: utf-8 -*-
"""场景 7：真实处理 fuji.mp4（抽帧间隔 10s，禁用 VLM），测试「取消」是否真的能停。"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import app, pump, shot, SHOTS, ROOT

import gui_qt
# 关掉 VLM，避免真实调用额度（只测 GUI 流程）
gui_qt.load_api_key = lambda *a, **k: None

mw = common.MainWindow()
mw.show()
mw.url_edit.setText(os.path.join(ROOT, "fuji.mp4"))
mw.interval_spin.setValue(10.0)
mw.maxh_spin.setValue(360)
pump(200)

t0 = time.time()
mw._start(False)
print("worker started")

def wait(sec):
    end = time.time() + sec
    while time.time() < end:
        app.processEvents()
        time.sleep(0.05)

wait(6)
print(f"t={time.time()-t0:.1f}s status=", mw.status_label.text(), "| progress=", mw.progress.value())
shot(mw, "50_真实处理中_6s")

# 点取消
mw._cancel()
print("clicked cancel -> status:", mw.status_label.text(), "| btn enabled:", mw.cancel_btn.isEnabled())
wait(2)
shot(mw, "51_点取消后_2s")
print(f"t={time.time()-t0:.1f}s after cancel status=", mw.status_label.text(),
      "| progress=", mw.progress.value(), "| worker running=", mw.worker.isRunning())

wait(12)
print(f"t={time.time()-t0:.1f}s +12s status=", mw.status_label.text(),
      "| progress=", mw.progress.value(), "| worker running=", mw.worker.isRunning())
shot(mw, "52_点取消后_14s")

# 等到结束或 240s
while time.time() - t0 < 240:
    app.processEvents()
    time.sleep(0.05)
    if mw.worker and not mw.worker.isRunning():
        break
el = time.time() - t0
print(f"finished/stopped at t={el:.1f}s | worker running=", mw.worker.isRunning(),
      "| status=", mw.status_label.text(), "| log tail:")
print(mw.log_text.toPlainText()[-800:])
shot(mw, "53_处理结束_主窗口")
# 是否有核验窗口弹出
rev = getattr(mw, "review", None)
print("review window exists:", rev is not None and rev.isVisible())
if rev is not None:
    pump(300)
    shot(rev, "54_真实核验窗口")
    # 行数/耗时
    print("rows:", len(rev.rows), "| result kept:", len(mw.result.kept_rows) if mw.result else None)
    rev.close()
mw.close()
print("DONE")
