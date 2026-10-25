from pathlib import Path

HERE = Path(__file__).resolve().parent
film = HERE / "film" / "film.py"
s = film.read_text(encoding="utf-8")
new = (HERE / "_s3_new.txt").read_text(encoding="utf-8")

start_marker = "# --------------------------------------------------------------------------- #\n# S3 — extraction (14.4 - 26.4)\n# --------------------------------------------------------------------------- #"
end_marker = "    return _flash_cut(img, t, 26.22, 26.4)"

i = s.index(start_marker)
j = s.index(end_marker) + len(end_marker)
s = s[:i] + new.rstrip() + s[j:]
film.write_text(s, encoding="utf-8")
print("patched S3 v2", len(s))
