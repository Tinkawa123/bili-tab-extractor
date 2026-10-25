from pathlib import Path

HERE = Path(__file__).resolve().parent
film = HERE / "film" / "film.py"
s = film.read_text(encoding="utf-8")
new = (HERE / "_s56_new.txt").read_text(encoding="utf-8")

start = s.index("def scene5(t):")
end = s.index("def _placeholder(t, name):")
# keep the dispatch section after _placeholder
s = s[:start] + new.rstrip() + "\n\n\n" + s[end:]
film.write_text(s, encoding="utf-8")
print("patched S5+S6", len(s))
