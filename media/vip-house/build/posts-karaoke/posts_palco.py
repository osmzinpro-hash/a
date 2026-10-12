"""VIP House karaoke posts in the 'o palco é seu' direction: crowned gold microphone art,
gold classic titles, italic taglines and a translucent VIP ticket with the real info."""
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, '/tmp/claude-0/-home-user-a/8f0652ee-1482-53b0-83c8-c0d027028c46/scratchpad')
import titles as T
from titles import make_elem as E, blit

S = T.S
ART = '/home/user/a/media/raw/vip-house/palco'
OUT = f'{S}/posts_palco'
W, H, M = 1080, 1350, 64
T.W, T.H = W, H
GOLD = (214, 172, 88)
FA = f'{S}/fonts2/fa-solid-900.ttf'
FAB = f'{S}/fonts2/fa-brands-400.ttf'
PHONE = '(27) 99696-3321'


def cover(path, focus=(0.5, 0.5), zoom=1.0):
    im = Image.open(path).convert('RGB')
    sc = max(W / im.width, H / im.height) * zoom
    im = im.resize((int(im.width * sc + 0.5), int(im.height * sc + 0.5)), Image.LANCZOS)
    x0 = int(min(max(im.width * focus[0] - W / 2, 0), im.width - W))
    y0 = int(min(max(im.height * focus[1] - H / 2, 0), im.height - H))
    return im.crop((x0, y0, x0 + W, y0 + H))


def shade(im, top_to=520, top_a=0.55, bot_from=880, bot_a=0.75):
    f = np.asarray(im, np.float32) / 255
    y = np.arange(H, dtype=np.float32)[:, None, None]
    f *= 1 - np.clip((top_to - y) / top_to, 0, 1) ** 1.3 * top_a
    f *= 1 - np.clip((y - bot_from) / (H - bot_from), 0, 1) ** 1.2 * bot_a
    return f


def icon(d, xy, cp, size, brand=False, anchor='mm'):
    d.text(xy, chr(cp), font=ImageFont.truetype(FAB if brand else FA, size), fill=GOLD, anchor=anchor)


def ticket_shapes(im, y, h=200):
    """Translucent dark card with a thin gold line and a perforated stub."""
    x0, x1 = M, W - M
    card = Image.new('L', (W, H), 0)
    ImageDraw.Draw(card).rounded_rectangle((x0, y, x1, y + h), radius=20, fill=170)
    im.paste((10, 9, 7), (0, 0), card)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((x0, y, x1, y + h), radius=20, outline=GOLD, width=2)
    sx = x0 + 590
    for yy in range(y + 26, y + h - 20, 20):
        d.line((sx, yy, sx, yy + 10), fill=GOLD, width=3)
    icon(d, (x0 + 46, y + 62), 0xf133, 36)       # calendar
    icon(d, (x0 + 46, y + 140), 0xf017, 32)      # clock
    icon(d, ((sx + x1) / 2, y + 48), 0xf091, 38)  # trophy
    icon(d, (sx + 44, y + 152), 0xf232, 30, brand=True)  # whatsapp
    return sx


def ticket_text(f, y, sx, line1='QUINTA-FEIRA', h=200):
    x0, x1 = M, W - M
    items = [(E(line1, 'cinzel9', 52, 4, 'gold', glow=0.35, shadow=0.4), 'l', x0 + 84, y + 62),
             (E('A PARTIR DAS 20H30', 'mont6', 32, 3, 'white', glow=0.0, shadow=0.3), 'l', x0 + 84, y + 140),
             (E('PREMIAÇÃO', 'cinzel9', 40, 4, 'gold', glow=0.35, shadow=0.4), 'm', (sx + x1) / 2, y + 100),
             (E(PHONE, 'mont6', 30, 1, 'white', glow=0.0, shadow=0.3), 'l', sx + 70, y + 152)]
    for e, al, x, yy in items:
        cx = x + (e['w'] - 120) / 2 if al == 'l' else x  # elems are centred; 60px pad each side
        blit(f, e, cx, yy, 1.0)


