"""Sound design building blocks: heel footsteps, trailer hits, risers, reverb."""
import numpy as np
from scipy import signal

SR = 48000
rng = np.random.default_rng(7)


def t_axis(dur):
    return np.arange(int(dur * SR)) / SR


def sos_filter(x, kind, freq, order=2):
    sos = signal.butter(order, freq, btype=kind, fs=SR, output='sos')
    return signal.sosfilt(sos, x, axis=0)


def bandpass(x, lo, hi, order=2):
    return sos_filter(x, 'bandpass', [lo, hi], order)


def peaking(x, f0, gain_db, q=1.0):
    a = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * f0 / SR
    alpha = np.sin(w0) / (2 * q)
    b = [1 + alpha * a, -2 * np.cos(w0), 1 - alpha * a]
    den = [1 + alpha / a, -2 * np.cos(w0), 1 - alpha / a]
    return signal.lfilter(b, den, x, axis=0)


def shelf(x, f0, gain_db, kind='low'):
    a = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * f0 / SR
    alpha = np.sin(w0) / 2 * np.sqrt(2)
    c = np.cos(w0)
    if kind == 'low':
        b = [a * ((a + 1) - (a - 1) * c + 2 * np.sqrt(a) * alpha), 2 * a * ((a - 1) - (a + 1) * c),
             a * ((a + 1) - (a - 1) * c - 2 * np.sqrt(a) * alpha)]
        den = [(a + 1) + (a - 1) * c + 2 * np.sqrt(a) * alpha, -2 * ((a - 1) + (a + 1) * c),
               (a + 1) + (a - 1) * c - 2 * np.sqrt(a) * alpha]
    else:
        b = [a * ((a + 1) + (a - 1) * c + 2 * np.sqrt(a) * alpha), -2 * a * ((a - 1) + (a + 1) * c),
             a * ((a + 1) + (a - 1) * c - 2 * np.sqrt(a) * alpha)]
        den = [(a + 1) - (a - 1) * c + 2 * np.sqrt(a) * alpha, 2 * ((a - 1) - (a + 1) * c),
               (a + 1) - (a - 1) * c - 2 * np.sqrt(a) * alpha]
    return signal.lfilter(b, den, x, axis=0)


def make_ir(rt60=2.0, predelay=0.02, damp=6000, er=True, seed=1, width=1.0):
    """Stereo reverb impulse response: early reflections + a damped noise tail."""
    r = np.random.default_rng(seed)
    n = int((rt60 * 1.3 + predelay) * SR)
    t = np.arange(n) / SR
    ir = np.zeros((n, 2))
    tail = r.standard_normal((n, 2))
    # the tail darkens as it decays: blend a bright and a dark copy
    dark = sos_filter(tail, 'lowpass', damp * 0.35)
    bright = sos_filter(tail, 'lowpass', damp)
    mix = np.exp(-t / (rt60 * 0.35))[:, None]
    tail = bright * mix + dark * (1 - mix)
    env = np.exp(-6.9 * t / rt60)
    env[t < predelay] = 0
    fade_in = np.clip((t - predelay) / 0.03, 0, 1)
    ir += tail * (env * fade_in)[:, None]
    if er:
        for _ in range(14):
            d = predelay * 0.5 + r.uniform(0.003, 0.06)
            i = int(d * SR)
            ir[i, 0] += r.uniform(-1, 1) * 1.6 * np.exp(-d * 18)
            ir[i + int(r.uniform(0, 0.004) * SR), 1] += r.uniform(-1, 1) * 1.6 * np.exp(-d * 18)
    mid = ir.mean(1, keepdims=True)
    side = (ir[:, :1] - ir[:, 1:]) / 2
    ir = np.hstack([mid + side * width, mid - side * width])
    return ir / np.sqrt((ir ** 2).sum() / 2)


def reverb(x, ir, wet=0.3, dry=1.0):
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    out = np.zeros((len(x) + len(ir) - 1, 2))
    for c in range(2):
        out[:, c] = signal.fftconvolve(x[:, c], ir[:, c])
    out[:len(x)] = out[:len(x)] * wet + x * dry
    out[len(x):] *= wet
    return out


def pan(x, p):
    """Constant-power pan, p in [-1, 1]."""
    a = (p + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], 1)


