# -*- coding: utf-8 -*-
"""场景 2：核验窗口交互（默认/选中/AI 伪造结果/重复组/撤销/右键/空状态）。"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (app, pump, shot, grab_while_modal, grab_menu, make_review,
                    fake_ai, load_rows, SHOTS, ROOT, TabRow, QPoint, QMenu)
from PySide6.QtWidgets import QLabel, QDialog, QMessageBox
from PySide6.QtCore import Qt

mw, rev, result = make_review("富士山下", "富士山下")
rev.resize(1360, 860)
pump(200)
shot(rev, "10_核验_初始")

# 选中第 1 行 → 预览
rev.list_widget.setCurrentRow(0)
pump(200)
shot(rev, "11_核验_选中第1行")

# 伪造 AI 结果：第 4-6 行一组、第 12-13 行一组；第 21、24 行碎片
fake_ai(rev, [[3, 4, 5], [11, 12]], {20, 23})
pump(200)
shot(rev, "12_核验_伪造AI结果")
shot(rev.nav_container, "13_核验_导航方块")
shot(rev.list_widget, "14_核验_列表区")

# 选中重复组成员 → 浮动条
rev.list_widget.setCurrentRow(4)
pump(250)
shot(rev, "15_核验_选中重复行_浮动条")
shot(rev.float_bar, "16_浮动条")
print("float text:", rev.float_label.text(), "| btn:", rev.keep_first_btn.text())

# 点「保留组内第一个」
rev._on_keep_first()
pump(300)
shot(rev, "17_核验_保留第一个之后")
print("after keep_first rows:", len(rev.rows))

# 撤销
rev._undo()
pump(300)
shot(rev, "18_核验_撤销之后")
print("after undo rows:", len(rev.rows))

# 顶部标题label是否跟着行数更新
labels = [w.text() for w in rev.findChildren(QLabel) if "共" in w.text() or "疑似重复" in w.text()]
print("HEADER LABELS:", labels)

# 右键菜单（选中重复行上右键）
lw = rev.list_widget
idx_item = lw.item(4)
rect = lw.visualItemRect(idx_item)
pos = rect.center()
grab_menu(pos, lw.customContextMenuRequested.emit, "19_右键菜单")
pump(200)

# 预览缩放保持测试
pv = rev.preview_view
rev.list_widget.setCurrentRow(10)
pump(150)
pv.scale(2.0, 2.0)
s1 = pv.transform().m11()
rev.list_widget.setCurrentRow(11)
pump(150)
s2 = pv.transform().m11()
print(f"PREVIEW ZOOM before={s1:.3f} after_switch_row={s2:.3f}")

# 双击大图（_on_double_click 里 exec 阻塞，直接造 ZoomDialog 观察界面）
from gui_qt import ZoomDialog
zd = ZoomDialog(rev.rows[11].image.copy(), "第 12 行预览（t=22s）", rev)
zd.show()
pump(300)
shot(zd, "20_双击大图")
zd.close()

# 找回落选行（先造两行被丢弃的）
extra = load_rows("沙龙", max_rows=4, prefix="salon_")
result.all_rows.extend(extra)
from gui_qt import RecoverDialog
rd = RecoverDialog(extra, rev)
rd.show()
pump(300)
shot(rd, "21_找回被丢弃的行")
rd.close()

# AI 清理确认框
rev.list_widget.setCurrentRow(2)
grab_while_modal(rev._on_clean, "22_AI清理确认框")
pump(200)

# 删除到空
while len(rev.rows) > 0:
    rev.list_widget.setCurrentRow(0)
    rev._delete_selected()
pump(300)
shot(rev, "23_核验_删空状态")
print("empty status:", rev.status_top.text(), "| list count:", rev.list_widget.count())

# 空状态点确认输出
grab_while_modal(rev._confirm_output, "24_空状态确认输出")
pump(200)

# 恢复一些行，测性能
mw2, rev2, result2 = make_review("沙龙", "沙龙")
rev2.resize(1360, 860)
pump(200)
n = len(rev2.rows)
t0 = time.time(); rev2._render_list(); t1 = time.time()
t2 = time.time(); rev2._compute_similar(); t3 = time.time()
t4 = time.time(); rev2._refresh_nav_grid(); t5 = time.time()
print(f"PERF rows={n} render_list={1000*(t1-t0):.0f}ms compute_similar={1000*(t3-t2):.0f}ms nav_grid={1000*(t5-t4):.0f}ms")
rev2.list_widget.setCurrentRow(3)
t6 = time.time(); rev2._delete_selected(); t7 = time.time()
print(f"PERF delete_one={1000*(t7-t6):.0f}ms")

# 60 行（两份测试集拼起来，模拟长视频）
mw3 = None
rows = load_rows("富士山下") + load_rows("沙龙", prefix="b_")
result3 = type(result2)("合集60行", None, list(rows), list(rows))
from gui_qt import MainWindow, ReviewWindow
mw3 = MainWindow(); mw3.work_dir = os.path.join(SHOTS, "_sim", "_work")
rev3 = ReviewWindow(mw3, result3)
rev3.resize(1360, 860); rev3.show(); pump(200)
t0 = time.time(); rev3._render_list(); t1 = time.time()
t2 = time.time(); rev3._compute_similar(); t3 = time.time()
t4 = time.time(); rev3._refresh_nav_grid(); t5 = time.time()
print(f"PERF60 rows={len(rows)} render_list={1000*(t1-t0):.0f}ms compute_similar={1000*(t3-t2):.0f}ms nav_grid={1000*(t5-t4):.0f}ms")
fake_ai(rev3, [[2, 22, 42], [5, 25], [8, 28], [10, 30], [12, 32]], {14, 34, 50})
pump(200)
shot(rev3, "25_60行_导航多行")
shot(rev3.nav_container, "26_60行_导航区细节")
rev3.close(); mw3.close()
rev.close(); mw.close(); mw2.close(); rev2.close()
print("DONE")
