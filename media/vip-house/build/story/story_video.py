"""15 s vertical story creative: Higgsfield heels + spotlight shots, real karaoke
footage cropped to 9:16, gold titles and a VIP end card."""
import json
import subprocess
import sys
import numpy as np
from PIL import Image
import titles as T
from titles import make_elem, blit, row, fade, ease_out, ease_in_out, ease_out_back, clamp01, blur

S = T.S
FF = T.FF
W, H, FPS = 1080, 1920, 30
T.W, T.H = W, H
OUT = sys.argv[1] if len(sys.argv) > 1 else f'{S}/story/out.mp4'
PREVIEW = sys.argv[2:]
TL = json.load(open(f'{S}/story/timeline.json'))
HIT1, MONT, MONT_END = TL['hit1'], TL['mont'], TL['mont_end']
VA, VB, HIT, TOTAL = TL['voice_a_at'], TL['voice_b_at'], TL['final_hit'], TL['total']
BEAT = TL['beat']
NF = int(round(TOTAL * FPS))
C = '/home/user/a/media/raw/vip-house/criativo'
SRC = '/root/.claude/uploads/8f0652ee-1482-53b0-83c8-c0d027028c46/ab23c45c-202609282114.mp4'

GRADE = ("curves=master='0/0.03 0.25/0.22 0.5/0.5 0.75/0.79 1/0.97',"
         "colorbalance=rs=-0.02:bs=0.035:rh=0.035:bh=-0.03,eq=saturation=1.06:contrast=1.03")
AI_GRADE = "eq=contrast=1.04:saturation=1.04"


def crop916(cx):
    w = 608
    x0 = int(min(max(cx - w / 2, 0), 1920 - w))
    return f"crop={w}:1080:{x0}:0,scale={W}:{H}:flags=lanczos"


# segments of the base timeline: (start_t, end_t, source, in_point, video filter)
clip_len = 2 * BEAT
montage = [(1.55, 1330), (0.25, 850), (5.40, 520), (7.05, 1000), (12.69, 900)]
SEGS = [(0.0, HIT1, f'{C}/kling-saltos.mp4', 0.0, f"scale={W}:{H},{AI_GRADE}"),
        (HIT1, MONT, f'{C}/kling-microfone.mp4', 0.35, f"scale={W}:{H},{AI_GRADE}")]
for k, (tin, cx) in enumerate(montage):
    a = MONT + k * clip_len
    SEGS.append((a, a + clip_len, SRC, tin, f"scale=in_color_matrix=bt709:in_range=tv,{crop916(cx)},{GRADE}"))


