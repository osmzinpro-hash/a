"""Builds the full soundtrack for the VIP House karaoke promo.

Stems: music (score + trailer hits), sfx (heels + whooshes), voice (narration),
then a ducked, limited mix. Timeline constants are shared with the video build.
"""
import json
import sys
import numpy as np
import scipy.io.wavfile as wavfile
from sfx import (SR, t_axis, sos_filter, bandpass, peaking, shelf, make_ir, reverb, pan, place,
                 footsteps, polyblep_saw, boom, braam, riser, reverse_cymbal, shimmer, to_stereo)

S = '/tmp/claude-0/-home-user-a/8f0652ee-1482-53b0-83c8-c0d027028c46/scratchpad'



rng = np.random.default_rng(42)


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def adsr(n, a, d, s, r, hold):
    t = np.arange(n) / SR
    env = np.where(t < a, t / max(a, 1e-4), 1.0)
    dec = np.exp(-np.clip(t - a, 0, None) / max(d, 1e-4)) * (1 - s) + s
    env = np.where(t >= a, dec, env)
    rel = np.clip((t - hold) / r, 0, 1)
    return env * (1 - rel)


# ------------------------------------------------------------------ instruments

def pad_chord(notes, dur, bright=1600, attack=0.5, release=0.9):
    n = int((dur + release) * SR)
    x = np.zeros((n, 2))
    for m in notes:
        for d in (-0.09, -0.03, 0.04, 0.1):
            v = polyblep_saw(midi(m) * 2 ** (d / 12), dur + release, rng.uniform())
            x += pan(v, d * 7)
    x = sos_filter(x, 'lowpass', bright, 2)
    x = sos_filter(x, 'highpass', 120, 2)
    env = adsr(n, attack, 0.8, 0.8, release, dur)
    return x * env[:, None] / (len(notes) * 4)


def bass_note(m, dur, cutoff=520):
    n = int((dur + 0.05) * SR)
    t = np.arange(n) / SR
    saw = polyblep_saw(midi(m + 12), dur + 0.05, rng.uniform())
    saw = sos_filter(saw, 'lowpass', cutoff, 2)
    sub = np.sin(2 * np.pi * midi(m) * t)
    env = adsr(n, 0.004, 0.12, 0.45, 0.05, dur)
    return (saw * 0.6 + sub * 0.8) * env


def kick(level=1.0):
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    f = 46 + 110 * np.exp(-t / 0.035)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.28)
    click = sos_filter(rng.standard_normal(n) * np.exp(-t / 0.003), 'bandpass', [1500, 7000]) * 0.25
    x = np.tanh((x + click) * 1.6)
    return x * level


def snap(level=1.0):
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for k, dt in enumerate((0.0, 0.006, 0.011)):
        i = int(dt * SR)
        b = rng.standard_normal(n - i) * np.exp(-t[:n - i] / (0.004 if k < 2 else 0.035))
        x[i:] += b * (0.7 if k < 2 else 1.0)
    x = bandpass(x, 1100, 5200)
    x += 0.35 * np.sin(2 * np.pi * 2300 * t) * np.exp(-t / 0.01)
    return x / np.max(np.abs(x)) * level


def hat(level=1.0, open_=False):
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    x = sos_filter(rng.standard_normal(n), 'highpass', 7500, 2) * np.exp(-t / (0.09 if open_ else 0.018))
    return x / np.max(np.abs(x)) * level


def epiano(m, dur=0.9, level=1.0):
    """Soft FM electric-piano / bell."""
    n = int((dur + 0.6) * SR)
    t = np.arange(n) / SR
    f = midi(m)
    idx = 2.2 * np.exp(-t / 0.25)
    mod = np.sin(2 * np.pi * f * t)
    x = np.sin(2 * np.pi * f * t + idx * mod) * np.exp(-t / 0.9)
    x += 0.25 * np.sin(2 * np.pi * f * 4.0 * t) * np.exp(-t / 0.12)
    x *= np.clip(t / 0.002, 0, 1) * (1 - np.clip((t - dur) / 0.6, 0, 1))
    return x * level


def crash(level=1.0, dur=3.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = sos_filter(rng.standard_normal((n, 2)), 'highpass', 4000, 2)
    x = peaking(x, 7000, 4, 0.7)
    x *= (np.exp(-t / 0.9) * (1 - np.exp(-t / 0.002)))[:, None]
    return x / np.max(np.abs(x)) * level


def whoosh(dur=0.45, peak_at=0.3, level=1.0):
    n = int(dur * SR)
    out = np.zeros((n, 2))
    for c in range(2):
        noise = rng.standard_normal(n)
        from scipy import signal
        f, tt, Z = signal.stft(noise, fs=SR, nperseg=1024)
        fc = np.interp(tt, [0, peak_at, dur], [500, 3500, 900])
        mask = np.exp(-((np.log(f[:, None] + 1) - np.log(fc[None, :])) ** 2) / (2 * 0.45 ** 2))
        _, y = signal.istft(Z * mask, fs=SR, nperseg=1024)
        out[:, c] = y[:n]
    t = np.arange(n) / SR
    env = np.where(t < peak_at, (t / peak_at) ** 2.5, np.exp(-(t - peak_at) / 0.06))
    out *= env[:, None]
    p = np.linspace(-0.6, 0.6, n)
    out[:, 0] *= np.sqrt((1 - p) / 2) * 1.4
    out[:, 1] *= np.sqrt((1 + p) / 2) * 1.4
    return out / np.max(np.abs(out)) * level


