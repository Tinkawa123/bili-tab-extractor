# -*- coding: utf-8 -*-
"""用户试用：公共初始化 + 截图工具（不改动项目源码）。"""
import os
import sys
import time
import glob

ROOT = r"C:\Users\20849\Desktop\视频扒谱"
SHOTS = os.path.join(ROOT, "_user_test_shots")
os.makedirs(SHOTS, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "bili_tab_extractor"))

os.environ.setdefault("QT_SCALE_FACTOR", "1")

import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import (QApplication, QMenu, QDialog, QMessageBox)

from gui_qt import MainWindow, ReviewWindow, QSS, ApiSettingsDialog  # noqa: E402
from pipeline import PipelineResult, TabRow  # noqa: E402
from util import imread  # noqa: E402

app = QApplication.instance() or QApplication([])
app.setStyle("Fusion")
app.setStyleSheet(QSS)


def pump(ms=150):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.008)


def shot(widget, name, delay=250):
    pump(delay)
    p = os.path.join(SHOTS, name + ".png")
    widget.grab().save(p)
    print("SHOT", p, widget.width(), "x", widget.height())
    return p


def screen_shot(name):
    pump(150)
    p = os.path.join(SHOTS, name + ".png")
    QGuiApplication.primaryScreen().grabWindow(0).save(p)
    print("SHOT(screen)", p)
    return p


def close_visible_modal():
    for w in app.topLevelWidgets():
        if isinstance(w, QMenu) and w.isVisible():
            w.close()
        elif isinstance(w, (QDialog, QMessageBox)) and w.isVisible():
            w.done(0)
    pump(80)


def grab_while_modal(fn, name, delay=500):
    """fn() 会阻塞弹出模态框；在阻塞期间截「新出现的弹窗」，然后自动关闭。"""
    before = {id(w) for w in app.topLevelWidgets()}
    captured = {"ok": False}

    def _grab():
        for w in app.topLevelWidgets():
            if id(w) not in before and w.isVisible() and isinstance(w, (QDialog, QMessageBox, QMenu)):
                p = os.path.join(SHOTS, name + ".png")
                w.grab().save(p)
                print("SHOT(modal)", p, w.width(), "x", w.height())
                captured["ok"] = True
                break

    def _close():
        for w in app.topLevelWidgets():
            if id(w) not in before and w.isVisible():
                try:
                    w.done(0)
                except Exception:
                    w.close()

    QTimer.singleShot(delay, _grab)
    QTimer.singleShot(delay + 400, _close)
    out = fn()
    pump(120)
    return out


def grab_menu(pos, signal, name, delay=400):
    """触发右键菜单（menu.exec 阻塞），截下菜单本身后关闭。"""
    def _grab():
        for w in app.topLevelWidgets():
            if isinstance(w, QMenu) and w.isVisible():
                p = os.path.join(SHOTS, name + ".png")
                w.grab().save(p)
                print("SHOT(menu)", p, w.width(), "x", w.height())
                w.close()
                return
        print("WARN no menu visible")

    QTimer.singleShot(delay, _grab)
    signal(pos)
    pump(120)


def load_rows(folder, max_rows=None, prefix=""):
    files = sorted(glob.glob(os.path.join(ROOT, "out", "测试集", folder, "行*.png")))
    if max_rows:
        files = files[:max_rows]
    rows = []
    for i, f in enumerate(files):
        img = imread(f)
        if img is None:
            continue
        rows.append(TabRow(img, i * 2.0, prefix + os.path.basename(f), i))
    return rows


def make_review(folder="富士山下", title="富士山下", extra_rows=0, win=None):
    rows = load_rows(folder)
    if extra_rows:
        rows += load_rows("沙龙", max_rows=extra_rows, prefix="salon_")
    result = PipelineResult(title, None, list(rows), list(rows))
    mw = win or MainWindow()
    mw.work_dir = os.path.join(SHOTS, "_sim", "_work")
    os.makedirs(mw.work_dir, exist_ok=True)
    mw.review_result = result
    rev = ReviewWindow(mw, result)
    rev.resize(1250, 800)
    rev.show()
    pump(300)
    return mw, rev, result


def fake_ai(rev, dup_groups, incomplete, analyses_extra=None):
    """伪造 AI 分析结果（不消耗额度），用于观察界面。"""
    analyses = {}
    chords_pool = [["Am", "C", "G", "D"], ["F", "G", "Em", "Am"], ["C", "G", "Am", "F"]]
    lyrics_pool = ["故事的小黄花", "从出生那年就飘着", "童年的荡秋千", "随记忆一直晃到现在"]
    for i, r in enumerate(rev.rows):
        analyses[i] = {
            "chords": chords_pool[i % len(chords_pool)],
            "lyrics": lyrics_pool[i % len(lyrics_pool)],
            "bar_numbers": [i * 2 + 1, i * 2 + 2],
            "complete": i not in incomplete,
        }
    if analyses_extra:
        analyses.update(analyses_extra)
    rev._ai_analyses = analyses
    rev._ai_dup_groups = [list(g) for g in dup_groups]
    rev._ai_dups = {}
    for g in dup_groups:
        for i in g:
            rev._ai_dups.setdefault(i, [x for x in g if x != i])
    rev._incomplete_rows = set(incomplete)
    rev._ai_done = True
    rev.clean_btn.setEnabled(True)
    rev.status_top.setText(
        f"AI 分析完成：{len(analyses)} 行｜碎片/空谱 {len(incomplete)} 行｜疑似重复 {len(dup_groups)} 组")
    rev._render_list()
