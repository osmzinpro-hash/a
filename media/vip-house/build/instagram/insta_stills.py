"""Instagram stills for the week: feed post, two stories and a printable table card with a QR code."""
import numpy as np
import qrcode
from PIL import Image, ImageDraw
import titles as T
from titles import make_elem, blit

S = T.S
D = f'{S}/insta'


def canvas_from(bg_path, w, h, y_center=0.5):
    im = Image.open(bg_path).convert('RGB')
    sc = w / im.width
    im = im.resize((w, int(im.height * sc)), Image.LANCZOS)
    if im.height < h:
        sc = h / im.height
        im = im.resize((int(im.width * sc), h), Image.LANCZOS)
    y0 = int(min(max(im.height * y_center - h / 2, 0), im.height - h))
    x0 = (im.width - w) // 2
    return np.asarray(im.crop((x0, y0, x0 + w, y0 + h)), np.float32) / 255


def shade(f, top_to, bot_from, top_a=0.6, bot_a=0.7):
    h = f.shape[0]
    y = np.arange(h, dtype=np.float32)[:, None, None]
    f *= 1 - np.clip((top_to - y) / top_to, 0, 1) ** 1.4 * top_a
    f *= 1 - np.clip((y - bot_from) / (h - bot_from), 0, 1) ** 1.2 * bot_a
    return f


def save(f, name):
    Image.fromarray((np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8)).save(f'{D}/{name}', quality=92, subsampling=0)
    print('saved', name)


def place(f, items):
    T.W, T.H = f.shape[1], f.shape[0]
    for e, y in items:
        blit(f, e, T.W / 2, y, 1.0, 1.0, shine=0.42)


# 1) feed post, 4:5 — evergreen "toda quinta" with the in-store coupon
f = canvas_from(f'{D}/bg_cartoon.png', 1080, 1350, 0.47)
f = shade(f, 420, 1000)
place(f, [
    (make_elem('TODA QUINTA  •  20H30', 'mont6', 44, 10, 'white', glow=0.15), 90),
    (make_elem('KARAOKÊ', 'cinzel9', 160, 8, 'gold', glow=0.6), 205),
    (make_elem('MOSTRE ESTE POST NO BALCÃO', 'mont6', 40, 6, 'white', glow=0.15), 1140),
    (make_elem('E GANHE UM BRINDE', 'cinzel9', 66, 4, 'gold', glow=0.5), 1218),
    (make_elem('@viphousesm  •  aqui você é VIP', 'mont5', 30, 4, 'white', glow=0.1), 1298),
])
save(f, 'feed-karaoke-toda-quinta.jpg')

# 2) wednesday story — tomorrow + reservation through the direct
f = canvas_from(f'{D}/bg_mic.png', 1080, 1920, 0.5)
f = shade(f, 760, 1300, 0.72, 0.75)
place(f, [
    (make_elem('AMANHÃ TEM', 'mont6', 64, 18, 'white', glow=0.15), 300),
    (make_elem('KARAOKÊ', 'cinzel9', 170, 8, 'gold', glow=0.6), 440),
    (make_elem('20H30', 'cinzel9', 150, 8, 'gold', glow=0.55), 610),
    (make_elem('RESERVE SUA MESA', 'mont6', 54, 10, 'white', glow=0.15), 1540),
    (make_elem('CHAMA NO DIRECT', 'cinzel9', 84, 4, 'gold', glow=0.5), 1640),
    (make_elem('VIP HOUSE  •  aqui você é VIP', 'mont5', 32, 6, 'white', glow=0.1), 1760),
])
save(f, 'story-quarta-amanha.jpg')

# 3) thursday morning story — "é hoje"
f = canvas_from(f'{D}/bg_heels.png', 1080, 1920, 0.5)
f = shade(f, 720, 1350, 0.7, 0.75)
place(f, [
    (make_elem('É HOJE!', 'cinzel9', 190, 8, 'gold', glow=0.6), 330),
    (make_elem('KARAOKÊ  •  20H30', 'mont6', 58, 10, 'white', glow=0.15), 495),
    (make_elem('CHEGUE CEDO E GARANTA SUA MESA', 'mont6', 40, 4, 'white', glow=0.15), 1600),
    (make_elem('VIP HOUSE', 'cinzel9', 110, 10, 'gold', glow=0.55), 1700),
    (make_elem('aqui você é VIP', 'play_i', 66, 1, 'white', glow=0.15), 1810),
])
save(f, 'story-quinta-e-hoje.jpg')

# 4) printable table card, 10x15 cm at 300 dpi, with a QR code to the profile
w, h = 1181, 1772
card = np.zeros((h, w, 3), np.float32) + np.array([0.04, 0.035, 0.03], np.float32)
yy = np.arange(h, dtype=np.float32)[:, None, None]
card += np.exp(-((yy - 330) / 420) ** 2) * np.array([0.10, 0.075, 0.03], np.float32)
qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=16, border=2)
qr.add_data('https://instagram.com/viphousesm')
qr.make(fit=True)
q = qr.make_image(fill_color='black', back_color='white').convert('RGB').resize((560, 560), Image.NEAREST)
img = Image.fromarray((card * 255).astype(np.uint8))
d = ImageDraw.Draw(img)
gold = (214, 172, 88)
d.rounded_rectangle((28, 28, w - 28, h - 28), radius=36, outline=gold, width=5)
d.rounded_rectangle((w // 2 - 300, 760, w // 2 + 300, 1360), radius=28, fill=(255, 255, 255))
img.paste(q, (w // 2 - 280, 780))
card = np.asarray(img, np.float32) / 255
place(card, [
    (make_elem('TODA QUINTA', 'mont6', 58, 16, 'white', glow=0.12), 170),
    (make_elem('KARAOKÊ', 'cinzel9', 176, 8, 'gold', glow=0.55), 330),
    (make_elem('20H30', 'cinzel9', 120, 8, 'gold', glow=0.5), 500),
    (make_elem('aqui você é VIP', 'play_i', 62, 1, 'white', glow=0.12), 640),
    (make_elem('SIGA @VIPHOUSESM', 'mont6', 54, 6, 'white', glow=0.12), 1450),
    (make_elem('Poste sua foto cantando e marque a gente', 'play_i', 48, 0, 'white', glow=0.1), 1545),
    (make_elem('VIP HOUSE', 'cinzel7', 64, 14, 'gold', glow=0.4), 1660),
])
save(card, 'cartao-mesa-qr-10x15.jpg')
