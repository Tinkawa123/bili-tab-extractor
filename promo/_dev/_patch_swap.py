from pathlib import Path

HERE = Path(__file__).resolve().parent
root = HERE.parent

# ---------------- pages: real rows from the 搬运 video (Paranoid / BV19f421Q76h)
pg = HERE / "film" / "pages.py"
s = pg.read_text(encoding="utf-8")
s = s.replace(
    '''ROWS_DIRS = [
    Path(__file__).resolve().parents[2] / "out" / "GUI完整流程" / "谱行图片",
    Path(__file__).resolve().parents[2] / "out" / "「圣诞结」完整还原前奏、间奏和尾奏的吉他改编" / "谱行图片",
]''',
    '''ROWS_DIRS = [
    # 搬运视频素材（非付费谱）：Black Sabbath - Paranoid, BV19f421Q76h
    Path(__file__).resolve().parents[2] / "out" / "测试集" / "Paranoid",
]''',
)
pg.write_text(s, encoding="utf-8")

f = HERE / "film" / "film.py"
s = f.read_text(encoding="utf-8")

# ---------------- S1 hero shot -> Paranoid playthrough
s = s.replace('v = video_sprite("numb1_30.png", (0, 90, 1920, 1080), D.W, D.H)',
              'v = video_sprite("bv19f_20.png", (0, 0, 1920, 1080), D.W, D.H)')
s = s.replace('    tab_top = 648\n    tab_bottom = D.H - 52', '    tab_top = 596\n    tab_bottom = D.H - 52')
# S1 polaroid caption / stats stay

# ---------------- S3 source card
s = s.replace('v = video_sprite("numb1_18.png", (0, 90, 1920, 1080), vw, vh).rgb.copy()',
              'v = video_sprite("bv19f_20.png", (0, 0, 1920, 1080), vw, vh).rgb.copy()')

# ---------------- S3 stack: fewer, wider rows (source rows are 5:1)
s = s.replace('    idx = [0, 4, 7, 12, 15, 18, 21, 24, 27, 30, 33, 36]\n    out = []\n    w = 560',
              '    idx = [0, 4, 9, 14, 19, 24, 29, 34]\n    out = []\n    w = 470')
s = s.replace('        out.append({"spr": spr, "h": h, "dup": i in (7, 18, 30), "idx": len(out)})',
              '        out.append({"spr": spr, "h": h, "dup": i in (9, 24), "idx": len(out)})')
s = s.replace('        t_in = 15.25 + i * 0.265', '        t_in = 15.25 + i * 0.30')

# ---------------- S2 URL
s = s.replace('URL = "bilibili.com/video/BV1nU4y1r7xJ"', 'URL = "bilibili.com/video/BV19f421Q76h"')

# ---------------- S4 header
s = s.replace('text_sprite("核验  ·  富士山下", D.UI_TEXT, "sans_bold", 29, tracking=1.0)',
              'text_sprite("核验  ·  Paranoid", D.UI_TEXT, "sans_bold", 29, tracking=1.0)')

# ---------------- pages: titles / row ranges
s = s.replace('''    titles = [("富士山下", "吉他谱 · 完整版"), ("富士山下", "吉他谱 · 完整版"), ("富士山下", "吉他谱 · 完整版")]
    starts = [0, 9, 18]''',
              '''    titles = [("Paranoid", "Black Sabbath · 吉他谱"), ("Paranoid", "Black Sabbath · 吉他谱"), ("Paranoid", "Black Sabbath · 吉他谱")]
    starts = [0, 7, 14]''')
s = s.replace('pages.build_page(list(range(0, 9)), "富士山下", "吉他谱 · 完整版", 1, 3)',
              'pages.build_page(list(range(0, 7)), "Paranoid", "Black Sabbath · 吉他谱", 1, 3)')
s = s.replace('page = pages.build_page(list(range(0, 9)), "富士山下", "吉他谱 · 完整版", 1, 3)',
              'page = pages.build_page(list(range(0, 7)), "Paranoid", "Black Sabbath · 吉他谱", 1, 3)')

f.write_text(s, encoding="utf-8")
print("swapped assets to Paranoid")
