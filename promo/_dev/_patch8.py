from pathlib import Path

HERE = Path(__file__).resolve().parent
p = HERE / "film" / "film.py"
s = p.read_text(encoding="utf-8")

# 1) finish(): per-scene bloom control
s = s.replace(
    "def finish(img, t, grain_amt=0.024, vig=0.52, warm=0.0, lift=0.0, contrast=1.03, sat=1.0):",
    "def finish(img, t, grain_amt=0.024, vig=0.52, warm=0.0, lift=0.0, contrast=1.03, sat=1.0, bloom_amt=0.13, halo_amt=0.05):",
)
s = s.replace(
    "    img = light_pass(img, threshold=0.68, sigma=28, bloom_gain=0.13, halo_gain=0.05, halo_tint=(1.0, 0.58, 0.42))",
    "    img = light_pass(img, threshold=0.70, sigma=28, bloom_gain=bloom_amt, halo_gain=halo_amt, halo_tint=(1.0, 0.58, 0.42))",
)

# 2) dispatch: warm/paper scenes get less bloom
s = s.replace(
    "    warm = 0.6 if D.S5 <= t < D.S6 else 0.0\n    vig = 0.58 if t < D.S2 else (0.4 if t < D.S5 else 0.55)\n    return finish(img, t, grain_amt=0.023, vig=vig, warm=warm)",
    "    warm = 0.6 if D.S5 <= t < D.S6 else 0.0\n    vig = 0.58 if t < D.S2 else (0.4 if t < D.S5 else 0.55)\n    bloom_amt = 0.07 if D.S5 <= t < D.S6 else 0.13\n    halo_amt = 0.03 if D.S5 <= t < D.S6 else 0.05\n    return finish(img, t, grain_amt=0.023, vig=vig, warm=warm, bloom_amt=bloom_amt, halo_amt=halo_amt)",
)

# 3) S1: draw a teal seam in from the very first frame, gentler fade
s = s.replace(
    "    # fade in from black\n    fade = remap(t, 0.0, 0.45, ease_out_cubic)\n    img = img * fade",
    "    # fade in from black + the protagonist line draws in\n    fade = remap(t, 0.0, 0.35, ease_out_cubic)\n    img = img * fade\n    seam = remap(t, 0.05, 0.85, ease_out_cubic)\n    if seam > 0:\n        lw = int(D.W * 0.72 * seam)\n        over(img, solid(lw, 2, D.TEAL), (D.W - lw) / 2, 560, 0.65 * seam, blend=\"add\")\n        over(img, glow_field(D.W, 120, (D.W * 0.5, 560), D.W * 0.36 * seam + 2, D.TEAL, falloff=2.0, gain=0.35), 0, 500, seam, blend=\"add\")",
)

# 4) S5 entrance starts exactly at the cut
s = s.replace("    ent = remap(t, 36.15, 37.15, ease_out_cubic)\n    lift = remap(t, 36.15, 37.2, ease_out_cubic)",
              "    ent = remap(t, 35.98, 37.05, ease_out_cubic)\n    lift = remap(t, 35.98, 37.1, ease_out_cubic)")
p.write_text(s, encoding="utf-8")

# 5) audio loudness: normalise to ~ -15.5 dBFS RMS
a = HERE / "audio.py"
t = a.read_text(encoding="utf-8")
t = t.replace(
    "    peak = np.max(np.abs(mix))\n    mix = mix / peak * 0.97\n    rms = np.sqrt(np.mean(mix**2))",
    "    rms0 = np.sqrt(np.mean(mix**2))\n    target = 10 ** (-15.5 / 20)\n    mix = mix * (target / (rms0 + 1e-9))\n    peak = np.max(np.abs(mix))\n    if peak > 0.97:\n        mix = mix / peak * 0.97\n    rms = np.sqrt(np.mean(mix**2))",
)
a.write_text(t, encoding="utf-8")
print("patched round 2")
