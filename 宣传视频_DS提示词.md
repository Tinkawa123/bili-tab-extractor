# 宣传视频生成任务：B站吉他谱视频 → PDF 工具

你是视频生成助手。请根据下面的分镜和提示词，生成一支 **45 秒**的产品宣传视频。

---

## 一、任务概述

| 项目 | 要求 |
|---|---|
| 产品 | 一个桌面工具：把 B站吉他教学视频自动截取谱面、拼接成完整谱、输出 A4 PDF |
| 视频时长 | **45 秒**（6 个镜头，可裁成 30 秒精简版） |
| 画面比例 | **16:9**（另出 9:16 竖版） |
| 帧率 | 30fps |
| 整体风格 | 干净、科技感、真实产品演示感 |
| 主色调 | 黑 `#1a1a1a` + 白 `#ffffff` + **青绿 `#00796b`**（产品按钮色）+ 黄色 `#ffd54f`（重复标记色） |
| 音乐 | lo-fi 电子，100 BPM，鼓点卡剪辑切点 |
| 核心卖点 | 自动抽帧拼接、智能去重、人工核验、AI 识别、一键出 PDF |

---

## 二、必须遵守的约定

1. **镜头 2 和镜头 4 是 UI 界面镜头**：画面中不要生成任何文字（中文/英文都不要），只生成界面布局、按钮、光标、交互动效的示意。真实文字由后期叠加。
2. 不要生成品牌 logo、水印、字幕。
3. 所有镜头保持同一套色彩规范（黑/白/青绿/黄），不要出现其他饱和色。
4. 镜头之间的转场：硬切 + 0.3 秒白闪（后期做，生成时不用做转场）。
5. 每个镜头独立生成，时长按分镜表控制。

---

## 三、分镜脚本（共 6 镜，总 45 秒）

### 镜头 1（0-4s）｜痛点开场

- **画面**：笔记本电脑播放吉他教学视频，六线谱快速向上滚动；鼠标慌张点击暂停想截图；谱面碎成散落的小块飞散。
- **情绪**：焦躁、无奈
- **字幕（后期加）**：谱面滚太快，截屏截到手软？

**Prompt：**
```
Screen recording style cinematic shot: a laptop screen in a dark room playing a guitar tutorial video, guitar tablature scrolling upward very fast, a mouse cursor desperately clicking to pause the video, then the tablature fragments into scattered small pieces flying apart, screen glow illuminating the desk, shallow depth of field, clean 16:9, 30fps, no text, no watermark, no logo
```

---

### 镜头 2（4-9s）｜粘贴链接，一键开始（UI 示意）

- **画面**：极简桌面应用界面（白底、黑色标题、青绿色强调按钮）。一段很长的网址被粘贴进圆角输入框，鼠标点击一个黑色按钮，按钮边缘泛起青绿光晕，点击有涟漪反馈。
- **字幕（后期加）**：粘贴链接，一键开始
- **禁止**：不要生成任何文字字符。

**Prompt：**
```
Extreme close-up of a modern minimal desktop application UI, pure white background, soft shadows, a rounded text input field receiving a pasted long URL as a solid grey block, a black rounded button with a subtle teal-green glow being clicked by a mouse cursor, gentle click ripple, ultra clean screen-recording aesthetic, no text glyphs, no letters, no watermark, 5 seconds
```

---

### 镜头 3（9-18s）｜自动处理：抽帧→拼接→去重（抽象动效）

- **画面**：抽象科技动效。一个播放器窗口中飞出矩形帧，每帧变成一条横向谱带（黑白横线纹理），谱带像磁铁一样吸附拼接成一张连续长谱；进度条推进；青绿色粒子光点漂浮。
- **情绪**：流畅、智能
- **字幕（后期加）**：自动抽帧 · 智能拼接 · 去重排序

**Prompt：**
```
Abstract tech motion graphics: rectangular video frames flowing out of a minimal video player window, each frame transforming into a horizontal strip of black-and-white musical tablature lines, strips magnetically snapping together into one long continuous sheet of notation, a smooth progress bar sweeping across the bottom, glowing teal-green particles floating, dark charcoal background, elegant smooth animation, no text, 9 seconds
```

---

### 镜头 4（18-28s）｜人工核验界面（核心卖点，UI 示意）

