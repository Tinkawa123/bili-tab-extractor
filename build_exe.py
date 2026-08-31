# -*- coding: utf-8 -*-
"""PyInstaller 打包脚本：生成免安装 exe。"""
import os
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

PYLIBS = os.path.join(BASE, "pylibs")

# 把构建时间写入 _build_info.py，供 GUI 窗口标题显示（确认版本用）
BUILD_TIME = time.strftime("%Y-%m-%d %H:%M:%S")
with open(os.path.join(BASE, "bili_tab_extractor", "_build_info.py"),
          "w", encoding="utf-8") as f:
    f.write(f'# 自动生成\nBUILD_TIME = "{BUILD_TIME}"\n')
print("构建时间:", BUILD_TIME)

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm", "--clean",
    "--onefile",           # 单文件 exe
    "--windowed",          # 无控制台（GUI）
    "--name", "视频扒谱工具",
    "--paths", PYLIBS,     # 收集 pylibs 中的包
    "--collect-all", "yt_dlp",
    "--collect-submodules", "yt_dlp",
    "--collect-data", "imageio_ffmpeg",
    "--collect-data", "yt_dlp",
    "--exclude-module", "matplotlib",
    "--exclude-module", "PIL.ImageShow",
    os.path.join(BASE, "bili_tab_extractor", "gui_qt.py"),
]
print("运行:", " ".join(cmd))
r = subprocess.run(cmd)
print("PyInstaller exit:", r.returncode)

exe = os.path.join(BASE, "dist", "视频扒谱工具.exe")
if os.path.exists(exe):
    print(f"打包成功: {exe} ({os.path.getsize(exe) / 1024 / 1024:.1f} MB)")
else:
    print("打包失败")
