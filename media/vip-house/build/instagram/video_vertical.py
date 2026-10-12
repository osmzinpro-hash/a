"""9:16 Reels version of the 25 s VIP House promo: same audio and timing,
each shot reframed to vertical, titles laid out for a phone screen."""
import json
import subprocess
import sys
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter
import titles as T
from titles import make_elem, blit, row, fade, ease_out, ease_in_out, ease_out_back, clamp01, blur

S = T.S
FF = T.FF
W, H, FPS = 1080, 1920, 30
T.W, T.H = W, H
OUT = sys.argv[1] if len(sys.argv) > 1 else f'{S}/reels/out.mp4'
PREVIEW = sys.argv[2:]
SRC = '/root/.claude/uploads/8f0652ee-1482-53b0-83c8-c0d027028c46/ab23c45c-202609282114.mp4'
TL = json.load(open(f'{S}/timeline.json'))
INTRO, VID_END, TOTAL = TL['intro'], TL['vid_end'], TL['total']
VA, VB, HIT = TL['voice_a_at'], TL['voice_b_at'], TL['final_hit']
NF = int(round(TOTAL * FPS))

# crop centre (source x, of 1920) for each shot of the source, by source time
SHOTS = [(0.0, 850, 0, 1080), (1.48, 1330, 0, 1080), (3.05, 760, 0, 1080), (5.27, 520, 0, 1080),
         (6.74, 1000, 68, 1012), (9.57, 1060, 0, 1080), (12.69, 900, 0, 1080)]  # last two: rows without the source's bars


def reframe(src, ts):
    _, cx, y0, y1 = [s for s in SHOTS if ts >= s[0]][-1]
    cw = int(round((y1 - y0) * 9 / 16))
    x0 = int(min(max(cx - cw / 2, 0), 1920 - cw))
    im = Image.fromarray(np.ascontiguousarray(src[y0:y1, x0:x0 + cw]))
    return np.asarray(im.resize((W, H), Image.BICUBIC), np.float32) / 255


