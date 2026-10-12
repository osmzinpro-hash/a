"""VIP House: five new feed posts (4:5) for the Thursday karaoke.

Direction: "palco amarelo" poster. Black ink type as image on the VIP yellow stage,
real karaoke photos in black and white, posts alternating yellow / black, and a
"VIP ticket" strip that always carries the real info (quinta, 20h30, praça, inscrições).
"""
import sys
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

S = '/tmp/claude-0/-home-user-a/8f0652ee-1482-53b0-83c8-c0d027028c46/scratchpad'
F = f'{S}/fonts2'
OUT = f'{S}/posts_preto'
FOTOS = f'{S}/posts/fotos'
W, H, M = 1080, 1350, 64

YEL, INK, PAPER, WHITE = (245, 197, 24), (17, 17, 17), (255, 244, 214), (255, 255, 255)
ANTON = f'{F}/fontsource-anton-5.3.0/files/anton-latin-400-normal.woff'
OSW6 = f'{F}/fontsource-oswald-5.3.0/files/oswald-latin-600-normal.woff'
OSW5 = f'{F}/fontsource-oswald-5.3.0/files/oswald-latin-500-normal.woff'
FA = f'{F}/fa-solid-900.ttf'
FAB = f'{F}/fa-brands-400.ttf'
ICON = {'calendar': 0xf133, 'clock': 0xf017, 'pin': 0xf3c5, 'trophy': 0xf091, 'mic': 0xf130,
        'comment': 0xf075, 'crown': 0xf521, 'star': 0xf005}
BRAND = {'whatsapp': 0xf232}
PHONE = '(27) 99696-3321'


def font(path, size):
    return ImageFont.truetype(path, size)


def fit(text, path, max_w, start=400, min_size=20):
    size = start
    while size > min_size:
        f = font(path, size)
        if f.getlength(text) <= max_w:
            return f
        size -= 2
    return font(path, min_size)


def text(d, xy, s, f, fill, anchor='la', tracking=0):
    if not tracking:
        d.text(xy, s, font=f, fill=fill, anchor=anchor)
        return f.getlength(s)
    # manual tracking
    total = sum(f.getlength(c) for c in s) + tracking * (len(s) - 1)
    x, y = xy
    if anchor[0] == 'm':
        x -= total / 2
    elif anchor[0] == 'r':
        x -= total
    for c in s:
        d.text((x, y), c, font=f, fill=fill, anchor='l' + anchor[1])
        x += f.getlength(c) + tracking
    return total



def stack(d, x, y, lines, gap):
    """Draw lines top-down using each line's ink box, so accents never touch the line above."""
    for s, f, fill in lines:
        x0, top, x1, bottom = f.getbbox(s, anchor='ls')
        base = y - top
        d.text((x, base), s, font=f, fill=fill, anchor='ls')
        y = base + bottom + gap
    return y


def icon(d, xy, name, size, fill, anchor='lm'):
    cp, path = (ICON[name], FA) if name in ICON else (BRAND[name], FAB)
    d.text(xy, chr(cp), font=font(path, size), fill=fill, anchor=anchor)


def photo(name, box_w, box_h, focus=(0.5, 0.5), zoom=1.0):
    """Black-and-white documentary treatment, cropped to the box around a focus point."""
    im = Image.open(f'{FOTOS}/{name}').convert('RGB')
    target = box_w / box_h
    cw = min(im.width, im.height * target) / zoom
    ch = cw / target
    cx, cy = focus[0] * im.width, focus[1] * im.height
    x0 = min(max(cx - cw / 2, 0), im.width - cw)
    y0 = min(max(cy - ch / 2, 0), im.height - ch)
    im = im.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((box_w, box_h), Image.LANCZOS)
    g = ImageOps.autocontrast(im.convert('L'), cutoff=1)
    g = ImageOps.colorize(g, black=(14, 13, 11), white=(250, 246, 236), mid=(128, 124, 116))
    return g.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))


def paste_photo(img, ph, x, y, border=INK, bw=8):
    d = ImageDraw.Draw(img)
    d.rectangle((x - bw, y - bw, x + ph.width + bw - 1, y + ph.height + bw - 1), fill=border)
    img.paste(ph, (x, y))


def ticket(img, y, dark, line1='QUINTA-FEIRA', line2='A PARTIR DAS 20H30'):
    """The VIP ticket: real info + perforated stub with prize and sign-up."""
    d = ImageDraw.Draw(img)
    bg = INK if dark else YEL
    fg = YEL if dark else INK
    sub = WHITE if dark else INK
    stage = YEL if dark else INK  # colour of the poster behind the ticket
    x0, x1, h = M, W - M, 214
    d.rounded_rectangle((x0, y, x1, y + h), radius=22, fill=bg)
    sx = x0 + 600  # perforation
    r = 22
    for cy in (y, y + h):
        d.ellipse((sx - r, cy - r, sx + r, cy + r), fill=stage)
    for yy in range(y + 30, y + h - 24, 22):
        d.line((sx, yy, sx, yy + 11), fill=fg, width=4)
    # left: day and time, with icons
    icon(d, (x0 + 36, y + 66), 'calendar', 40, fg)
    text(d, (x0 + 96, y + 66), line1, font(ANTON, 64), fg, 'lm')
    icon(d, (x0 + 36, y + 148), 'clock', 36, fg)
    text(d, (x0 + 96, y + 148), line2, font(OSW6, 40), sub, 'lm')
    # stub: prize + sign-up
    cx = (sx + x1) / 2
    icon(d, (cx, y + 58), 'trophy', 44, fg, 'mm')
    text(d, (cx, y + 112), 'PREMIAÇÃO', font(ANTON, 44), fg, 'mm', tracking=2)
    icon(d, (sx + 34, y + 168), 'whatsapp', 32, fg, 'lm')
    text(d, (sx + 74, y + 168), PHONE, font(OSW6, 34), sub, 'lm')


def header(img, dark):
    d = ImageDraw.Draw(img)
    fg = YEL if dark else INK
    text(d, (M, 74), 'VIP HOUSE', font(ANTON, 46), fg, 'lm', tracking=3)
    text(d, (W - M, 74), 'PRAÇA SÃO BENEDITO • SÃO MATEUS', font(OSW5, 28), WHITE if dark else INK, 'rm', tracking=2)
    d.line((M, 112, W - M, 112), fill=fg, width=3)


def canvas(dark):
    return Image.new('RGB', (W, H), INK if dark else YEL)


def save(img, name):
    img.save(f'{OUT}/{name}.jpg', quality=94, subsampling=0)
    print('saved', name)


