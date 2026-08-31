@echo off
rem ============================================
rem  bili_tab_extractor - B站吉他谱视频转PDF
rem  用法1: 双击运行，然后粘贴 B 站视频链接
rem  用法2: 把本地视频文件直接拖到这个图标上
rem ============================================
cd /d "%~dp0"

echo.
echo  ==========================================
echo    视频扒谱工具  bili_tab_extractor
echo  ==========================================
echo.

if not "%~1"=="" (
    echo  [输入] 本地视频: %~1
    python bili_tab_extractor\main.py --video "%~1"
    goto :end
)

set /p URL=请输入B站视频链接(直接回车退出): 
if "%URL%"=="" goto :end

python bili_tab_extractor\main.py "%URL%"

:end
echo.
pause
