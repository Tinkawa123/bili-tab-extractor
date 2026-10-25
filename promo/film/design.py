"""Design tokens + timeline for 「视频扒谱工具」promo film."""

from engine import hexc, beat_time

# ---- canvas -------------------------------------------------------------
W, H = 1920, 1080
FPS = 30
DURATION = 60.0
BPM = 100.0
BEAT = beat_time(BPM)          # 0.6 s
BAR = BEAT * 4                 # 2.4 s

# ---- palette ------------------------------------------------------------
BG0 = hexc("#050708")          # deepest stage black
BG1 = hexc("#0A0E10")          # stage
BG2 = hexc("#11171A")
INK = hexc("#101315")          # ink on paper
INK_SOFT = hexc("#3A4348")
PAPER = hexc("#F4EFE5")        # warm paper
PAPER_DIM = hexc("#E7DFD1")
PAPER_SHADOW = hexc("#C9BFAE")
TEAL = hexc("#16E3AE")         # screen accent (bright, emissive)
TEAL_DEEP = hexc("#0B7A66")    # ink accent on paper / UI button
TEAL_DARK = hexc("#073B33")
AMBER = hexc("#FFC24B")        # duplicate marks
RED = hexc("#FF6A55")          # fragments
GREEN = hexc("#5FD08A")        # normal rows
WHITE = hexc("#FFFFFF")
GREY = hexc("#8E9AA0")
GREY_DIM = hexc("#5A666C")
# product UI (light)
UI_BG = hexc("#F7F3EB")
UI_PANEL = hexc("#FFFDF8")
UI_LINE = hexc("#D8D0C2")
UI_TEXT = hexc("#191C1E")

# ---- type ---------------------------------------------------------------
SERIF = "serif"
SANS = "sans"
SANS_B = "sans_bold"
MONO = "mono"
MONO_B = "mono_bold"

# display sizes (1080p)
T_HERO = 132        # big serif statement
T_HERO_S = 104
T_LEAD = 48
T_BODY = 30
T_SMALL = 24
T_MICRO = 19
T_UI_TITLE = 34
T_UI = 22

# ---- timeline (seconds) -------------------------------------------------
S1, S2, S3, S4, S5, S6 = 0.0, 7.2, 14.4, 26.4, 36.0, 45.6
END = 60.0


def bar(n: float) -> float:
    """Absolute time of bar n (1-indexed)."""
    return (n - 1) * BAR


def beat_at(n: float) -> float:
    return (n - 1) * BEAT


# key story beats (all on the grid)
T = {
    # scene 1
    "s1_line_in": 0.30,
    "s1_video_up": 1.55,
    "s1_head_1": 3.05,
    "s1_head_2": 4.55,
    "s1_shots": [4.30, 4.90, 5.50],
    "s1_counter": 5.72,
    "s1_cut": 7.20,
    # scene 2
    "s2_window": 7.35,
    "s2_type": 7.95,
    "s2_click": 9.90,
    "s2_ripple": 9.95,
    "s2_proc": 10.60,
    "s2_logs": [10.90, 11.45, 12.00, 12.55],
    "s2_zoom": 13.55,
    # scene 3
    "s3_start": 14.40,
    "s3_scan": 15.30,
    "s3_strips": 17.10,
    "s3_snap0": 18.10,
    "s3_snap_step": 0.30,
    "s3_snap_n": 12,
    "s3_dedupe": 22.10,
    "s3_ai": 23.30,
    "s3_page": 25.00,
    # scene 4
    "s4_ui": 26.40,
    "s4_select": 28.10,
    "s4_bar": 29.00,
    "s4_keep": 30.00,
    "s4_reorder": 31.10,
    "s4_zoom": 33.20,
    "s4_confirm": 34.70,
    # scene 5
    "s5_page": 36.20,
    "s5_light": 37.10,
    "s5_flip": 39.30,
    "s5_macro": 41.60,
    "s5_stack": 42.90,
    # scene 6
    "s6_page_away": 45.80,
    "s6_line": 47.00,
    "s6_head_1": 49.20,
    "s6_head_2": 50.60,
    "s6_logo": 53.00,
    "s6_word": 54.20,
    "s6_tag": 56.40,
    "s6_foot": 58.00,
}
