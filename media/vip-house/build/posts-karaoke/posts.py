"""VIP House: five new feed posts (4:5) for the Thursday karaoke.

Direction: "palco amarelo" poster. Black ink type as image on the VIP yellow stage,
real karaoke photos in black and white, posts alternating yellow / black, and a
"VIP ticket" strip that always carries the real info (quinta, 20h30, praça, inscrições).
"""
import sys
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

S = '/tmp/claude-0/-home-user-a/8f0652ee-1482-53b0-83c8-c0d027028c46/scratchpad'
F = f'{S}/fonts2'
OUT = f'{S}/posts'
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


# ---------------------------------------------------------------- 1. chamada (amarelo)
img = canvas(False)
d = ImageDraw.Draw(img)
header(img, False)
big = fit('SOLTAR', ANTON, W - 2 * M, 212)
y = stack(d, M - 4, 150, [('QUINTA É DIA DE', fit('QUINTA É DIA DE', ANTON, 640, 100), INK),
                          ('SOLTAR', big, INK), ('A VOZ', big, INK)], 22)
ph_h = 1044 - (y + 18)
ph = photo('karaoke_0.9.jpg', 430, ph_h, focus=(0.30, 0.42), zoom=1.15)
paste_photo(img, ph, M + 8, y + 18)
tx, ty = M + 8 + 430 + 40, y + 18
stack(d, tx, ty, [('Karaokê ao vivo,', font(OSW5, 40), INK), ('palco aberto e', font(OSW5, 40), INK),
                  ('premiação pra quem', font(OSW5, 40), INK), ('mandar bem.', font(OSW5, 40), INK)], 14)
icon(d, (tx, ty + ph_h - 22), 'mic', 38, INK, 'lm')
text(d, (tx + 40, ty + ph_h - 22), 'INSCRIÇÕES NO WHATS', font(ANTON, 42), INK, 'lm')
ticket(img, 1080, dark=True)
save(img, 'post1-quinta-e-dia-de-soltar-a-voz')

# ---------------------------------------------------------------- 2. premiação (preto)
img = canvas(True)
d = ImageDraw.Draw(img)
header(img, True)
f1 = fit('SAI COM PRÊMIO.', ANTON, W - 2 * M, 200)
y = stack(d, M - 4, 140, [('SOBE NO PALCO.', f1, YEL), ('SAI COM PRÊMIO.', f1, WHITE)], 18)
ph = photo('karaoke_2.2.jpg', W - 2 * M, 330, focus=(0.58, 0.78), zoom=1.39)
paste_photo(img, ph, M, y + 26, border=YEL, bw=6)
# podium: three places, no invented values; trophies inside the blocks
pw, gap = 300, 26
heights = {1: 176, 2: 148, 3: 124}
order = [(2, M), (1, M + pw + gap), (3, M + 2 * (pw + gap))]
base = 1046
for place, x in order:
    h = heights[place]
    d.rounded_rectangle((x, base - h, x + pw, base), radius=14, fill=YEL)
    icon(d, (x + pw / 2, base - h + 36), 'trophy', 40 if place == 1 else 34, INK, 'mm')
    text(d, (x + pw / 2, base - h + 90), f'{place}º LUGAR', font(ANTON, 50), INK, 'mm')
ticket(img, 1080, dark=False)
save(img, 'post2-sobe-no-palco-sai-com-premio')

# ---------------------------------------------------------------- 3. engajamento (amarelo)
img = canvas(False)
d = ImageDraw.Draw(img)
header(img, False)
f = fit('QUAL MÚSICA', ANTON, W - 2 * M, 160)
y = stack(d, M - 4, 146, [('QUAL MÚSICA', f, INK), ('VOCÊ VAI', f, INK), ('CANTAR?', f, INK)], 16)
top = y + 22
ph = photo('karaoke_5.6.jpg', 560, 1030 - top, focus=(0.30, 0.55), zoom=1.2)
paste_photo(img, ph, M + 8, top)
# comment bubble with the mechanic
bx0, by0, bx1, by1 = M + 600, top, W - M, 1030
d.rounded_rectangle((bx0, by0, bx1, by1), radius=24, fill=INK)
d.polygon([(bx0 + 40, by1 - 2), (bx0 + 90, by1 - 2), (bx0 + 30, by1 + 40)], fill=INK)
icon(d, (bx0 + 30, by0 + 52), 'comment', 40, YEL, 'lm')
text(d, (bx0 + 84, by0 + 52), 'COMENTA', font(ANTON, 50), YEL, 'lm')
stack(d, bx0 + 30, by0 + 96, [('a sua música', font(OSW5, 36), WHITE), ('aqui embaixo.', font(OSW5, 36), WHITE),
                              ('A mais pedida', font(OSW5, 36), YEL), ('abre a noite!', font(OSW5, 36), YEL)], 12)
ticket(img, 1080, dark=True)
save(img, 'post3-qual-musica-voce-vai-cantar')

# ---------------------------------------------------------------- 4. humor (preto)
img = canvas(True)
d = ImageDraw.Draw(img)
header(img, True)
text(d, (M - 4, 140), 'NO BANHO,', fit('NO BANHO,', ANTON, 640, 190), WHITE, 'lt')
f = fit('TODO MUNDO É CANTOR.', ANTON, W - 2 * M, 150)
text(d, (M - 4, 330), 'TODO MUNDO É CANTOR.', f, YEL, 'lt')
ph = photo('karaoke_7.4.jpg', W - 2 * M, 420, focus=(0.55, 0.45), zoom=1.35)
paste_photo(img, ph, M, 500, border=YEL, bw=6)
text(d, (M, 975), 'NA QUINTA, TODO MUNDO É', font(ANTON, 58), WHITE, 'lm')
w = font(ANTON, 58).getlength('NA QUINTA, TODO MUNDO É ')
text(d, (M + w, 975), 'VIP.', font(ANTON, 58), YEL, 'lm')
ticket(img, 1080, dark=False)
save(img, 'post4-no-banho-todo-mundo-e-cantor')

# ---------------------------------------------------------------- 5. é hoje (amarelo)
img = canvas(False)
d = ImageDraw.Draw(img)
header(img, False)
fh = fit('É HOJE.', ANTON, W - 2 * M, 460)
text(d, (M - 8, 120), 'É HOJE.', fh, INK, 'lt')
ph = photo('karaoke_13.3.jpg', 470, 430, focus=(0.47, 0.42), zoom=1.3)
paste_photo(img, ph, M, 590)
tx = M + 470 + 40
stack(d, tx, 600, [('KARAOKÊ', font(ANTON, 92), INK), ('NA VIP HOUSE', font(ANTON, 56), INK)], 16)
stack(d, tx, 790, [('Chega cedo,', font(OSW5, 38), INK), ('garante sua mesa', font(OSW5, 38), INK),
                   ('e escolhe a música.', font(OSW5, 38), INK)], 14)
ticket(img, 1080, dark=True, line1='HOJE', line2='A PARTIR DAS 20H30')
save(img, 'post5-e-hoje')
