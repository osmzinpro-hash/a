import json
import subprocess
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy.ndimage import gaussian_filter
S = '/tmp/claude-0/-home-user-a/8f0652ee-1482-53b0-83c8-c0d027028c46/scratchpad'
FF = f'{S}/bin/ffmpeg'
W, H, FPS = 1920, 1080, 30
FD = f'{S}/fonts'
FONT = {
    'cinzel7': f'{FD}/fontsource-cinzel-5.3.0/files/cinzel-latin-700-normal.woff',
    'cinzel9': f'{FD}/fontsource-cinzel-5.3.0/files/cinzel-latin-900-normal.woff',
    'play_i': f'{FD}/fontsource-playfair-display-5.3.0/files/playfair-display-latin-400-italic.woff',
    'mont5': f'{FD}/fontsource-montserrat-5.3.0/files/montserrat-latin-500-normal.woff',
    'mont6': f'{FD}/fontsource-montserrat-5.3.0/files/montserrat-latin-600-normal.woff',
    'mont3': f'{FD}/fontsource-montserrat-5.3.0/files/montserrat-latin-300-normal.woff',
}

# ---- easing

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


