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
from PySide6.QtCore import (Qt, QSize, QThread, Signal, QEasingCurve,
                            QPropertyAnimation, QTimer)
from PySide6.QtGui import QImage, QPixmap, QIcon, QPainter, QColor, QBrush
from PySide6.QtWidgets import ( 
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QProgressBar, QTextEdit,
    QListWidget, QListWidgetItem, QSplitter, QDialog, QScrollArea,
    QFileDialog, QMessageBox, QSpinBox, QDoubleSpinBox, QStyle,
    QAbstractItemView, QScroller, QGridLayout,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
)

from pipeline import process, TabRow, PipelineResult
from stitch import make_pdf_from_rows, verify_and_clean_pdf
from util import imread, imwrite, log
from rows import row_fingerprint, _fp_dist
from vlm import (DEFAULT_MODEL, load_api_key, load_config_key, load_model,
                 save_api_key)
from vlm_dedup import bar_label
from vlm_recognize import (analyze_rows, find_duplicate_groups,
                           find_incomplete_rows)

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


class GuiLogStream:
    """把 print 输出（逐行）转发到 GUI 日志框。

    PyInstaller --windowed 下 sys.stdout 是无效流，pipeline 里的
    log.step/info/warn（都是 print）会全部丢失；处理期间重定向到本类，
    日志就能实时显示在界面里（抽帧数量/谱面类型/VLM 识别小节号/拼接/去重等）。
    """

    def __init__(self, emit):
        self._emit = emit
        self._buf = ""

    def write(self, s):
        try:
            self._buf += s
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                line = line.rstrip()
                if line:
                    self._emit(line)
        except Exception:
            pass
        return len(s)

    def flush(self):
        if self._buf.strip():
            try:
                self._emit(self._buf.rstrip())
            except Exception:
                pass
        self._buf = ""

    def isatty(self):
        return False