def header(f):
    blit(f, E('VIP HOUSE', 'cinzel7', 44, 14, 'gold', glow=0.3), W / 2, 72)
    blit(f, E('PRAÇA SÃO BENEDITO  •  SÃO MATEUS-ES', 'mont5', 22, 6, 'white', glow=0.0, shadow=0.3), W / 2, 118)


def build(bg, titles_, line1='QUINTA-FEIRA', extra=None, shade_kw=None):
    im = Image.fromarray((shade(bg, **(shade_kw or {})) * 255).astype(np.uint8))
    ty = 1100
    sx = ticket_shapes(im, ty)
    if extra:
        extra(im)
    f = np.asarray(im, np.float32) / 255
    header(f)
    for e, x, y in titles_:
        blit(f, e, x, y, 1.0, 1.0, shine=0.42)
    ticket_text(f, ty, sx, line1)
    return Image.fromarray((np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8))


def save(im, name):
    im.save(f'{OUT}/{name}.jpg', quality=94, subsampling=0)
    print('saved', name)


C = W / 2
gold = lambda s, size, tr=8, g=0.6: E(s, 'cinzel9', size, tr, 'gold', glow=g)
white = lambda s, size, tr=8: E(s, 'mont6', size, tr, 'white', glow=0.12)
ital = lambda s, size: E(s, 'play_i', size, 1, 'white', glow=0.15)


def fitE(maker, s, size, max_w, *a):
    """Largest element (from `size` down) whose text fits max_w."""
    while size > 20:
        e = maker(s, size, *a)
        if e['w'] - 120 <= max_w:
            return e
        size -= 2
    return maker(s, 20, *a)


def at_left(f, e, x, y, **k):
    blit(f, e, x + (e['w'] - 120) / 2, y, 1.0, 1.0, **k)


def finish(im_or_f):
    f = im_or_f if isinstance(im_or_f, np.ndarray) else np.asarray(im_or_f, np.float32) / 255
    return Image.fromarray((np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8))


def side_shade(im, x_from, a=0.62):
    f = np.asarray(im, np.float32) / 255
    x = np.arange(W, dtype=np.float32)[None, :, None]
    f *= 1 - np.clip((x - x_from) / (W - x_from), 0, 1) ** 0.9 * a
    return Image.fromarray((f * 255).astype(np.uint8))


# 1. toda quinta, o palco é seu: titles above the crown
save(build(cover(f'{ART}/arte-2x3.png', (0.5, 0.0)), [
    (white('TODA QUINTA,', 40, 20), C, 182),
    (fitE(gold, 'O PALCO É SEU', 110, W - 2 * M, 8), C, 282),
    (ital('karaokê com premiação para quem mandar bem', 40), C, 1032),
], shade_kw=dict(top_to=420, top_a=0.5)), 'post1-toda-quinta-o-palco-e-seu')

def podium(im):
    d = ImageDraw.Draw(im)
    pw, gap, base = 290, 24, 1040
    for place, x, h in [(2, M + 18, 150), (1, M + 18 + pw + gap, 180), (3, M + 18 + 2 * (pw + gap), 126)]:
        mask = Image.new('L', (W, H), 0)
        ImageDraw.Draw(mask).rounded_rectangle((x, base - h, x + pw, base), radius=14, fill=190)
        im.paste((10, 9, 7), (0, 0), mask)
        d.rounded_rectangle((x, base - h, x + pw, base), radius=14, outline=GOLD, width=2)
        icon(d, (x + pw / 2, base - h + 40), 0xf091, 40 if place == 1 else 32)
        podium.labels.append((x + pw / 2, base - h + 100, place))


