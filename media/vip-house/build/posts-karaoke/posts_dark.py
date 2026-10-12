"""VIP House karaoke posts: black-and-gold version (the house style), same layouts and content."""
import sys
sys.path.insert(0, '/tmp/claude-0/-home-user-a/8f0652ee-1482-53b0-83c8-c0d027028c46/scratchpad')
from PIL import Image, ImageDraw, ImageOps, ImageEnhance, ImageFilter
import posts_lib as L
from posts_lib import W, H, M, ANTON, OSW5, OSW6, PHONE, font, fit, icon

BG = (14, 13, 11)
CARD = (26, 23, 18)
GOLD = (212, 166, 74)
GOLD_HI = (243, 220, 140)
WHITE = (255, 255, 255)
INK = (14, 13, 11)
STOPS = [(0.0, (156, 116, 36)), (0.38, (246, 226, 122)), (0.55, (255, 244, 196)), (0.7, (212, 166, 74)), (1.0, (150, 108, 34))]


def gradient(w, h):
    g = Image.new('RGB', (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        for (a, ca), (b, cb) in zip(STOPS, STOPS[1:]):
            if a <= t <= b:
                k = (t - a) / (b - a)
                g.putpixel((0, y), tuple(int(ca[i] + (cb[i] - ca[i]) * k) for i in range(3)))
                break
    return g.resize((w, h))


def gold_text(img, xy, s, f, anchor='ls'):
    """Text filled with the gold gradient of the house flyers."""
    x0, y0, x1, y1 = f.getbbox(s, anchor=anchor)
    pad = 4
    w, h = int(x1 - x0) + 2 * pad, int(y1 - y0) + 2 * pad
    mask = Image.new('L', (w, h), 0)
    ImageDraw.Draw(mask).text((pad - x0, pad - y0), s, font=f, fill=255, anchor=anchor)
    px, py = int(xy[0] + x0 - pad), int(xy[1] + y0 - pad)
    shadow = mask.filter(ImageFilter.GaussianBlur(6))
    img.paste((0, 0, 0), (px + 3, py + 5), shadow.point(lambda v: v * 0.7))
    img.paste(gradient(w, h), (px, py), mask)


def stack(img, x, y, lines, gap):
    d = ImageDraw.Draw(img)
    for s, f, fill in lines:
        bx0, top, bx1, bottom = f.getbbox(s, anchor='ls')
        base = y - top
        if fill == 'GOLD':
            gold_text(img, (x, base), s, f, 'ls')
        else:
            d.text((x, base), s, font=f, fill=fill, anchor='ls')
        y = base + bottom + gap
    return y


def gtext(img, xy, s, f, anchor):
    gold_text(img, xy, s, f, anchor)


def canvas():
    """Near-black stage with a warm spotlight glow from the top."""
    img = Image.new('RGB', (W, H), BG)
    glow = Image.new('L', (W, H), 0)
    ImageDraw.Draw(glow).ellipse((-200, -520, W + 200, 620), fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(180)).point(lambda v: int(v * 0.22))
    img.paste((120, 86, 30), (0, 0), glow)
    return img


def photo(name, box_w, box_h, focus=(0.5, 0.5), zoom=1.0):
    """Real photo in colour, warm and slightly punchier, to match the house's night photos."""
    im = Image.open(f'{L.FOTOS}/{name}').convert('RGB')
    target = box_w / box_h
    cw = min(im.width, im.height * target) / zoom
    ch = cw / target
    cx, cy = focus[0] * im.width, focus[1] * im.height
    x0 = min(max(cx - cw / 2, 0), im.width - cw)
    y0 = min(max(cy - ch / 2, 0), im.height - ch)
    im = im.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((box_w, box_h), Image.LANCZOS)
    im = ImageOps.autocontrast(im, cutoff=0.5)
    im = ImageEnhance.Color(im).enhance(1.12)
    r, g, b = im.split()
    im = Image.merge('RGB', (r.point(lambda v: min(255, int(v * 1.04 + 4))), g, b.point(lambda v: int(v * 0.93))))
    return im.filter(ImageFilter.UnsharpMask(radius=2, percent=50, threshold=2))


def paste_photo(img, ph, x, y, bw=5):
    d = ImageDraw.Draw(img)
    d.rectangle((x - bw, y - bw, x + ph.width + bw - 1, y + ph.height + bw - 1), fill=GOLD)
    img.paste(ph, (x, y))


def ticket(img, y, line1='QUINTA-FEIRA', line2='A PARTIR DAS 20H30'):
    d = ImageDraw.Draw(img)
    x0, x1, h = M, W - M, 214
    d.rounded_rectangle((x0, y, x1, y + h), radius=22, fill=CARD, outline=GOLD, width=3)
    sx, r = x0 + 600, 22
    for cy in (y, y + h):
        d.ellipse((sx - r, cy - r, sx + r, cy + r), fill=BG, outline=GOLD, width=3)
        d.rectangle((sx - r - 2, cy - r - 4 if cy == y else cy, sx + r + 2, cy if cy == y else cy + r + 4), fill=BG)
    for yy in range(y + 30, y + h - 24, 22):
        d.line((sx, yy, sx, yy + 11), fill=GOLD, width=4)
    icon(d, (x0 + 36, y + 66), 'calendar', 40, GOLD)
    gtext(img, (x0 + 96, y + 66), line1, font(ANTON, 64), 'lm')
    icon(d, (x0 + 36, y + 148), 'clock', 36, GOLD)
    d.text((x0 + 96, y + 148), line2, font=font(OSW6, 40), fill=WHITE, anchor='lm')
    cx = (sx + x1) / 2
    icon(d, (cx, y + 58), 'trophy', 44, GOLD, 'mm')
    gtext(img, (cx, y + 112), 'PREMIAÇÃO', font(ANTON, 46), 'mm')
    icon(d, (sx + 34, y + 168), 'whatsapp', 32, GOLD, 'lm')
    d.text((sx + 74, y + 168), PHONE, font=font(OSW6, 34), fill=WHITE, anchor='lm')


def header(img):
    d = ImageDraw.Draw(img)
    gtext(img, (M, 74), 'VIP HOUSE', font(ANTON, 48), 'lm')
    L.text(d, (W - M, 74), 'PRAÇA SÃO BENEDITO • SÃO MATEUS', font(OSW5, 28), WHITE, 'rm', tracking=2)
    d.line((M, 112, W - M, 112), fill=GOLD, width=2)


def save(img, name):
    img.save(f'{L.OUT}/{name}.jpg', quality=94, subsampling=0)
    print('saved', name)


# 1 ------------------------------------------------------------------ quinta é dia de soltar a voz
img = canvas(); d = ImageDraw.Draw(img); header(img)
big = fit('SOLTAR', ANTON, W - 2 * M, 212)
y = stack(img, M - 4, 150, [('QUINTA É DIA DE', fit('QUINTA É DIA DE', ANTON, 640, 100), WHITE),
                            ('SOLTAR', big, 'GOLD'), ('A VOZ', big, 'GOLD')], 22)
ph_h = 1044 - (y + 18)
paste_photo(img, photo('karaoke_0.9.jpg', 430, ph_h, focus=(0.30, 0.42), zoom=1.15), M + 6, y + 18)
tx, ty = M + 6 + 430 + 40, y + 18
stack(img, tx, ty, [('Karaokê ao vivo,', font(OSW5, 40), WHITE), ('palco aberto e', font(OSW5, 40), WHITE),
                    ('premiação pra quem', font(OSW5, 40), WHITE), ('mandar bem.', font(OSW5, 40), WHITE)], 14)
icon(d, (tx, ty + ph_h - 22), 'mic', 38, GOLD, 'lm')
gtext(img, (tx + 40, ty + ph_h - 22), 'INSCRIÇÕES NO WHATS', font(ANTON, 42), 'lm')
ticket(img, 1080)
save(img, 'post1-quinta-e-dia-de-soltar-a-voz')

# 2 ------------------------------------------------------------------ sobe no palco, sai com prêmio
img = canvas(); d = ImageDraw.Draw(img); header(img)
f1 = fit('SAI COM PRÊMIO.', ANTON, W - 2 * M, 200)
y = stack(img, M - 4, 140, [('SOBE NO PALCO.', f1, 'GOLD'), ('SAI COM PRÊMIO.', f1, WHITE)], 18)
paste_photo(img, photo('karaoke_2.2.jpg', W - 2 * M, 330, focus=(0.58, 0.78), zoom=1.39), M, y + 26)
pw, gap, base = 300, 26, 1046
heights = {1: 176, 2: 148, 3: 124}
for place, x in [(2, M), (1, M + pw + gap), (3, M + 2 * (pw + gap))]:
    h = heights[place]
    d.rounded_rectangle((x, base - h, x + pw, base), radius=14, fill=CARD, outline=GOLD, width=3)
    icon(d, (x + pw / 2, base - h + 36), 'trophy', 40 if place == 1 else 34, GOLD, 'mm')
    gtext(img, (x + pw / 2, base - h + 90), f'{place}º LUGAR', font(ANTON, 50), 'mm')
ticket(img, 1080)
save(img, 'post2-sobe-no-palco-sai-com-premio')

# 3 ------------------------------------------------------------------ qual música você vai cantar?
img = canvas(); d = ImageDraw.Draw(img); header(img)
f = fit('QUAL MÚSICA', ANTON, W - 2 * M, 160)
y = stack(img, M - 4, 146, [('QUAL MÚSICA', f, 'GOLD'), ('VOCÊ VAI', f, WHITE), ('CANTAR?', f, 'GOLD')], 16)
top = y + 22
paste_photo(img, photo('karaoke_5.6.jpg', 560, 1030 - top, focus=(0.30, 0.55), zoom=1.2), M + 6, top)
bx0, by0, bx1, by1 = M + 600, top, W - M, 1030
d.rounded_rectangle((bx0, by0, bx1, by1), radius=24, fill=GOLD)
d.polygon([(bx0 + 40, by1 - 2), (bx0 + 90, by1 - 2), (bx0 + 30, by1 + 40)], fill=GOLD)
icon(d, (bx0 + 30, by0 + 52), 'comment', 40, INK, 'lm')
d.text((bx0 + 84, by0 + 52), 'COMENTA', font=font(ANTON, 50), fill=INK, anchor='lm')
stack(img, bx0 + 30, by0 + 96, [('a sua música', font(OSW5, 36), INK), ('aqui embaixo.', font(OSW5, 36), INK),
                                ('A mais pedida', font(OSW6, 36), INK), ('abre a noite!', font(OSW6, 36), INK)], 12)
ticket(img, 1080)
save(img, 'post3-qual-musica-voce-vai-cantar')

# 4 ------------------------------------------------------------------ no banho todo mundo é cantor
img = canvas(); d = ImageDraw.Draw(img); header(img)
y = stack(img, M - 4, 140, [('NO BANHO,', fit('NO BANHO,', ANTON, 640, 190), WHITE),
                            ('TODO MUNDO É CANTOR.', fit('TODO MUNDO É CANTOR.', ANTON, W - 2 * M, 150), 'GOLD')], 18)
paste_photo(img, photo('karaoke_7.4.jpg', W - 2 * M, 420, focus=(0.55, 0.45), zoom=1.35), M, y + 30)
fq = font(ANTON, 58)
d.text((M, 1010), 'NA QUINTA, TODO MUNDO É', font=fq, fill=WHITE, anchor='ls')
gtext(img, (M + fq.getlength('NA QUINTA, TODO MUNDO É '), 1010), 'VIP.', fq, 'ls')
ticket(img, 1080)
save(img, 'post4-no-banho-todo-mundo-e-cantor')

# 5 ------------------------------------------------------------------ é hoje
img = canvas(); d = ImageDraw.Draw(img); header(img)
fh = fit('É HOJE.', ANTON, W - 2 * M, 460)
stack(img, M - 8, 150, [('É HOJE.', fh, 'GOLD')], 0)
paste_photo(img, photo('karaoke_13.3.jpg', 470, 430, focus=(0.47, 0.42), zoom=1.3), M + 6, 590)
tx = M + 6 + 470 + 40
stack(img, tx, 600, [('KARAOKÊ', font(ANTON, 92), 'GOLD'), ('NA VIP HOUSE', font(ANTON, 56), WHITE)], 16)
stack(img, tx, 790, [('Chega cedo,', font(OSW5, 38), WHITE), ('garante sua mesa', font(OSW5, 38), WHITE),
                     ('e escolhe a música.', font(OSW5, 38), WHITE)], 14)
ticket(img, 1080, line1='HOJE')
save(img, 'post5-e-hoje')
