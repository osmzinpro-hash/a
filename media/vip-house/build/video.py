"""Composites the VIP House karaoke promo: spotlight intro, graded footage with
gold titles and letterbox, and a freeze-frame end card. Pipes frames to ffmpeg."""
import json
import subprocess
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy.ndimage import gaussian_filter

S = '/tmp/claude-0/-home-user-a/8f0652ee-1482-53b0-83c8-c0d027028c46/scratchpad'
FF = f'{S}/bin/ffmpeg'
SRC = '/root/.claude/uploads/8f0652ee-1482-53b0-83c8-c0d027028c46/ab23c45c-202609282114.mp4'
OUT = sys.argv[1] if len(sys.argv) > 1 else f'{S}/out.mp4'
PREVIEW = sys.argv[2:]  # optional list of seconds to dump as PNG instead of encoding

TL = json.load(open(f'{S}/timeline.json'))
W, H, FPS = 1920, 1080, 30
BAR = 110
INTRO, VID_END, TOTAL = TL['intro'], TL['vid_end'], TL['total']
VA, VB, HIT = TL['voice_a_at'], TL['voice_b_at'], TL['final_hit']
NFRAMES = int(round(TOTAL * FPS))

FD = f'{S}/fonts'
FONT = {
    'cinzel7': f'{FD}/fontsource-cinzel-5.3.0/files/cinzel-latin-700-normal.woff',
    'cinzel9': f'{FD}/fontsource-cinzel-5.3.0/files/cinzel-latin-900-normal.woff',
    'play_i': f'{FD}/fontsource-playfair-display-5.3.0/files/playfair-display-latin-400-italic.woff',
    'mont5': f'{FD}/fontsource-montserrat-5.3.0/files/montserrat-latin-500-normal.woff',
    'mont6': f'{FD}/fontsource-montserrat-5.3.0/files/montserrat-latin-600-normal.woff',
    'mont3': f'{FD}/fontsource-montserrat-5.3.0/files/montserrat-latin-300-normal.woff',
}


# ------------------------------------------------------------------ easing

def clamp01(x):
    return max(0.0, min(1.0, x))


