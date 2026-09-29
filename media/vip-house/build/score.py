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
TL = json.load(open(f'{S}/timeline.json'))

INTRO = TL['intro']            # video starts here
VID_END = TL['vid_end']        # last source frame
BEAT = TL['beat']
BAR = 4 * BEAT
VA_AT, VB_AT = TL['voice_a_at'], TL['voice_b_at']
FINAL_HIT = TL['final_hit']
TOTAL = TL['total']
CUTS = TL['cuts']
N = int(TOTAL * SR)

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


# ------------------------------------------------------------------ score

music = np.zeros((N, 2))
drums = np.zeros((N, 2))
keys = np.zeros((N, 2))
hits = np.zeros((N, 2))


def put(buf, clip, at):
    place(buf, to_stereo(clip), at)


# Intro drone: low A and E, darkening into the first hit
drone_len = INTRO + 0.4
dr = pad_chord([33, 40, 45], drone_len, bright=420, attack=1.6, release=0.4) * 2.0
t = np.arange(len(dr)) / SR
dr *= np.clip(t / 2.0, 0, 1)[:, None]
put(music, dr, 0.0)
air = sos_filter(rng.standard_normal((int(INTRO * SR), 2)), 'bandpass', [5000, 12000]) * 0.012
air *= np.linspace(0, 1, len(air))[:, None]
put(music, air, 0.0)
put(hits, reverse_cymbal(1.6) * 0.32, INTRO - 1.6)
put(hits, riser(1.2, 200, 4000, seed=3) * 0.18, INTRO - 1.2)

# Harmony through the video section: one chord per bar
prog = [
    ('Am', [57, 60, 64], 33),
    ('F', [57, 60, 65], 29),
    ('C', [55, 60, 64], 36),
    ('G', [55, 59, 62], 31),
    ('Am', [57, 60, 64], 33),
    ('F', [57, 60, 65], 29),
    ('E', [56, 59, 64], 28),
]
arp_shapes = {  # upper-octave chord tones for the e-piano line
    'Am': [69, 72, 76, 81], 'F': [65, 69, 72, 77], 'C': [67, 72, 76, 79],
    'G': [67, 71, 74, 79], 'E': [68, 71, 76, 80],
}
for b, (name, notes, root) in enumerate(prog):
    t0 = INTRO + b * BAR
    last = b == len(prog) - 1
    put(music, pad_chord(notes, BAR, bright=1300 if b < 2 else 2000, attack=0.25 if b else 0.02) * 0.9, t0)
    # driving eighth-note bass (drops out in the break bar)
    for k in range(8):
        if last and k >= 4:
            break
        acc = 1.0 if k % 2 == 0 else 0.7
        put(music, bass_note(root, BEAT / 2 * 0.9, cutoff=380 + 260 * (b >= 2)) * 0.34 * acc, t0 + k * BEAT / 2)
    if last:
        put(music, bass_note(root, BEAT * 2, cutoff=300) * 0.34, t0 + 2 * BEAT)
    # drums
    if not last:
        for k in range(4):
            if k in (0, 2):
                put(drums, kick(0.9), t0 + k * BEAT)
            if k in (1, 3):
                put(drums, pan(snap(0.55), 0.15 if k == 1 else -0.15), t0 + k * BEAT)
        if b >= 2:
            put(drums, kick(0.55), t0 + 2.5 * BEAT)
            for k in range(16):
                lvl = 0.10 if k % 2 else 0.16
                put(drums, pan(hat(lvl, open_=(k % 8 == 6)), 0.35), t0 + k * BEAT / 4)
    else:
        # build: snap roll that speeds up into the outro hit
        steps = [0, 0.5, 1, 1.5, 2, 2.25, 2.5, 2.75, 3, 3.125, 3.25, 3.375, 3.5, 3.625, 3.75, 3.875]
        for i, s in enumerate(steps):
            put(drums, pan(snap(0.25 + 0.6 * i / len(steps)), 0.0), t0 + s * BEAT)
        put(drums, kick(0.8), t0)
    # e-piano arpeggio from bar 2 on, eighths, ping-pong feel via pan
    if b >= 2 and not last:
        shape = arp_shapes[name]
        pattern = [0, 2, 1, 3, 2, 1, 3, 2]
        for k, pi in enumerate(pattern):
            put(keys, pan(epiano(shape[pi], 0.35, 0.16), -0.45 if k % 2 else 0.45), t0 + k * BEAT / 2)
    if b == 1:
        # a sparse lead motif to introduce the keys
        for k, m in enumerate([76, 72, 69]):
            put(keys, pan(epiano(m, 0.8, 0.14), 0.2), t0 + (1 + k) * BEAT)

