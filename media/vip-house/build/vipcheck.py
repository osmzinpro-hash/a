"""Scores how closely the first 'VIP' of each take matches a known-good 'VIP'.

MFCC features + subsequence DTW: the reference word is searched inside the
first phrase of each take; lower normalized cost = closer pronunciation.
"""
import sys
import numpy as np
import scipy.io.wavfile as wavfile
from scipy.fft import dct

SR = 48000
V = '/tmp/claude-0/-home-user-a/8f0652ee-1482-53b0-83c8-c0d027028c46/scratchpad/voz'


def load(name):
    sr, x = wavfile.read(f'{V}/{name}.wav')
    return x.astype(np.float64) / 32768


def mel_fb(nfft=1024, n=26, lo=80, hi=8000):
    mel = lambda f: 2595 * np.log10(1 + f / 700)
    imel = lambda m: 700 * (10 ** (m / 2595) - 1)
    pts = imel(np.linspace(mel(lo), mel(hi), n + 2))
    bins = np.floor((nfft + 1) * pts / SR).astype(int)
    fb = np.zeros((n, nfft // 2 + 1))
    for i in range(n):
        a, b, c = bins[i], bins[i + 1], bins[i + 2]
        fb[i, a:b] = (np.arange(a, b) - a) / max(b - a, 1)
        fb[i, b:c] = (c - np.arange(b, c)) / max(c - b, 1)
    return fb


FB = mel_fb()


def mfcc(x):
    x = np.append(x[0], x[1:] - 0.97 * x[:-1])
    n, hop = int(0.025 * SR), int(0.01 * SR)
    frames = np.stack([x[i:i + n] * np.hamming(n) for i in range(0, len(x) - n, hop)])
    p = np.abs(np.fft.rfft(frames, 1024)) ** 2
    m = np.log(p @ FB.T + 1e-10)
    c = dct(m, type=2, axis=1, norm='ortho')[:, 1:13]
    d = np.gradient(c, axis=0)
    return np.hstack([c, d * 2])


def subseq_dtw(ref, seq):
    cost = np.linalg.norm(ref[:, None, :] - seq[None, :, :], axis=2)
    n, m = cost.shape
    D = np.full((n, m), np.inf)
    D[0] = cost[0]
    for i in range(1, n):
        D[i, 0] = D[i - 1, 0] + cost[i, 0]
        for j in range(1, m):
            D[i, j] = cost[i, j] + min(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1])
    j = int(np.argmin(D[-1]))
    return D[-1, j] / n, j


def phrase1_end(x):
    hop = int(0.02 * SR)
    e = np.array([np.sqrt((x[i:i + hop] ** 2).mean()) for i in range(0, len(x) - hop, hop)])
    quiet = e < 10 ** (-40 / 20)
    run = 0
    for i, q in enumerate(quiet):
        run = run + 1 if q else 0
        if run >= 10 and i * 0.02 > 0.8:
            return (i - run + 1) * 0.02
    return len(x) / SR


def speech_on(x):
    return np.argmax(np.abs(x) > 0.02) / SR


def cmn(f, stats):
    return (f - stats[0]) / stats[1]


g2 = load('gideon-2')
g1 = load('gideon-1b')
refs = {
    'fim da frase (certo)': g2[int(3.74 * SR):int(4.24 * SR)],
}
takes = ['gideon-2'] + sys.argv[1:]
for take in takes:
    x = load(take)
    st, en = speech_on(x), phrase1_end(x)
    seg = x[int(st * SR):int(en * SR)]
    feats = mfcc(seg)
    # later half of the phrase holds "VIP House"; search the whole phrase anyway
    out = []
    for name, r in refs.items():
        rf = mfcc(r)
        allf = np.vstack([feats, rf])
        stats = (allf.mean(0), allf.std(0) + 1e-6)
        c, j = subseq_dtw(cmn(rf, stats), cmn(feats, stats))
        out.append(f'{name}: {c:.3f} (termina em {st + (j + 2) * 0.01:.2f}s)')
    print(f'{take:22s} frase1 {st:.2f}-{en:.2f}s dur {len(x) / SR:.2f}s | ' + ' | '.join(out))
