from pathlib import Path

HERE = Path(__file__).resolve().parent

# --- S4 exit flash timing (scene ends at 36.0)
p = HERE / "film" / "film.py"
s = p.read_text(encoding="utf-8")
s = s.replace("    fl = pulse(t, 34.75, 0.3)\n    if fl > 0:\n        img = img * (1 - fl * 0.85) + fl * 0.85",
              "    fl = pulse(t, 35.72, 0.34)\n    if fl > 0:\n        img = img * (1 - fl * 0.9) + fl * 0.9")
p.write_text(s, encoding="utf-8")

# --- audio: tame drone, louder master
a = HERE / "audio.py"
t = a.read_text(encoding="utf-8")
t = t.replace("    m.add(drone, 0.0, 0.30)", "    m.add(drone, 0.0, 0.17)")
t = t.replace("    mus[:, 0] += v * 0.7\n    mus[:, 1] += np.roll(v, 137) * 0.7",
              "    mus[:, 0] += v * 0.45\n    mus[:, 1] += np.roll(v, 137) * 0.45")
t = t.replace("    mix = mix / peak * 0.92", "    mix = mix / peak * 0.97")
a.write_text(t, encoding="utf-8")
print("patched")
