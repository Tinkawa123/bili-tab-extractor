from pathlib import Path
import re

HERE = Path(__file__).resolve().parent

# ---- engine: let the renderer control cv2 threads
e = HERE / "film" / "engine.py"
es = e.read_text(encoding="utf-8")
es = es.replace(
    "cv2.setNumThreads(min(8, cv2.getNumberOfCPUs()))",
    'import os as _os\n\n_t = _os.environ.get("DSH_CV_THREADS")\ncv2.setNumThreads(int(_t) if _t else min(8, cv2.getNumberOfCPUs()))',
)
e.write_text(es, encoding="utf-8")

f = HERE / "film" / "film.py"
s = f.read_text(encoding="utf-8")

# ---------- S2 UI type scale up (legibility at 1080p)
pairs = [
    ('text_sprite("视频扒谱工具", D.UI_TEXT, "sans_bold", 36, tracking=1.2)',
     'text_sprite("视频扒谱工具", D.UI_TEXT, "sans_bold", 38, tracking=1.2)'),
    ('text_sprite("B站教学视频  →  完整吉他谱  /  A4 PDF", D.INK_SOFT, "sans", 17, tracking=1.8)',
     'text_sprite("B站教学视频  →  完整吉他谱  /  A4 PDF", D.INK_SOFT, "sans", 18, tracking=1.8)'),
    ('text_sprite("B站视频链接", D.INK_SOFT, "sans", 17, tracking=2.4)',
     'text_sprite("B站视频链接", D.INK_SOFT, "sans", 19, tracking=2.4)'),
    ('text_sprite("输出标题（可选）", D.INK_SOFT, "sans", 17, tracking=2.4)',
     'text_sprite("输出标题（可选）", D.INK_SOFT, "sans", 19, tracking=2.4)'),
    ('text_sprite("留空自动用视频标题", D.GREY_DIM, "sans", 18, tracking=1.2)',
     'text_sprite("留空自动用视频标题", D.GREY_DIM, "sans", 20, tracking=1.2)'),
    ('text_sprite(lab, D.UI_TEXT, "sans", 19, tracking=0.8)',
     'text_sprite(lab, D.UI_TEXT, "sans", 21, tracking=0.8)'),
    ('text_sprite("正在检测谱面区域…", D.INK_SOFT, "sans", 18, tracking=1.4)',
     'text_sprite("正在检测谱面区域…", D.INK_SOFT, "sans", 20, tracking=1.4)'),
    ('text_sprite(f"{int(prog*100):02d}%", D.UI_TEXT, "mono_bold", 20, tracking=1.0)',
     'text_sprite(f"{int(prog*100):02d}%", D.UI_TEXT, "mono_bold", 22, tracking=1.0)'),
    ('text_sprite(typed, D.UI_TEXT, "mono", 28, tracking=0.4)',
     'text_sprite(typed, D.UI_TEXT, "mono", 30, tracking=0.4)'),
    ('measure_text(typed, "mono", 28, 0.4)', 'measure_text(typed, "mono", 30, 0.4)'),
]
for a, b in pairs:
    if a in s:
        s = s.replace(a, b)
    else:
        print("MISS S2:", a[:60])

# ---------- S4 UI type scale up
pairs4 = [
    ('text_sprite("核验  ·  Paranoid", D.UI_TEXT, "sans_bold", 29, tracking=1.0)',
     'text_sprite("核验  ·  Paranoid", D.UI_TEXT, "sans_bold", 32, tracking=1.0)'),
    ('text_sprite("36 行谱面  ·  6 组疑似重复  ·  拖拽排序 / 双击放大", D.INK_SOFT, "sans", 15, tracking=1.2)',
     'text_sprite("36 行谱面  ·  6 组疑似重复  ·  拖拽排序 / 双击放大", D.INK_SOFT, "sans", 16, tracking=1.2)'),
    ('text_sprite(c["name"], D.UI_TEXT, "sans_bold", 19, tracking=0.6)',
     'text_sprite(c["name"], D.UI_TEXT, "sans_bold", 21, tracking=0.6)'),
    ('text_sprite(c["meta"], D.GREY_DIM, "mono", 12, tracking=0.8)',
     'text_sprite(c["meta"], D.GREY_DIM, "mono", 13, tracking=0.8)'),
    ('text_sprite(lab, D.INK_SOFT, "sans", 14, tracking=0.6)',
     'text_sprite(lab, D.INK_SOFT, "sans", 15, tracking=0.6)'),
    ('text_sprite("第 3 行  ·  双击可放大", D.INK_SOFT, "sans", 13, tracking=1.0)',
     'text_sprite("第 3 行  ·  双击可放大", D.INK_SOFT, "sans", 15, tracking=1.0)'),
    ('text_sprite("AI 已识别 6 组重复", D.TEAL, "sans", 16, tracking=1.0)',
     'text_sprite("AI 已识别 6 组重复", D.TEAL, "sans", 17, tracking=1.0)'),
    ('text_sprite(lab, D.WHITE, "sans", 13, tracking=0.6)',
     'text_sprite(lab, D.WHITE, "sans", 14, tracking=0.6)'),
    ('text_sprite("全自动输出", D.GREY_DIM, "sans", 14, tracking=0.6)',
     'text_sprite("全自动输出", D.GREY_DIM, "sans", 15, tracking=0.6)'),
]
for a, b in pairs4:
    if a in s:
        s = s.replace(a, b)
    else:
        print("MISS S4:", a[:60])

f.write_text(s, encoding="utf-8")
print("patched font scales")