# break bar: riser and reverse cymbal into the outro
put(hits, riser(BAR, 250, 9000, seed=5) * 0.55, VID_END - BAR)
put(hits, reverse_cymbal(1.2) * 0.3, VID_END - 1.2)

# Outro: held A minor bed, sparse keys, soft pulse; big pad after the final hit
outro_len = FINAL_HIT - VID_END
put(music, pad_chord([45, 57, 60, 64], outro_len, bright=1100, attack=0.05, release=0.6) * 0.95, VID_END)
for k in range(int(outro_len / (BEAT * 2))):
    put(music, bass_note(33, BEAT * 1.2, cutoff=260) * 0.22, VID_END + k * BEAT * 2)
for k, (m, bt) in enumerate([(76, 2), (72, 4), (74, 6), (71, 7)]):
    tt = VID_END + bt * BEAT
    if tt < FINAL_HIT - 0.3:
        put(keys, pan(epiano(m, 1.0, 0.11), 0.3 if k % 2 else -0.3), tt)
tail = TOTAL - FINAL_HIT
put(music, pad_chord([45, 57, 64, 71, 72], tail - 0.8, bright=2600, attack=0.02, release=1.2) * 1.0, FINAL_HIT)
put(music, bass_note(33, tail - 1.0, cutoff=240) * 0.3, FINAL_HIT)

# Trailer hits
for at, big in ((INTRO, 1.0), (VID_END, 0.9), (FINAL_HIT, 1.25)):
    put(hits, to_stereo(boom(3.5, big, seed=int(at))) * 0.85 * big, at)
    put(hits, braam(dur=3.0, seed=int(at)) * 0.42 * big, at)
    put(hits, crash(0.30 * big), at)
put(hits, shimmer(3.2, base=880, seed=2) * 0.2, FINAL_HIT + 0.02)

# ------------------------------------------------------------------ reverb buses
room = make_ir(rt60=1.8, predelay=0.02, damp=7000, seed=5)
hall = make_ir(rt60=3.2, predelay=0.035, damp=5500, seed=9, width=1.2)
music = reverb(music, hall, wet=0.28)[:N]
keys = reverb(keys, hall, wet=0.55)[:N]
drums = reverb(drums, room, wet=0.22)[:N]
hits = reverb(hits, hall, wet=0.35)[:N]
score = music + keys + drums + hits

# ------------------------------------------------------------------ sfx: heels + whooshes
steps_in = [INTRO - BEAT * k for k in range(7, 0, -1)]
d_in = list(np.linspace(0.7, 0.0, len(steps_in)))
p_in = list(np.linspace(-0.55, 0.05, len(steps_in)))
steps_out = [FINAL_HIT + 0.75 + BEAT * k for k in range(5)]
d_out = list(np.linspace(0.15, 1.0, len(steps_out)))
p_out = list(np.linspace(0.05, 0.6, len(steps_out)))
fx = np.zeros((N, 2))
fs_in = footsteps(steps_in, d_in, p_in, seed=3)
fs_out = footsteps(steps_out, d_out, p_out, seed=8)
put(fx, fs_in[:int((INTRO + 0.6) * SR)] * 0.95, 0.0)
put(fx, fs_out, 0.0)
for c in CUTS:
    if INTRO + 0.3 < c < VID_END - 1.0:
        put(fx, whoosh(0.45, 0.3, 0.13), c - 0.3)