E = {
    'vip_house_intro': make_elem('VIP HOUSE', 'cinzel7', 112, 14, 'gold', glow=0.55),
    'apresenta': make_elem('APRESENTA', 'mont3', 32, 16, 'white', glow=0.15),
    'venha_para_o': make_elem('VENHA PARA O', 'mont5', 38, 12, 'white', glow=0.12),
    'karaoke': make_elem('KARAOKÊ', 'cinzel9', 150, 8, 'gold', glow=0.6),
    'da_vip_house': make_elem('DA VIP HOUSE', 'mont6', 40, 14, 'white', glow=0.12),
    'quinta': make_elem('QUINTA-FEIRA', 'mont6', 46, 8, 'white', glow=0.15),
    'dot': make_elem('•', 'mont6', 46, 0, 'gold', glow=0.3),
    'hora': make_elem('20H30', 'cinzel9', 60, 6, 'gold', glow=0.45),
    'cap_top': make_elem('VIP HOUSE', 'cinzel7', 46, 16, 'gold', glow=0.25),
    'cap_k': make_elem('KARAOKÊ', 'cinzel9', 112, 8, 'gold', glow=0.55),
    'cap_info': make_elem('QUINTA-FEIRA  •  20H30', 'mont6', 48, 8, 'white', glow=0.15),
    'venha_para_a': make_elem('Venha para a', 'play_i', 80, 1, 'white', glow=0.15),
    'vip_house_end': make_elem('VIP HOUSE', 'cinzel9', 140, 10, 'gold', glow=0.6),
    'que_aqui': make_elem('que aqui você é', 'play_i', 80, 1, 'white', glow=0.15),
    'vip_big': make_elem('VIP', 'cinzel9', 330, 18, 'gold', glow=0.75),
    'info_end': make_elem('KARAOKÊ  •  QUINTA-FEIRA  •  20H30', 'mont6', 34, 6, 'white', glow=0.12),
}

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
dx = xx - W / 2
halfw = 60 + yy * 0.42
cone = np.exp(-2.2 * (dx / halfw) ** 2) * np.clip(yy / 80, 0, 1) * (0.35 + 0.65 * yy / H)
pool = np.exp(-2.0 * ((dx / 420) ** 2 + ((yy - 1560) / 90) ** 2))
rng = np.random.default_rng(3)
haze = np.asarray(Image.fromarray(rng.random((H // 24 + 2, W // 24 + 2)).astype(np.float32), 'F')
                  .resize((W + 48, H + 48), Image.BICUBIC))
haze = gaussian_filter(haze, 6)
spot = np.array([1.0, 0.92, 0.78], np.float32)
dust = rng.random((110, 4)).astype(np.float32)
grain = [np.asarray(Image.fromarray(rng.standard_normal((H // 2, W // 2)).astype(np.float32), 'F')
                    .resize((W, H), Image.BILINEAR))[:, :, None] * (3.2 / 255) for _ in range(6)]
g3 = yy[:, :1, None]
grad_bot = np.clip((g3 - 1000) / (1760 - 1000), 0, 1) ** 1.3 * 0.68
grad_top = np.clip((520 - g3) / 520, 0, 1) ** 1.5 * 0.55
vign = (1 - 0.35 * np.clip(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H / 2) / (H * 0.62)) ** 2, 0, 1))[:, :, None]


def intro_frame(t):
    f = np.zeros((H, W, 3), np.float32)
    lvl = 0.12 + 0.5 * ease_in_out(t / 3.2)
    flick = 1 + 0.03 * np.sin(t * 23) * np.sin(t * 7.3)
    ox, oy = int(t * 14) % 48, int(t * 5) % 48
    hz = haze[oy:oy + H, ox:ox + W]
    f += ((cone * (0.55 + 0.6 * hz) * lvl * flick + pool * 0.32 * lvl)[:, :, None] * spot) * 0.62
    for x, y, sp, sz in dust:
        px, py = W / 2 + (x - 0.5) * 700, (y * H - t * (8 + sp * 20)) % H
        c = np.exp(-2.2 * ((px - W / 2) / (60 + py * 0.42)) ** 2)
        if c < 0.08:
            continue
        r = 1 + int(sz * 2)
        yi, xi = int(py), int(px)
        f[max(0, yi - r):yi + r + 1, max(0, xi - r):xi + r + 1] += 0.25 * c * lvl * (0.5 + sz)
    blit(f, E['vip_house_intro'], W / 2, 880, fade(t, 1.15, 0.9), 1.08 - 0.08 * ease_out((t - 1.15) / 1.6),
         shine=(t - 2.05) / 0.9)
    blit(f, E['apresenta'], W / 2, 975, fade(t, 2.15, 0.6))
    return f


def video_frame(t, src):
    f = reframe(src, t - INTRO) * vign
    block_out = 10.75
    block = fade(t, VA + 0.05, 0.5, block_out, 0.45)
    if block > 0:
        f *= 1 - grad_bot * block
    rise = lambda t0: 14 * (1 - ease_out((t - t0) / 0.7))
    blit(f, E['venha_para_o'], W / 2, 1285 + rise(VA + 0.05), fade(t, VA + 0.05, 0.5, block_out, 0.45))
    blit(f, E['karaoke'], W / 2, 1385, fade(t, VA + 0.35, 0.4, block_out, 0.45),
         1.12 - 0.12 * ease_out((t - (VA + 0.35)) / 0.6), shine=(t - (VA + 0.9)) / 0.9)
    blit(f, E['da_vip_house'], W / 2, 1485 + rise(VA + 1.25), fade(t, VA + 1.25, 0.5, block_out, 0.45))
    tq, th = VA + 2.8, VA + 3.98
    row(f, [(E['quinta'], fade(t, tq, 0.4, block_out, 0.45), None),
            (E['dot'], fade(t, th - 0.1, 0.4, block_out, 0.45), None),
            (E['hora'], fade(t, th, 0.4, block_out, 0.45), (t - th - 0.3) / 0.8)], 1585, 24)
    cap = fade(t, 11.3, 0.6, VID_END - 0.35, 0.3)
    if cap > 0:
        f *= 1 - grad_bot * cap
        f *= 1 - grad_top * cap
        blit(f, E['cap_top'], W / 2, 200, cap)
        blit(f, E['cap_k'], W / 2, 1560, cap, 1.06 - 0.06 * ease_out((t - 11.3) / 0.6), shine=(t - 11.8) / 0.9)
        blit(f, E['cap_info'], W / 2, 1670, fade(t, 11.55, 0.5, VID_END - 0.35, 0.3))
    k = t - INTRO
    if k < 0.6:
        f = f + 0.85 * np.exp(-k / 0.09) * (1 - f) * np.array([1.0, 0.96, 0.88], np.float32)
    return f


def outro_frame(t, sharp, soft):
    k = t - VID_END
    bl = ease_in_out(k / 0.8)
    base = sharp * (1 - bl) + soft * bl
    z = 1 + 0.07 * ease_in_out(k / (TOTAL - VID_END))
    cw, ch = W / z, H / z
    cy = min(max(H * 0.45, ch / 2), H - ch / 2)
    im = Image.fromarray((base * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR,
                                                               box=(W / 2 - cw / 2, cy - ch / 2, W / 2 + cw / 2, cy + ch / 2))
    f = np.asarray(im, np.float32) / 255 * (1 - 0.58 * ease_in_out(k / 0.8)) * vign
    fl = 0.55 * np.exp(-k / 0.1) if k < 0.7 else 0
    kh = t - HIT
    if 0 <= kh < 0.8:
        fl = max(fl, 0.95 * np.exp(-kh / 0.12))
    out1 = VB + TL['vb_phrase2'] - 0.3
    blit(f, E['venha_para_a'], W / 2, 770 + 14 * (1 - ease_out((t - VB) / 0.7)), fade(t, VB, 0.5, out1, 0.3))
    blit(f, E['vip_house_end'], W / 2, 900, fade(t, VB + 0.55, 0.45, out1, 0.3),
         1.1 - 0.1 * ease_out((t - VB - 0.55) / 0.7), shine=(t - VB - 1.0) / 1.0)
    tq = VB + TL['vb_phrase2']
    blit(f, E['que_aqui'], W / 2, 700 + 14 * (1 - ease_out((t - tq) / 0.7)), fade(t, tq, 0.5))
    if kh >= -0.02:
        blit(f, E['vip_big'], W / 2, 930, clamp01(kh / 0.06), 1.35 - 0.35 * ease_out_back(kh / 0.4),
             shine=(kh - 0.35) / 1.0)
        blit(f, E['info_end'], W / 2, 1165 + 14 * (1 - ease_out((kh - 0.7) / 0.7)), fade(kh, 0.7, 0.6))
    if fl > 0.004:
        f = f + fl * (1 - f) * np.array([1.0, 0.95, 0.85], np.float32)
    return f


grade = ("scale=in_color_matrix=bt709:in_range=tv,fps=30,"
         "curves=master='0/0.03 0.25/0.22 0.5/0.5 0.75/0.79 1/0.97',"
         "colorbalance=rs=-0.02:bs=0.035:rh=0.035:bh=-0.03,eq=saturation=1.06:contrast=1.03,format=rgb24")
dec = subprocess.Popen([FF, '-v', 'error', '-i', SRC, '-an', '-vf', grade, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                       stdout=subprocess.PIPE, bufsize=10 ** 8)
FB = 1920 * 1080 * 3


def read_src():
    b = dec.stdout.read(FB)
    return None if len(b) < FB else np.frombuffer(b, np.uint8).reshape(1080, 1920, 3)


enc = None
if not PREVIEW:
    enc = subprocess.Popen([FF, '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
                            '-i', '-', '-i', f'{S}/mix.wav',
                            '-af', 'volume=3.0dB,alimiter=limit=0.72:attack=2:release=60:level=disabled',
                            '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p',
                            '-c:v', 'libx264', '-preset', 'slow', '-b:v', '9000k', '-maxrate', '12000k', '-bufsize', '18000k',
                            '-profile:v', 'high', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
                            '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', '-t', f'{TOTAL:.3f}', OUT],
                           stdin=subprocess.PIPE)
want = {int(round(float(s) * FPS)) for s in PREVIEW}
last = sharp = soft = None
for i in range(NF):
    t = i / FPS
    if t < INTRO:
        f = intro_frame(t)
    elif t < VID_END:
        src = read_src()
        last = src if src is not None else last
        f = video_frame(t, last)
    else:
        if sharp is None:
            nxt = read_src()
            while nxt is not None:
                last, nxt = nxt, read_src()
            sharp = reframe(last, 13.0)
            soft = np.asarray(blur(Image.fromarray((sharp * 255).astype(np.uint8)).resize((W // 2, H // 2)), 7)
                              .resize((W, H), Image.BILINEAR), np.float32) / 255
        f = outro_frame(t, sharp, soft)
    f = f + grain[i % len(grain)]
    f *= clamp01(t / 0.4) * (1 - ease_in_out((t - (TOTAL - 1.2)) / 1.2))
    out = (np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8)
    if PREVIEW:
        if i in want:
            Image.fromarray(out).save(f'{S}/reels/prev_{t:05.2f}.png')
        if i > max(want):
            break
    else:
        enc.stdin.write(out.tobytes())
dec.stdout.close()
dec.wait()
if enc:
    enc.stdin.close()
    enc.wait()
print('done')
