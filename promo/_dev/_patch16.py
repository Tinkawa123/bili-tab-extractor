from pathlib import Path

p = Path(__file__).resolve().parent / "audio.py"
s = p.read_text(encoding="utf-8")

old = """    rms0 = np.sqrt(np.mean(mix**2))
    target = 10 ** (-15.5 / 20)
    mix = mix * (target / (rms0 + 1e-9))
    peak = np.max(np.abs(mix))
    if peak > 0.97:
        mix = mix / peak * 0.97
    rms = np.sqrt(np.mean(mix**2))"""
new = """    # loudness: normalise then soft-limit so quiet sections stay usable on phones
    rms0 = np.sqrt(np.mean(mix**2))
    target = 10 ** (-16.0 / 20)
    mix = mix * (target / (rms0 + 1e-9))
    mix = np.tanh(mix / 0.82) * 0.82
    rms = np.sqrt(np.mean(mix**2))
    mix = mix * (target / (rms + 1e-9))
    mix = np.tanh(mix / 0.94) * 0.94
    rms = np.sqrt(np.mean(mix**2))"""
assert old in s
s = s.replace(old, new)
p.write_text(s, encoding="utf-8")
print("patched audio loudness")
