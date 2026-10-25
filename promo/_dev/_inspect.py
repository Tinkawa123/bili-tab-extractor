from pathlib import Path

s = Path(__file__).resolve().parent.joinpath("film/film.py").read_text(encoding="utf-8")
keys = [
    "    push = remap(t, 13.2, 14.32",
    "    push = remap(t, 33.2, 34.9",
    "    ent = remap(t, 26.4, 27.2",
    "    ent = remap(t, 7.22, 8.05",
    "    op = p * (1 - page_fade) * (1 - dup_die)",
    "    sel = 27.5 < t < 30.3",
    "    blit_perspective(img, p2, q2, ent)",
]
for k in keys:
    i = s.find(k)
    print("===", k[:44], "at", i)
    if i >= 0:
        print(s[max(0, i - 300) : i + 300].replace("\n", "\n|"))
