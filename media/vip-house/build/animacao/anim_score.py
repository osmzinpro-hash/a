"""Short jingle bed for the animated karaoke poster."""
import json
import numpy as np
import scipy.io.wavfile as wavfile
from instruments import *  # noqa: F401,F403

S = '/tmp/claude-0/-home-user-a/8f0652ee-1482-53b0-83c8-c0d027028c46/scratchpad'
TL = json.load(open(f'{S}/anim/timeline.json'))
BEAT = TL['beat']
BAR = 4 * BEAT
VA_AT, VB_AT, HIT, TOTAL = TL['voice_a_at'], TL['voice_b_at'], TL['final_hit'], TL['total']
N = int(TOTAL * SR)
music, drums, keys, hits = (np.zeros((N, 2)) for _ in range(4))


def put(buf, clip, at):
    place(buf, to_stereo(clip), at)


# a soft hit to open, then three bars of groove and a break into the VIP hit
put(hits, to_stereo(boom(2.5, 0.6, seed=1)) * 0.5, 0.0)
put(hits, crash(0.18), 0.0)
prog = [('Am', [57, 60, 64], 33), ('F', [57, 60, 65], 29), ('C', [55, 60, 64], 36)]
arp = {'Am': [69, 72, 76, 81], 'F': [65, 69, 72, 77], 'C': [67, 72, 76, 79]}
for b, (name, notes, root) in enumerate(prog):
    t0 = b * BAR
    put(music, pad_chord(notes, BAR, bright=2000, attack=0.05 if b == 0 else 0.25) * 0.9, t0)
    for k in range(8):
        put(music, bass_note(root, BEAT / 2 * 0.9, cutoff=600) * 0.34 * (1.0 if k % 2 == 0 else 0.7), t0 + k * BEAT / 2)
    for k in range(4):
        if k in (0, 2):
            put(drums, kick(0.9), t0 + k * BEAT)
        if k in (1, 3):
            put(drums, pan(snap(0.55), 0.15 if k == 1 else -0.15), t0 + k * BEAT)
    put(drums, kick(0.55), t0 + 2.5 * BEAT)
    for k in range(16):
        put(drums, pan(hat(0.10 if k % 2 else 0.16, open_=(k % 8 == 6)), 0.35), t0 + k * BEAT / 4)
    for k, pi in enumerate([0, 2, 1, 3, 2, 1, 3, 2]):
        put(keys, pan(epiano(arp[name][pi], 0.35, 0.16), -0.45 if k % 2 else 0.45), t0 + k * BEAT / 2)
brk = 3 * BAR
put(music, pad_chord([56, 59, 64], HIT - brk, bright=1600, attack=0.1) * 0.9, brk)
put(music, bass_note(28, HIT - brk - 0.05, cutoff=320) * 0.34, brk)
rolls = np.arange(0, (HIT - brk) / BEAT, 0.25)
for i, r in enumerate(rolls):
    put(drums, pan(snap(0.3 + 0.6 * i / len(rolls)), 0.0), brk + r * BEAT)
put(hits, riser(HIT - brk + 0.6, 250, 9000, seed=5) * 0.55, HIT - (HIT - brk + 0.6))
put(hits, reverse_cymbal(1.0) * 0.3, HIT - 1.0)
tail = TOTAL - HIT
put(music, pad_chord([45, 57, 64, 71, 72], tail - 0.3, bright=2600, attack=0.02, release=0.9) * 1.0, HIT)
put(music, bass_note(33, tail - 0.5, cutoff=240) * 0.3, HIT)
put(hits, to_stereo(boom(2.5, 1.2, seed=7)) * 1.0, HIT)
put(hits, braam(dur=2.0, seed=7) * 0.5, HIT)
put(hits, crash(0.36), HIT)
put(hits, shimmer(2.0, base=880, seed=2) * 0.22, HIT + 0.02)

room = make_ir(rt60=1.8, predelay=0.02, damp=7000, seed=5)
hall = make_ir(rt60=2.6, predelay=0.035, damp=5500, seed=9, width=1.2)
score = (reverb(music, hall, wet=0.25)[:N] + reverb(keys, hall, wet=0.5)[:N]
         + reverb(drums, room, wet=0.2)[:N] + reverb(hits, hall, wet=0.32)[:N])


def load(path):
    sr, x = wavfile.read(path)
    x = x.astype(np.float64) / 32768.0
    return x.mean(1) if x.ndim > 1 else x


def voice_chain(x):
    x = sos_filter(x, 'highpass', 70, 2)
    x = shelf(x, 160, 1.5, 'low')
    x = peaking(x, 320, -2.0, 1.0)
    x = peaking(x, 3200, 2.5, 0.9)
    x = shelf(x, 9000, 1.5, 'high')
    env = np.sqrt(sos_filter(x ** 2, 'lowpass', 12, 1).clip(1e-12))
    lvl = 20 * np.log10(env)
    gr = np.where(lvl > -24.0, (-24.0 - lvl) * (1 - 1 / 3.0), 0.0)
    x = x * 10 ** (gr / 20)
    return x / np.max(np.abs(x))


va = voice_chain(load(TL['voice_a']))[:int(TL['voice_a_len'] * SR)]
va *= np.clip((TL['voice_a_len'] - np.arange(len(va)) / SR) / 0.05, 0, 1)
vb = voice_chain(load(TL['voice_b']))
voice = np.zeros((N, 2))
plate = make_ir(rt60=1.4, predelay=0.03, damp=6500, seed=21)
put(voice, reverb(to_stereo(va), plate, wet=0.10), VA_AT)
put(voice, reverb(to_stereo(vb), plate, wet=0.10), VB_AT)
vt = np.zeros(len(vb))
i0 = int((HIT - VB_AT - 0.35) * SR)
vt[i0:] = vb[i0:]
put(voice, reverb(to_stereo(vt), hall, wet=0.35, dry=0.0), VB_AT)

venv = sos_filter(np.abs(voice).max(1), 'lowpass', 6, 1)
venv = np.clip(venv / (np.percentile(venv[venv > 1e-4], 90) + 1e-9), 0, 1)
score_d = score * (10 ** (-10.0 * venv / 20))[:, None]
voice *= 10 ** (-3.0 / 20) / np.max(np.abs(voice))
score_d *= 10 ** (-2.0 / 20) / np.max(np.abs(score_d)) * 0.9
mix = voice + score_d * 0.85
fade = np.clip((TOTAL - np.arange(N) / SR) / 0.7, 0, 1) ** 1.5
mix = sos_filter(mix * fade[:, None], 'highpass', 25, 2)
mix = mix / np.max(np.abs(mix)) * 0.89
wavfile.write(f'{S}/anim/mix.wav', SR, (mix * 32767).astype(np.int16))
print('anim mix', N / SR)
