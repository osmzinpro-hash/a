"""Soundtrack for the 15 s vertical story creative (same palette as the promo)."""
import json
import numpy as np
import scipy.io.wavfile as wavfile
from instruments import *  # noqa: F401,F403  (SR, pad_chord, bass_note, kick, snap, ...)

S = '/tmp/claude-0/-home-user-a/8f0652ee-1482-53b0-83c8-c0d027028c46/scratchpad'
TL = json.load(open(f'{S}/story/timeline.json'))
BEAT = TL['beat']
BAR = 4 * BEAT
HIT1, MONT, MONT_END = TL['hit1'], TL['mont'], TL['mont_end']
VA_AT, VB_AT, FINAL_HIT, TOTAL = TL['voice_a_at'], TL['voice_b_at'], TL['final_hit'], TL['total']
STEPS = TL['steps']
N = int(TOTAL * SR)
rng = np.random.default_rng(11)

music = np.zeros((N, 2))
drums = np.zeros((N, 2))
keys = np.zeros((N, 2))
hits = np.zeros((N, 2))


def put(buf, clip, at):
    place(buf, to_stereo(clip), at)


# hook: low drone under the heels, reverse swell into the first hit
dr = pad_chord([33, 40, 45], HIT1 + 0.3, bright=420, attack=0.9, release=0.3) * 2.0
put(music, dr, 0.0)
put(hits, reverse_cymbal(1.4) * 0.34, HIT1 - 1.4)
put(hits, riser(1.1, 200, 4000, seed=3) * 0.2, HIT1 - 1.1)

# groove: four bars from the first hit to the end card
prog = [('Am', [57, 60, 64], 33, 4), ('F', [57, 60, 65], 29, 4), ('C', [55, 60, 64], 36, 4), ('E', [56, 59, 64], 28, 2)]
arp = {'Am': [69, 72, 76, 81], 'F': [65, 69, 72, 77], 'C': [67, 72, 76, 79]}
t0 = HIT1
for b, (name, notes, root, nb) in enumerate(prog):
    last = b == len(prog) - 1
    dur = nb * BEAT
    put(music, pad_chord(notes, dur, bright=1500 if b == 0 else 2100, attack=0.05 if b == 0 else 0.25) * 0.9, t0)
    if last:
        put(music, bass_note(root, dur * 0.95, cutoff=320) * 0.34, t0)
        rolls = [0, 0.5, 1, 1.25, 1.5, 1.625, 1.75, 1.875]
        for i, r in enumerate(rolls):
            put(drums, pan(snap(0.3 + 0.6 * i / len(rolls)), 0.0), t0 + r * BEAT)
        put(drums, kick(0.8), t0)
    else:
        for k in range(nb * 2):
            put(music, bass_note(root, BEAT / 2 * 0.9, cutoff=420 + 220 * (b >= 1)) * 0.34 * (1.0 if k % 2 == 0 else 0.7),
                t0 + k * BEAT / 2)
        for k in range(nb):
            if k in (0, 2):
                put(drums, kick(0.9), t0 + k * BEAT)
            if k in (1, 3):
                put(drums, pan(snap(0.55), 0.15 if k == 1 else -0.15), t0 + k * BEAT)
        put(drums, kick(0.55), t0 + 2.5 * BEAT)
        for k in range(nb * 4):
            put(drums, pan(hat(0.10 if k % 2 else 0.16, open_=(k % 8 == 6)), 0.35), t0 + k * BEAT / 4)
        if b >= 1:
            shape = arp[name]
            for k, pi in enumerate([0, 2, 1, 3, 2, 1, 3, 2]):
                put(keys, pan(epiano(shape[pi], 0.35, 0.16), -0.45 if k % 2 else 0.45), t0 + k * BEAT / 2)
    t0 += dur
put(hits, riser(BAR, 250, 9000, seed=5) * 0.55, MONT_END - BAR)
put(hits, reverse_cymbal(1.2) * 0.3, MONT_END - 1.2)