# 2. sobe no palco, sai com prêmio: mic on the right third, titles in a left column
podium.labels = []
bg2 = cover(f'{ART}/arte-16x9.png', (0.60, 0.42))
im2 = build(bg2, [], extra=podium, shade_kw=dict(top_to=640, top_a=0.45, bot_from=760, bot_a=0.8))
f2 = np.asarray(im2, np.float32) / 255
x = np.arange(W, dtype=np.float32)[None, :, None]
f2 *= 1 - np.clip((620 - x) / 620, 0, 1) * np.clip((780 - np.arange(H, dtype=np.float32)[:, None, None]) / 780, 0, 1) * 0.55
T.W, T.H = W, H
at_left(f2, gold('SOBE NO', 96, 6), M - 4, 230, shine=0.42)
at_left(f2, gold('PALCO.', 96, 6), M - 4, 350, shine=0.42)
at_left(f2, white('SAI COM', 58, 10), M, 470)
at_left(f2, white('PRÊMIO.', 58, 10), M, 550)
for px, py, place in podium.labels:
    blit(f2, gold(f'{place}º LUGAR', 46, 4, 0.4), px, py)
save(finish(f2), 'post2-sobe-no-palco-sai-com-premio')

# 3. qual música: crowned mic close-up on the left, text column on the right
CX0 = 630


def bubble(im):
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = CX0 - 20, 740, W - M, 1036
    mask = Image.new('L', (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((x0, y0, x1, y1), radius=20, fill=205)
    im.paste((10, 9, 7), (0, 0), mask)
    d.rounded_rectangle((x0, y0, x1, y1), radius=20, outline=GOLD, width=2)
    icon(d, (x0 + 40, y0 + 52), 0xf075, 34)


bg3 = side_shade(cover(f'{ART}/arte-close-4x5.png', (0.68, 0.5), zoom=1.15), 560, 0.7)
im3 = build(bg3, [], extra=bubble, shade_kw=dict(top_to=300, top_a=0.4, bot_from=1000, bot_a=0.7))
f3 = np.asarray(im3, np.float32) / 255
T.W, T.H = W, H
colw = W - M - CX0
y = 250
for line, mk, sz, step in [('QUAL', gold, 96, 108), ('MÚSICA', gold, 96, 112), ('VOCÊ VAI', white, 56, 74), ('CANTAR?', white, 56, 0)]:
    at_left(f3, fitE(mk, line, sz, colw, 6), CX0, y, shine=0.42)
    y += step
at_left(f3, fitE(lambda t, z: E(t, 'cinzel9', z, 3, 'gold', glow=0.35), 'COMENTA', 40, colw - 70), CX0 + 46, 792)
for i, line in enumerate(['a música que você', 'vai cantar. A mais', 'pedida abre a noite!']):
    at_left(f3, fitE(lambda t, z: E(t, 'play_i', z, 0, 'white', glow=0.1), line, 38, colw - 20), CX0, 862 + i * 52)
save(finish(f3), 'post3-qual-musica-voce-vai-cantar')

# 4. humor with the VIP rope
save(build(cover(f'{ART}/arte-cordao-vip-4x5.png', (0.5, 0.5)), [
    (fitE(ital, 'No banho, todo mundo é cantor.', 66, W - 2 * M), C, 220),
    (white('NA QUINTA,', 40, 18), C, 930),
    (fitE(gold, 'TODO MUNDO É VIP', 96, W - 2 * M, 6), C, 1022),
], shade_kw=dict(top_to=380, top_a=0.55, bot_from=760, bot_a=0.85)), 'post4-na-quinta-todo-mundo-e-vip')

# 5. é hoje
save(build(cover(f'{ART}/arte-9x16.png', (0.5, 0.0)), [
    (fitE(gold, 'É HOJE', 200, W - 2 * M, 12), C, 280),
    (white('KARAOKÊ NA VIP HOUSE', 40, 12), C, 400),
    (ital('Chegue cedo e garanta sua mesa', 46), C, 1030),
], line1='HOJE', shade_kw=dict(top_to=480, top_a=0.5)), 'post5-e-hoje')
