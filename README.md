# 视频扒谱工具（B站吉他谱 → PDF）

**本项目基于dsh开发**

把 B 站吉他教学视频里**实时显示的谱面**自动截取、排序、（可选人工核验）后，输出为完整 PDF 和谱行图片。

> 适用于"画面下方实时显示谱面（TAB/歌词谱）"的 B 站教学视频。

## 功能特性

- **输入**：B 站视频链接 或 本地视频文件
- **全自动管线**：下载 → 抽帧 → 谱面区域检测 → 谱行切分 → 自动去重排序
- **现代 GUI（PySide6）**：
  - 大缩略图列表，**鼠标拖拽排序**、删除、找回被丢弃行、导入本地图片
  - **相似行自动标黄**（疑似重复，人工判断），导航看板快速定位
  - 侧边栏大图预览 + 双击全屏可缩放
  - 核验状态可暂存，退出后随时「重新打开核验」继续编辑
- **全自动模式**：跳过人工核验一键输出
- **输出**：A4 PDF + 谱行图片文件夹，PDF 生成后自动做肤色检查剔除漏网的演奏画面
- **纯本地**：无需 API key；免安装 exe 单文件分发

## 使用

### GUI（推荐）

运行 `dist\视频扒谱工具.exe`（免安装），或源码运行：

```bash
python bili_tab_extractor/gui_qt.py
```

1. 输入 B 站视频链接（或本地视频路径），点「开始处理」；
2. 自动处理后弹出**人工核验窗口**：拖拽调整谱行顺序、删除误判行、找回被丢弃的行、双击放大确认；
3. 点「确认输出」生成 PDF + 图片，或「全自动输出」跳过核验。

### 命令行

```bash
python bili_tab_extractor/main.py "https://www.bilibili.com/video/BVxxxx"
python bili_tab_extractor/main.py --video 视频.mp4
```

常用选项：`--interval` 抽帧间隔、`--box` 手动指定谱面区域、`--rows-per-page` 每页行数、`--out` 输出目录。

### 打包 exe

```bash
pip install -r requirements.txt
python build_exe.py        # 生成 dist/视频扒谱工具.exe
```

## 依赖

见 `requirements.txt`（yt-dlp / opencv / numpy / Pillow / pypdf / PySide6 / imageio-ffmpeg）。

## 借鉴的开源项目

思路借鉴了以下两个开源项目（均只支持 YouTube，本项目针对 B 站场景并用纯本地 CV 重新实现）：

- [rohin-garg/youtube-guitar-tab-parser](https://github.com/rohin-garg/youtube-guitar-tab-parser)（yt-dlp 下载 + 区域裁剪 + PDF 拼接）
- [marcelpanse/youtube-guitar-tab-parser](https://github.com/marcelpanse/youtube-guitar-tab-parser)（多帧采样定位谱面区域 + 去重思路）

## 目录结构

```
视频扒谱/
├── bili_tab_extractor/     # 核心代码
│   ├── gui_qt.py           # PySide6 GUI（核验窗口）
│   ├── pipeline.py         # 可复用处理流程
│   ├── download.py         # yt-dlp 下载
│   ├── frames.py           # ffmpeg 抽帧
│   ├── detect.py           # 谱面区域检测
│   ├── rows.py             # 谱行切分 + 去重
│   ├── stitch.py           # PDF 输出 + 后检查
│   └── main.py             # CLI 入口
├── repo_rohin/             # 借鉴的开源项目①源码
├── repo_marcelpanse/       # 借鉴的开源项目②源码
├── build_exe.py            # 打包脚本
└── 视频扒谱.bat               # 快捷启动脚本
```

## 说明与局限
- **目前版本视觉能力暂时较弱，只能适应较为简单的场景，比如静止的谱，滚动谱暂时效果不佳**
- 输出谱面是**视频画面的图片拼接**，非 OCR 重排，清晰度取决于视频分辨率（建议下载 720p 以上）；
- 谱行切分/去重依赖谱面形态（TAB、歌词谱、滚动/翻页式），**目前版本建议手动调整删除重复谱面**；
- 部分 B 站视频受风控（HTTP 412），稍后或换网络重试即可，与工具无关。

## 欢迎贡献

本项目是个人维护的开源项目，欢迎任何形式的贡献：

- **提 Bug**：遇到问题请在 [Issues](https://github.com/Tinkawa123/bili-tab-extractor/issues) 反馈，附上视频链接和报错信息更利于排查；
- **提需求**：有想要的功能（如更多谱面格式支持、批量处理等），欢迎开 Issue 讨论；
- **提交代码**：Fork 本仓库 → 修改 → 提交 Pull Request，请附上改动说明；
- **贡献谱面样本**：如果你有不同形态的谱面视频（TAB / 歌词谱 / 滚动式等），欢迎分享，帮助改进识别效果。

所有贡献者都会在 README 致谢。