def decode(src, tin, dur, vf):
    n = int(round(dur * FPS)) + 2
    cmd = [FF, '-v', 'error', '-ss', f'{tin:.3f}', '-i', src, '-an', '-t', f'{dur + 0.2:.3f}',
           '-vf', f'fps={FPS},{vf},format=rgb24', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
    return fr[:n]


print('decoding segments...', flush=True)
seg_frames = [decode(src, tin, b - a, vf) for a, b, src, tin, vf in SEGS]
# end card base: last frame of the spotlight shot, blurred and darkened
mic_last = decode(f'{C}/kling-microfone.mp4', 4.9, 0.1, f"scale={W}:{H},{AI_GRADE}")[-1]
end_sharp = np.asarray(mic_last, np.float32) / 255
end_soft = np.asarray(blur(Image.fromarray(mic_last).resize((W // 2, H // 2), Image.BILINEAR), 6)
                      .resize((W, H), Image.BILINEAR), np.float32) / 255


def base_frame(t):
    for (a, b, *_), fr in zip(SEGS, seg_frames):
        if a <= t < b:
            i = min(int((t - a) * FPS + 1e-6), len(fr) - 1)
            return fr[i].astype(np.float32) / 255
    return None


# ------------------------------------------------------------------ titles
print('building titles...', flush=True)
E = {
    'o_karaoke': make_elem('O KARAOKÊ', 'cinzel9', 124, 6, 'gold', glow=0.6),
    'ja_vai': make_elem('JÁ VAI COMEÇAR!', 'mont6', 74, 6, 'white', glow=0.2),
    'hoje': make_elem('HOJE', 'mont6', 64, 26, 'white', glow=0.15),
    'hora': make_elem('20H30', 'cinzel9', 250, 8, 'gold', glow=0.65),
    'vip_top': make_elem('VIP HOUSE', 'cinzel7', 46, 16, 'gold', glow=0.25),
    'lt_karaoke': make_elem('KARAOKÊ', 'cinzel9', 120, 8, 'gold', glow=0.55),
    'lt_info': make_elem('HOJE  •  20H30', 'mont6', 56, 10, 'white', glow=0.15),
    'vem_pra': make_elem('Vem pra', 'play_i', 92, 1, 'white', glow=0.15),
    'vip_house': make_elem('VIP HOUSE', 'cinzel9', 150, 12, 'gold', glow=0.6),
    'que_aqui': make_elem('que aqui você é', 'play_i', 86, 1, 'white', glow=0.15),
    'vip_big': make_elem('VIP', 'cinzel9', 330, 18, 'gold', glow=0.75),
    'end_info': make_elem('KARAOKÊ  •  HOJE  •  20H30', 'mont6', 44, 6, 'white', glow=0.12),
}
yy = np.arange(H, dtype=np.float32)[:, None, None]
grad_bottom = (np.clip((yy - 1050) / (1750 - 1050), 0, 1) ** 1.3 * 0.7)
grad_top = (np.clip((700 - yy) / 700, 0, 1) ** 1.6 * 0.55)
xx = np.arange(W, dtype=np.float32)[None, :, None]
vign = 1 - 0.38 * np.clip(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H / 2) / (H * 0.62)) ** 2, 0, 1)
rng = np.random.default_rng(5)
grain = [np.asarray(Image.fromarray(rng.standard_normal((H // 2, W // 2)).astype(np.float32), 'F')
                    .resize((W, H), Image.BILINEAR))[:, :, None] * (3.0 / 255) for _ in range(6)]


def flash(f, k, peak, tau):
    if 0 <= k < 0.8:
        a = peak * np.exp(-k / tau)
        f = f + a * (1 - f) * np.array([1.0, 0.95, 0.86], np.float32)
    return f


def frame(t, i):
    if t < MONT_END:
        f = base_frame(t)
    else:
        k = t - MONT_END
        bl = ease_in_out(k / 0.6)
        base = end_sharp * (1 - bl) + end_soft * bl
        z = 1 + 0.06 * ease_in_out(k / (TOTAL - MONT_END))
        cw, ch = W / z, H / z
        box = (W / 2 - cw / 2, H * 0.45 - ch / 2, W / 2 + cw / 2, H * 0.45 + ch / 2)
        box = (box[0], max(0, box[1]), box[2], min(H, box[3]))
        im = Image.fromarray((base * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR, box=box)
        f = np.asarray(im, np.float32) / 255 * (1 - 0.55 * ease_in_out(k / 0.6))
    f = f * vign

    # hook: heels walking in, the big promise up top
    if t < HIT1 + 0.2:
        a = fade(t, VA + 0.05, 0.45, HIT1 - 0.15, 0.15)
        f *= 1 - grad_top * a
        s = 1.12 - 0.12 * ease_out((t - VA - 0.05) / 0.6)
        blit(f, E['o_karaoke'], W / 2, 420, a, s, shine=(t - VA - 0.5) / 0.9)
        blit(f, E['ja_vai'], W / 2, 548 + 12 * (1 - ease_out((t - VA - 1.3) / 0.6)),
             fade(t, VA + 1.3, 0.4, HIT1 - 0.15, 0.15))
    # spotlight shot: HOJE / 20H30
    if HIT1 - 0.05 < t < MONT + 0.3:
        tv = VA + 3.34
        a = fade(t, tv - 0.05, 0.35, MONT - 0.1, 0.2)
        f *= 1 - grad_bottom * a
        blit(f, E['hoje'], W / 2, 1330 + 10 * (1 - ease_out((t - tv) / 0.5)), a)
        th = VA + 4.19
        blit(f, E['hora'], W / 2, 1500, fade(t, th - 0.05, 0.3, MONT - 0.1, 0.2),
             1.15 - 0.15 * ease_out((t - th) / 0.45), shine=(t - th - 0.3) / 0.8)
    # montage: lower third and the venue name up top
    if MONT - 0.1 < t < MONT_END + 0.1:
        a = fade(t, MONT + 0.1, 0.4, MONT_END - 0.25, 0.2)
        f *= 1 - grad_bottom * a
        f *= 1 - grad_top * a * 0.8
        blit(f, E['vip_top'], W / 2, 210, a)
        blit(f, E['lt_karaoke'], W / 2, 1540, a, 1.06 - 0.06 * ease_out((t - MONT - 0.1) / 0.5),
             shine=(t - MONT - 0.6) / 0.9)
        blit(f, E['lt_info'], W / 2, 1660, fade(t, MONT + 0.35, 0.4, MONT_END - 0.25, 0.2))
    # end card
    if t >= MONT_END:
        out1 = VB + TL['vb_phrase2'] - 0.25
        blit(f, E['vem_pra'], W / 2, 760 + 12 * (1 - ease_out((t - VB) / 0.6)), fade(t, VB, 0.4, out1, 0.25))
        blit(f, E['vip_house'], W / 2, 900, fade(t, VB + 0.35, 0.35, out1, 0.25),
             1.1 - 0.1 * ease_out((t - VB - 0.35) / 0.6), shine=(t - VB - 0.7) / 0.9)
        tq = VB + TL['vb_phrase2']
        blit(f, E['que_aqui'], W / 2, 700 + 12 * (1 - ease_out((t - tq) / 0.6)), fade(t, tq, 0.45))
        kh = t - HIT
        if kh >= -0.02:
            blit(f, E['vip_big'], W / 2, 920, clamp01(kh / 0.06), 1.35 - 0.35 * ease_out_back(kh / 0.4),
                 shine=(kh - 0.35) / 0.9)
            blit(f, E['end_info'], W / 2, 1150 + 12 * (1 - ease_out((kh - 0.6) / 0.6)), fade(kh, 0.6, 0.5))
    for at, pk in ((HIT1, 0.8), (MONT_END, 0.6), (HIT, 0.95)):
        f = flash(f, t - at, pk, 0.1)
    f = f + grain[i % len(grain)]
    g = clamp01(t / 0.25) * (1 - ease_in_out((t - (TOTAL - 0.9)) / 0.9))
    return (np.clip(f * g, 0, 1) * 255 + 0.5).astype(np.uint8)


enc = None
if not PREVIEW:
    enc = subprocess.Popen([FF, '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
                            '-i', '-', '-i', f'{S}/story/mix.wav',
                            '-af', 'volume=2.6dB,alimiter=limit=0.72:attack=2:release=60:level=disabled',
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
        Image.fromarray(out).save(f'{S}/story/prev_{t:05.2f}.png')
    else:
        enc.stdin.write(out.tobytes())
if enc:
    enc.stdin.close()
    enc.wait()
print('done')