- **画面**：核验界面示意：左侧一列谱行缩略图卡片（每张是黑白谱面纹理）；顶部一排紧凑的彩色小方块阵列（绿色/黄色/红色）；点击其中一个黄色方块组 → 顶部滑出一条深色浮动条，浮动条右侧有一个青绿色圆角按钮；然后某几行卡片被拖动重新排序。
- **情绪**：掌控感、高效
- **字幕（后期加）**：人工核验：拖拽排序 · 一键去重 · AI 识别
- **禁止**：不要生成任何文字字符，方块和按钮保持纯色/色块，不要写字。

**Prompt：**
```
Screen recording of a music tablature review interface: left panel shows a vertical list of white thumbnail cards each containing black-and-white guitar tablature texture, top bar shows a compact grid of small colored squares in green, yellow and red, clicking one yellow square group triggers a dark floating bar sliding down from the top with a teal-green rounded button on its right side, then several thumbnail cards smoothly reorder by drag and drop with a soft highlight trail, crisp clean UI, soft shadows, no text glyphs, no letters, no watermark, 10 seconds
```

---

### 镜头 5（28-36s）｜输出 A4 PDF

- **画面**：一叠 A4 谱面纸，页面翻动像翻书，黑色五线谱/TAB 线条清晰干净，白色纸张，柔和自然阴影，暖色桌面灯光，镜头缓慢推进，浅景深。
- **情绪**：精致、有成品感
- **字幕（后期加）**：输出 A4 PDF，直接打印

**Prompt：**
```
Elegant product shot: a finished A4 sheet of guitar tablature flipping through pages like a book, crisp black music notation on white paper, soft natural shadows, warm desktop lighting, slow cinematic push-in, shallow depth of field, premium stationery feel, no text glyphs, no watermark, 8 seconds
```

---

### 镜头 6（36-45s）｜收尾 + slogan

- **画面**：干净的产品界面窗口全景（白底界面、谱面），镜头缓慢拉远；随后窗口收缩变成一个简洁几何 App 图标；背景变为深色 + 青绿渐变光晕；画面中央留出后期 slogan 的位置。
- **情绪**：简洁、收束
- **字幕（后期加）**：B站吉他谱 → PDF ｜ 一键扒谱，专治手截

**Prompt：**
```
Minimal hero product shot: a clean white desktop application window showing guitar tablature content, slow zoom out revealing the whole interface, the window then shrinks and morphs into a simple geometric app icon, background transitions to dark charcoal with a subtle teal-green radial gradient glow, elegant modern motion design, no text glyphs, no watermark, 9 seconds
```

---

## 四、统一风格关键词（每镜末尾追加）

```
screen recording aesthetic, ultra clean, black and white with teal green accent, soft shadows, high DPI, 16:9, 30fps, cinematic depth of field, no text overlays, no watermark, no logo, no brand marks
```

---

## 五、成片输出要求

1. **6 个镜头独立生成**，按分镜顺序编号输出（shot01 ~ shot06），时长分别为 4s / 5s / 9s / 10s / 8s / 9s（合计 45s）。
2. 每镜都要**留出安全边距**（画面四周 5% 不要放关键元素），方便后期加字幕。
3. 色彩统一：不要出现橙红紫等高饱和色，只要黑/白/青绿/黄。
4. 若某镜生成失败或文字糊了，用同提示词重试，不要自行改剧情。

---

## 六、后期叠加清单（给剪辑用，非生成内容）

| 时间 | 叠加内容 |
|---|---|
| 0-4s | 字幕：谱面滚太快，截屏截到手软？ |
| 4-9s | 字幕：粘贴链接，一键开始 |
| 9-18s | 字幕：自动抽帧 · 智能拼接 · 去重排序 |
| 18-28s | 字幕：人工核验：拖拽排序 · 一键去重 · AI 识别 |
| 28-36s | 字幕：输出 A4 PDF，直接打印 |
| 36-45s | 主标题：B站吉他谱 → PDF；Slogan：一键扒谱，专治手截 |
| 45s | 结尾：产品图标 + 二维码/链接（可选） |

**音乐建议**：lo-fi electronic, 100 BPM, light and uplifting, subtle beat drops on cuts

---

## 七、30 秒精简版（可选）

如果要做短视频，砍成 5 个镜头：

| 镜头 | 时长 | 内容 |
|---|---|---|
| 1 | 0-3s | 痛点（谱面快速滚动） |
| 2 | 3-6s | 粘贴链接 + 点击开始 |
| 3 | 6-15s | 核验界面（核心卖点，加长） |
| 4 | 15-20s | A4 PDF 成品 |
| 5 | 20-25s | slogan 收尾 |

---

**开始生成。按 shot01 → shot06 顺序输出。**