class Worker(QThread):
    """后台处理线程（QThread + Signal）。"""

    progress = Signal(str, float)
    done = Signal(object, bool)      # (PipelineResult, auto)
    error = Signal(str)
    log_msg = Signal(str)            # pipeline 内部日志（print 转发）

    def __init__(self, url, auto, interval, max_height, title, work_dir, parent=None):
        super().__init__(parent)
        self.url = url
        self.auto = auto
        self.interval = interval
        self.max_height = max_height
        self.title = title
        self.work_dir = work_dir

    def run(self):
        import sys as _sys

        stream = GuiLogStream(self.log_msg.emit)
        old_out, old_err = _sys.stdout, _sys.stderr
        _sys.stdout = stream
        _sys.stderr = stream
        try:
            result = process(
                url=self.url if re.match(r"^https?://", self.url) else None,
                video=self.url if not re.match(r"^https?://", self.url) else None,
                title=self.title,
                interval=self.interval,
                max_height=self.max_height if self.max_height > 0 else 720,
                work_dir=self.work_dir,
                allow_manual=False,  # 后台线程不能弹手动框选窗口
                api_key=load_api_key(),  # 横向滚动谱面用 VLM 读小节号
                progress=lambda text, frac: self.progress.emit(text, frac),
            )
            self.done.emit(result, self.auto)
        except SystemExit as e:
            self.error.emit(f"处理被终止: {e}")
        except Exception as e:
            self.error.emit(str(e))
        finally:
            stream.flush()
            _sys.stdout, _sys.stderr = old_out, old_err


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
        self.settings_btn = QPushButton("AI 设置")
        btns.addWidget(self.start_btn)
        btns.addWidget(self.auto_btn)
        btns.addWidget(self.reopen_review_btn)
        btns.addWidget(self.cancel_btn)
        btns.addWidget(self.settings_btn)
        btns.addStretch(1)
        lay.addLayout(btns)

        self.start_btn.clicked.connect(lambda: self._start(False))
        self.auto_btn.clicked.connect(lambda: self._start(True))
        self.reopen_review_btn.clicked.connect(self._reopen_review)
        self.cancel_btn.clicked.connect(self._cancel)
        self.settings_btn.clicked.connect(self._open_settings)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        lay.addWidget(self.progress)

        self.status_label = QLabel("就绪")
        lay.addWidget(self.status_label)

        self.ai_status_label = QLabel(self._ai_status_text())
        self.ai_status_label.setObjectName("hint")
        lay.addWidget(self.ai_status_label)

        lay.addWidget(QLabel("处理日志:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(140)
        lay.addWidget(self.log_text)

    def _ai_status_text(self) -> str:
        key = load_api_key()
        if key:
            return f"AI：已配置 Key（{key[:6]}…{key[-4:]}），核验页可用 AI 识别去重"
        return "AI：未配置 Key（点「AI 设置」填写，启用 AI 识别/去重）"

    def _open_settings(self):
        """AI 设置对话框：配置 API Key。"""
        dlg = ApiSettingsDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self.ai_status_label.setText(self._ai_status_text())
            self._log("AI 设置已更新")

    def _log(self, msg: str):
        self.log_text.append(msg)

    def _work_base_dir(self) -> str:
        """工作目录基路径（保证可写）。

        不能用 os.getcwd()：
        - 从 IDE/终端启动时 cwd 可能是不存在的目录（如 D:\\Microsoft VS），
          导致 yt-dlp 写视频报 "Postprocessing: Error opening output files:
          Permission denied"。
        优先：exe 所在目录（打包模式）/ 项目根目录（源码模式）→ 系统临时目录。
        """
        import tempfile

        if getattr(sys, "frozen", False):
            cands = [os.path.dirname(sys.executable)]
        else:
            here = os.path.dirname(os.path.abspath(__file__))
            cands = [os.path.dirname(here), here]   # 项目根优先，其次包目录
        cands.append(tempfile.gettempdir())
        for d in cands:
            try:
                test = os.path.join(d, "_wtest_%d.tmp" % os.getpid())
                with open(test, "w", encoding="utf-8") as f:
                    f.write("x")
                os.remove(test)
                return d
            except Exception:
                continue
        return tempfile.gettempdir()

    def _start(self, auto: bool):
        if self.worker and self.worker.isRunning():
            return
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "提示", "请输入 B 站视频链接或本地视频路径")
            return

        # 工作目录基路径：不能用 os.getcwd()（从 IDE/终端启动时 cwd 可能是
        # 无写权限的目录，导致 yt-dlp 写文件报 "Permission denied"）。
        base = self._work_base_dir()
        # 清理旧的临时目录
        import glob
        for d in glob.glob(os.path.join(base, "_gui_work_*")):
            if d != self.work_dir:
                try:
                    shutil.rmtree(d, ignore_errors=True)
                except Exception:
                    pass

        self.work_dir = os.path.join(base, "_gui_work_" + str(int(time.time())))
        try:
            os.makedirs(self.work_dir, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(
                self, "无法创建工作目录",
                f"无法创建临时工作目录：\n{self.work_dir}\n\n{e}\n\n"
                f"请检查磁盘空间/目录权限。")
            return

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
        self.worker.log_msg.connect(self._log)   # pipeline 内部日志 → 界面
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


class ApiSettingsDialog(QDialog):
    """AI 设置对话框：配置 AI 提供商、API Key 与模型。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI 设置")
        self.resize(600, 330)
        from PySide6.QtWidgets import QComboBox
        from vlm import PROVIDERS, load_provider

        lay = QVBoxLayout(self)

        # 提供商选择
        lay.addWidget(QLabel("AI 提供商："))
        self.provider_combo = QComboBox()
        self._providers = PROVIDERS
        for pid, p in PROVIDERS.items():
            self.provider_combo.addItem(p["name"], pid)
        cur_p = load_provider()
        idx = self.provider_combo.findData(cur_p)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)
        lay.addWidget(self.provider_combo)

        lay.addWidget(QLabel("API Key："))
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText("sk-...")
        lay.addWidget(self.key_edit)

        lay.addWidget(QLabel("模型（可下拉选择推荐模型，也可手动输入）："))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)   # 允许手动输入非列表模型
        lay.addWidget(self.model_combo)

        self.hint = QLabel("")
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)

        self.test_label = QLabel("")
        lay.addWidget(self.test_label)

        btns = QHBoxLayout()
        self.test_btn = QPushButton("测试连接")
        self.test_btn.clicked.connect(self._test)
        self.save_btn = QPushButton("保存")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self._save)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        btns.addStretch(1)
        btns.addWidget(self.test_btn)
        btns.addWidget(cancel)
        btns.addWidget(self.save_btn)
        lay.addLayout(btns)

        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        self._on_provider_changed()   # 初始化：填充 Key/模型/提示

    def _on_provider_changed(self):
        """切换提供商：刷新 Key、模型列表、提示文字。"""
        from vlm import load_config_key, load_model
        pid = self.provider_combo.currentData() or "dashscope"
        prov = self._providers.get(pid, {})
        # Key（按提供商分别读取）
        self.key_edit.setText(load_config_key(pid) or "")
        # 模型列表
        self.model_combo.clear()
        for code, desc in prov.get("models", []):
            self.model_combo.addItem(f"{code}    （{desc}）", code)
        cur = load_model(pid)
        idx = self.model_combo.findData(cur)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        else:
            self.model_combo.setEditText(cur)
        # 提示
        if pid == "deepseek":
            self.hint.setText(
                "申请地址：https://platform.deepseek.com → API keys\n"
                "注意：deepseek-flash 是推理模型，单张图 30-60 秒（慢但识别准），"
                "max_tokens 需给足。\n"
                "Key 保存在 bili_tab_extractor/vlm_config.json（已 gitignore，不会上传）。")
        else:
            self.hint.setText(
                "申请地址：https://bailian.console.aliyun.com → API-KEY 管理\n"
                "提示：主模型额度耗尽（403）时会自动降级到 qwen-vl-ocr 系列（会弹框确认）。\n"
                "Key 保存在 bili_tab_extractor/vlm_config.json（已 gitignore，不会上传）。")

    def _current_model(self) -> str:
        """当前选中的模型 code（下拉项取 data，手动输入取文本）。"""
        text = self.model_combo.currentText().strip()
        code = self.model_combo.currentData()
        if code and text.startswith(str(code)):
            return str(code)
        return text.split("    ")[0].strip()

    def _save(self):
        from vlm import save_api_key, set_provider
        key = self.key_edit.text().strip()
        pid = self.provider_combo.currentData() or "dashscope"
        if not key:
            QMessageBox.warning(self, "提示", "请填写 API Key")
            return
        save_api_key(key, self._current_model() or None, provider=pid)
        set_provider(pid)
        self.accept()

    def _test(self):
        key = self.key_edit.text().strip()
        if not key:
            self.test_label.setText("请先填写 API Key")
            return
        pid = self.provider_combo.currentData() or "dashscope"
        prov = self._providers.get(pid, {})
        base_url = prov.get("base_url", "")
        model = self._current_model()
        self.test_label.setText("测试中…")
        self.test_btn.setEnabled(False)
        try:
            import requests
            # 实际测"当前模型"能否调用（比 /models 列表更准）。
            # 推理模型（deepseek-flash）max_tokens 太小会被 reasoning 吃掉，
            # 这里只验证连通性，max_tokens 给小值即可（返回 200 就算通）。
            r = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"},
                json={"model": model,
                      "messages": [{"role": "user", "content": "hi"}],
                      "max_tokens": 5},
                timeout=60)
            if r.status_code == 200:
                self.test_label.setText(f"连接成功（{prov.get('name', pid)} / {model} 可用）")
            elif r.status_code == 403:
                code = ""
                try:
                    code = str(r.json().get("error", {}).get("code", ""))
                except Exception:
                    pass
                self.test_label.setText(
                    f"模型 {model} 额度/权限不足（403 {code}）—— 保存后处理时会自动降级")
            else:
                self.test_label.setText(f"失败：HTTP {r.status_code} {r.text[:100]}")
        except Exception as e:
            self.test_label.setText(f"失败：{e}")
        finally:
            self.test_btn.setEnabled(True)


class BarReader(QThread):
    """后台用 VLM 分析所有行（识别内容 + 碎片判定 + 语义去重依据），带进度。"""

    progress = Signal(int, int)   # (done, total)
    done = Signal(object)         # {row_index: 分析结果dict}
    error = Signal(str)
    ask_fallback = Signal(str, str, str, object)  # (失败模型, 错误, 备用模型, 上下文)

    def __init__(self, rows, cache_path, api_key=None, parent=None):
        super().__init__(parent)
        self.rows = rows
        self.cache_path = cache_path
        self.api_key = api_key

    def run(self):
        import threading

        import vlm as _vlm

        def asker(failed_model: str, err_msg: str, use_model: str) -> bool:
            """跨线程：发信号到主线程弹框确认，阻塞等待用户选择。"""
            ctx = {"event": threading.Event(), "ok": True}
            self.ask_fallback.emit(failed_model, err_msg, use_model, ctx)
            ctx["event"].wait(timeout=180)
            return bool(ctx["ok"])

        _vlm.set_fallback_asker(asker)
        try:
            results = analyze_rows(
                self.rows, api_key=self.api_key, cache_path=self.cache_path,
                progress=lambda d, t: self.progress.emit(d, t),
                max_workers=4)
            # 写回各行的 bars 字段（兼容旧渲染）
            for i, a in results.items():
                if i < len(self.rows):
                    self.rows[i].bars = list(a.get("bar_numbers") or [])
            self.done.emit(results)
        except SystemExit as e:
            self.error.emit(f"处理被终止: {e}")
        except Exception as e:
            self.error.emit(str(e))
        finally:
            _vlm.set_fallback_asker(None)


class PreviewView(QGraphicsView):
    """右侧大图预览：滚轮缩放 + 左键拖拽平移。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setRenderHints(self.renderHints())

    def wheelEvent(self, event):
        """滚轮缩放（不滚动滚动条）。"""
        factor = 1.15 if event.angleDelta().y() > 0 else (1.0 / 1.15)
        self.scale(factor, factor)

    def mouseDoubleClickEvent(self, event):
        # 双击由父窗口处理（打开全屏大图），这里不拦截
        super().mouseDoubleClickEvent(event)


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
        self._thumb_cache: dict[tuple, QPixmap] = {}  # (source,index) -> 缩略图缓存
        self._similar: dict[int, list[int]] = {}  # 原始索引 -> 相似行索引列表
        self._compute_similar()
        # VLM 分析状态
        self._bar_thread: BarReader | None = None
        self._bar_dups: dict[int, list[int]] = {}   # 兼容旧字段
        self._bar_done = False
        self._ai_analyses: dict[int, dict] = {}     # row_idx -> 分析结果
        self._ai_done = False
        self._ai_dups: dict[int, list[int]] = {}    # row_idx -> 重复的其它行
        self._ai_dup_groups: list[list[int]] = []
        self._incomplete_rows: set[int] = set()     # 碎片/空谱行
        # 撤销/重做栈（存完整状态快照）
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        # 重复组交互状态
        self._active_group: int | None = None   # 当前激活的重复组索引
        self._hover_group: int | None = None    # 鼠标悬停的组（整组高亮）
        self._blink_on = True                   # 闪烁相位
        self._nav_group_of: dict[int, int] = {} # 行索引 -> 组索引
        self._nav_group_rows: list[list[int]] = []  # 组索引 -> 行索引列表

        self.setWindowTitle(f"人工核验 - {result.title}")
        self.resize(1250, 800)

        self._build_ui()
        self._render_list()

    # ---------- AI 识别 + 去重（VLM 主导） ----------
    def _on_ai_analyze(self):
        """后台用 VLM 分析所有行：识别内容、标记碎片/空谱、找出语义重复。"""
        if self._bar_thread and self._bar_thread.isRunning():
            return
        key = load_api_key()
        if not key:
            QMessageBox.warning(
                self, "未配置 API Key",
                "请先在主窗口点「AI 设置」填写 API Key。")
            return
        cache_path = os.path.join(
            self.main_win.work_dir or os.getcwd(), "vlm_analysis_cache.json")
        self.status_top.setText("AI 分析中…")
        self.read_bars_btn.setEnabled(False)
        self._bar_thread = BarReader(self.rows, cache_path, api_key=key, parent=self)
        self._bar_thread.progress.connect(self._on_ai_progress)
        self._bar_thread.done.connect(self._on_ai_done)
        self._bar_thread.error.connect(self._on_ai_error)
        self._bar_thread.ask_fallback.connect(self._on_ask_fallback)
        self._bar_thread.start()

    def _on_ask_fallback(self, failed_model: str, err_msg: str, use_model: str, ctx: dict):
        """模型降级前询问用户（跨线程：由 Worker 发信号到主线程弹框）。"""
        self._log(f"[警告] 模型 {failed_model} 调用失败：{err_msg}")
        reply = QMessageBox.question(
            self, "AI 模型额度不足",
            f"模型 {failed_model} 调用失败：\n{err_msg}\n\n"
            f"是否自动切换到备用模型 {use_model} 继续？\n"
            f"（选「否」将中止本次 AI 分析）",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        ctx["ok"] = (reply == QMessageBox.Yes)
        ctx["event"].set()
        if ctx["ok"]:
            self._log(f"已确认降级 → {use_model}")
        else:
            self._log("用户拒绝降级，已中止")

    def _on_ai_progress(self, done: int, total: int):
        self.status_top.setText(f"AI 分析中… {done}/{total}")

    def _on_ai_error(self, err: str):
        self.status_top.setText("AI 分析失败")
        self.read_bars_btn.setEnabled(True)
        QMessageBox.critical(self, "AI 分析失败", err)

    def _on_ai_done(self, analyses: dict):
        """AI 分析完成：标记碎片行、重复组，显示识别内容。"""
        self._ai_analyses = analyses
        self._ai_done = True
        self.read_bars_btn.setEnabled(True)

        # 碎片/空谱行（VLM 判定 + CV 复核）
        self._incomplete_rows = set(find_incomplete_rows(analyses, self.rows))
        # 语义重复组
        self._ai_dup_groups = find_duplicate_groups(analyses)
        self._ai_dups = {}
        for g in self._ai_dup_groups:
            for i in g:
                self._ai_dups.setdefault(i, [x for x in g if x != i])

        n_frag = len(self._incomplete_rows)
        n_dup = len(self._ai_dup_groups)
        self.status_top.setText(
            f"AI 分析完成：{len(analyses)} 行｜碎片/空谱 {n_frag} 行｜疑似重复 {n_dup} 组")
        self._log(f"AI 分析完成：碎片 {n_frag} 行，重复 {n_dup} 组")
        self.clean_btn.setEnabled(True)
        self._render_list()

    def _on_read_bars(self):
        # 兼容旧调用：统一走 AI 分析
        self._on_ai_analyze()

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
                # 形状安全：行高/行宽可能不等（crop_screen_top 逐帧裁掉不同
                # 高度的顶部演奏画面），统一到较小尺寸再逐像素比较，否则
                # numpy 会报 "operands could not be broadcast together"。
                h = min(a.shape[0], b.shape[0])
                w = min(a.shape[1], b.shape[1])
                if h <= 0 or w <= 0:
                    continue
                a2 = a if a.shape[:2] == (h, w) else cv2.resize(a, (w, h))
                b2 = b if b.shape[:2] == (h, w) else cv2.resize(b, (w, h))
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
        self.status_top = QLabel("")
        top.addWidget(self.status_top)
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
        self.read_bars_btn = QPushButton("AI 识别 + 去重")
        self.read_bars_btn.clicked.connect(self._on_ai_analyze)
        top.addWidget(self.read_bars_btn)
        # 撤销 / 重做（实体按钮）
        self.undo_btn = QPushButton("↶ 撤销")
        self.undo_btn.setEnabled(False)
        self.undo_btn.setToolTip("撤销上一步（Ctrl+Z）")
        self.undo_btn.clicked.connect(self._undo)
        top.addWidget(self.undo_btn)
        self.redo_btn = QPushButton("↷ 重做")
        self.redo_btn.setEnabled(False)
        self.redo_btn.setToolTip("重做被撤销的操作（Ctrl+Y）")
        self.redo_btn.clicked.connect(self._redo)
        top.addWidget(self.redo_btn)
        lay.addLayout(top)

        # 快捷键：Ctrl+Z 撤销 / Ctrl+Y（或 Ctrl+Shift+Z）重做 / Delete 删除
        from PySide6.QtGui import QKeySequence, QShortcut
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self._undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, activated=self._redo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, activated=self._redo)
        QShortcut(QKeySequence("Delete"), self, activated=self._delete_selected)

        # 方块阵列导航：每行一个色块，点击跳转；左侧带图例
        nav_row = QHBoxLayout()
        nav_row.setSpacing(6)
        nav_title = QLabel("导航")
        nav_title.setObjectName("sectionTitle")
        nav_row.addWidget(nav_title)
        # 图例：绿=正常 / 黄=疑似重复 / 红=残谱
        for color, text in (("#81c784", "正常"),
                            ("#ffd54f", "疑似重复"),
                            ("#ef5350", "残谱")):
            box = QLabel()
            box.setFixedSize(12, 12)
            box.setStyleSheet(
                f"background:{color}; border:1px solid #999; border-radius:2px;")
            nav_row.addWidget(box)
            nav_row.addWidget(QLabel(text))
        nav_row.addSpacing(14)
        self.nav_container = QWidget()
        self.nav_grid = QGridLayout(self.nav_container)
        self.nav_grid.setContentsMargins(0, 0, 0, 0)
        self.nav_grid.setSpacing(2)
        self.nav_buttons: list[QPushButton] = []
        self._nav_base_color: dict[int, str] = {}
        nav_row.addWidget(self.nav_container)
        nav_row.addStretch(1)
        lay.addLayout(nav_row)

        # 浮动操作条：激活重复组时出现在导航区正下方（靠近操作，不用跑到底部）
        self.float_bar = QWidget()
        self.float_bar.setObjectName("floatBar")
        self.float_bar.setStyleSheet(
            "QWidget#floatBar {"
            "  background: #ffffff;"
            "  border: 1px solid #d0d0d0;"
            "  border-radius: 6px;"
            "}")
        self.float_bar.setAttribute(Qt.WA_StyledBackground, True)
        bar_lay = QHBoxLayout(self.float_bar)
        bar_lay.setContentsMargins(10, 6, 10, 6)
        self.float_label = QLabel("")
        self.float_label.setStyleSheet(
            "color: #1a1a1a; font-weight: 700; font-size: 13px;"
            "border: none; background: transparent;")
        bar_lay.addWidget(self.float_label)
        bar_lay.addStretch(1)
        self.keep_first_btn = QPushButton("保留组内第一个")
        self.keep_first_btn.setStyleSheet(
            "QPushButton {"
            "  background: #00796b; color: #ffffff; font-weight: 600;"
            "  border: none; border-radius: 5px; padding: 6px 14px;"
            "}"
            "QPushButton:hover { background: #009688; }"
            "QPushButton:pressed { background: #00695c; }")
        self.keep_first_btn.setToolTip("保留该重复组第一行，删除其余（可 Ctrl+Z 撤销）")
        self.keep_first_btn.clicked.connect(self._on_keep_first)
        bar_lay.addWidget(self.keep_first_btn)
        self.keep_all_btn = QPushButton("全部保留第一个")
        self.keep_all_btn.setStyleSheet(
            "QPushButton {"
            "  background: #455a64; color: #eceff1; font-weight: 600;"
            "  border: 1px solid #607d8b; border-radius: 5px; padding: 6px 12px;"
            "}"
            "QPushButton:hover { background: #546e7a; }")
        self.keep_all_btn.setToolTip("所有重复组都只保留第一行（可 Ctrl+Z 撤销）")
        self.keep_all_btn.clicked.connect(self._on_keep_all)
        bar_lay.addWidget(self.keep_all_btn)
        self.float_bar.setVisible(False)
        lay.addWidget(self.float_bar)

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
        # 连续平滑滚动：像素级滚动（滚轮平滑）
        # 注意：不要用 QScroller.grabGesture(LeftMouseButtonGesture)——它会抢占
        # 滚动条和列表项的鼠标拖动，导致"拖滚动条"变成"拖谱条"。
        self.list_widget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.list_widget.verticalScrollBar().setSingleStep(24)
        self.list_widget.currentItemChanged.connect(self._on_select)
        self.list_widget.itemDoubleClicked.connect(self._on_double_click)
        # 右键菜单（保留组内第一个 / 删除 / 撤销）
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._on_context_menu)
        # 拖拽排序：记录拖拽前快照（支持撤销）+ 拖拽后重排 rows
        self._drag_snapshot = None
        self.list_widget.model().rowsAboutToBeMoved.connect(self._on_rows_about_to_move)
        self.list_widget.model().rowsMoved.connect(self._on_rows_moved)
        splitter.addWidget(self.list_widget)

        # 重复组方块闪烁定时器（吸引用户点击）
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._on_blink)
        self._blink_timer.start(700)

        # 右：侧边栏预览（PreviewView：滚轮缩放 + 拖拽平移）
        self.preview_view = PreviewView()
        self.preview_scene = QGraphicsScene(self.preview_view)
        self.preview_view.setScene(self.preview_scene)
        self.preview_view.setBackgroundBrush(QColor("#f0f0f0"))
        self.preview_view.setToolTip("滚轮缩放 · 按住左键拖拽平移 · 双击全屏")
        self.preview_item = None
        self.preview_pixmap = None
        self._preview_fit_done = False
        splitter.addWidget(self.preview_view)
        splitter.setSizes([680, 470])

        # 操作按钮
        ops = QHBoxLayout()
        ops.addWidget(QLabel("操作:"))
        self.del_btn = QPushButton("删除选中行")
        self.del_btn.clicked.connect(self._delete_selected)
        ops.addWidget(self.del_btn)
        self.clean_btn = QPushButton("按 AI 建议清理（删碎片+去重）")
        self.clean_btn.setEnabled(False)
        self.clean_btn.clicked.connect(self._on_clean)
        ops.addWidget(self.clean_btn)
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

    def _on_rows_about_to_move(self, *args):
        """拖拽开始：记录快照（撤销用）。"""
        self._drag_snapshot = self._snapshot()

    def _on_rows_moved(self, *args):
        """拖拽完成：按显示顺序重排 rows，重映射标记，记录撤销点。"""
        pre = self._drag_snapshot
        self._drag_snapshot = None
        old_rows = list(self.rows)
        new_order = self._current_rows()
        if [id(r) for r in new_order] == [id(r) for r in old_rows]:
            return  # 顺序没变
        self.rows = new_order
        # 旧索引 -> 新索引映射（按对象 identity）
        pos = {id(r): i for i, r in enumerate(new_order)}
        remap = {}
        for old_i, r in enumerate(old_rows):
            ni = pos.get(id(r))
            if ni is not None and ni != old_i:
                remap[old_i] = ni
        if remap:
            def rk(k):
                return remap.get(k, k)
            def remap_dict(d):
                out = {}
                for k, v in d.items():
                    nk = rk(k)
                    out[nk] = [rk(x) for x in v] if isinstance(v, list) else v
                return out
            self._ai_analyses = remap_dict(self._ai_analyses)
            self._ai_dups = remap_dict(self._ai_dups)
            self._similar = remap_dict(self._similar)
            self._incomplete_rows = {rk(x) for x in self._incomplete_rows}
            self._ai_dup_groups = [[rk(x) for x in g] for g in self._ai_dup_groups]
            self._similar_groups = [[rk(x) for x in g] for g in self._similar_groups]
        if pre is not None:
            self._undo_stack.append(pre)
            self._redo_stack.clear()
            self._update_undo_buttons()
        self._render_list()
        self.status_top.setText("已调整顺序（可 Ctrl+Z 撤销）")

    def _snapshot(self) -> dict:
        """当前完整状态快照（撤销/重做用）。"""
        return {
            "rows": list(self.rows),
            "ai_analyses": dict(self._ai_analyses),
            "ai_dups": {k: list(v) for k, v in self._ai_dups.items()},
            "ai_dup_groups": [list(g) for g in self._ai_dup_groups],
            "incomplete": set(self._incomplete_rows),
            "similar": {k: list(v) for k, v in self._similar.items()},
            "similar_groups": [list(g) for g in self._similar_groups],
            "ai_done": self._ai_done,
        }

    def _restore(self, snap: dict):
        """恢复到某个快照。"""
        self.rows = list(snap["rows"])
        self._ai_analyses = dict(snap["ai_analyses"])
        self._ai_dups = {k: list(v) for k, v in snap["ai_dups"].items()}
        self._ai_dup_groups = [list(g) for g in snap["ai_dup_groups"]]
        self._incomplete_rows = set(snap["incomplete"])
        self._similar = {k: list(v) for k, v in snap["similar"].items()}
        self._similar_groups = [list(g) for g in snap["similar_groups"]]
        self._ai_done = snap["ai_done"]

    def _push_undo(self):
        """操作前调用：保存当前状态，清空重做栈。"""
        self._undo_stack.append(self._snapshot())
        self._redo_stack.clear()
        self._update_undo_buttons()

    def _undo(self):
        if not self._undo_stack:
            return
        self._redo_stack.append(self._snapshot())
        self._restore(self._undo_stack.pop())
        self._render_list()
        self._update_undo_buttons()
        self.status_top.setText(f"已撤销（剩 {len(self.rows)} 行）")

    def _redo(self):
        if not self._redo_stack:
            return
        self._undo_stack.append(self._snapshot())
        self._restore(self._redo_stack.pop())
        self._render_list()
        self._update_undo_buttons()
        self.status_top.setText(f"已重做（剩 {len(self.rows)} 行）")

    def _update_undo_buttons(self):
        self.undo_btn.setEnabled(bool(self._undo_stack))
        self.redo_btn.setEnabled(bool(self._redo_stack))

    def _row_item_content(self, i: int):
        """第 i 行列表项内容：(缩略图, 文本, 背景色|None, tooltip|None)。"""
        row = self.rows[i]
        key = (row.source, row.index)
        pm = self._thumb_cache.get(key)
        if pm is None:
            pm = bgr_to_pixmap(row.image, THUMB_W, THUMB_H)
            self._thumb_cache[key] = pm
        text = f"第 {i + 1} 行   {row.image.shape[1]}×{row.image.shape[0]}   t={row.time:.0f}s"
        # AI 识别内容摘要
        a = self._ai_analyses.get(i) if self._ai_done else None
        if a:
            if a.get("chords"):
                text += "   " + "-".join(a["chords"][:4])
            if a.get("lyrics"):
                text += f"   「{a['lyrics'][:10]}」"
        elif row.bars:
            text += f"   {bar_label(row.bars)}"
        frag = i in self._incomplete_rows
        ai_dup = i in self._ai_dups
        pix_dup = i in self._similar
        bg = None
        tip = None
        if frag:
            text += "   ✖ 碎片/空谱"
            bg = "#ffcdd2"
            tip = "AI 判定为残谱/碎片（内容不完整），建议删除"
        elif ai_dup:
            text += "   ⚠ AI 判重复"
            group_color = self._dup_group_color()
            bg = group_color.get(i, "#ffe0b2")
            gi = next((k for k, g in enumerate(self._ai_dup_groups) if i in g), -1)
            tip = f"疑似重复（第 {gi + 1} 组）"
        elif pix_dup:
            text += "   ⚠ 疑似重复"
            bg = "#eceff1"
        return pm, text, bg, tip

    def _render_list(self):
        # 记录"当前顶部可见项"的 key（比滚动像素值更稳定：行高不同也不会跳）
        sb = self.list_widget.verticalScrollBar()
        scroll = sb.value() if self.list_widget.count() > 0 else 0
        top_key = None
        if self.list_widget.count() > 0:
            vp = self.list_widget.viewport()
            item_at_top = self.list_widget.itemAt(vp.mapTo(self.list_widget, vp.rect().topLeft()))
            if item_at_top is None:
                # 取第一个可见项
                for pos in range(self.list_widget.count()):
                    rect = self.list_widget.visualItemRect(self.list_widget.item(pos))
                    if rect.bottom() > sb.value():
                        item_at_top = self.list_widget.item(pos)
                        break
            if item_at_top is not None:
                idx = item_at_top.data(Qt.UserRole)
                if isinstance(idx, int) and 0 <= idx < len(self.rows):
                    r = self.rows[idx]
                    top_key = (r.source, r.index)
        self.list_widget.clear()
        self._thumbs.clear()
        for i in range(len(self.rows)):
            pm, text, bg, tip = self._row_item_content(i)
            self._thumbs[i] = pm
            item = QListWidgetItem(QIcon(pm), text)
            item.setData(Qt.UserRole, i)
            item.setSizeHint(QSize(THUMB_W, THUMB_H + 24))
            if bg:
                item.setBackground(QColor(bg))
            if tip:
                item.setToolTip(tip)
            self.list_widget.addItem(item)
        # 更新跳转范围与方块导航
        self.jump_spin.setRange(1, max(1, len(self.rows)))
        self._refresh_nav_grid()
        # 恢复滚动位置：优先定位到"原来的顶部项"（无跳动），找不到再按像素偏移恢复
        if top_key is not None:
            for pos in range(self.list_widget.count()):
                it = self.list_widget.item(pos)
                old_idx = it.data(Qt.UserRole)
                if 0 <= old_idx < len(self.rows):
                    r = self.rows[old_idx]
                    if (r.source, r.index) == top_key:
                        self.list_widget.scrollToItem(it, QAbstractItemView.PositionAtTop)
                        break
        else:
            self.list_widget.verticalScrollBar().setValue(scroll)

    # 重复组配色板（不同组用不同黄色系，便于区分 A1A2 / B1B2 两组）
    DUP_PALETTE = ["#ffd54f", "#ffb74d", "#ffe082", "#ffcc80",
                   "#fff176", "#ffcf40", "#ffab91", "#ffe0b2"]

    def _dup_group_color(self) -> dict[int, str]:
        """行索引 -> 该行所属重复组的颜色（不同组不同色）。"""
        out = {}
        for gi, g in enumerate(self._ai_dup_groups):
            color = self.DUP_PALETTE[gi % len(self.DUP_PALETTE)]
            for i in g:
                out[i] = color
        return out

    def _refresh_nav_grid(self):
        """方块阵列导航：按重复组排列（组内连续、组间留空隙），点击跳转/激活组。

        颜色：绿=正常 / 红=残谱 / 黄系=重复组（不同组不同黄）。
        重复组方块缓慢闪烁吸引注意；选中行粗边框；激活/悬停组整组高亮。
        """
        for btn in self.nav_buttons:
            btn.setParent(None)
            btn.deleteLater()
        self.nav_buttons = []
        self._nav_base_color = {}
        self._nav_group_of = {}
        self._nav_group_rows = []
        group_color = self._dup_group_color()

        # 重复组（AI + 像素相似）用于分组排列
        groups = self._all_dup_groups()
        row2gi: dict[int, int] = {}
        for gi, g in enumerate(groups):
            self._nav_group_rows.append(g)
            for r in g:
                row2gi[r] = gi
                self._nav_group_of[r] = gi

        # 构建槽位：组 = 连续方块 + 组后留 1 空格；散行 = 1 格
        slots: list[tuple[str, int]] = []
        i = 0
        n = len(self.rows)
        while i < n:
            gi = row2gi.get(i)
            if gi is not None and i == groups[gi][0]:
                slots.append(("group", gi))
                i = groups[gi][-1] + 1
            else:
                slots.append(("row", i))
                i += 1

        cols = 24
        row = 0
        col = 0
        for kind, payload in slots:
            if kind == "row":
                self._make_nav_button(payload, row2gi.get(payload, -1),
                                      group_color.get(payload, ""), row, col)
                col += 1
                if col >= cols:
                    col = 0
                    row += 1
            else:
                gi = payload
                for idx in groups[gi]:
                    self._make_nav_button(idx, gi, group_color.get(idx, "#ffd54f"),
                                          row, col)
                    col += 1
                    if col >= cols:
                        col = 0
                        row += 1
                # 组间空隙（留一列空白）
                col += 1
                if col >= cols:
                    col = 0
                    row += 1
        cur = self.list_widget.currentRow()
        self._highlight_nav(cur if cur >= 0 else -1)

    def _make_nav_button(self, idx: int, gi: int, color: str,
                         row: int, col: int):
        """创建一个导航方块（gi=-1 表示不属于重复组）。"""
        frag = idx in self._incomplete_rows
        pix_dup = idx in self._similar
        if frag:
            color = "#ef5350"
            tip = f"第 {idx + 1} 行：残谱/碎片"
        elif gi >= 0:
            color = color or "#ffd54f"
            g = self._nav_group_rows[gi] if 0 <= gi < len(self._nav_group_rows) else []
            rng = f"第 {g[0] + 1}-{g[-1] + 1} 行" if g else ""
            tip = (f"第 {idx + 1} 行：重复组 {gi + 1}（{rng}）"
                   f"—— 点击激活，可一键保留第一个")
        elif pix_dup:
            color = "#b0bec5"
            tip = f"第 {idx + 1} 行：疑似重复（像素）"
        else:
            color = "#81c784"
            tip = f"第 {idx + 1} 行"
        self._nav_base_color[idx] = color
        btn = QPushButton()
        btn.setFixedSize(16, 16)
        btn.setToolTip(tip)
        btn.setProperty("row_idx", int(idx))
        btn.setProperty("group_idx", int(gi))
        btn.installEventFilter(self)
        btn.clicked.connect(
            lambda checked=False, i=idx, g=gi: self._on_nav_click(i, g if g >= 0 else None))
        self.nav_grid.addWidget(btn, row, col)
        self.nav_buttons.append(btn)

    def _on_nav_click(self, idx: int, gi: int | None):
        """点导航方块：跳转；若属于重复组则激活该组。"""
        self._jump_to_index(idx)
        if gi is not None:
            self._activate_dup_group(gi)

    def _activate_dup_group(self, gi: int):
        """激活重复组：高亮整组、显示浮动操作条（含「保留组内第一个」）。"""
        if gi is None or not (0 <= gi < len(self._nav_group_rows)):
            return
        self._active_group = gi
        g = self._nav_group_rows[gi]
        if g:
            self._jump_to_index(g[0])
        self._update_keep_first_btn()
        self._highlight_nav(g[0] if g else -1)

    def _clear_active_group(self):
        """取消激活组（隐藏浮动条）。"""
        self._active_group = None
        self._update_keep_first_btn()

    def _update_keep_first_btn(self):
        """根据激活组更新浮动操作条（可见性/文字）。"""
        if self._active_group is None or self._active_group >= len(self._nav_group_rows):
            self.float_bar.setVisible(False)
            return
        g = self._nav_group_rows[self._active_group]
        if len(g) < 2:
            self.float_bar.setVisible(False)
            return
        rows_txt = f"第 {g[0] + 1} 行"
        if len(g) > 1:
            rows_txt = f"第 {g[0] + 1}、{g[0] + 2}" + (
                f"…{g[-1] + 1}" if len(g) > 2 else "") + " 行"
        self.float_label.setText(f"重复组 {self._active_group + 1}：{rows_txt}（{len(g)} 行）")
        self.keep_first_btn.setText(f"保留第一个（删其余 {len(g) - 1} 行）")
        self.float_bar.setVisible(True)
        # 有多个组时显示批量按钮
        self.keep_all_btn.setVisible(len(self._all_dup_groups()) > 1)

    def _on_keep_first(self):
        """点「保留组内第一个」：保留激活组第一行，删其余。"""
        if self._active_group is None:
            return
        g = list(self._nav_group_rows[self._active_group])
        self._active_group = None
        self._keep_first_of_group(g)

    def _on_keep_all(self):
        """批量：所有重复组都只保留第一行。"""
        groups = self._all_dup_groups()
        if not groups:
            return
        to_del: set[int] = set()
        for g in groups:
            to_del.update(g[1:])
        if not to_del:
            return
        reply = QMessageBox.question(
            self, "全部保留第一个",
            f"共 {len(groups)} 个重复组，将删除每组除第一行外的 {len(to_del)} 行，"
            f"保留 {len(self.rows) - len(to_del)} 行。\n\n确认？（可 Ctrl+Z 撤销）",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply != QMessageBox.Yes:
            return
        self._push_undo()
        for i in sorted(to_del):
            if 0 <= i < len(self.rows):
                self.result.all_rows.append(self.rows[i])
        self._remap_after_delete_rows(to_del)
        self.rows = [r for i, r in enumerate(self.rows) if i not in to_del]
        self._active_group = None
        self._render_list()
        msg = f"已批量保留各组第一个：删除 {len(to_del)} 行，剩 {len(self.rows)} 行（可撤销）"
        self.status_top.setText(msg)
        self._log(msg)

    def _highlight_nav(self, cur: int):
        """高亮导航方块：选中行 > 激活组 > 悬停组 > 重复组闪烁 > 普通。"""
        for btn in self.nav_buttons:
            idx = btn.property("row_idx")
            gi = btn.property("group_idx")
            base = self._nav_base_color.get(idx, "#81c784")
            if idx == cur:
                border = "3px solid #1a1a1a"
            elif gi is not None and gi >= 0 and gi == self._active_group:
                border = "3px solid #00796b"      # 深青绿：激活组
            elif gi is not None and gi >= 0 and gi == self._hover_group:
                border = "3px solid #3949ab"      # 深蓝：悬停组
            elif gi is not None and gi >= 0 and self._blink_on:
                border = "2px solid #ffb74d"      # 柔和琥珀：重复组闪烁
            else:
                border = "1px solid #999"
            btn.setStyleSheet(
                f"QPushButton {{ background: {base}; border: {border}; border-radius: 2px; }}")

    def _on_blink(self):
        """重复组方块闪烁（切换相位）。"""
        if not self._nav_group_rows:
            self._blink_on = True
            return
        self._blink_on = not self._blink_on
        cur = self.list_widget.currentRow()
        self._highlight_nav(cur if cur >= 0 else -1)

    def eventFilter(self, obj, event):
        """导航方块悬停：整组高亮。"""
        from PySide6.QtCore import QEvent
        t = event.type()
        if t in (QEvent.Enter, QEvent.Leave):
            try:
                gi = obj.property("group_idx")
            except Exception:
                gi = None
            if gi is not None and gi >= 0:
                if t == QEvent.Enter:
                    self._hover_group = gi
                elif self._hover_group == gi:
                    self._hover_group = None
                cur = self.list_widget.currentRow()
                self._highlight_nav(cur if cur >= 0 else -1)
        return super().eventFilter(obj, event)

    def _on_context_menu(self, pos):
        """列表右键菜单：保留组内第一个 / 删除 / 撤销。"""
        from PySide6.QtWidgets import QMenu
        item = self.list_widget.itemAt(pos)
        if item is None:
            return
        idx = item.data(Qt.UserRole)
        g = self._dup_group_of(idx) if isinstance(idx, int) else None
        menu = QMenu(self)
        if g and len(g) >= 2:
            act = menu.addAction(
                f"保留组内第一个（第 {g[0] + 1} 行，删其余 {len(g) - 1} 行）")
            act.triggered.connect(lambda: self._keep_first_of_group(list(g)))
        act_del = menu.addAction("删除选中行")
        act_del.triggered.connect(self._delete_selected)
        if self._undo_stack:
            menu.addSeparator()
            act_undo = menu.addAction("撤销（Ctrl+Z）")
            act_undo.triggered.connect(self._undo)
        menu.exec(self.list_widget.mapToGlobal(pos))

    def _jump_to_index(self, idx: int):
        """跳到指定行（方块阵列/导航用）。"""
        item = self.list_widget.item(idx)
        if item:
            self.list_widget.scrollToItem(item, QAbstractItemView.PositionAtCenter)
            self.list_widget.setCurrentItem(item)
            self.jump_spin.setValue(idx + 1)
            self._highlight_nav(idx)

    def _jump_to(self):
        target = self.jump_spin.value() - 1  # 显示 1-based，内部 0-based
        item = self.list_widget.item(target)
        if item:
            self.list_widget.scrollToItem(item, QAbstractItemView.PositionAtCenter)
            self.list_widget.setCurrentItem(item)

    def _next_similar(self):
        """跳到下一处问题行（像素相似 / AI 判重 / 碎片，循环）。"""
        flagged = set(self._similar) | set(self._ai_dups) | self._incomplete_rows
        if not flagged:
            return
        cur = self.list_widget.currentRow()
        sim_rows = sorted(flagged)
        nxt = None
        for r in sim_rows:
            if r > cur:
                nxt = r
                break
        if nxt is None and sim_rows:
            nxt = sim_rows[0]
        if nxt is not None:
            item = self.list_widget.item(nxt)
            if item:
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
        if not (0 <= orig < len(self.rows)):
            return
        row = self.rows[orig]
        self._set_preview(row.image)
        # 联动：导航方块也高亮当前行
        self._highlight_nav(self.list_widget.currentRow())
        # 选中重复行 → 自动激活该组（浮动操作条出现）
        for gi, g in enumerate(self._nav_group_rows):
            if orig in g:
                if self._active_group != gi:
                    self._active_group = gi
                    self._update_keep_first_btn()
                    self._highlight_nav(self.list_widget.currentRow())
                break
        else:
            # 非重复行：取消激活（隐藏浮动条）
            if self._active_group is not None:
                self._clear_active_group()
                self._highlight_nav(self.list_widget.currentRow())

    def _set_preview(self, image):
        """右侧大图预览（QGraphicsView，支持滚轮缩放 + 拖拽）。"""
        from PySide6.QtGui import QPixmap
        from PySide6.QtWidgets import QGraphicsPixmapItem

        # BGR → QPixmap（保留原始分辨率，缩放交给视图）
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w, _ = rgb.shape
        from PySide6.QtGui import QImage
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
        self.preview_pixmap = QPixmap.fromImage(qimg)
        self.preview_scene.clear()
        self.preview_item = QGraphicsPixmapItem(self.preview_pixmap)
        self.preview_scene.addItem(self.preview_item)
        self.preview_scene.setSceneRect(0, 0, w, h)
        # 首次显示：适应窗口；之后保持用户缩放级别
        self.preview_view.resetTransform()
        self.preview_view.fitInView(self.preview_item, Qt.KeepAspectRatio)
        self._preview_fit_done = True

    def _on_double_click(self, item):
        orig = item.data(Qt.UserRole)
        if not (0 <= orig < len(self.rows)):
            return
        row = self.rows[orig]
        dlg = ZoomDialog(row.image.copy(), f"第 {orig + 1} 行预览（t={row.time:.0f}s）", self)
        dlg.exec()

    def _on_clean(self):
        """按 AI 建议清理：删除碎片/空谱行 + 重复组只留第一行。"""
        if not self._ai_done:
            return
        to_del = set(self._incomplete_rows)
        for g in self._ai_dup_groups:
            # 保留组内第一个（按当前列表顺序），其余删除
            for i in g[1:]:
                to_del.add(i)
        if not to_del:
            QMessageBox.information(self, "清理", "AI 没有发现需要清理的行")
            return
        n_frag = len(self._incomplete_rows)
        n_dup = len(to_del) - n_frag
        reply = QMessageBox.question(
            self, "按 AI 建议清理",
            f"将删除：\n"
            f"· 碎片/空谱行 {n_frag} 行\n"
            f"· 重复行 {n_dup} 行（每组保留第一行）\n\n"
            f"共删除 {len(to_del)} 行，保留 {len(self.rows) - len(to_del)} 行。\n"
            f"确认清理？（清理后可用「找回被丢弃的行」恢复）",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self._push_undo()   # 清理前快照（支持 Ctrl+Z 撤销）
        # 删除前把被删的行存入"丢弃池"（供找回）
        for i in sorted(to_del):
            if 0 <= i < len(self.rows):
                self.result.all_rows.append(self.rows[i])
        self.rows = [r for i, r in enumerate(self.rows) if i not in to_del]
        # 索引变化，清空 AI 状态（重新分析会命中缓存）
        self._ai_analyses = {}
        self._ai_dups = {}
        self._ai_dup_groups = []
        self._incomplete_rows = set()
        self._ai_done = False
        self.clean_btn.setEnabled(False)
        self._compute_similar()
        self._render_list()
        self.status_top.setText(f"已清理，剩 {len(self.rows)} 行（可 Ctrl+Z 撤销）")
        self._log(f"按 AI 建议清理完成：剩 {len(self.rows)} 行")

    def _remap_after_delete(self, idx: int):
        """删除第 idx 行后，重映射所有按索引存储的结果（AI 标记/相似/碎片），
        而不是清空或重算——这样删掉一对重复行后，其余标记仍然保留，且删除很快。"""
        self._remap_after_delete_rows({idx})

    def _remap_after_delete_rows(self, deleted: set[int]):
        """删除多行（索引集合）后重映射所有按索引存储的结果。"""
        n_old = len(self.rows)
        mapping: dict[int, int] = {}
        j = 0
        for i in range(n_old):
            if i in deleted:
                continue
            mapping[i] = j
            j += 1

        def shift_list(lst):
            return [mapping[x] for x in lst if x in mapping]

        def shift_dict(d):
            out = {}
            for k, v in d.items():
                if k not in mapping:
                    continue
                nk = mapping[k]
                out[nk] = shift_list(v) if isinstance(v, list) else v
            return out

        self._bar_dups = {}
        # 像素相似标记：直接重映射（不重算，避免 O(n²) 像素比较导致卡顿）
        self._similar = shift_dict(self._similar)
        self._similar_groups = [shift_list(g) for g in self._similar_groups]
        self._thumbs = shift_dict(self._thumbs)
        if not self._ai_done:
            return
        self._ai_analyses = shift_dict(self._ai_analyses)
        self._ai_dups = shift_dict(self._ai_dups)
        self._incomplete_rows = {mapping[x] for x in self._incomplete_rows if x in mapping}
        self._ai_dup_groups = [shift_list(g) for g in self._ai_dup_groups]

    # ---------- 重复组操作（保留组内第一个）----------

    def _all_dup_groups(self) -> list[list[int]]:
        """所有重复组（AI 语义判重 + 像素相似），去重后按首行排序。"""
        groups: list[list[int]] = []
        seen: set[tuple] = set()
        for g in list(self._ai_dup_groups) + list(self._similar_groups):
            g = sorted(x for x in g if 0 <= x < len(self.rows))
            if len(g) < 2:
                continue
            key = tuple(g)
            if key in seen:
                continue
            seen.add(key)
            groups.append(g)
        groups.sort(key=lambda g: g[0])
        return groups

    def _dup_group_of(self, row_idx: int) -> list[int] | None:
        """该行所属的重复组（没有则 None）。"""
        for g in self._all_dup_groups():
            if row_idx in g:
                return g
        return None

    def _keep_first_of_group(self, group: list[int]):
        """保留组内第一行，删除其余（可 Ctrl+Z 撤销）。"""
        valid = sorted(x for x in group if 0 <= x < len(self.rows))
        if len(valid) < 2:
            return
        keep = valid[0]
        to_del = set(valid[1:])
        self._push_undo()
        # 删除前把被删行存入"丢弃池"（供找回）
        for i in sorted(to_del):
            self.result.all_rows.append(self.rows[i])
        self._remap_after_delete_rows(to_del)
        self.rows = [r for i, r in enumerate(self.rows) if i not in to_del]
        self._render_list()
        msg = f"已保留第 {keep + 1} 行，删除组内其余 {len(to_del)} 行（可 Ctrl+Z 撤销）"
        self.status_top.setText(msg)
        self._log(msg)

    def _recalc_bar_dups(self):
        """兼容旧调用：行变化后重算相似标记（保留 AI 结果）。"""
        self._bar_dups = {}

    def _log(self, msg: str):
        """转发到主窗口日志。"""
        self.main_win._log(msg)

    def _delete_selected(self):
        """删除选中行：增量移除列表项（不重建列表 → 滚动/页面完全不跳）。"""
        item = self.list_widget.currentItem()
        if item is None:
            return
        idx = item.data(Qt.UserRole)
        pos = self.list_widget.row(item)   # 列表位置（= idx，当前顺序一致）

        self._push_undo()   # 删除前快照（支持 Ctrl+Z 撤销）
        del self.rows[idx]
        self._remap_after_delete(idx)   # 重映射标记（不重算，快）
        self._active_group = None

        # 关键：增量移除这一项，不 clear/重建 → 滚动位置不变
        self.list_widget.takeItem(pos)
        # 更新剩余项的索引/文本/图标/背景（行号变了）
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            pm, text, bg, tip = self._row_item_content(i)
            it.setIcon(QIcon(pm))
            it.setText(text)
            it.setData(Qt.UserRole, i)
            if bg:
                it.setBackground(QColor(bg))
            else:
                it.setBackground(QBrush())
            it.setToolTip(tip or "")

        n = len(self.rows)
        if n <= 0:
            self._refresh_nav_grid()
            self.status_top.setText("已删除全部行（可 Ctrl+Z 撤销）")
            return
        # 选中原位置的下一行（删的是最后一行则选上一行）
        ni = min(pos, self.list_widget.count() - 1)
        self.list_widget.setCurrentItem(self.list_widget.item(ni))
        self.jump_spin.setRange(1, max(1, n))
        self._refresh_nav_grid()
        self.status_top.setText(f"已删除，剩 {n} 行（可 Ctrl+Z 撤销）")

    def _recover(self):
        kept_keys = {(r.source, r.index) for r in self.rows}
        recoverable = [r for r in self.result.all_rows
                       if (r.source, r.index) not in kept_keys]
        if not recoverable:
            QMessageBox.information(self, "找回", "没有可找回的行")
            return
        dlg = RecoverDialog(recoverable, self)
        if dlg.exec() == QDialog.Accepted:
            self._push_undo()   # 找回前快照
            added = dlg.selected_rows()
            self.rows.extend(added)
            self.rows.sort(key=lambda r: (r.time, r.index))
            self._compute_similar()
            self._recalc_bar_dups()
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
        self._push_undo()   # 导入前快照
        self.rows.append(TabRow(img, -1, os.path.basename(path), 0))
        self._compute_similar()
        self._recalc_bar_dups()
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
