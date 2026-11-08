"""Synthesise the sound-effect library and a music bed (no samples, no licences).

usage: python3 tools/sfx.py [out_dir]     (default: assets/sfx)

Effects (48 kHz mono WAV):
  pop      - character / prop pops in          whoosh  - slide in / big move
  swoosh   - short text / title fly-in         whip    - close-up cut
  impact   - punch / shake                     thud    - board lands
  boom     - drama beat (bg goes dark)         ding    - correct / check mark
  buzz     - wrong / X mark                    scribble- marker drawing (X, circle, underline)
  tick     - quiet word-build tick             riser   - build-up into a reveal
Music: music_beat.wav  - 96 bpm motivational drum + bass loop (8 bars)
"""
import os, sys
import numpy as np
import soundfile as sf
from scipy import signal

SR = 48000
rng = np.random.default_rng(7)


def t_(dur):
    return np.arange(int(SR * dur)) / SR


def env(n, a=0.002, d=0.1, shape=4.0):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-shape * t / max(d, 1e-4))
    return e


def sweep(f0, f1, dur, curve="exp"):
    t = t_(dur)
    f = f0 * (f1 / f0) ** (t / dur) if curve == "exp" else f0 + (f1 - f0) * t / dur
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def bandnoise(dur, lo, hi):
    n = rng.standard_normal(int(SR * dur))
    b, a = signal.butter(2, [lo / (SR / 2), min(hi / (SR / 2), 0.99)], "band")
    return signal.lfilter(b, a, n)


def moving_lowpass(x, f_start, f_end):
    """One-pole low-pass whose cutoff sweeps over the clip."""
    fc = np.geomspace(f_start, f_end, len(x))
    a = np.exp(-2 * np.pi * fc / SR)
    y = np.zeros_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a[i]) * x[i] + a[i] * acc
        y[i] = acc
    return y


def norm(x, peak=0.9):
    m = np.abs(x).max()
    return x / m * peak if m > 0 else x


def pop():
    s = sweep(1100, 280, 0.09) * env(int(SR * 0.09), 0.001, 0.05)
    click = bandnoise(0.01, 2000, 8000) * np.linspace(1, 0, int(SR * 0.01)) * 0.3
    s[:len(click)] += click
    return norm(s, 0.8)


def whoosh(dur=0.42, f0=300, f1=4500):
    n = rng.standard_normal(int(SR * dur))
    x = moving_lowpass(n, f0, f1) - moving_lowpass(n, f0 / 3, f1 / 3) * 0.6
    t = t_(dur)
    e = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.6
    return norm(x * e, 0.75)


def swoosh():
    return whoosh(0.22, 900, 9000) * 0.8


def whip():
    n = bandnoise(0.13, 1500, 12000)
    e = env(len(n), 0.004, 0.05, 3)
    return norm(n * e + sweep(2400, 500, 0.13) * env(len(n), 0.002, 0.04) * 0.3, 0.7)


def impact():
    d = 0.6
    sub = sweep(95, 38, d) * env(int(SR * d), 0.002, 0.35, 3)
    crack = bandnoise(0.08, 300, 6000) * env(int(SR * 0.08), 0.001, 0.03)
    s = sub.copy()
    s[:len(crack)] += crack * 0.8
    return norm(np.tanh(s * 2.2), 0.9)


def thud():
    d = 0.3
    s = sweep(110, 45, d) * env(int(SR * d), 0.002, 0.12, 3)
    s[:int(SR * 0.02)] += bandnoise(0.02, 200, 2000) * 0.4
    return norm(np.tanh(s * 1.8), 0.85)


def boom():
    d = 1.6
    sub = sweep(70, 28, d) * env(int(SR * d), 0.003, 0.9, 2.5)
    rumble = moving_lowpass(rng.standard_normal(int(SR * d)), 400, 60) * env(int(SR * d), 0.01, 0.8, 3) * 3
    return norm(np.tanh((sub + rumble) * 1.6), 0.95)


