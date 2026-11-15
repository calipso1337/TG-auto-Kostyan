#!/usr/bin/env python3
"""Логотип канала @All_About_Brawl: оригинальный, без персонажей и логотипов Supercell.

python3 tools/make_logo.py branding/   рисует варианты logo-star.png, logo-shield.png, logo-neon.png

Аватарка Telegram круглая, поэтому всё важное держится внутри круга.
Шрифты Russo One и Bungee (лицензия SIL OFL) лежат в tools/assets.
"""
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ASSETS = Path(__file__).resolve().parent / "assets"
RUSSO = str(ASSETS / "RussoOne-Regular.ttf")
BUNGEE = str(ASSETS / "Bungee-Regular.ttf")
SIZE = 1024
INK = (24, 10, 48)
YELLOW = (255, 214, 10)
ORANGE = (255, 140, 26)


def font(path, size):
    return ImageFont.truetype(path, size)


def radial(size, inner, outer, center=(0.5, 0.45)):
    """Радиальный градиент от inner в центре к outer по краям."""
    mask = Image.new("L", (size, size))
    cx, cy = size * center[0], size * center[1]
    reach = math.hypot(max(cx, size - cx), max(cy, size - cy))
    pixels = mask.load()
    for y in range(size):
        for x in range(size):
            pixels[x, y] = min(255, int(255 * math.hypot(x - cx, y - cy) / reach))
    return Image.composite(Image.new("RGB", (size, size), outer), Image.new("RGB", (size, size), inner), mask)


def rays(size, count, color, alpha, center=(0.5, 0.45)):
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cx, cy = size * center[0], size * center[1]
    for i in range(count):
        a = 2 * math.pi * i / count
        width = math.pi / count * 0.55
        far = size * 1.2
        draw.polygon([(cx, cy), (cx + far * math.cos(a - width), cy + far * math.sin(a - width)),
                      (cx + far * math.cos(a + width), cy + far * math.sin(a + width))], fill=(*color, alpha))
    return layer


def star_points(cx, cy, outer, inner, rotation=-90, points=5):
    result = []
    for i in range(points * 2):
        radius = outer if i % 2 == 0 else inner
        angle = math.radians(rotation + i * 180 / points)
        result.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return result


def bolt_points(cx, cy, scale):
    shape = [(0.10, -0.50), (-0.28, 0.06), (-0.02, 0.06), (-0.14, 0.50), (0.30, -0.10), (0.04, -0.10), (0.18, -0.50)]
    return [(cx + x * scale, cy + y * scale) for x, y in shape]


def outlined_polygon(base, points, fill, outline=INK, width=26, shadow=(18, 22)):
    """Многоугольник с толстой обводкой и сдвинутой тенью, как у игровых значков."""
    draw = ImageDraw.Draw(base)
    sx, sy = shadow
    draw.polygon([(x + sx, y + sy) for x, y in points], fill=(*INK, 160))
    draw.line(points + [points[0]], fill=outline, width=width * 2, joint="curve")
    draw.polygon(points, fill=fill)


def glossy(base, points, top_alpha=90):
    """Блик на верхней половине фигуры."""
    mask = Image.new("L", base.size)
    ImageDraw.Draw(mask).polygon(points, fill=255)
    ys = [y for _, y in points]
    middle = (min(ys) + max(ys)) / 2
    cut = Image.new("L", base.size)
    ImageDraw.Draw(cut).rectangle((0, 0, base.size[0], middle), fill=top_alpha)
    shine = Image.new("RGBA", base.size, (255, 255, 255, 0))
    shine.putalpha(ImageChops.multiply(mask, cut))
    base.alpha_composite(shine)


def text_3d(base, xy, text, face, fill, outline=INK, stroke=14, depth=10, anchor="mm"):
    draw = ImageDraw.Draw(base)
    x, y = xy
    for d in range(depth, 0, -1):
        draw.text((x + d, y + d), text, font=face, fill=outline, anchor=anchor, stroke_width=stroke, stroke_fill=outline)
    draw.text((x, y), text, font=face, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=outline)


def sparkles(base, count, color, seed, box):
    rng = random.Random(seed)
    draw = ImageDraw.Draw(base)
    for _ in range(count):
        x, y = rng.uniform(box[0], box[2]), rng.uniform(box[1], box[3])
        r = rng.uniform(10, 26)
        draw.polygon(star_points(x, y, r, r * 0.3, rotation=rng.uniform(0, 90), points=4), fill=(*color, 230))


def ribbon(base, cy, text, fill, ink=INK, width=560, height=118):
    draw = ImageDraw.Draw(base)
    cx = SIZE / 2
    left, right = cx - width / 2, cx + width / 2
    top, bottom = cy - height / 2, cy + height / 2
    tail = 46
    for side in (-1, 1):  # Хвосты ленты.
        x = left if side < 0 else right
        draw.polygon([(x, top + 22), (x + side * (tail + 40), top + 22), (x + side * 40, cy + 30),
                      (x + side * (tail + 40), bottom + 22), (x, bottom + 22)], fill=(*ink, 255))
    draw.rounded_rectangle((left + 10, top + 14, right + 10, bottom + 14), radius=26, fill=(*ink, 200))
    draw.rounded_rectangle((left, top, right, bottom), radius=26, fill=(*fill, 255), outline=ink, width=12)
    draw.text((cx, cy + 4), text, font=font(RUSSO, 76), fill=(255, 255, 255), anchor="mm",
              stroke_width=8, stroke_fill=ink)


