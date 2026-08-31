# -*- coding: utf-8 -*-
"""B站吉他谱提取器 GUI（PySide6 现代 UI）。

功能：
1. 输入 B 站 URL / 本地视频 → 自动截取并排序谱行
2. 人工核验窗口：
   - 大缩略图列表（480px 宽），鼠标拖拽排序
   - 右侧常驻大图预览（点选即显示），双击弹出可缩放全屏大图
   - 删除、找回被丢弃行、导入本地图片
3. 全自动按钮跳过核验直接输出；输出 PDF + 谱行图片文件夹
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import time

import cv2
import numpy as np
from PySide6.QtCore import Qt, QSize, QThread, Signal, QEasingCurve, QPropertyAnimation
from PySide6.QtGui import QImage, QPixmap, QIcon, QPainter, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QProgressBar, QTextEdit,
    QListWidget, QListWidgetItem, QSplitter, QDialog, QScrollArea,
    QFileDialog, QMessageBox, QSpinBox, QDoubleSpinBox, QStyle,
    QAbstractItemView, QScroller,
)

from pipeline import process, TabRow, PipelineResult
from stitch import make_pdf_from_rows, verify_and_clean_pdf
from util import imread, imwrite, log
from rows import row_fingerprint, _fp_dist

# 缩略图尺寸
THUMB_W, THUMB_H = 480, 90

# 简洁黑白主题 QSS
QSS = """
* { font-family: "Microsoft YaHei", "Segoe UI", sans-serif; font-size: 13px; }
QMainWindow, QDialog, QWidget { background: #fafafa; color: #1a1a1a; }
QLabel { color: #1a1a1a; }
QLabel#appTitle { color: #000000; font-size: 19px; font-weight: bold; }
QLabel#sectionTitle { color: #000000; font-size: 14px; font-weight: bold; }
QLabel#hint { color: #888888; font-size: 12px; }

QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox {
    background: #ffffff; border: 1px solid #cccccc; border-radius: 4px;
    padding: 7px 10px; color: #1a1a1a; selection-background-color: #333333;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #333333;
}
QSpinBox::up-button, QDoubleSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::down-button {
    background: #f0f0f0; border: none; width: 16px;
}

QPushButton {
    background: #ffffff; border: 1px solid #cccccc; border-radius: 4px;
    padding: 8px 18px; color: #1a1a1a;
}
QPushButton:hover { background: #f0f0f0; border-color: #999999; }
QPushButton:pressed { background: #e0e0e0; }
QPushButton:disabled { color: #aaaaaa; border-color: #dddddd; }

QPushButton#primary {
    background: #1a1a1a; color: #ffffff; font-weight: bold; border: none;
    padding: 10px 24px;
}
QPushButton#primary:hover { background: #333333; }
QPushButton#primary:disabled { background: #cccccc; color: #888888; }

QListWidget {
    background: #ffffff; border: 1px solid #cccccc; border-radius: 4px;
    padding: 4px; outline: none;
}
QListWidget::item { color: #1a1a1a; border-radius: 3px; padding: 2px; }
QListWidget::item:selected { background: #e0e0e0; }
QListWidget::item:hover:!selected { background: #f0f0f0; }

QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #f0f0f0; width: 10px; border-radius: 5px; }
QScrollBar::handle:vertical { background: #bbbbbb; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #888888; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }

QProgressBar {
    background: #f0f0f0; border: 1px solid #cccccc; border-radius: 4px;
    text-align: center; color: #1a1a1a; height: 18px;
}
QProgressBar::chunk { background: #1a1a1a; border-radius: 4px; }

QSplitter::handle { background: #dddddd; width: 3px; }
QCheckBox { color: #1a1a1a; spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #999999; border-radius: 3px; background: #ffffff; }
QCheckBox::indicator:checked { background: #1a1a1a; border-color: #1a1a1a; }
QMessageBox, QMessageBox QLabel { background: #ffffff; }
"""


def _safe(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    if name in ("", ".", ".."):
        return "tab"
    if name.upper() in ("CON", "PRN", "AUX", "NUL") or name[1:2] == ":":
        return "tab_" + name
    return name[:80] or "tab"


def _unique_path(path: str) -> str:
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    n = 1
    while os.path.exists(f"{base}({n}){ext}"):
        n += 1
    return f"{base}({n}){ext}"


def bgr_to_qimage(img: np.ndarray) -> QImage:
    """BGR ndarray → QImage（RGB888）。"""
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    return QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)


def bgr_to_pixmap(img: np.ndarray, max_w: int, max_h: int) -> QPixmap:
    """BGR → 缩略图 QPixmap（保持比例，白底）。"""
    h, w = img.shape[:2]
    scale = min(max_w / w, max_h / h)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    qimg = bgr_to_qimage(resized)
    return QPixmap.fromImage(qimg)


class Worker(QThread):
    """后台处理线程（QThread + Signal）。"""

    progress = Signal(str, float)
    done = Signal(object, bool)      # (PipelineResult, auto)
    error = Signal(str)

    def __init__(self, url, auto, interval, max_height, title, work_dir, parent=None):
        super().__init__(parent)
        self.url = url
        self.auto = auto
        self.interval = interval
        self.max_height = max_height
        self.title = title
        self.work_dir = work_dir

    def run(self):
        try:
            result = process(
                url=self.url if re.match(r"^https?://", self.url) else None,
                video=self.url if not re.match(r"^https?://", self.url) else None,
                title=self.title,
                interval=self.interval,
                max_height=self.max_height if self.max_height > 0 else 720,
                work_dir=self.work_dir,
                allow_manual=False,  # 后台线程不能弹手动框选窗口
                progress=lambda text, frac: self.progress.emit(text, frac),
            )
            self.done.emit(result, self.auto)
        except SystemExit as e:
            self.error.emit(f"处理被终止: {e}")
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """主窗口。"""

    _output_signal = Signal(bool, str, str)  # (成功?, pdf路径/错误, img_dir)

    def __init__(self):
        super().__init__()
        try:
            from _build_info import BUILD_TIME
            self.setWindowTitle(f"B站吉他谱提取器 (构建 {BUILD_TIME})")
        except Exception:
            self.setWindowTitle("B站吉他谱提取器")
        self.resize(700, 560)
        self.worker: Worker | None = None
        self.result: PipelineResult | None = None
        self.work_dir: str | None = None
        self.review_rows: list[TabRow] | None = None   # 核验暂存（退出后可重开）
        self.review_result: PipelineResult | None = None
        self.review: ReviewWindow | None = None

        self._output_signal.connect(self._on_output_result)
        self._build_ui()

    def _on_output_result(self, ok: bool, pdf_path: str, img_dir: str):
        if ok:
            self.status_label.setText("输出完成")
            self._log(f"PDF 已生成: {pdf_path}")
            self._log(f"谱行图片: {img_dir}")
            QMessageBox.information(self, "完成",
                                    f"输出完成！\nPDF: {pdf_path}\n图片: {img_dir}")
        else:
            self.status_label.setText("输出失败")
            self._log(f"输出失败: {pdf_path}")
            QMessageBox.critical(self, "输出失败", pdf_path)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        lay = QVBoxLayout(central)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)

        title = QLabel("B站吉他谱视频 → PDF")
        title.setObjectName("appTitle")
        lay.addWidget(title)
        hint = QLabel("自动截取谱面 · 人工核验排序 · 输出 PDF")
        hint.setObjectName("hint")
        lay.addWidget(hint)

        lay.addWidget(QLabel("B站视频链接（或本地视频路径）:"))
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://www.bilibili.com/video/BV…")
        lay.addWidget(self.url_edit)

        lay.addWidget(QLabel("输出标题（留空自动用视频标题）:"))
        self.title_edit = QLineEdit()
        lay.addWidget(self.title_edit)

        opt = QHBoxLayout()
        opt.addWidget(QLabel("抽帧间隔(秒):"))
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.5, 10.0)
        self.interval_spin.setValue(2.0)
        self.interval_spin.setSingleStep(0.5)
        opt.addWidget(self.interval_spin)
        opt.addWidget(QLabel("  分辨率上限:"))
        self.maxh_spin = QSpinBox()
        self.maxh_spin.setRange(0, 1080)
        self.maxh_spin.setValue(0)
        self.maxh_spin.setSingleStep(360)
        opt.addWidget(self.maxh_spin)
        opt.addWidget(QLabel("(0=最高清晰度)"))
        opt.addStretch(1)
        lay.addLayout(opt)

        btns = QHBoxLayout()
        self.start_btn = QPushButton("开始处理")
        self.auto_btn = QPushButton("全自动（跳过核验直接输出）")
        self.reopen_review_btn = QPushButton("重新打开核验")
        self.reopen_review_btn.setEnabled(False)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setEnabled(False)
        btns.addWidget(self.start_btn)
        btns.addWidget(self.auto_btn)
        btns.addWidget(self.reopen_review_btn)
        btns.addWidget(self.cancel_btn)
        btns.addStretch(1)
        lay.addLayout(btns)

        self.start_btn.clicked.connect(lambda: self._start(False))
        self.auto_btn.clicked.connect(lambda: self._start(True))
        self.reopen_review_btn.clicked.connect(self._reopen_review)
        self.cancel_btn.clicked.connect(self._cancel)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        lay.addWidget(self.progress)

        self.status_label = QLabel("就绪")
        lay.addWidget(self.status_label)

        lay.addWidget(QLabel("处理日志:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(140)
        lay.addWidget(self.log_text)

    def _log(self, msg: str):
        self.log_text.append(msg)

    def _start(self, auto: bool):
        if self.worker and self.worker.isRunning():
            return
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "提示", "请输入 B 站视频链接或本地视频路径")
            return

        # 清理旧的临时目录
        import glob
        for d in glob.glob(os.path.join(os.getcwd(), "_gui_work_*")):
            if d != self.work_dir:
                try:
                    shutil.rmtree(d, ignore_errors=True)
                except Exception:
                    pass

        self.work_dir = os.path.join(os.getcwd(), "_gui_work_" + str(int(time.time())))
        os.makedirs(self.work_dir, exist_ok=True)

        self.start_btn.setEnabled(False)
        self.auto_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress.setValue(0)
        self.status_label.setText("处理中…")
        self._log("开始处理: " + url)

        self.worker = Worker(
            url=url,
            auto=auto,
            interval=self.interval_spin.value(),
            max_height=self.maxh_spin.value(),
            title=self.title_edit.text().strip() or None,
            work_dir=self.work_dir,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.done.connect(self._on_done)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _cancel(self):
        self.status_label.setText("正在停止…（等待当前步骤完成）")
        self._log("已请求取消")

    def _on_progress(self, text, frac):
        self.status_label.setText(text)
        self.progress.setValue(int(frac))

    def _on_done(self, result: PipelineResult, auto: bool):
        self.result = result
        self.start_btn.setEnabled(True)
        self.auto_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress.setValue(100)
        self.status_label.setText(
            f"完成：{len(result.kept_rows)} 行谱面（共截取 {len(result.all_rows)} 行）")
        self._log(f"处理完成：标题「{result.title}」，自动保留 {len(result.kept_rows)} 行")
        if auto:
            self._output(result.kept_rows, result.title)
        else:
            self.review_rows = None
            self.review_result = result
            self.review = ReviewWindow(self, result)
            self.review.show()

    def _reopen_review(self):
        """重新打开核验窗口（恢复上次的排序/增删状态）。"""
        if self.review_result is None:
            QMessageBox.information(self, "提示", "没有可重新打开的核验")
            return
        if self.review is not None and self.review.isVisible():
            self.review.raise_()
            self.review.activateWindow()
            return
        self.review = ReviewWindow(self, self.review_result)
        self.review.show()

    def _on_error(self, err: str):
        self.start_btn.setEnabled(True)
        self.auto_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.status_label.setText("处理失败")
        self._log("错误: " + err)
        QMessageBox.critical(self, "处理失败", err)

    def _output(self, rows, title):
        """输出 PDF + 图片（后台线程）。"""
        if not rows:
            QMessageBox.warning(self, "提示", "没有可输出的谱行")
            return
        out_dir = os.path.join(os.getcwd(), "out", _safe(title))
        os.makedirs(out_dir, exist_ok=True)
        pdf_path = _unique_path(os.path.join(out_dir, f"{_safe(title)}.pdf"))
        img_dir = os.path.join(out_dir, "谱行图片")

        self.status_label.setText("正在输出…")
        self._log(f"开始输出：{len(rows)} 行 → {out_dir}")

        def worker():
            try:
                os.makedirs(img_dir, exist_ok=True)
                for i, row in enumerate(rows):
                    imwrite(os.path.join(img_dir, f"行{i + 1:03d}.png"), row.image)
                make_pdf_from_rows([(r.image, r.source, r.index) for r in rows],
                                   pdf_path, title)
                verify_and_clean_pdf(pdf_path)
                self._output_signal.emit(True, pdf_path, img_dir)
            except SystemExit as e:
                self._output_signal.emit(False, f"处理被终止: {e}", "")
            except Exception as e:
                self._output_signal.emit(False, str(e), "")

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait(1000)
        if self.work_dir and os.path.isdir(self.work_dir):
            try:
                shutil.rmtree(self.work_dir, ignore_errors=True)
            except Exception:
                pass
        super().closeEvent(event)


class ZoomDialog(QDialog):
    """双击弹出的可缩放大图窗口（滚轮缩放）。"""

    def __init__(self, img: np.ndarray, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1000, 720)
        self.img = img
        self.scale = 1.0

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.label = QLabel(self.scroll)
        self.label.setAlignment(Qt.AlignCenter)
        self.scroll.setWidget(self.label)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.scroll)

        self._refresh()

    def _refresh(self):
        h, w = self.img.shape[:2]
        nw = max(1, int(w * self.scale))
        nh = max(1, int(h * self.scale))
        resized = cv2.resize(self.img, (nw, nh), interpolation=cv2.INTER_AREA)
        pixmap = QPixmap.fromImage(bgr_to_qimage(resized))
        self.label.setPixmap(pixmap)
        self.label.adjustSize()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self.scale = min(8.0, self.scale * 1.2)
        else:
            self.scale = max(0.1, self.scale / 1.2)
        self._refresh()


class ReviewWindow(QMainWindow):
    """人工核验窗口：大缩略图拖拽排序 + 侧边栏预览 + 双击全屏 + 相似行标黄 + 导航。"""

    def __init__(self, main_win: MainWindow, result: PipelineResult):
        super().__init__(main_win)
        self.main_win = main_win
        self.result = result
        # 若之前核验过（退出后重开），恢复上次顺序
        if main_win.review_rows is not None and main_win.review_result is result:
            self.rows = list(main_win.review_rows)
        else:
            self.rows = list(result.kept_rows)
        self._thumbs: dict[int, QPixmap] = {}
        self._similar: dict[int, list[int]] = {}  # 原始索引 -> 相似行索引列表
        self._compute_similar()

        self.setWindowTitle(f"人工核验 - {result.title}")
        self.resize(1250, 800)

        self._build_ui()
        self._render_list()

    def _compute_similar(self):
        """检测大致相同的行（指纹距离 < 阈值 且 像素差异小），标黄供人工核验。"""
        self._similar.clear()
        if len(self.rows) < 2:
            return
        fps = [row_fingerprint(r.image) for r in self.rows]
        n = len(fps)
        for i in range(n):
            for j in range(i + 1, n):
                if _fp_dist(fps[i], fps[j]) >= 6.0:
                    continue
                # 像素级确认：高度对齐后比较，差异小才算"大致相同"
                a = self.rows[i].image
                b = self.rows[j].image
                h = min(a.shape[0], b.shape[0])
                if h <= 0:
                    continue
                a2 = a if a.shape[0] == h else cv2.resize(a, (a.shape[1], h))
                b2 = b if b.shape[0] == h else cv2.resize(b, (b.shape[1], h))
                diff = np.abs(a2.astype(np.int16) - b2.astype(np.int16)) > 40
                if float(diff.mean()) < 0.05:
                    self._similar.setdefault(i, []).append(j)
                    self._similar.setdefault(j, []).append(i)
        self._similar_groups = self._build_groups()

    def _build_groups(self) -> list[list[int]]:
        """把相似行聚类成分组（连通分量），返回组列表。"""
        seen = set()
        groups = []
        for i in self._similar:
            if i in seen:
                continue
            stack = [i]
            comp = []
            while stack:
                k = stack.pop()
                if k in seen:
                    continue
                seen.add(k)
                comp.append(k)
                stack.extend(self._similar.get(k, []))
            if len(comp) >= 2:
                groups.append(sorted(comp))
        return groups

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        lay = QVBoxLayout(central)
        lay.setContentsMargins(10, 10, 10, 10)

        # 顶部：标题 + 导航看板
        top = QHBoxLayout()
        top.addWidget(QLabel(f"「{self.result.title}」  共 {len(self.rows)} 行谱面"))
        if self._similar_groups:
            n_dup = sum(len(g) for g in self._similar_groups)
            lbl = QLabel(f"  疑似重复 {len(self._similar_groups)} 组（{n_dup} 行，已标黄）")
            lbl.setStyleSheet("color: #b8860b; font-weight: bold;")
            top.addWidget(lbl)
        top.addStretch(1)
        # 导航看板：行号跳转
        top.addWidget(QLabel("跳转到第"))
        self.jump_spin = QSpinBox()
        self.jump_spin.setRange(1, max(1, len(self.rows)))
        self.jump_spin.setFixedWidth(70)
        top.addWidget(self.jump_spin)
        top.addWidget(QLabel("行"))
        self.jump_btn = QPushButton("定位")
        self.jump_btn.clicked.connect(self._jump_to)
        top.addWidget(self.jump_btn)
        self.next_sim_btn = QPushButton("下一处疑似重复")
        self.next_sim_btn.clicked.connect(self._next_similar)
        top.addWidget(self.next_sim_btn)
        lay.addLayout(top)

        # 左右分栏：列表 + 预览
        splitter = QSplitter(Qt.Horizontal)
        lay.addWidget(splitter, 1)

        # 左：缩略图列表
        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(THUMB_W, THUMB_H))
        self.list_widget.setSpacing(6)
        self.list_widget.setDragDropMode(QListWidget.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.MoveAction)
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        # 连续平滑滚动：像素级滚动 + 惯性
        self.list_widget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.list_widget.verticalScrollBar().setSingleStep(24)
        QScroller.grabGesture(self.list_widget, QScroller.LeftMouseButtonGesture)
        self.list_widget.currentItemChanged.connect(self._on_select)
        self.list_widget.itemDoubleClicked.connect(self._on_double_click)
        splitter.addWidget(self.list_widget)

        # 右：侧边栏预览
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_label = QLabel("点击左侧缩略图查看大图")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background: #f0f0f0; color: #888;")
        self.preview_scroll.setWidget(self.preview_label)
        splitter.addWidget(self.preview_scroll)
        splitter.setSizes([680, 470])

        # 操作按钮
        ops = QHBoxLayout()
        ops.addWidget(QLabel("操作:"))
        self.del_btn = QPushButton("删除选中行")
        self.del_btn.clicked.connect(self._delete_selected)
        ops.addWidget(self.del_btn)
        self.recover_btn = QPushButton("找回被丢弃的行…")
        self.recover_btn.clicked.connect(self._recover)
        ops.addWidget(self.recover_btn)
        self.import_btn = QPushButton("导入本地图片…")
        self.import_btn.clicked.connect(self._import_image)
        ops.addWidget(self.import_btn)
        ops.addStretch(1)
        lay.addLayout(ops)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.auto_out_btn = QPushButton("全自动输出（跳过核验）")
        self.auto_out_btn.clicked.connect(self._auto_output)
        bottom.addWidget(self.auto_out_btn)
        self.confirm_btn = QPushButton("确认输出 PDF + 图片")
        self.confirm_btn.setObjectName("primary")
        self.confirm_btn.clicked.connect(self._confirm_output)
        bottom.addWidget(self.confirm_btn)
        lay.addLayout(bottom)

    def _render_list(self):
        self.list_widget.clear()
        self._thumbs.clear()
        for i, row in enumerate(self.rows):
            pm = bgr_to_pixmap(row.image, THUMB_W, THUMB_H)
            self._thumbs[i] = pm
            text = f"第 {i + 1} 行   {row.image.shape[1]}×{row.image.shape[0]}   t={row.time:.0f}s"
            if i in self._similar:
                text += "   ⚠ 疑似重复"
            item = QListWidgetItem(QIcon(pm), text)
            item.setData(Qt.UserRole, i)
            item.setSizeHint(QSize(THUMB_W, THUMB_H + 24))
            if i in self._similar:
                item.setBackground(QColor("#fff3cd"))  # 浅黄标出疑似重复
            self.list_widget.addItem(item)
        # 更新跳转范围
        self.jump_spin.setRange(1, max(1, len(self.rows)))

    def _jump_to(self):
        target = self.jump_spin.value() - 1  # 显示 1-based，内部 0-based
        item = self.list_widget.item(target)
        if item:
            self.list_widget.scrollToItem(item, QAbstractItemView.PositionAtCenter)
            self.list_widget.setCurrentItem(item)

    def _next_similar(self):
        """跳到下一处疑似重复（循环）。"""
        if not self._similar:
            return
        cur = self.list_widget.currentRow()
        # 收集所有相似行（按当前列表顺序的 row 号）
        sim_rows = sorted(set(j for i in self._similar for j in [i] + self._similar[i]))
        # 找当前行之后的第一个相似行
        nxt = None
        for r in sim_rows:
            if r > cur:
                nxt = r
                break
        if nxt is None and sim_rows:
            nxt = sim_rows[0]
        if nxt is not None:
            item = self.list_widget.item(nxt)
            self.list_widget.scrollToItem(item, QAbstractItemView.PositionAtCenter)
            self.list_widget.setCurrentItem(item)

    def _current_rows(self) -> list[TabRow]:
        """按当前列表顺序返回 rows（拖拽后顺序已变）。"""
        ordered = []
        for idx in range(self.list_widget.count()):
            item = self.list_widget.item(idx)
            orig = item.data(Qt.UserRole)
            ordered.append(self.rows[orig])
        return ordered

    def _on_select(self, current, _prev):
        if current is None:
            return
        orig = current.data(Qt.UserRole)
        row = self.rows[orig]
        pm = bgr_to_pixmap(row.image, 520, 420)
        self.preview_label.setPixmap(pm)
        self.preview_label.setStyleSheet("background: #f0f0f0;")

    def _on_double_click(self, item):
        orig = item.data(Qt.UserRole)
        row = self.rows[orig]
        dlg = ZoomDialog(row.image.copy(), f"第 {orig + 1} 行预览（t={row.time:.0f}s）", self)
        dlg.exec()

    def _delete_selected(self):
        item = self.list_widget.currentItem()
        if item is None:
            return
        orig = item.data(Qt.UserRole)
        del self.rows[orig]
        self._compute_similar()
        self._render_list()

    def _recover(self):
        kept_keys = {(r.source, r.index) for r in self.rows}
        recoverable = [r for r in self.result.all_rows
                       if (r.source, r.index) not in kept_keys]
        if not recoverable:
            QMessageBox.information(self, "找回", "没有可找回的行")
            return
        dlg = RecoverDialog(recoverable, self)
        if dlg.exec() == QDialog.Accepted:
            added = dlg.selected_rows()
            self.rows.extend(added)
            self.rows.sort(key=lambda r: (r.time, r.index))
            self._compute_similar()
            self._render_list()

    def _import_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择谱面图片", "",
            "图片 (*.png *.jpg *.jpeg *.bmp *.webp);;所有文件 (*.*)")
        if not path:
            return
        img = imread(path)
        if img is None:
            QMessageBox.critical(self, "错误", f"无法读取图片: {path}")
            return
        self.rows.append(TabRow(img, -1, os.path.basename(path), 0))
        self._compute_similar()
        self._render_list()

    def _confirm_output(self):
        self.main_win._output(self._current_rows(), self.result.title)
        self.close()

    def _auto_output(self):
        self.main_win._output(self._current_rows(), self.result.title)
        self.close()

    def closeEvent(self, event):
        """关闭时把当前顺序存回主窗口，以便随时重新打开核验继续编辑。"""
        try:
            self.main_win.review_rows = self._current_rows()
            self.main_win.review_result = self.result
            self.main_win.reopen_review_btn.setEnabled(True)
            self.main_win._log(f"核验已暂存 {len(self.main_win.review_rows)} 行（可重新打开继续）")
        except Exception:
            pass
        super().closeEvent(event)


class RecoverDialog(QDialog):
    """找回被丢弃行的对话框（勾选 + 缩略图）。"""

    def __init__(self, rows, parent=None):
        super().__init__(parent)
        self.setWindowTitle("找回被丢弃的行")
        self.resize(760, 560)
        self.rows = rows
        self._checks = []

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"共 {len(rows)} 行被自动丢弃（可能是重复或非谱面），勾选要加回的："))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner_lay = QVBoxLayout(inner)
        from PySide6.QtWidgets import QCheckBox
        for i, row in enumerate(rows):
            chk = QCheckBox(f"时间 {row.time:.0f}s  {row.image.shape[1]}×{row.image.shape[0]}")
            chk.setIcon(QIcon(bgr_to_pixmap(row.image, 200, 40)))
            chk.setIconSize(QSize(200, 40))
            self._checks.append(chk)
            inner_lay.addWidget(chk)
        inner_lay.addStretch(1)
        scroll.setWidget(inner)
        lay.addWidget(scroll)

        btns = QHBoxLayout()
        ok = QPushButton("加回选中的行")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        btns.addStretch(1)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        lay.addLayout(btns)

    def selected_rows(self):
        return [row for row, chk in zip(self.rows, self._checks) if chk.isChecked()]


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # 跨平台一致的现代样式
    app.setStyleSheet(QSS)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
