"""Procedural score + sound design for the promo film.

100 BPM, A minor, 60 s.  Everything is synthesised with numpy so the whole
soundtrack is code-generated and deterministic.

Bus layout:
    music  (guitar / rhodes / pad / bass / drums / vinyl)
    sfx    (shutters, whooshes, UI clicks, paper, risers, impacts)
    master -> gentle glue compression, high-pass, soft clip
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 48000
DUR = 60.0
N = int(SR * DUR)
BPM = 100.0
BEAT = 60.0 / BPM
BAR = 4 * BEAT
NP = np.float32

rng = np.random.default_rng(7)

NOTE = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4, "F#": -3, "G": -2, "G#": -1, "A": 0, "A#": 1, "B": 2}


def hz(name, octave):
    """'A', 3 -> 220.0"""
    semis = NOTE[name] + (octave - 4) * 12
    return 440.0 * 2 ** (semis / 12.0)


def t_axis(dur):
    return np.arange(int(dur * SR), dtype=NP) / SR


def env_ad(n, attack, decay, curve=2.0):
    a = max(1, int(attack * SR))
    d = max(1, n - a)
    e_a = np.linspace(0, 1, a, dtype=NP) ** 0.6
    e_d = np.exp(-np.linspace(0, curve * 3.0, d, dtype=NP))
    return np.concatenate([e_a, e_d])


def saw(f, dur, phase=0.0, detune=0.0):
    t = t_axis(dur)
    f = f * (1 + detune)
    x = (t * f + phase) % 1.0
    return (2 * x - 1).astype(NP)


def lowpass(x, cutoff, order=2):
    cutoff = min(cutoff, SR * 0.45)
    b, a = signal.butter(order, cutoff / (SR / 2), btype="low")
    return signal.lfilter(b, a, x).astype(NP)


def highpass(x, cutoff, order=2):
    b, a = signal.butter(order, cutoff / (SR / 2), btype="high")
    return signal.lfilter(b, a, x).astype(NP)


def bandpass(x, lo, hi, order=2):
    b, a = signal.butter(order, [lo / (SR / 2), min(hi, SR * 0.45) / (SR / 2)], btype="band")
    return signal.lfilter(b, a, x).astype(NP)


# --------------------------------------------------------------------------- #
# instruments
# --------------------------------------------------------------------------- #


def guitar(f, dur=1.6, vel=0.8, bright=1.0):
    """Nylon-ish pluck: additive partials with slight inharmonicity + body."""
    t = t_axis(dur)
    out = np.zeros_like(t)
    partials = [(1, 1.0), (2, 0.42 * bright), (3, 0.24 * bright), (4, 0.12 * bright), (5, 0.06 * bright)]
    for k, amp in partials:
        inh = 1 + 0.0004 * (k**2)
        out += amp * np.sin(2 * np.pi * f * k * inh * t) * np.exp(-t * (2.4 + 2.2 * k))
    # pluck attack noise
    att = rng.normal(0, 1, len(t)).astype(NP)
    att = bandpass(att, 1800, 6000) * np.exp(-t * 90) * 0.25
    body = np.sin(2 * np.pi * 98 * t) * np.exp(-t * 9) * 0.18
    out = (out + att + body) * vel
    return out


def rhodes(f, dur=2.4, vel=0.7):
    t = t_axis(dur)
    mod = np.sin(2 * np.pi * f * 2 * t) * 1.6 * np.exp(-t * 3.2)
    x = np.sin(2 * np.pi * f * t + mod) * np.exp(-t * 1.9)
    x += 0.22 * np.sin(2 * np.pi * f * 2.01 * t) * np.exp(-t * 3.0)
    x += 0.10 * np.sin(2 * np.pi * f * 4.0 * t) * np.exp(-t * 5.0)
    return (x * vel).astype(NP)


def pad(freqs, dur, vel=0.5, cutoff=1400):
    t = t_axis(dur)
    out = np.zeros_like(t)
    for f in freqs:
        for det in (-0.003, 0.0, 0.004):
            out += saw(f, dur, phase=rng.random(), detune=det)
    out /= max(1, len(freqs) * 3)
    out = lowpass(out, cutoff)
    lfo = 0.75 + 0.25 * np.sin(2 * np.pi * 0.11 * t)
    env = np.minimum(1.0, t / 0.9) * np.exp(-np.maximum(0, t - dur * 0.55) * 5.0)
    return (out * lfo * env * vel).astype(NP)


def bass(f, dur=0.5, vel=0.85):
    t = t_axis(dur)
    x = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 2 * t) + 0.12 * np.sin(2 * np.pi * f * 3 * t)
    env = np.minimum(1, t / 0.008) * np.exp(-t * 5.5)
    click = rng.normal(0, 1, len(t)).astype(NP) * np.exp(-t * 180) * 0.15
    return ((x + click) * env * vel).astype(NP)


def kick(vel=1.0):
    dur = 0.42
    t = t_axis(dur)
    f = 128 * np.exp(-t * 26) + 44
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) * np.exp(-t * 6.5)
    click = rng.normal(0, 1, len(t)).astype(NP) * np.exp(-t * 260) * 0.35
    return (np.tanh((x + click) * 1.6) * vel).astype(NP)


def rim(vel=0.8):
    dur = 0.22
    t = t_axis(dur)
    n = rng.normal(0, 1, len(t)).astype(NP)
    n = bandpass(n, 900, 4200) * np.exp(-t * 26)
    tone = np.sin(2 * np.pi * 330 * t) * np.exp(-t * 34) * 0.5
    return ((n * 0.7 + tone) * vel).astype(NP)


def hat(vel=0.5, open_=False):
    dur = 0.16 if not open_ else 0.4
    t = t_axis(dur)
    n = rng.normal(0, 1, len(t)).astype(NP)
    n = highpass(n, 7000) * np.exp(-t * (30 if not open_ else 12))
    return (n * vel).astype(NP)


def clap(vel=0.6):
    dur = 0.3
    t = t_axis(dur)
    n = rng.normal(0, 1, len(t)).astype(NP)
    n = bandpass(n, 800, 3800)
    e = np.zeros_like(t)
    for k, off in enumerate([0.0, 0.012, 0.026]):
        idx = int(off * SR)
        seg = np.exp(-np.maximum(0, t - off) * 22) * (t >= off)
        e = np.maximum(e, seg)
    return (n * e * vel).astype(NP)


def shaker(vel=0.3):
    dur = 0.12
    t = t_axis(dur)
    n = highpass(rng.normal(0, 1, dur).astype(NP), 5000) * (np.exp(-t * 40) * (1 - np.exp(-t * 300)))
    return (n * vel).astype(NP)


# --------------------------------------------------------------------------- #
# sfx
# --------------------------------------------------------------------------- #


def click(vel=0.5, f=2200, dur=0.05):
    t = t_axis(dur)
    n = rng.normal(0, 1, len(t)).astype(NP) * np.exp(-t * 220)
    tone = np.sin(2 * np.pi * f * t) * np.exp(-t * 180)
    return (bandpass(n, 1200, 7000) * 0.6 + tone) * vel


def shutter(vel=0.7):
    """Camera / screenshot shutter: two quick mechanical transients."""
    dur = 0.16
    t = t_axis(dur)
    x = np.zeros_like(t)
    for off, g in [(0.0, 1.0), (0.045, 0.7)]:
        idx = int(off * SR)
        seg = bandpass(rng.normal(0, 1, int(0.03 * SR)).astype(NP), 1500, 8000) * np.exp(-np.arange(int(0.03 * SR)) / SR * 120)
        x[idx : idx + len(seg)] += seg * g
    t2 = t_axis(0.09)
    low = np.sin(2 * np.pi * 150 * t2) * np.exp(-t2 * 45) * 0.4
    x[: len(low)] += low
    return x * vel


def whoosh(dur=0.55, up=True, vel=0.6, lo=300, hi=6000):
    t = t_axis(dur)
    n = rng.normal(0, 1, len(t)).astype(NP)
    # morphing bandpass via short blocks
    out = np.zeros_like(n)
    blocks = 24
    seg_len = max(1, len(n) // blocks)
    for i in range(blocks):
        p = i / max(1, blocks - 1)
        c = lo + (hi - lo) * (p if up else 1 - p)
        band = bandpass(n, max(150, c * 0.6), min(c * 1.8, SR * 0.45))
        out[i * seg_len : (i + 1) * seg_len] = band[i * seg_len : (i + 1) * seg_len]
    e = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.4
    return out * e * vel * 1.4


def riser(dur=2.0, vel=0.45):
    t = t_axis(dur)
    n = rng.normal(0, 1, len(t)).astype(NP)
    out = np.zeros_like(n)
    blocks = 40
    seg = max(1, len(n) // blocks)
    for i in range(blocks):
        p = i / (blocks - 1)
        f0 = 300 * (2 ** (p * 3.4))
        band = bandpass(n, max(200, f0 * 0.8), min(SR * 0.45, f0 * 2.2))
        out[i * seg : (i + 1) * seg] = band[i * seg : (i + 1) * seg]
    tone = np.sin(2 * np.pi * np.cumsum(200 * (2 ** (np.linspace(0, 3.0, len(t))))) / SR) * 0.15
    e = np.linspace(0, 1, len(t)) ** 2.2
    return (out * 1.3 + tone) * e * vel


def impact(vel=1.0):
    dur = 1.6
    t = t_axis(dur)
    f = 78 * np.exp(-t * 5.5) + 30
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) * np.exp(-t * 2.6)
    x += rng.normal(0, 1, len(t)).astype(NP) * np.exp(-t * 12) * 0.25
    return np.tanh(x * 1.4) * vel


def chime(f=880, dur=2.2, vel=0.4):
    t = t_axis(dur)
    out = np.zeros_like(t)
    for k, a in [(1, 1.0), (2.76, 0.45), (5.4, 0.22), (8.9, 0.1)]:
        out += a * np.sin(2 * np.pi * f * k * t) * np.exp(-t * (2.2 + k * 1.6))
    return out * vel


def paper_flip(vel=0.5, dur=0.45):
    t = t_axis(dur)
    n = rng.normal(0, 1, len(t)).astype(NP)
    n = bandpass(n, 1500, 7000)
    flutter = 0.55 + 0.45 * np.sin(2 * np.pi * 11 * t + 0.4)
    e = np.exp(-((t - dur * 0.35) ** 2) / (2 * (dur * 0.22) ** 2))
    return n * e * flutter * vel * 1.6


def paper_place(vel=0.6):
    dur = 0.5
    t = t_axis(dur)
    n = bandpass(rng.normal(0, 1, len(t)).astype(NP), 600, 5000) * np.exp(-t * 18)
    thud = np.sin(2 * np.pi * 90 * t) * np.exp(-t * 18) * 0.5
    return (n * 0.5 + thud) * vel


def tick(vel=0.28, f=1400):
    return click(vel, f, 0.035)


def glitch(vel=0.3, dur=0.12):
    t = t_axis(dur)
    n = rng.normal(0, 1, len(t)).astype(NP)
    sq = np.sign(np.sin(2 * np.pi * 1200 * t))
    return bandpass(n, 800, 6000) * 0.6 * np.exp(-t * 20) * vel + sq * 0.05 * vel


# --------------------------------------------------------------------------- #
# mixing helpers
# --------------------------------------------------------------------------- #


class Bus:
    def __init__(self):
        self.x = np.zeros((N, 2), np.float32)

    def add(self, sig, t0, gain=1.0, pan=0.0):
        if sig is None:
            return
        i0 = int(t0 * SR)
        if i0 >= N:
            return
        sig = np.asarray(sig, dtype=np.float32)
        if sig.ndim == 1:
            l = math.sqrt(0.5 * (1 - pan))
            r = math.sqrt(0.5 * (1 + pan))
            sig = np.stack([sig * l, sig * r], axis=1) * 1.414
        n = min(len(sig), N - i0)
        if n <= 0:
            return
        self.x[i0 : i0 + n] += sig[:n] * gain

    def add2(self, sigL, sigR, t0, gain=1.0):
        i0 = int(t0 * SR)
        n = min(len(sigL), N - i0)
        if n <= 0:
            return
        self.x[i0 : i0 + n, 0] += sigL[:n] * gain
        self.x[i0 : i0 + n, 1] += sigR[:n] * gain


def reverb(x, dur=2.2, mix=0.25, predelay=0.02):
    n_ir = int(dur * SR)
    t = np.arange(n_ir, dtype=NP) / SR
    ir = rng.normal(0, 1, (n_ir, 2)).astype(NP)
    ir *= np.exp(-t * (2.6 / dur))[:, None]
    ir = np.stack([lowpass(ir[:, 0], 5200), lowpass(ir[:, 1], 5200)], axis=1)
    ir[: int(predelay * SR)] = 0
    ir /= np.max(np.abs(ir)) + 1e-9
    wet = np.stack(
        [
            signal.fftconvolve(x[:, 0], ir[:, 0])[: len(x)],
            signal.fftconvolve(x[:, 1], ir[:, 1])[: len(x)],
        ],
        axis=1,
    ).astype(NP)
    wet /= np.max(np.abs(wet)) + 1e-9
    return x * (1 - mix) + wet * mix * 1.6


def compress(x, thresh=0.5, ratio=2.5, attack=0.01, release=0.15):
    env = np.abs(x).max(axis=1)
    # smooth envelope
    a = math.exp(-1 / (attack * SR))
    rel = math.exp(-1 / (release * SR))
    e = np.zeros_like(env)
    prev = 0.0
    for i in range(len(env)):
        v = env[i]
        coef = a if v > prev else rel
        prev = coef * prev + (1 - coef) * v
        e[i] = prev
    gain = np.ones_like(e)
    over = e > thresh
    gain[over] = (thresh + (e[over] - thresh) / ratio) / (e[over] + 1e-9)
    smooth_gain = signal.lfilter([0.02], [1, -0.98], gain)
    return x * smooth_gain[:, None]


def soft_clip(x, drive=1.2):
    return np.tanh(x * drive) / np.tanh(drive)


# --------------------------------------------------------------------------- #
# score
# --------------------------------------------------------------------------- #


def build_music():
    m = Bus()
    A = hz("A", 2)
    chords = {
        "Am": [hz("A", 3), hz("C", 4), hz("E", 4)],
        "F": [hz("F", 3), hz("A", 3), hz("C", 4)],
        "C": [hz("C", 3), hz("E", 3), hz("G", 3)],
        "G": [hz("G", 3), hz("B", 3), hz("D", 4)],
    }
    roots = {"Am": hz("A", 2), "F": hz("F", 1), "C": hz("C", 2), "G": hz("G", 1)}
    bass_roots = {"Am": hz("A", 1), "F": hz("F", 1), "C": hz("C", 2), "G": hz("G", 1)}

    def bar_t(b):
        return (b - 1) * BAR

    # -------- chord map (bar -> chord)
    cmap = {}
    for b in range(1, 4):
        cmap[b] = "Am"
    for b, c in zip(range(4, 12), ["Am", "Am", "F", "F", "C", "C", "G", "G"]):
        cmap[b] = c
    for b, c in zip(range(12, 16), ["Am", "Am", "F", "F"]):
        cmap[b] = c
    for b, c in zip(range(16, 20), ["C", "C", "G", "G"]):
        cmap[b] = c
    for b, c in zip(range(20, 26), ["Am", "Am", "F", "G", "Am", "Am"]):
        cmap[b] = c

    # -------- intro: drone + sparse harmonics + vinyl
    t = t_axis(BAR * 3)
    drone = (np.sin(2 * np.pi * A * t) * 0.5 + np.sin(2 * np.pi * A * 1.5 * t) * 0.18) * np.minimum(1, t / 1.2)
    drone *= np.exp(-np.maximum(0, t - BAR * 2.2) * 1.2)
    m.add(drone, 0.0, 0.17)
    for i, (tt, f, v) in enumerate([(0.0, hz("A", 4), 0.5), (1.2, hz("E", 5), 0.35), (3.6, hz("C", 5), 0.4), (5.4, hz("A", 4), 0.35)]):
        m.add(guitar(f, 2.6, v * 0.6), tt, 0.5, pan=-0.2 + 0.1 * i)

    # -------- drums patterns
    def drums(bar_from, bar_to, level=1.0, hats16=False, claps=False, fills=False):
        for b in range(bar_from, bar_to + 1):
            bt = bar_t(b)
            for beat_i in range(4):
                tt = bt + beat_i * BEAT
                if beat_i in (0, 2):
                    m.add(kick(0.9 * level), tt, 0.55)
                if beat_i in (1, 3) and b > 3:
                    m.add(rim(0.8 * level), tt, 0.22, pan=0.15)
                if claps and beat_i == 2:
                    m.add(clap(0.5 * level), tt, 0.20, pan=-0.1)
                if hats16:
                    for s in range(4):
                        m.add(hat(0.35 * level if s % 2 == 0 else 0.2 * level), tt + s * BEAT / 4, 0.16, pan=0.3)
                else:
                    m.add(hat(0.32 * level), tt + BEAT / 2, 0.14, pan=0.3)
            if fills and b == bar_to:
                for k in range(4):
                    m.add(rim(0.5 + 0.1 * k), bt + BAR - BEAT + k * BEAT / 4, 0.2, pan=-0.2 + 0.15 * k)

    # -------- groove A (4-11)
    drums(4, 11, 0.85, hats16=False, claps=False, fills=True)
    drums(7, 11, 0.95, hats16=True, claps=True)

    # -------- bass (4-25)
    for b in range(4, 26):
        c = cmap[b]
        bt = bar_t(b)
        rootf = bass_roots[c]
        if b < 16:
            for beat_i in [0, 1.5, 2, 3.5]:
                tt = bt + beat_i * BEAT
                if tt > DUR - 0.3:
                    continue
                m.add(bass(rootf if int(beat_i) % 2 == 0 else rootf, 0.45, 0.75), tt, 0.34)
        elif b < 20:
            for beat_i in [0, 2]:
                m.add(bass(rootf, 0.9, 0.6), bt + beat_i * BEAT, 0.30)
        else:
            for beat_i in [0, 1.5, 2, 3.5]:
                m.add(bass(rootf, 0.5, 0.7), bt + beat_i * BEAT, 0.30)

    # -------- guitar arpeggios
    def arp(bar_from, bar_to, step=0.5 * BEAT, level=0.32, octave_shift=0):
        for b in range(bar_from, bar_to + 1):
            notes = chords[cmap[b]]
            if octave_shift:
                notes = [n * 2**octave_shift for n in notes]
            bt = bar_t(b)
            n = int(BAR / step)
            for i in range(n):
                tt = bt + i * step
                if tt >= DUR - 0.4:
                    return
                f = notes[i % len(notes)]
                if i % 3 == 2:
                    f *= 1.0
                m.add(guitar(f, 1.4, level * (0.75 + 0.25 * ((i % 4) / 3))), tt, 0.42, pan=-0.25 + 0.12 * (i % 3))

    arp(4, 11, 0.5 * BEAT, 0.30)
    arp(12, 15, 0.5 * BEAT, 0.26)
    arp(16, 19, BEAT, 0.24)
    arp(20, 24, 0.5 * BEAT, 0.30)
    # high sparkle notes
    for tt, ch in [(bar_t(20), "Am"), (bar_t(22), "F"), (bar_t(23), "G")]:
        f = chords[ch][2] * 2
        m.add(guitar(f, 2.4, 0.30), tt, 0.30, pan=0.25)

    # -------- rhodes chord stabs + pad
    for b, c in cmap.items():
        bt = bar_t(b)
        notes = chords[c]
        if b <= 3:
            continue
        gain = 0.22 if 4 <= b <= 11 else (0.18 if 12 <= b <= 19 else 0.24)
        if b % 2 == 1 or b in (12, 16, 20):
            for f in notes:
                m.add(rhodes(f, 2.6, 0.55), bt, gain, pan=-0.1)
        # pad an octave up
        if b >= 12:
            pv = pad([n / 2 for n in notes], BAR * 1.02, 0.42, cutoff=1100)
            m.add(pv, bt, 0.16)

    # -------- final resolve chord
    m.add(pad([hz("A", 3), hz("C", 4), hz("E", 4), hz("B", 4)], 3.2, 0.5, cutoff=1500), bar_t(24), 0.22)
    for f in [hz("A", 4), hz("C", 5), hz("E", 5)]:
        m.add(guitar(f, 3.4, 0.35), bar_t(24), 0.34)
    return m


def build_sfx():
    s = Bus()
    # ---- intro / S1
    s.add(impact(0.7), 0.02, 0.5)
    s.add(whoosh(0.5, up=True, vel=0.35, lo=200, hi=3000), 1.72, 0.5)
    for tt, v in [(2.9, 0.35), (4.3, 0.5), (4.9, 0.55), (5.5, 0.6)]:
        s.add(shutter(v), tt, 0.55, pan=0.25)
    s.add(riser(0.9, 0.4), 6.35, 0.5)
    s.add(whoosh(0.45, up=True, vel=0.4, lo=400, hi=5000), 6.9, 0.5)

    # ---- S2 UI
    s.add(whoosh(0.5, up=True, vel=0.3, lo=300, hi=3500), 7.22, 0.45, pan=-0.2)
    for i, tt in enumerate(np.arange(7.95, 9.15, 0.052)):
        s.add(tick(0.12 + 0.03 * (i % 3), 1800), tt, 0.22, pan=0.1)
    s.add(click(0.6, 1400), 9.90, 0.6)
    s.add(chime(hz("E", 5), 1.2, 0.18), 9.95, 0.35, pan=0.1)
    s.add(whoosh(0.4, up=False, vel=0.22, lo=500, hi=4500), 10.45, 0.4)
    for tt in [10.9, 11.45, 12.0, 12.55]:
        s.add(tick(0.3, 1100), tt, 0.28, pan=-0.15)
    s.add(riser(0.6, 0.35), 13.5, 0.45)

    # ---- S3 extraction
    s.add(impact(0.75), 14.4, 0.55)
    s.add(whoosh(1.9, up=False, vel=0.3, lo=1800, hi=300), 14.95, 0.45)
    for i in range(12):
        tt = 15.35 + i * 0.265 + 0.35
        f = 900 * (2 ** (i / 12.0))
        s.add(tick(0.30, f), tt, 0.30, pan=-0.35 + 0.06 * i)
        s.add(chime(f * 2.2, 0.5, 0.10), tt, 0.22, pan=-0.2 + 0.05 * i)
    for i, tt in enumerate([20.2, 20.5, 20.8]):
        s.add(glitch(0.35, 0.14), tt, 0.5, pan=0.3)
        s.add(whoosh(0.3, up=False, vel=0.25, lo=1200, hi=400), tt, 0.4)
    s.add(whoosh(0.5, up=True, vel=0.3, lo=400, hi=6000), 20.95, 0.45)
    s.add(riser(1.1, 0.25), 21.6, 0.4)
    s.add(chime(hz("A", 5), 1.4, 0.16), 22.1, 0.32, pan=0.2)
    s.add(whoosh(0.7, up=True, vel=0.25, lo=800, hi=7000), 22.05, 0.4)
    s.add(paper_place(0.5), 23.6, 0.5)
    s.add(whoosh(1.2, up=True, vel=0.35, lo=200, hi=4000), 25.0, 0.5)
    s.add(impact(0.6), 26.35, 0.45)

    # ---- S4 review
    s.add(whoosh(0.5, up=True, vel=0.3, lo=250, hi=3000), 26.42, 0.4, pan=-0.2)
    s.add(click(0.5, 1500), 27.45, 0.5, pan=-0.1)
    s.add(click(0.5, 1200), 28.45, 0.5, pan=0.1)
    s.add(whoosh(0.7, up=False, vel=0.22, lo=900, hi=300), 29.35, 0.4)
    s.add(chime(hz("C", 6), 1.6, 0.2), 31.0, 0.3, pan=0.25)
    s.add(click(0.55, 1100), 33.2, 0.55)
    s.add(riser(0.5, 0.3), 34.2, 0.4)

    # ---- S5 paper
    s.add(paper_place(0.7), 36.2, 0.55)
    s.add(whoosh(1.1, up=True, vel=0.2, lo=600, hi=5000), 37.2, 0.35)
    s.add(paper_flip(0.7), 38.75, 0.55)
    s.add(paper_place(0.5), 40.1, 0.45)
    s.add(whoosh(1.4, up=False, vel=0.28, lo=2000, hi=300), 40.5, 0.45)
    s.add(paper_flip(0.5), 42.35, 0.45)
    s.add(whoosh(1.0, up=True, vel=0.3, lo=300, hi=4500), 43.9, 0.5)
    s.add(riser(0.8, 0.3), 44.8, 0.4)

    # ---- S6 brand
    s.add(impact(0.9), 45.55, 0.6)
    s.add(chime(hz("E", 5), 2.6, 0.22), 47.15, 0.35, pan=-0.15)
    s.add(chime(hz("A", 4), 2.2, 0.16), 49.2, 0.3, pan=0.15)
    s.add(chime(hz("C", 5), 2.4, 0.18), 50.6, 0.32, pan=-0.1)
    s.add(whoosh(0.8, up=True, vel=0.25, lo=500, hi=6000), 52.55, 0.4)
    s.add(chime(hz("E", 5), 2.0, 0.2), 53.35, 0.3)
    s.add(click(0.3, 900), 53.4, 0.4)
    s.add(chime(hz("A", 5), 2.4, 0.18), 55.35, 0.3)
    s.add(chime(hz("E", 6), 2.0, 0.10), 56.2, 0.3, pan=0.2)
    return s


def vinyl(n):
    t = np.arange(n, dtype=NP) / SR
    noise = rng.normal(0, 1, n).astype(NP)
    hiss = lowpass(highpass(noise, 2000), 9000) * 0.018
    crackle = np.zeros(n, dtype=NP)
    idx = rng.integers(0, n - 100, int(DUR * 26))
    for i in idx:
        ln = int(rng.integers(6, 40))
        crackle[i : i + ln] += rng.normal(0, 1, ln) * rng.uniform(0.05, 0.35)
    crackle = highpass(crackle, 1500) * 0.5
    return hiss + crackle


def main():
    print("building music…")
    music = build_music()
    print("building sfx…")
    sfx = build_sfx()

    mus = music.x.copy()
    fx = sfx.x.copy()

    # vinyl bed
    v = vinyl(N).astype(NP)
    mus[:, 0] += v * 0.45
    mus[:, 1] += np.roll(v, 137) * 0.45

    # musical sidechain pump from the score (subtle)
    mus = reverb(mus, 2.0, mix=0.18)
    fx = reverb(fx, 1.6, mix=0.22)

    mix = mus * 0.9 + fx * 0.75
    # eq + glue
    mix[:, 0] = highpass(mix[:, 0], 32)
    mix[:, 1] = highpass(mix[:, 1], 32)
    mix = compress(mix, 0.30, 3.4)
    mix = soft_clip(mix * 1.1, 1.1)
    mix = compress(mix, 0.45, 2.0)
    # fades
    fade_in = min(int(0.15 * SR), N)
    mix[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
    fade_out = int(1.4 * SR)
    mix[-fade_out:] *= np.linspace(1, 0, fade_out)[:, None] ** 1.5
    # loudness: normalise then soft-limit so quiet sections stay usable on phones
    rms0 = np.sqrt(np.mean(mix**2))
    target = 10 ** (-16.0 / 20)
    mix = mix * (target / (rms0 + 1e-9))
    mix = np.tanh(mix / 0.82) * 0.82
    rms = np.sqrt(np.mean(mix**2))
    mix = mix * (target / (rms + 1e-9))
    mix = np.tanh(mix / 0.94) * 0.94
    rms = np.sqrt(np.mean(mix**2))
    peak = np.max(np.abs(mix))
    mix = mix / (peak + 1e-9) * 0.93
    peak = np.max(np.abs(mix))
    print(f"peak {peak:.3f} rms {20*np.log10(rms+1e-9):.1f} dBFS")
    out = Path(__file__).resolve().parent / "out"
    out.mkdir(exist_ok=True)
    wavfile.write(str(out / "score.wav"), SR, (mix * 32767).astype(np.int16))
    print("wrote", out / "score.wav")


if __name__ == "__main__":
    main()
