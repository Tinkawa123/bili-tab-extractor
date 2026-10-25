"""Replace the S2 block in film.py with the contents of _s2_new.txt."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
film = HERE / "film" / "film.py"
src = film.read_text(encoding="utf-8")
new = (HERE / "_s2_new.txt").read_text(encoding="utf-8")

start_marker = 'URL = "bilibili.com/video/BV1nU4y1r7xJ"'
end_marker = "# --------------------------------------------------------------------------- #\n# stubs for S3-S6"

i = src.index(start_marker)
j = src.index(end_marker)
out = src[:i] + new.rstrip() + "\n\n\n" + src[j:]
film.write_text(out, encoding="utf-8")
print("patched", len(out))