def place(buf, clip, at):
    i = int(round(at * SR))
    if i >= len(buf):
        return
    j = min(len(buf), i + len(clip))
    buf[i:j] += clip[:j - i]


# ---------------------------------------------------------------- heels

def heel_click(bright=1.0, seed=None):
    """One stiletto heel strike on a hard tiled floor, then the sole landing."""
    r = np.random.default_rng(seed)
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    # sharp tip impact: a few samples of broadband energy
    k = r.standard_normal(40) * np.exp(-np.arange(40) / 6)
    x[:40] += k * 0.9
    # dense cluster of short modes (heel tip + tile): an impact, not a bell
    sc = r.uniform(0.94, 1.06)
    for _ in range(26):
        f = np.exp(r.uniform(np.log(1300), np.log(11000))) * sc
        d = r.uniform(0.002, 0.011) * (2500 / f) ** 0.3
        a = r.uniform(0.15, 0.6) * (3000 / f) ** 0.25
        x += a * bright * np.sin(2 * np.pi * f * t + r.uniform(0, 6.28)) * np.exp(-t / d)
    # two slightly stronger tile resonances give the floor its "tak"
    for f, d, a in ((2600, 0.012, 0.55), (4300, 0.008, 0.45)):
        f *= sc * r.uniform(0.97, 1.03)
        x += a * bright * np.sin(2 * np.pi * f * t + r.uniform(0, 6.28)) * np.exp(-t / d)
    # short noise burst for the crack
    nb = r.standard_normal(n) * np.exp(-t / 0.005)
    x += bandpass(nb, 1200, 12000) * 1.6
    # knock of the floor and the shoe body
    x += 0.30 * np.sin(2 * np.pi * r.uniform(480, 620) * t) * np.exp(-t / 0.008)
    x += 0.30 * np.sin(2 * np.pi * 170 * t) * np.exp(-t / 0.016) * (1 - np.exp(-t / 0.0015))
    # sole landing, softer and duller, ~90 ms later
    d = r.uniform(0.075, 0.11)
    i = int(d * SR)
    ts = t[:n - i]
    sole = r.standard_normal(n - i) * np.exp(-ts / 0.012) * (1 - np.exp(-ts / 0.002))
    sole = bandpass(sole, 400, 4000) * 0.22
    sole += 0.12 * np.sin(2 * np.pi * 140 * ts) * np.exp(-ts / 0.02)
    x[i:] += sole
    return x / np.max(np.abs(x))


def footsteps(times, dists, pans, seed=3):
    """Render heel steps. dist 0 = close and dry, 1 = far and roomy."""
    total = max(times) + 3.0
    dry = np.zeros((int(total * SR), 2))
    wet_send = np.zeros((int(total * SR), 2))
    for k, (tm, dist, p) in enumerate(zip(times, dists, pans)):
        c = heel_click(seed=seed * 100 + k)
        # distance: quieter, darker
        cutoff = 14000 - 9000 * dist
        c = sos_filter(c, 'lowpass', cutoff)
        g = 10 ** ((-16 * dist) / 20) * rng.uniform(0.85, 1.0)
        s = pan(c * g, p)
        place(dry, s * (1 - 0.55 * dist), tm)
        place(wet_send, s * (0.35 + 0.65 * dist), tm)
    ir = make_ir(rt60=1.6, predelay=0.012, damp=7000, seed=11)
    wet = reverb(wet_send, ir, wet=1.0, dry=0.0)[:len(dry)]
    return dry + wet * 0.45


# ---------------------------------------------------------------- trailer hits

def polyblep_saw(freq, dur, phase0=0.0):
    t = t_axis(dur)
    f = np.broadcast_to(np.asarray(freq, float), t.shape)
    ph = (phase0 + np.cumsum(f) / SR) % 1.0
    dt = f / SR
    y = 2 * ph - 1
    m1 = ph < dt
    x1 = ph[m1] / dt[m1]
    y[m1] -= x1 + x1 - x1 * x1 - 1
    m2 = ph > 1 - dt
    x2 = (ph[m2] - 1) / dt[m2]
    y[m2] -= x2 * x2 + x2 + x2 + 1
    return y


