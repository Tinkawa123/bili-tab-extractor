# -*- coding: utf-8 -*-
"""场景 3：图表诊断（导航布局/列表背景色/输出流程/拖拽/浮动条残留）。"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import app, pump, shot, make_review, fake_ai, load_rows, SHOTS
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QColor
import cv2
import numpy as np

mw, rev, result = make_review("富士山下", "富士山下")
rev.resize(1360, 860)
fake_ai(rev, [[3, 4, 5], [11, 12]], {20, 23})
pump(200)

# ---- A. 列表 item 背景色是否真的画出来 ----
lw = rev.list_widget
def item_avg_color(row):
    it = lw.item(row)
    r = lw.visualItemRect(it)
    pm = lw.viewport().grab(r)
    img = pm.toImage()
    # 取文字区（右侧 30% 宽度）平均色
    w, h = img.width(), img.height()
    x0, x1 = int(w * 0.75), w - 5
    y0, y1 = 5, h - 5
    vals = []
    for y in range(y0, y1, 3):
        for x in range(x0, x1, 3):
            c = img.pixelColor(x, y)
            vals.append((c.red(), c.green(), c.blue()))
    arr = np.array(vals)
    return arr.mean(axis=0), it.background().color().name()

for row in (0, 3, 4, 20):
    avg, bg = item_avg_color(row)
    print(f"ITEM row={row+1} 代码设定背景={bg} 实际渲染平均色={avg.round(1)}")

# ---- B. 导航方块布局诊断 ----
def nav_diag(label, review):
    nc = review.nav_container
    lay = review.nav_grid
    print(f"NAV[{label}] buttons={len(review.nav_buttons)} container={nc.width()}x{nc.height()} "
          f"sizeHint={nc.sizeHint().width()}x{nc.sizeHint().height()} "
          f"visible={nc.isVisible()}")
    pos = {}
    for b in review.nav_buttons:
        i = lay.indexOf(b)
        if i < 0:
            continue
        r, c, rs, cs = lay.getItemPosition(i)
        pos[b.property("row_idx")] = (r, c, b.isVisible())
    print("   first10:", list(pos.items())[:10])
    print("   max_row:", max((v[0] for v in pos.values()), default=-1),
          " buttons_pos_populated:", len(pos))

nav_diag("fuji-25", rev)
shot(rev.nav_container, "30_nav_25行")

# 60 行
rows = load_rows("富士山下") + load_rows("沙龙", prefix="b_")
from pipeline import PipelineResult
from gui_qt import MainWindow, ReviewWindow
mw3 = MainWindow(); mw3.work_dir = os.path.join(SHOTS, "_sim", "_work")
res3 = PipelineResult("合集49行", None, list(rows), list(rows))
rev3 = ReviewWindow(mw3, res3)
rev3.resize(1360, 860); rev3.show(); pump(200)
fake_ai(rev3, [[2, 22], [5, 25], [8, 28], [10, 30], [12, 32]], {14, 34, 50})
pump(200)
nav_diag("fuji49", rev3)
shot(rev3.nav_container, "31_nav_49行")
shot(rev3, "32_49行整体")

# 200 行（模拟长视频：把行复制 4 份）
import copy
many = []
for k in range(4):
    for r in rows:
        many.append(r)
res4 = PipelineResult("超长200行", None, list(many), list(many))
mw4 = MainWindow(); mw4.work_dir = os.path.join(SHOTS, "_sim", "_work")
t0 = time.time()
rev4 = ReviewWindow(mw4, res4)   # __init__ 里会跑 _compute_similar
t1 = time.time()
print(f"NAV[200] 打开核验耗时={1000*(t1-t0):.0f}ms")
rev4.resize(1360, 860); rev4.show(); pump(200)
nav_diag("200rows", rev4)
shot(rev4.nav_container, "33_nav_200行")
shot(rev4, "34_200行整体")
rev4.close(); mw4.close()

# ---- C. 拖拽排序（用 model.moveRow 模拟） ----
rev3.list_widget.setCurrentRow(0)
before = [r.source for r in rev3.rows[:4]]
rev3.list_widget.model().moveRow(QModelIndex(), 0, QModelIndex(), 3)
pump(200)
after = [r.source for r in rev3.rows[:4]]
print("MOVE before:", before, "after:", after, "undo_stack:", len(rev3._undo_stack))
rev3._undo()
pump(150)
print("MOVE after undo:", [r.source for r in rev3.rows[:4]])

# ---- D. 浮动条残留：选中重复行→保留第一个→看是否还显示 ----
rev3.list_widget.setCurrentRow(2)
pump(150)
print("FLOAT visible before keep:", rev3.float_bar.isVisible(), "|", rev3.float_label.text())
rev3._on_keep_first()
pump(200)
print("FLOAT visible after keep(no click):", rev3.float_bar.isVisible(), "|", rev3.float_label.text())
last_sel = rev3.list_widget.currentRow()
print("SELECTED after keep:", last_sel, "rows:", len(rev3.rows))
shot(rev3, "35_保留第一个后_浮动条残留")

# ---- E. 输出流程（临时 cwd，不污染项目 out/） ----
tmp = tempfile.mkdtemp(prefix="outtest_")
os.chdir(tmp)
mw5, rev5, res5 = make_review("富士山下", "输出测试")
rev5.resize(1200, 780)
rev5.show()
pump(200)
print("cwd for output:", os.getcwd())
rev5._confirm_output()
t0 = time.time()
while time.time() - t0 < 25:
    app.processEvents()
    if os.path.isdir(os.path.join(tmp, "out")):
        pdfs = []
        for root, dirs, files in os.walk(os.path.join(tmp, "out")):
            pdfs += [os.path.join(root, f) for f in files if f.endswith(".pdf")]
        if pdfs:
            break
    time.sleep(0.1)
pump(1200)
print("OUT files:", [os.path.relpath(os.path.join(r, f), tmp) for r, d, fs in os.walk(tmp) for f in fs][:6])
# 输出完成弹窗
for w in app.topLevelWidgets():
    from PySide6.QtWidgets import QMessageBox, QDialog
    if isinstance(w, (QMessageBox, QDialog)) and w.isVisible():
        shot(w, "36_输出完成弹窗")
        w.done(0)
pump(300)
shot(mw5, "37_主窗口_输出完成后日志")
os.chdir(r"C:\Users\20849\Desktop\视频扒谱")

rev.close(); mw.close(); rev3.close(); mw3.close(); mw5.close()
print("DONE")