# end card: held A minor under the voice, then the big VIP hit and its tail
put(music, pad_chord([45, 57, 60, 64], FINAL_HIT - MONT_END, bright=1100, attack=0.05, release=0.6) * 0.95, MONT_END)
for k in range(int((FINAL_HIT - MONT_END) / (BEAT * 2)) + 1):
    if MONT_END + k * BEAT * 2 < FINAL_HIT - 0.2:
        put(music, bass_note(33, BEAT * 1.2, cutoff=260) * 0.22, MONT_END + k * BEAT * 2)
tail = TOTAL - FINAL_HIT
put(music, pad_chord([45, 57, 64, 71, 72], tail - 0.6, bright=2600, attack=0.02, release=1.0) * 1.0, FINAL_HIT)
put(music, bass_note(33, tail - 0.8, cutoff=240) * 0.3, FINAL_HIT)
for at, big in ((HIT1, 1.0), (MONT_END, 0.9), (FINAL_HIT, 1.25)):
    put(hits, to_stereo(boom(3.0, big, seed=int(at * 10))) * 0.85 * big, at)
    put(hits, braam(dur=2.6, seed=int(at * 10)) * 0.42 * big, at)
    put(hits, crash(0.30 * big), at)
put(hits, shimmer(2.6, base=880, seed=2) * 0.2, FINAL_HIT + 0.02)

room = make_ir(rt60=1.8, predelay=0.02, damp=7000, seed=5)
hall = make_ir(rt60=3.0, predelay=0.035, damp=5500, seed=9, width=1.2)
score = (reverb(music, hall, wet=0.28)[:N] + reverb(keys, hall, wet=0.55)[:N]
         + reverb(drums, room, wet=0.22)[:N] + reverb(hits, hall, wet=0.35)[:N])

# heels in the hook, synced to the steps in the generated shot
fx = np.zeros((N, 2))
d = list(np.linspace(0.35, 0.0, len(STEPS)))
p = list(np.linspace(-0.25, 0.1, len(STEPS)))
put(fx, footsteps(STEPS, d, p, seed=3), 0.0)
for k in range(0, 5):  # light whooshes on the montage cuts
    put(fx, whoosh(0.4, 0.28, 0.10), MONT + k * 2 * BEAT - 0.28)


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


va, vb = voice_chain(load(TL['voice_a'])), voice_chain(load(TL['voice_b']))
voice = np.zeros((N, 2))
plate = make_ir(rt60=1.4, predelay=0.03, damp=6500, seed=21)
put(voice, reverb(to_stereo(va), plate, wet=0.10), VA_AT)
put(voice, reverb(to_stereo(vb), plate, wet=0.10), VB_AT)
vb_tail = np.zeros(len(vb))
i0 = int((FINAL_HIT - VB_AT - 0.35) * SR)
vb_tail[i0:] = vb[i0:]
put(voice, reverb(to_stereo(vb_tail), hall, wet=0.35, dry=0.0), VB_AT)

venv = sos_filter(np.abs(voice).max(1), 'lowpass', 6, 1)
venv = np.clip(venv / (np.percentile(venv[venv > 1e-4], 90) + 1e-9), 0, 1)
score_d = score * (10 ** (-10.0 * venv / 20))[:, None]
voice *= 10 ** (-3.0 / 20) / np.max(np.abs(voice))
score_d *= 10 ** (-2.0 / 20) / np.max(np.abs(score_d)) * 0.9
fx *= 10 ** (-4.0 / 20) / np.max(np.abs(fx))
mix = voice + score_d * 0.85 + fx * 0.95
fade = np.clip((TOTAL - np.arange(N) / SR) / 0.9, 0, 1) ** 1.5
mix *= fade[:, None]
mix = sos_filter(mix, 'highpass', 25, 2)
mix = mix / np.max(np.abs(mix)) * 0.89
wavfile.write(f'{S}/story/mix.wav', SR, (mix * 32767).astype(np.int16))
print('story mix written', N / SR, 's')