def boom(dur=3.5, big=1.0, seed=0):
    """Cinematic sub drop + impact."""
    r = np.random.default_rng(seed)
    t = t_axis(dur)
    f = 28 + 62 * np.exp(-t / 0.09)
    ph = 2 * np.pi * np.cumsum(f) / SR
    sub = np.sin(ph) * np.exp(-t / (0.9 * big)) * (1 - np.exp(-t / 0.002))
    sub = np.tanh(sub * 2.2) / np.tanh(2.2)
    noise = r.standard_normal(len(t)) * np.exp(-t / 0.08)
    thud = sos_filter(noise, 'lowpass', 220, 4) * 3
    crack = sos_filter(r.standard_normal(len(t)) * np.exp(-t / 0.03), 'bandpass', [900, 6000]) * 0.35
    x = sub * 0.9 + thud * 0.6 + crack
    return x / np.max(np.abs(x))


def braam(notes=(55.0, 110.0, 164.81), dur=3.2, seed=0):
    """Low brass-like swell: detuned saws through an opening then closing filter."""
    t = t_axis(dur)
    x = np.zeros((len(t), 2))
    r = np.random.default_rng(seed)
    for f0 in notes:
        for d in (-0.12, -0.05, 0.0, 0.06, 0.13):
            v = polyblep_saw(f0 * 2 ** (d / 12), dur, r.uniform())
            x += pan(v, d * 6)
    # time-varying low-pass via blocks
    cut = 180 + 1700 * np.exp(-((t - 0.12) ** 2) / 0.08) * (t > 0) + 450 * np.exp(-t / 1.2)
    out = np.zeros_like(x)
    blk = 512
    zi = None
    for i in range(0, len(t), blk):
        fc = float(np.clip(cut[i], 60, 18000))
        sos = signal.butter(2, fc, 'lowpass', fs=SR, output='sos')
        if zi is None:
            zi = np.zeros((sos.shape[0], 2, 2))
        seg, zi = signal.sosfilt(sos, x[i:i + blk], axis=0, zi=zi)
        out[i:i + blk] = seg
    env = (1 - np.exp(-t / 0.03)) * np.exp(-t / 1.6)
    out *= env[:, None]
    out = np.tanh(out * 1.8)
    return out / np.max(np.abs(out))


def riser(dur=2.0, f_from=300, f_to=9000, seed=0):
    """Noise sweep that rises into a hit (built in the STFT domain)."""
    r = np.random.default_rng(seed)
    n = int(dur * SR)
    out = np.zeros((n, 2))
    for c in range(2):
        noise = r.standard_normal(n)
        f, tt, Z = signal.stft(noise, fs=SR, nperseg=2048)
        prog = (tt / dur).clip(0, 1)
        fc = f_from * (f_to / f_from) ** (prog ** 1.6)
        mask = np.exp(-((np.log(f[:, None] + 1) - np.log(fc[None, :])) ** 2) / (2 * 0.35 ** 2))
        _, y = signal.istft(Z * mask, fs=SR, nperseg=2048)
        out[:, c] = y[:n]
    t = t_axis(dur)
    tone_f = 110 * 2 ** (2 * (t / dur) ** 1.5)
    tone = np.sin(2 * np.pi * np.cumsum(tone_f) / SR) * 0.25
    env = (t / dur) ** 2.2
    out = out / np.max(np.abs(out)) + tone[:, None]
    return out * env[:, None]


def reverse_cymbal(dur=1.5, seed=0):
    r = np.random.default_rng(seed)
    n = int(dur * SR)
    x = sos_filter(r.standard_normal((n, 2)), 'highpass', 3500)
    t = t_axis(dur)
    x *= ((t / dur) ** 3)[:, None]
    return x / np.max(np.abs(x))


def shimmer(dur=3.0, base=880.0, seed=0):
    """Bright bell cluster for the final VIP sparkle."""
    r = np.random.default_rng(seed)
    t = t_axis(dur)
    x = np.zeros((len(t), 2))
    for k, m in enumerate([1, 1.5, 2, 2.5, 3, 4, 5.04, 6]):
        f = base * m * r.uniform(0.995, 1.005)
        st = r.uniform(0, 0.25)
        e = np.clip((t - st) / 0.004, 0, 1) * np.exp(-np.clip(t - st, 0, None) / r.uniform(0.6, 1.4))
        x += pan(np.sin(2 * np.pi * f * t) * e * (0.5 / (1 + k * 0.3)), r.uniform(-0.8, 0.8))
    return x / np.max(np.abs(x))


def to_stereo(x):
    return np.stack([x, x], 1) if x.ndim == 1 else x