def logo_star():
    base = radial(SIZE, (190, 38, 224), (46, 8, 92)).convert("RGBA")
    base.alpha_composite(rays(SIZE, 18, (255, 255, 255), 26))
    points = star_points(SIZE / 2, SIZE * 0.47, 370, 176)
    outlined_polygon(base, points, YELLOW)
    inner = star_points(SIZE / 2, SIZE * 0.47, 305, 145)
    ImageDraw.Draw(base).polygon(inner, fill=ORANGE)
    ImageDraw.Draw(base).polygon(star_points(SIZE / 2, SIZE * 0.46, 292, 138), fill=YELLOW)
    glossy(base, points, 70)
    sparkles(base, 7, (255, 255, 255), 3, (80, 80, SIZE - 80, SIZE * 0.6))  # До текста: не перекрывают буквы.
    text_3d(base, (SIZE / 2 - 6, SIZE * 0.49), "AB", font(BUNGEE, 280), (255, 255, 255), stroke=16, depth=12)
    ribbon(base, SIZE * 0.80, "НОВОСТИ", (236, 32, 112))
    return base


def shield_points(cx, top, width, height):
    half = width / 2
    return [(cx - half, top + 40), (cx, top), (cx + half, top + 40), (cx + half, top + height * 0.48),
            (cx + half * 0.72, top + height * 0.78), (cx, top + height), (cx - half * 0.72, top + height * 0.78),
            (cx - half, top + height * 0.48)]


def logo_shield():
    base = radial(SIZE, (20, 110, 255), (6, 18, 70)).convert("RGBA")
    base.alpha_composite(rays(SIZE, 24, (120, 200, 255), 22, center=(0.5, 0.5)))
    outer = shield_points(SIZE / 2, 150, 620, 760)
    outlined_polygon(base, outer, (255, 214, 10))
    inner = shield_points(SIZE / 2, 194, 530, 656)
    ImageDraw.Draw(base).polygon(inner, fill=(124, 44, 236))
    stripe = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(stripe).polygon([(SIZE / 2, 194), (SIZE / 2 + 265, 234), (SIZE / 2 + 265, 508),
                                    (SIZE / 2, 850)], fill=(255, 255, 255, 34))
    base.alpha_composite(stripe)
    bolt = bolt_points(SIZE / 2, SIZE * 0.42, 380)
    outlined_polygon(base, bolt, (255, 236, 64), width=14, shadow=(12, 14))
    glossy(base, bolt, 80)
    sparkles(base, 6, (255, 255, 255), 7, (100, 100, SIZE - 100, SIZE * 0.5))
    text_3d(base, (SIZE / 2, SIZE * 0.68), "ВСЁ О", font(RUSSO, 70), (255, 255, 255), stroke=10, depth=6)
    text_3d(base, (SIZE / 2, SIZE * 0.765), "BRAWL", font(BUNGEE, 104), YELLOW, stroke=12, depth=8)
    return base


def logo_neon():
    base = radial(SIZE, (40, 12, 70), (6, 2, 16)).convert("RGBA")
    ring = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse((92, 92, SIZE - 92, SIZE - 92), outline=(255, 46, 160, 255), width=22)
    glow = ring.filter(ImageFilter.GaussianBlur(26))
    base.alpha_composite(glow)
    base.alpha_composite(glow)
    base.alpha_composite(ring)
    bolt = bolt_points(SIZE / 2, SIZE * 0.40, 470)
    neon = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(neon).polygon(bolt, fill=(255, 226, 40, 255))
    halo = neon.filter(ImageFilter.GaussianBlur(34))
    base.alpha_composite(halo)
    base.alpha_composite(halo)
    base.alpha_composite(neon)
    # Светлая сердцевина неоновой трубки: та же молния, только тонкая линия внутри.
    ImageDraw.Draw(base).line(bolt + [bolt[0]], fill=(255, 252, 220, 255), width=10, joint="curve")
    sparkles(base, 9, (120, 230, 255), 11, (150, 150, SIZE - 150, SIZE * 0.62))
    for text, y, size, color in (("ALL ABOUT", 0.70, 82, (120, 230, 255)), ("BRAWL", 0.80, 132, (255, 70, 180))):
        layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((SIZE / 2, SIZE * y), text, font=font(BUNGEE, size), fill=(*color, 255), anchor="mm")
        base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(14)))
        base.alpha_composite(layer)
    return base


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "branding")
    out.mkdir(parents=True, exist_ok=True)
    for name, make in (("star", logo_star), ("shield", logo_shield), ("neon", logo_neon)):
        make().convert("RGB").save(out / f"logo-{name}.png", optimize=True)
        print(f"{out / f'logo-{name}.png'}")


if __name__ == "__main__":
    main()
