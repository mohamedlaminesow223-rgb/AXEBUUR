"""Intro vidéo 10 s (1920x1080) pour le podcast « Les voix de Clientelis ».

Les images sont calculées avec Pillow/NumPy puis envoyées brutes à ffmpeg.
Le logo fourni est utilisé tel quel (simplement recadré et mis à l'échelle).

Usage : python3 make_intro.py [sortie.mp4]
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
LOGO = HERE / "logo-clientelis-academia.jpg"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "intro-les-voix-de-clientelis.mp4"
FONT = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"

W, H, FPS, DURATION = 1920, 1080, 30, 10.0
VIOLET = np.array([0x65, 0x20, 0x6A], dtype=np.float32)
VERT = np.array([0x3A, 0xB5, 0x4A], dtype=np.float32)
TITLE = "Les voix de Clientelis"


def clamp01(x):
    return max(0.0, min(1.0, x))


def ease(t):
    """Ease-in-out cubique sur t déjà borné entre 0 et 1."""
    t = clamp01(t)
    return 4 * t**3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def progress(t, start, end):
    return ease((t - start) / (end - start))


def lerp(a, b, k):
    return a + (b - a) * k


# --- Logo : recadrage sur le contenu, fond blanc nettoyé des artefacts JPEG ---
logo = np.asarray(Image.open(LOGO).convert("RGB")).astype(np.float32)
ys, xs = np.where(logo.min(axis=2) < 235)
pad = 20
logo = logo[ys.min() - pad : ys.max() + pad, xs.min() - pad : xs.max() + pad]
logo[logo.min(axis=2) > 245] = 255.0
# On travaille en « encre » (255 - couleur) : le fond blanc vaut 0, ce qui
# permet de composer sur le fond blanc sans bord visible.
logo_ink = Image.fromarray((255 - logo).astype(np.uint8))
LOGO_H = 640  # hauteur affichée à l'échelle 1
logo_base = LOGO_H / logo_ink.height

# --- Titre : masque rendu une fois, centré ---
font = ImageFont.truetype(FONT, 76)
bbox = font.getbbox(TITLE)
title_mask = Image.new("L", (bbox[2] - bbox[0] + 8, bbox[3] - bbox[1] + 8), 0)
ImageDraw.Draw(title_mask).text((4 - bbox[0], 4 - bbox[1]), TITLE, font=font, fill=255)


def place(img, scale, cx, cy):
    """Transforme img (mise à l'échelle + position sub-pixel) sur le canevas."""
    inv = 1.0 / scale
    ox = cx - img.width * scale / 2
    oy = cy - img.height * scale / 2
    out = img.transform(
        (W, H),
        Image.AFFINE,
        (inv, 0, -ox * inv, 0, inv, -oy * inv),
        resample=Image.BICUBIC,
        fillcolor=0,
    )
    return np.asarray(out).astype(np.float32) / 255.0


# --- Onde sonore : barres arrondies, rendues en suréchantillonnage x4 ---
N_BARS, BAR_W, BAR_GAP, BAR_MAX, BAR_MIN = 25, 6, 8, 44, 6
rng = np.random.default_rng(7)
phases = rng.uniform(0, 2 * np.pi, N_BARS)
speeds = rng.uniform(2.0, 3.6, N_BARS)
envelope = np.exp(-(((np.arange(N_BARS) - (N_BARS - 1) / 2) / (N_BARS / 2.4)) ** 2))
WAVE_W = N_BARS * BAR_W + (N_BARS - 1) * BAR_GAP
WAVE_H = BAR_MAX + 4
SS = 4


def wave_mask(t):
    img = Image.new("L", (WAVE_W * SS, WAVE_H * SS), 0)
    d = ImageDraw.Draw(img)
    for i in range(N_BARS):
        level = 0.55 + 0.45 * np.sin(speeds[i] * t + phases[i])
        h = BAR_MIN + (BAR_MAX - BAR_MIN) * envelope[i] * level
        x0 = i * (BAR_W + BAR_GAP)
        y0 = (WAVE_H - h) / 2
        d.rounded_rectangle(
            [x0 * SS, y0 * SS, (x0 + BAR_W) * SS, (y0 + h) * SS],
            radius=BAR_W * SS / 2,
            fill=255,
        )
    small = img.resize((WAVE_W, WAVE_H), Image.LANCZOS)
    return np.asarray(small).astype(np.float32) / 255.0


def render(t):
    frame = np.full((H, W, 3), 255.0, dtype=np.float32)

    # 1) Logo : fondu + léger zoom (0 → 2,6 s), puis montée (2,6 → 4,2 s)
    appear = progress(t, 0.0, 2.2)
    zoom = progress(t, 0.0, 3.0)
    rise = progress(t, 2.6, 4.2)
    scale = logo_base * lerp(0.92, 1.0, zoom) * lerp(1.0, 0.84, rise)
    cy = lerp(540, 405, rise)
    if appear > 0:
        ink = place(logo_ink, scale, W / 2, cy)
        frame -= ink * 255.0 * appear

    # 2) Titre violet : fondu + petite remontée (4,2 → 5,6 s)
    tk = progress(t, 4.2, 5.6)
    if tk > 0:
        a = place(title_mask, 1.0, W / 2, lerp(808, 790, tk))[..., None] * tk
        frame = frame * (1 - a) + VIOLET * a

    # 3) Onde verte discrète (5,0 → fin)
    wk = progress(t, 5.0, 6.4)
    if wk > 0:
        m = wave_mask(t) * 0.85 * wk
        x0 = (W - WAVE_W) // 2
        y0 = 880 - WAVE_H // 2
        region = frame[y0 : y0 + WAVE_H, x0 : x0 + WAVE_W]
        region[:] = region * (1 - m[..., None]) + VERT * m[..., None]

    # 4) Fondu doux vers le blanc (8,4 → 10 s)
    out = progress(t, 8.4, 10.0)
    frame = frame * (1 - out) + 255.0 * out
    return np.clip(frame + 0.5, 0, 255).astype(np.uint8)


def main():
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-t", str(DURATION),
        "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart", "-shortest",
        str(OUT),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(DURATION * FPS)
    for i in range(n):
        proc.stdin.write(render(i / FPS).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit("ffmpeg a échoué")
    print(f"OK : {OUT}")


if __name__ == "__main__":
    main()