# ------------------------------------------------------------------ voice
def load(path):
    sr, x = wavfile.read(path)
    x = x.astype(np.float64) / 32768.0
    if x.ndim > 1:
        x = x.mean(1)
    assert sr == SR
    return x


def voice_chain(x):
    x = sos_filter(x, 'highpass', 70, 2)
    x = shelf(x, 160, 1.5, 'low')
    x = peaking(x, 320, -2.0, 1.0)
    x = peaking(x, 3200, 2.5, 0.9)
    x = shelf(x, 9000, 1.5, 'high')
    # gentle compression (feed-forward, RMS detector)
    env = np.sqrt(sos_filter(x ** 2, 'lowpass', 12, 1).clip(1e-12))
    lvl = 20 * np.log10(env)
    thr, ratio = -24.0, 3.0
    gr = np.where(lvl > thr, (thr - lvl) * (1 - 1 / ratio), 0.0)
    x = x * 10 ** (gr / 20)
    return x / np.max(np.abs(x))


va = voice_chain(load(TL['voice_a']))
vb = voice_chain(load(TL['voice_b']))
voice = np.zeros((N, 2))
plate = make_ir(rt60=1.4, predelay=0.03, damp=6500, seed=21)
put(voice, reverb(to_stereo(va), plate, wet=0.10), VA_AT)
put(voice, reverb(to_stereo(vb), plate, wet=0.10), VB_AT)
# a longer cinematic tail on the last word
vb_tail = np.zeros(len(vb))
vb_tail[int((FINAL_HIT - VB_AT - 0.35) * SR):] = vb[int((FINAL_HIT - VB_AT - 0.35) * SR):]
put(voice, reverb(to_stereo(vb_tail), hall, wet=0.35, dry=0.0), VB_AT)

# ------------------------------------------------------------------ mix
def rms_db(x):
    return 20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-12)


# duck the score under the narration
venv = np.abs(voice).max(1)
venv = sos_filter(venv, 'lowpass', 6, 1)
venv = np.clip(venv / (np.percentile(venv[venv > 1e-4], 90) + 1e-9), 0, 1)
duck = 10 ** (-10.0 * venv / 20)
score_d = score * duck[:, None]

voice_gain = 10 ** (-3.0 / 20) / np.max(np.abs(voice))
voice *= voice_gain
score_d *= 10 ** (-2.0 / 20) / np.max(np.abs(score_d)) * 0.9
fx *= 10 ** (-4.0 / 20) / np.max(np.abs(fx))

mix = voice + score_d * 0.85 + fx * 0.95
fade = np.clip((TOTAL - np.arange(N) / SR) / 1.2, 0, 1) ** 1.5
mix *= fade[:, None]
mix = sos_filter(mix, 'highpass', 25, 2)

for name, stem in (('voice', voice), ('score', score_d), ('fx', fx), ('mix', mix)):
    print(f'{name:6s} rms {rms_db(stem):6.1f} dB  peak {20 * np.log10(np.max(np.abs(stem)) + 1e-12):5.1f} dB')

peak = np.max(np.abs(mix))
mix = mix / peak * 0.89
wavfile.write(f'{S}/mix.wav', SR, (mix * 32767).astype(np.int16))
k = 0.89 / peak
for name, stem in (('voice', voice), ('score', score_d * 0.85), ('fx', fx * 0.95)):
    wavfile.write(f'{S}/stem_{name}.wav', SR, np.clip(stem * fade[:, None] * k * 32767, -32767, 32767).astype(np.int16))
print('wrote mix', mix.shape[0] / SR, 's')
