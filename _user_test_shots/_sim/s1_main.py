# -*- coding: utf-8 -*-
"""场景 1：主窗口首屏 / 空输入提示 / AI 设置对话框。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (app, pump, shot, screen_shot, grab_while_modal,
                    close_visible_modal, MainWindow, ApiSettingsDialog, SHOTS)

mw = MainWindow()
mw.show()
pump(400)
shot(mw, "01_主窗口_默认")

# 空输入点开始处理 → 警告
grab_while_modal(lambda: mw._start(False), "02_主窗口_空链接警告")

# AI 设置对话框
dlg = ApiSettingsDialog(mw)
dlg.show()
pump(300)
shot(dlg, "03_AI设置")
dlg.close()

# 输入一个不存在的本地文件 → 观察错误提示（真实流程，失败很快）
mw.url_edit.setText(r"C:\Users\20849\Desktop\视频扒谱\__nope__.mp4")
res = grab_while_modal(lambda: mw._start(False), "04_主窗口_本地文件不存在报错", delay=1200)
pump(500)
shot(mw, "05_主窗口_报错后日志")
print("status:", mw.status_label.text())

# 处理中状态（伪造进度，观察控件状态）
mw.url_edit.setText(r"C:\Users\20849\Desktop\视频扒谱\fuji.mp4")
mw.progress.setValue(43)
mw.status_label.setText("检测谱面区域…")
mw.start_btn.setEnabled(False)
mw.auto_btn.setEnabled(False)
mw.cancel_btn.setEnabled(True)
shot(mw, "06_主窗口_处理中状态")
mw.close()