def ding():
    d = 1.0
    t = t_(d)
    s = sum(a * np.sin(2 * np.pi * 1318.5 * r * t) * np.exp(-t * k) for a, r, k in [(1, 1, 4), (0.5, 2.0, 6), (0.25, 3.0, 9), (0.15, 4.2, 12)])
    s += 0.6 * np.sin(2 * np.pi * 1975.5 * t) * np.exp(-t * 5) * (t > 0.09)
    return norm(s * np.minimum(1, t / 0.002), 0.7)


def buzz():
    d = 0.42
    t = t_(d)
    sq = signal.square(2 * np.pi * (140 + 6 * np.sin(2 * np.pi * 18 * t)) * t)
    b, a = signal.butter(2, 2500 / (SR / 2))
    s = signal.lfilter(b, a, sq) * np.minimum(1, t / 0.01) * np.minimum(1, (d - t) / 0.05)
    return norm(s, 0.55)


def scribble():
    d = 0.32
    x = bandnoise(d, 1800, 7000)
    t = t_(d)
    e = (0.6 + 0.4 * np.sin(2 * np.pi * 22 * t) ** 2) * np.minimum(1, t / 0.02) * np.minimum(1, (d - t) / 0.05)
    return norm(x * e, 0.45)


def tick():
    s = bandnoise(0.018, 2500, 9000) * np.linspace(1, 0, int(SR * 0.018)) ** 2
    return norm(s, 0.3)


def riser():
    d = 1.4
    t = t_(d)
    x = moving_lowpass(rng.standard_normal(int(SR * d)), 200, 9000) * (t / d) ** 2
    s = sweep(180, 900, d) * (t / d) ** 2 * 0.4
    return norm(x + s, 0.6)


def music_beat(bpm=96, bars=8):
    beat = 60 / bpm
    n = int(SR * beat * 4 * bars)
    out = np.zeros(n)

    def add(x, at):
        i = int(at * SR)
        j = min(n, i + len(x))
        out[i:j] += x[:j - i]

    kick = sweep(150, 45, 0.35) * env(int(SR * 0.35), 0.001, 0.18, 3)
    snare = bandnoise(0.2, 180, 7000) * env(int(SR * 0.2), 0.001, 0.07) * 0.7 + sweep(220, 160, 0.2) * env(int(SR * 0.2), 0.001, 0.05) * 0.4
    hat = bandnoise(0.05, 7000, 16000) * env(int(SR * 0.05), 0.001, 0.015) * 0.35
    roots = [55.0, 55.0, 43.65, 49.0]  # A1, A1, F1, G1 — driving minor progression
    for bar in range(bars):
        t0 = bar * 4 * beat
        root = roots[bar % 4]
        for b in range(4):
            tb = t0 + b * beat
            add(kick, tb)
            if b in (1, 3):
                add(snare, tb)
            add(hat, tb + beat / 2)
            add(hat * 0.6, tb)
        if bar % 2 == 1:
            add(kick * 0.8, t0 + 3.5 * beat)  # pickup
        # bass: eighth-note pulse, saw through a low-pass
        for e8 in range(8):
            tt = t_(beat / 2 * 0.9)
            saw = signal.sawtooth(2 * np.pi * root * tt)
            b_, a_ = signal.butter(2, 380 / (SR / 2))
            add(signal.lfilter(b_, a_, saw) * env(len(tt), 0.004, 0.25, 2) * (0.55 if e8 % 2 else 0.75), t0 + e8 * beat / 2)
    return norm(np.tanh(out * 1.2), 0.8)


ALL = dict(pop=pop, whoosh=whoosh, swoosh=swoosh, whip=whip, impact=impact, thud=thud, boom=boom,
           ding=ding, buzz=buzz, scribble=scribble, tick=tick, riser=riser, music_beat=music_beat)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sfx")
    os.makedirs(out, exist_ok=True)
    for name, fn in ALL.items():
        x = fn().astype(np.float32)
        sf.write(os.path.join(out, name + ".wav"), x, SR)
        print(f"{name:11s} {len(x) / SR:5.2f} s")


if __name__ == "__main__":
    main()
