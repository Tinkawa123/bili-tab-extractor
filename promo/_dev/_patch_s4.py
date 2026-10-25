from pathlib import Path

HERE = Path(__file__).resolve().parent
film = HERE / "film" / "film.py"
s = film.read_text(encoding="utf-8")
new = (HERE / "_s4_new.txt").read_text(encoding="utf-8")

start = s.index("# --------------------------------------------------------------------------- #\n# S4 — review UI (26.4 - 36.0)")
end = s.index("def scene5(t):")
print("start", start, "end", end)
assert start < end
s = s[:start] + new.rstrip() + "\n\n\n" + s[end:]
film.write_text(s, encoding="utf-8")
print("patched S4 v2", len(s))
