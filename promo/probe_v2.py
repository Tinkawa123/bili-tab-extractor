import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "film"))
import numpy as np
import cv2
import design as D
from engine import *
import pages

OUT = Path(__file__).resolve().parent / "_test"
OUT.mkdir(exist_ok=True)


def stage_bg(w=1920, h=1080, warm=False):
    bg = radial_sprite(w, h, [(0.0, D.BG2 * 1.4), (0.55, D.BG1), (1.0, D.BG0)], (w * 0.5, h * 0.46), w * 0.75)
    base = bg.rgb.copy()
    if warm:
        warm_glow = radial_sprite(w, h, [(0, D.hexc("#3A2416") * 1.6), (1, D.hexc("#0A0705"))], (w * 0.34, h * 0.62), w * 0.8)
        base = np.clip(base + warm_glow.rgb * 0.55, 0, 1)
    return base


t0 = time.time()

# ---------------- 1. typography specimen ----------------
base = stage_bg()
g1 = radial_sprite(1200, 900, [(0, D.TEAL * 1.5), (1, np.zeros(3, F32))], (300, 240), 620)
over(base, g1, 120, -60, 0.35, blend="add")
g2 = radial_sprite(900, 700, [(0, D.hexc("#1B4B7A")), (1, np.zeros(3, F32))], (450, 350), 520)
over(base, g2, 900, 300, 0.30, blend="add")

hero = text_sprite("视频会划走，", D.PAPER, "serif", 118, tracking=4, weight=600)
over(base, hero, 168, 236)
hero2 = gradient_text_sprite("谱子会留下。", [(0, D.TEAL), (1, D.hexc("#8AF7DC"))], (0, 0), (760, 120), "serif", 118, tracking=4, weight=600)
over(base, hero2, 168, 396)

lead = text_sprite("把 B 站教学视频里的谱，变成一张能打印的 A4。", D.PAPER * 0.72, "sans", 34, tracking=1.6)
over(base, lead, 172, 600)
lead2 = text_sprite("视频扒谱工具 / TAB EXTRACTOR", D.TEAL, "mono_bold", 20, tracking=4.0)
over(base, lead2, 172, 700)
small = text_sprite("谱面在滚 · 截图在追 · 37 张截图，拼不成一首歌。", D.GREY, "sans", 24, tracking=1.2)
over(base, small, 172, 750)
num = text_sprite("386 帧 → 48 行 → 3 页 A4", D.AMBER, "mono", 26, tracking=2.0)
over(base, num, 172, 800)
for i, s in enumerate(["正片 · 获奖级", "1080P · 30FPS", "A4 PDF"]):
    t = text_sprite(s, D.GREY_DIM * 0.9, "mono", 15, tracking=2.4)
    over(base, t, 168 + i * 250, 950)

base = apply_grade(base, contrast=1.02, saturation=1.02)
base = bloom(base, 0.62, 24, 0.16)
base = halation(base, 0.75, 30, 0.06)
base = grain(base, 3.0, 0.028)
base *= vignette_mask(*base.shape[1::-1], 0.5)
save_png(base, OUT / "probe_type.png")

# ---------------- 2. paper page on warm stage ----------------
warm = stage_bg(warm=True)
page = pages.build_page(list(range(0, 6)), "富士山下", "吉他谱 · 完整版", 1, 3)
quad = pages.page_quad(960, 560, 690, 975, rx=6, ry=-12, rz=-1.5)
blit_perspective(warm, shadow(page, 34, 0.75, dx=-10, dy=14), pages.page_quad(960, 585, 690, 975, rx=6, ry=-12, rz=-1.5))
blit_perspective(warm, page, quad)
warm = apply_grade(warm, contrast=1.02, gain=(1.02, 1.0, 0.97))
warm = bloom(warm, 0.7, 26, 0.14)
warm = grain(warm, 8.0, 0.03)
warm *= vignette_mask(*warm.shape[1::-1], 0.55)
save_png(warm, OUT / "probe_page.png")

# ---------------- 3. video frame in stage with tab rows ----------------
dark = stage_bg()
vid = load_image(Path(__file__).resolve().parent / "film" / "assets" / "video" / "fuji_20.png", "RGB")
vid = cv2.resize(vid, (1280, 720))
vid_spr = from_float(np.dstack([vid, np.ones((720, 1280), F32)]))
quad = np.array([[400, 210], [1500, 150], [1560, 690], [360, 760]], F32)
blit_perspective(dark, shadow(vid_spr, 40, 0.8), quad + np.array([0, 22], F32))
blit_perspective(dark, vid_spr, quad)
m = line_mask(1300, 8, (6, 4), (1294, 4), 3)
ls = mask_to_sprite(m, D.TEAL)
gl = glow(ls, 18, 1.8, D.TEAL)
blit_perspective(dark, gl, np.array([[330, 430], [1620, 420], [1620, 530], [330, 540]], F32), 0.85, blend="add")
blit_perspective(dark, ls, np.array([[380, 470], [1580, 462], [1580, 468], [380, 476]], F32))
cap = text_sprite("谱面在滚。", D.PAPER, "serif", 96, tracking=3, weight=600)
over(dark, cap, 160, 820)
sub = text_sprite("截图在追。", D.AMBER, "sans", 44, tracking=2.4)
over(dark, sub, 166, 940)
dark = apply_grade(dark, contrast=1.03, saturation=0.98)
dark = bloom(dark, 0.6, 20, 0.22)
dark = halation(dark, 0.7, 26, 0.08)
dark = grain(dark, 2.0, 0.03)
dark *= vignette_mask(*dark.shape[1::-1], 0.6)
save_png(dark, OUT / "probe_video.png")

print("done in", round(time.time() - t0, 2), "s")
