from pathlib import Path

HERE = Path(__file__).resolve().parent
p = HERE / "film" / "film.py"
s = p.read_text(encoding="utf-8")

old = '''    push = remap(t, 33.2, 34.9, ease_in_out_cubic)
    scale = 1.0 + push * 0.34
    fx, fy = _RV_W - _RV_M - 110, _RV_H - 40
    focus_x = lerp(_RV_X + _RV_M + 260, 1010, push)
    focus_y = lerp(_RV_Y + 330, 600, push)
    ox = focus_x - fx * scale
    oy = focus_y - fy * scale'''
new = '''    push = remap(t, 33.2, 34.9, ease_in_out_cubic)
    scale = 1.0 + push * 0.22
    # interpolate the window position directly so it stays framed while pushing in
    ox = lerp(_RV_X, 196.0, push)
    oy = lerp(_RV_Y, 128.0, push)'''
assert old in s
s = s.replace(old, new)
p.write_text(s, encoding="utf-8")
print("patched S4 push")
