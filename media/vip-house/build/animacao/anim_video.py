"""Animated karaoke poster: the Higgsfield animation plus gold titles,
drifting sparkles, a held end frame and the VIP hit."""
import json
import subprocess
import sys
import numpy as np
from PIL import Image
import titles as T
from titles import make_elem, blit, fade, ease_out, ease_in_out, clamp01

S = T.S
FF = T.FF
W, H, FPS = 1080, 1920, 30
T.W, T.H = W, H
OUT = sys.argv[1] if len(sys.argv) > 1 else f'{S}/anim/out.mp4'
PREVIEW = sys.argv[2:]
TL = json.load(open(f'{S}/anim/timeline.json'))
ANIM, VA, VB, HIT, TOTAL = TL['anim_len'], TL['voice_a_at'], TL['voice_b_at'], TL['final_hit'], TL['total']
NF = int(round(TOTAL * FPS))
CLIP = '/home/user/a/media/raw/vip-house/animacao/animacao-kling.mp4'

raw = subprocess.run([FF, '-v', 'error', '-i', CLIP, '-an', '-vf',
                      f'fps={FPS},scale={W}:{H}:flags=lanczos,eq=contrast=1.03:saturation=1.05,format=rgb24',
                      '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
frames = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
print('animation frames', len(frames))

E = {
    'o_karaoke': make_elem('O KARAOKÊ', 'cinzel9', 124, 6, 'gold', glow=0.65),
    'ja_vai': make_elem('JÁ VAI COMEÇAR!', 'mont6', 70, 6, 'white', glow=0.25),
    'hoje': make_elem('HOJE  •  20H30', 'mont6', 54, 10, 'gold', glow=0.3),
    'vem': make_elem('VEM PRA VIP HOUSE', 'cinzel9', 72, 4, 'gold', glow=0.6),
    'que': make_elem('que aqui você é VIP', 'play_i', 76, 1, 'white', glow=0.2),
}
yy = np.arange(H, dtype=np.float32)[:, None, None]
grad_top = np.clip((620 - yy) / 620, 0, 1) ** 1.4 * 0.6
grad_bot = np.clip((yy - 1380) / (1920 - 1380), 0, 1) ** 1.2 * 0.75

# gold sparkles that keep drifting up, also over the held end frame
rng = np.random.default_rng(9)
NP = 140
px, py = rng.uniform(0, W, NP), rng.uniform(0, H, NP)
sp, sz, ph = rng.uniform(40, 120, NP), rng.uniform(1.2, 3.6, NP), rng.uniform(0, 6.28, NP)
gold = np.array([1.0, 0.82, 0.45], np.float32)
dots = {}


def dot(r):
    k = round(r * 2) / 2
    if k not in dots:
        n = int(k * 4) + 3
        g = np.arange(-n, n + 1, dtype=np.float32)
        d = np.exp(-(g[:, None] ** 2 + g[None, :] ** 2) / (2 * k * k))
        dots[k] = d[:, :, None]
    return dots[k]


def sparkles(f, t, boost=1.0):
    for i in range(NP):
        x = px[i] + 18 * np.sin(t * 1.3 + ph[i])
        y = (py[i] - sp[i] * t) % (H + 40) - 20
        tw = 0.5 + 0.5 * np.sin(t * 5 + ph[i] * 3)
        d = dot(sz[i])
        n = d.shape[0] // 2
        x0, y0 = int(x) - n, int(y) - n
        if x0 < 0 or y0 < 0 or x0 + d.shape[1] > W or y0 + d.shape[0] > H:
            continue
        f[y0:y0 + d.shape[0], x0:x0 + d.shape[1]] += d * gold * (0.35 + 0.65 * tw) * 0.55 * boost


def frame(t, i):
    if t < ANIM:
        f = frames[min(int(t * FPS), len(frames) - 1)].astype(np.float32) / 255
    else:
        # hold the last animated frame and keep pushing in slowly
        k = t - ANIM
        z = 1 + 0.035 * ease_in_out(k / (TOTAL - ANIM))
        cw, ch = W / z, H / z
        im = Image.fromarray(frames[-1]).resize((W, H), Image.BICUBIC,
                                                box=(W / 2 - cw / 2, H * 0.45 - ch * 0.45, W / 2 + cw / 2, H * 0.45 + ch * 0.55))
        f = np.asarray(im, np.float32) / 255
    a_top = fade(t, VA + 0.05, 0.4)
    f *= 1 - grad_top * a_top
    a_bot = fade(t, VB, 0.4)
    f *= 1 - grad_bot * a_bot
    kh = t - HIT
    sparkles(f, t, 1.0 + (2.0 * np.exp(-kh / 0.5) if kh >= 0 else 0))
    blit(f, E['o_karaoke'], W / 2, 165, fade(t, VA + 0.05, 0.4), 1.12 - 0.12 * ease_out((t - VA) / 0.6),
         shine=(t - VA - 0.5) / 0.9)
    blit(f, E['ja_vai'], W / 2, 282 + 12 * (1 - ease_out((t - VA - 1.2) / 0.6)), fade(t, VA + 1.2, 0.4))
    blit(f, E['hoje'], W / 2, 368 + 10 * (1 - ease_out((t - VA - 2.0) / 0.6)), fade(t, VA + 2.0, 0.4),
         shine=(t - VA - 2.4) / 0.8)
    blit(f, E['vem'], W / 2, 1640, fade(t, VB + 0.05, 0.4), 1.08 - 0.08 * ease_out((t - VB) / 0.6),
         shine=(kh + 0.05) / 0.9 if kh > -0.05 else (t - VB - 0.5) / 0.9)
    blit(f, E['que'], W / 2, 1765 + 12 * (1 - ease_out((t - VB - TL['vb_phrase2']) / 0.6)),
         fade(t, VB + TL['vb_phrase2'], 0.45))
    if 0 <= kh < 0.8:
        f = f + 0.85 * np.exp(-kh / 0.1) * (1 - f) * np.array([1.0, 0.95, 0.86], np.float32)
    g = clamp01(t / 0.2) * (1 - ease_in_out((t - (TOTAL - 0.6)) / 0.6))
    return (np.clip(f * g, 0, 1) * 255 + 0.5).astype(np.uint8)


enc = None
if not PREVIEW:
    enc = subprocess.Popen([FF, '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
                            '-i', '-', '-i', f'{S}/anim/mix.wav',
                            '-af', 'volume=1.0dB,alimiter=limit=0.75:attack=2:release=60:level=disabled',
                            '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p',
                            '-c:v', 'libx264', '-preset', 'slow', '-b:v', '9000k', '-maxrate', '12000k', '-bufsize', '18000k',
                            '-profile:v', 'high', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
                            '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', '-t', f'{TOTAL:.3f}', OUT],
                           stdin=subprocess.PIPE)
want = {int(round(float(s) * FPS)) for s in PREVIEW}
for i in range(NF):
    t = i / FPS
    if PREVIEW and i not in want:
        continue
    out = frame(t, i)
    if PREVIEW:
        Image.fromarray(out).save(f'{S}/anim/prev_{t:05.2f}.png')
    else:
        enc.stdin.write(out.tobytes())
if enc:
    enc.stdin.close()
    enc.wait()
print('done')
