# -*- coding: utf-8 -*-
"""GUI 完整流程测试：AI 分析 → 清理 → 输出。"""
import os
import sys

sys.path.insert(0, r"C:\Users\20849\Desktop\视频扒谱\bili_tab_extractor")
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer

from gui_qt import MainWindow, ReviewWindow, QSS
from pipeline import process

app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setStyleSheet(QSS)

# mock 确认框（自动 Yes）
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QMessageBox.information = staticmethod(lambda *a, **k: None)

win = MainWindow()
win.show()
result = process(video=os.path.abspath("fuji.mp4"), title="GUI完整流程",
                 work_dir=os.path.abspath("_gui_full_work"), max_height=360)
print(f"pipeline: {len(result.kept_rows)} 行")

win.work_dir = os.path.abspath("_gui_full_work")
win.review_result = result
review = ReviewWindow(win, result)
review.show()

state = {"ai_started": False, "cleaned": False}

def step_ai():
    review._on_ai_analyze()
    state["ai_started"] = True
    QTimer.singleShot(3000, step_check)

def step_check():
    if not review._ai_done:
        QTimer.singleShot(3000, step_check)
        return
    print(f"AI 完成：碎片 {len(review._incomplete_rows)} 行，重复 {len(review._ai_dup_groups)} 组")
    n_before = len(review.rows)
    review._on_clean()   # 会调用 mock 的 Yes
    state["cleaned"] = True
    print(f"清理后：{n_before} -> {len(review.rows)} 行")
    QTimer.singleShot(500, step_output)

def step_output():
    rows = review._current_rows()
    print(f"输出 {len(rows)} 行")
    review._confirm_output()
    QTimer.singleShot(1500, close_all)

def close_all():
    review.close()
    win.close()
    app.quit()

QTimer.singleShot(1000, step_ai)
app.exec()
print("GUI 完整流程测试完成")