def ease_out(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = clamp01(x)
    return 3 * x * x - 2 * x * x * x


def ease_out_back(x, s=1.4):
    x = clamp01(x)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def fade(t, t_in, d_in=0.5, t_out=None, d_out=0.4):
    a = ease_out((t - t_in) / d_in)
    if t_out is not None:
        a *= 1 - ease_in_out((t - t_out) / d_out)
    return a


# ------------------------------------------------------------------ text elements

def text_mask(text, font, size, tracking=0.0, pad=60):
    ft = ImageFont.truetype(FONT[font], size)
    widths = [ft.getlength(c) for c in text]
    total = sum(widths) + tracking * (len(text) - 1)
    asc, desc = ft.getmetrics()
    img = Image.new('L', (int(total + 2 * pad), int(asc + desc + 2 * pad)), 0)
    d = ImageDraw.Draw(img)
    x = pad
    for c, w in zip(text, widths):
        d.text((x, pad), c, font=ft, fill=255)
        x += w + tracking
    return img


def blur(img, r):
    return img.filter(ImageFilter.GaussianBlur(r))


def make_elem(text, font, size, tracking=0.0, style='gold', glow=0.5, shadow=0.65):
    m_img = text_mask(text, font, size, tracking)
    m = np.asarray(m_img, np.float32) / 255
    h, w = m.shape
    ys = np.linspace(0, 1, h)[:, None]
    if style == 'gold':
        # find the vertical extent of the glyphs for the gradient
        rows = np.where(m.max(1) > 0.1)[0]
        y0, y1 = rows[0] / h, rows[-1] / h
        g = np.clip((ys - y0) / max(y1 - y0, 1e-3), 0, 1)
        stops = np.array([0.0, 0.3, 0.48, 0.56, 0.78, 1.0])
        cols = np.array([[0.62, 0.45, 0.17], [0.98, 0.87, 0.55], [1.0, 0.97, 0.82],
                         [0.86, 0.66, 0.30], [0.72, 0.52, 0.20], [0.93, 0.78, 0.44]])
        fill = np.stack([np.interp(g[:, 0], stops, cols[:, c]) for c in range(3)], 1)[:, None, :]
        fill = np.broadcast_to(fill, (h, w, 3)).copy()
        # a soft bevel: light from the top edge, darker bottom edge
        hi = np.asarray(blur(m_img, 1.2), np.float32) / 255
        sh = np.roll(hi, -2, 0)
        edge = np.clip(hi - sh, 0, 1)[:, :, None]
        fill = np.clip(fill + edge * 0.35 - np.clip(sh - hi, 0, 1)[:, :, None] * 0.25, 0, 1)
        glow_col = np.array([1.0, 0.74, 0.32])
    else:
        fill = np.ones((h, w, 3), np.float32) * np.array([0.97, 0.95, 0.91])
        glow_col = np.array([1.0, 0.9, 0.75])
    # layers: shadow, glow, text (straight alpha composited into one RGBA)
    sh_a = np.roll(np.asarray(blur(m_img, 7), np.float32) / 255, 5, 0) * shadow
    gl_a = np.asarray(blur(m_img, max(6, size * 0.12)), np.float32) / 255 * glow
    rgb = np.zeros((h, w, 3), np.float32)
    a = np.zeros((h, w), np.float32)
    for col, al in ((np.zeros(3), sh_a), (glow_col, gl_a)):
        rgb = rgb * (1 - al[:, :, None]) + col * al[:, :, None]
        a = a + al * (1 - a)
    rgb = rgb * (1 - m[:, :, None]) + fill * m[:, :, None]
    a = m + a * (1 - m)
    # store premultiplied
    return {'rgb': rgb * a[:, :, None], 'a': a, 'core': m, 'w': w, 'h': h}


_scale_cache = {}


def scaled(elem, s):
    if abs(s - 1) < 1e-3:
        return elem
    key = (id(elem), round(s, 3))
    if key in _scale_cache:
        return _scale_cache[key]
    nw, nh = max(1, int(elem['w'] * s)), max(1, int(elem['h'] * s))
    rgba = np.dstack([elem['rgb'], elem['a'], elem['core']])
    out = []
    for c in range(5):
        im = Image.fromarray(rgba[:, :, c].astype(np.float32), 'F').resize((nw, nh), Image.BICUBIC)
        out.append(np.clip(np.asarray(im), 0, 1))
    e = {'rgb': np.dstack(out[:3]), 'a': out[3], 'core': out[4], 'w': nw, 'h': nh}
    if len(_scale_cache) > 400:
        _scale_cache.clear()
    _scale_cache[key] = e
    return e


def blit(frame, elem, cx, cy, opacity=1.0, scale=1.0, shine=None):
    if opacity <= 0.003:
        return
    e = scaled(elem, scale)
    x0, y0 = int(round(cx - e['w'] / 2)), int(round(cy - e['h'] / 2))
    fx0, fy0 = max(0, x0), max(0, y0)
    fx1, fy1 = min(W, x0 + e['w']), min(H, y0 + e['h'])
    if fx1 <= fx0 or fy1 <= fy0:
        return
    ex0, ey0 = fx0 - x0, fy0 - y0
    ex1, ey1 = ex0 + (fx1 - fx0), ey0 + (fy1 - fy0)
    a = e['a'][ey0:ey1, ex0:ex1, None] * opacity
    rgb = e['rgb'][ey0:ey1, ex0:ex1] * opacity
    region = frame[fy0:fy1, fx0:fx1]
    region *= 1 - a
    region += rgb
    if shine is not None and 0 < shine < 1:
        hh, ww = e['h'], e['w']
        xs = np.arange(ex0, ex1)[None, :]
        ys = np.arange(ey0, ey1)[:, None]
        pos = -0.2 * ww + shine * (1.4 * ww + 0.5 * hh)
        band = np.exp(-(((xs + ys * 0.5) - pos) / (0.07 * ww + 20)) ** 2)
        region += (band * e['core'][ey0:ey1, ex0:ex1] * 0.75 * opacity)[:, :, None] * np.array([1.0, 0.97, 0.85])
        np.clip(region, 0, 1, out=region)


def row(frame, parts, cy, gap):
    """Lay out several elements side by side, centered. parts: (elem, opacity, shine)."""
    widths = [p[0]['w'] - 120 for p in parts]  # remove the 2*pad from each
    total = sum(widths) + gap * (len(parts) - 1)
    x = W / 2 - total / 2
    for (e, op, sh), w in zip(parts, widths):
        blit(frame, e, x + w / 2, cy, op, 1.0, sh)
        x += w + gap


# ------------------------------------------------------------------ assets
print('building titles...', flush=True)
E = {
    'vip_house_intro': make_elem('VIP HOUSE', 'cinzel7', 150, 18, 'gold', glow=0.55),
    'apresenta': make_elem('APRESENTA', 'mont3', 34, 16, 'white', glow=0.15),
    'venha_para_o': make_elem('VENHA PARA O', 'mont5', 36, 12, 'white', glow=0.12),
    'karaoke': make_elem('KARAOKÊ', 'cinzel9', 168, 10, 'gold', glow=0.6),
    'da_vip_house': make_elem('DA VIP HOUSE', 'mont6', 38, 14, 'white', glow=0.12),
    'quinta': make_elem('QUINTA-FEIRA', 'mont6', 46, 8, 'white', glow=0.15),
    'dot': make_elem('•', 'mont6', 46, 0, 'gold', glow=0.3),
    'hora': make_elem('20H30', 'cinzel9', 56, 6, 'gold', glow=0.45),
    'bar_left': make_elem('KARAOKÊ', 'mont6', 28, 10, 'gold', glow=0.0, shadow=0.0),
    'bar_dot': make_elem('•', 'mont6', 28, 0, 'gold', glow=0.0, shadow=0.0),
    'bar_mid': make_elem('QUINTA-FEIRA', 'mont6', 28, 10, 'gold', glow=0.0, shadow=0.0),
    'bar_right': make_elem('20H30', 'mont6', 28, 10, 'gold', glow=0.0, shadow=0.0),
    'bar_top': make_elem('VIP HOUSE', 'cinzel7', 30, 14, 'gold', glow=0.0, shadow=0.0),
    'venha_para_a': make_elem('Venha para a', 'play_i', 78, 1, 'white', glow=0.15),
    'vip_house_end': make_elem('VIP HOUSE', 'cinzel9', 176, 16, 'gold', glow=0.6),
    'que_aqui': make_elem('que aqui você é', 'play_i', 78, 1, 'white', glow=0.15),
    'vip_big': make_elem('VIP', 'cinzel9', 380, 24, 'gold', glow=0.75),
    'info_end': make_elem('KARAOKÊ  •  QUINTA-FEIRA  •  20H30', 'mont6', 38, 8, 'white', glow=0.12),
}

# spotlight for the intro
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
dx = xx - W / 2
halfw = 70 + (yy - BAR) * 0.62
cone = np.exp(-2.2 * (dx / np.maximum(halfw, 1)) ** 2) * np.clip((yy - BAR) / 60, 0, 1)
cone *= 0.35 + 0.65 * (yy / H)
pool = np.exp(-2.0 * ((dx / 560) ** 2 + ((yy - 880) / 95) ** 2))
rng = np.random.default_rng(3)
haze_small = rng.random((H // 24 + 2, W // 24 + 2)).astype(np.float32)
haze = np.asarray(Image.fromarray(haze_small, 'F').resize((W + 48, H + 48), Image.BICUBIC))
haze = gaussian_filter(haze, 6)
spot_col = np.array([1.0, 0.92, 0.78], np.float32)
dust = rng.random((90, 4)).astype(np.float32)  # x, y, speed, size
grain = [(rng.standard_normal((H // 2, W // 2)).astype(np.float32)) for _ in range(6)]
grain = [np.asarray(Image.fromarray(g, 'F').resize((W, H), Image.BILINEAR))[:, :, None] * (3.2 / 255)
         for g in grain]

# bottom gradient for legible titles over footage
grad = np.clip((yy[:, :1] - 520) / (970 - 520), 0, 1) ** 1.4 * 0.62
grad = grad[:, :, None].astype(np.float32)


def intro_frame(t):
    f = np.zeros((H, W, 3), np.float32)
    lvl = 0.12 + 0.5 * ease_in_out(t / 3.2)
    flick = 1 + 0.03 * np.sin(t * 23) * np.sin(t * 7.3)
    ox, oy = int(t * 14) % 48, int(t * 5) % 48
    hz = haze[oy:oy + H, ox:ox + W]
    light = (cone * (0.55 + 0.6 * hz) * lvl * flick + pool * 0.32 * lvl)[:, :, None] * spot_col
    f += light * 0.62
    # dust in the beam
    for x, y, sp, sz in dust:
        px = W / 2 + (x - 0.5) * 900
        py = BAR + ((y * (H - 2 * BAR) - t * (8 + sp * 20)) % (H - 2 * BAR))
        c = np.exp(-2.2 * ((px - W / 2) / (70 + (py - BAR) * 0.62)) ** 2)
        if c < 0.08:
            continue
        r = 1 + int(sz * 2)
        yi, xi = int(py), int(px)
        f[yi - r:yi + r + 1, xi - r:xi + r + 1] += 0.25 * c * lvl * (0.5 + sz)
    # titles
    a1 = fade(t, 1.15, 0.9)
    s1 = 1.08 - 0.08 * ease_out((t - 1.15) / 1.6)
    blit(f, E['vip_house_intro'], W / 2, 520, a1, s1, shine=(t - 2.05) / 0.9)
    blit(f, E['apresenta'], W / 2, 628, fade(t, 2.15, 0.6))
    return f


src_last = None


def video_frame(t, src):
    f = src.astype(np.float32) / 255
    k = t - INTRO
    # title block (P1)
    block_out = 10.75
    block = fade(t, VA + 0.05, 0.5, block_out, 0.45)
    if block > 0:
        f *= 1 - grad * block
    rise = lambda t0: 14 * (1 - ease_out((t - t0) / 0.7))
    blit(f, E['venha_para_o'], W / 2, 640 + rise(VA + 0.05), fade(t, VA + 0.05, 0.5, block_out, 0.45))
    ks = 1.12 - 0.12 * ease_out((t - (VA + 0.35)) / 0.6)
    blit(f, E['karaoke'], W / 2, 738, fade(t, VA + 0.35, 0.4, block_out, 0.45), ks,
         shine=(t - (VA + 0.9)) / 0.9)
    blit(f, E['da_vip_house'], W / 2, 834 + rise(VA + 1.25), fade(t, VA + 1.25, 0.5, block_out, 0.45))
    tq, th = VA + 2.8, VA + 3.98
    row(f, [(E['quinta'], fade(t, tq, 0.4, block_out, 0.45), None),
            (E['dot'], fade(t, th - 0.1, 0.4, block_out, 0.45), None),
            (E['hora'], fade(t, th, 0.4, block_out, 0.45), (t - th - 0.3) / 0.8)], 912, 26)
    # hit flash on the first cut
    fl = 0.85 * np.exp(-max(k, 0) / 0.09) if k < 0.6 else 0
    if fl > 0.004:
        f = f + fl * (1 - f) * np.array([1.0, 0.96, 0.88], np.float32)
    return f


def outro_bases(last):
    a = Image.fromarray(last)
    b = blur(a.resize((W // 2, H // 2), Image.BILINEAR), 7).resize((W, H), Image.BILINEAR)
    return np.asarray(a, np.float32) / 255, np.asarray(b, np.float32) / 255


def outro_frame(t, sharp, soft):
    k = t - VID_END
    bl = ease_in_out(k / 0.8)
    base = sharp * (1 - bl) + soft * bl
    zoom = 1 + 0.07 * ease_in_out(k / (TOTAL - VID_END))
    if zoom > 1.001:
        cw, ch = W / zoom, H / zoom
        cx, cy = W / 2, min(max(H * 0.47, ch / 2), H - ch / 2)
        box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
        im = Image.fromarray((base * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR, box=box)
        base = np.asarray(im, np.float32) / 255
    dark = 1 - 0.58 * ease_in_out(k / 0.8)
    f = base * dark
    # vignette-ish radial darkening
    f *= (1 - 0.35 * np.clip(((xx - W / 2) / (W * 0.6)) ** 2 + ((yy - H / 2) / (H * 0.6)) ** 2, 0, 1))[:, :, None]
    fl = 0.55 * np.exp(-k / 0.1) if k < 0.7 else 0
    kh = t - HIT
    if 0 <= kh < 0.8:
        fl = max(fl, 0.95 * np.exp(-kh / 0.12))
    out_first = VB + TL['vb_phrase2'] - 0.3
    blit(f, E['venha_para_a'], W / 2, 420 + 14 * (1 - ease_out((t - VB) / 0.7)), fade(t, VB, 0.5, out_first, 0.3))
    blit(f, E['vip_house_end'], W / 2, 545, fade(t, VB + 0.55, 0.45, out_first, 0.3),
         1.1 - 0.1 * ease_out((t - VB - 0.55) / 0.7), shine=(t - VB - 1.0) / 1.0)
    # "que aqui você é" waits above the space where the big VIP will land
    tq = VB + TL['vb_phrase2']
    blit(f, E['que_aqui'], W / 2, 330 + 14 * (1 - ease_out((t - tq) / 0.7)), fade(t, tq, 0.5))
    if kh >= -0.02:
        s = 1.35 - 0.35 * ease_out_back(kh / 0.4)
        blit(f, E['vip_big'], W / 2, 560, clamp01(kh / 0.06), s, shine=(kh - 0.35) / 1.0)
        blit(f, E['info_end'], W / 2, 790 + 14 * (1 - ease_out((kh - 0.7) / 0.7)), fade(kh, 0.7, 0.6))
    if fl > 0.004:
        f = f + fl * (1 - f) * np.array([1.0, 0.95, 0.85], np.float32)
    return f


def finish(f, t, i):
    # letterbox and bar captions
    f[:BAR] = 0
    f[H - BAR:] = 0
    cap = fade(t, 11.3, 0.6, VID_END - 0.35, 0.3) if INTRO < t < VID_END else 0
    if cap > 0:
        row(f, [(E['bar_left'], cap, None), (E['bar_dot'], cap, None), (E['bar_mid'], cap, None),
                (E['bar_dot'], cap, None), (E['bar_right'], cap, None)], H - BAR / 2, 22)
        blit(f, E['bar_top'], W / 2, BAR / 2, cap)
    f += grain[i % len(grain)]
    # fade from black at the start, to black at the end
    g = clamp01(t / 0.4) * (1 - ease_in_out((t - (TOTAL - 1.2)) / 1.2))
    f *= g
    return (np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8)


# ------------------------------------------------------------------ run
grade = ("scale=in_color_matrix=bt709:in_range=tv,fps=30,"
         "curves=master='0/0.03 0.25/0.22 0.5/0.5 0.75/0.79 1/0.97',"
         "colorbalance=rs=-0.02:bs=0.035:rh=0.035:bh=-0.03,"
         "eq=saturation=1.06:contrast=1.03,vignette=angle=PI/5,format=rgb24")
dec = subprocess.Popen([FF, '-v', 'error', '-i', SRC, '-an', '-vf', grade, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                       stdout=subprocess.PIPE, bufsize=10 ** 8)
FRAME_BYTES = W * H * 3


def read_src():
    buf = dec.stdout.read(FRAME_BYTES)
    if len(buf) < FRAME_BYTES:
        return None
    return np.frombuffer(buf, np.uint8).reshape(H, W, 3)


enc = None
if not PREVIEW:
    enc = subprocess.Popen([FF, '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
                            '-i', '-', '-i', f'{S}/mix.wav',
                            '-af', 'volume=3.2dB,alimiter=limit=0.8:attack=3:release=60:level=disabled',
                            '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p',
                            '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-profile:v', 'high',
                            '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
                            '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart',
                            '-t', f'{TOTAL:.3f}', OUT], stdin=subprocess.PIPE)

preview_frames = {int(round(float(s) * FPS)) for s in PREVIEW}
sharp = soft = None
last = None
vid_frames = 0
for i in range(NFRAMES):
    t = i / FPS
    if t < INTRO:
        f = intro_frame(t)
    elif t < VID_END:
        src = read_src()
        if src is None:
            src = last
        else:
            last = src
            vid_frames += 1
        f = video_frame(t, src)
    else:
        if sharp is None:
            nxt = read_src()
            while nxt is not None:  # drain any leftover frames
                last = nxt
                nxt = read_src()
            sharp, soft = outro_bases(last)
        f = outro_frame(t, sharp, soft)
    out = finish(f, t, i)
    if PREVIEW:
        if i in preview_frames:
            Image.fromarray(out).save(f'{S}/frames/prev_{t:05.2f}.png')
        if i > max(preview_frames):
            break
    else:
        enc.stdin.write(out.tobytes())
    if i % 60 == 0:
        print(f'frame {i}/{NFRAMES}', flush=True)

dec.stdout.close()
dec.wait()
if enc:
    enc.stdin.close()
    enc.wait()
print('video frames used', vid_frames)
