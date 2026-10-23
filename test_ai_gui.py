# -*- coding: utf-8 -*-
"""GUI 冒烟测试：AI 识别按钮流程 + 清理按钮。"""
import os
import sys

sys.path.insert(0, r"C:\Users\20849\Desktop\视频扒谱\bili_tab_extractor")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from gui_qt import MainWindow, ReviewWindow, QSS
from pipeline import process

app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setStyleSheet(QSS)

win = MainWindow()
win.show()
result = process(video=os.path.abspath("fuji.mp4"), title="AI流程测试",
                 work_dir=os.path.abspath("_ai_gui_work"), max_height=360)
print(f"pipeline: {len(result.kept_rows)} 行")

win.work_dir = os.path.abspath("_ai_gui_work")
win.review_result = result
review = ReviewWindow(win, result)
review.show()
print("核验窗口 OK；AI按钮:", review.read_bars_btn.text(), "；清理按钮:", review.clean_btn.text())

def start_ai():
    print("触发 AI 识别 + 去重…")
    review._on_ai_analyze()

def check():
    if not review._ai_done:
        QTimer.singleShot(3000, check)
        return
    print(f"AI 完成：碎片 {len(review._incomplete_rows)} 行，重复组 {len(review._ai_dup_groups)} 组")
    print(f"清理按钮启用: {review.clean_btn.isEnabled()}")
    print(f"列表项数: {review.list_widget.count()}")
    # 检查标色
    n_bg = sum(1 for i in range(review.list_widget.count())
               if review.list_widget.item(i).background().color().name() != "#000000"
               and review.list_widget.item(i).background().style() != 0)
    print(f"带背景标记的项: {n_bg}")
    QTimer.singleShot(500, close_all)

def close_all():
    review.close()
    win.close()
    app.quit()

QTimer.singleShot(1000, start_ai)
QTimer.singleShot(3500, check)
app.exec()
print("GUI AI 流程测试完成")
