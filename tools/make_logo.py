#!/usr/bin/env python3
"""Логотип канала @All_About_Brawl: оригинальный, без персонажей и логотипов Supercell.

python3 tools/make_logo.py branding/   рисует logo-gold.png, logo-cyber.png, logo-pop.png (1024×1024)

Аватарка Telegram круглая, поэтому всё важное держится внутри круга. Рисуем в 2048 px и
уменьшаем: края получаются гладкими. Шрифты Unbounded и Exo 2 (лицензия SIL OFL) в tools/assets.
"""
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ASSETS = Path(__file__).resolve().parent / "assets"
S = 2048  # Рабочий размер; на выходе 1024.


def font(name, size, weight="Black"):
    face = ImageFont.truetype(str(ASSETS / name), size)
    try:
        face.set_variation_by_name(weight)
    except (OSError, ValueError):
        pass
    return face


def gradient(colors, angle=90, size=S):
    """Линейный градиент по нескольким цветам под углом (градусы, 90 = сверху вниз)."""
    line = Image.new("RGB", (512, 1))
    stops = len(colors) - 1
    for x in range(512):
        t = x / 511 * stops
        i = min(int(t), stops - 1)
        f = t - i
        a, b = colors[i], colors[i + 1]
        line.putpixel((x, 0), tuple(int(a[k] + (b[k] - a[k]) * f) for k in range(3)))
    big = line.resize((int(size * 1.5), int(size * 1.5)), Image.BILINEAR).rotate(-angle, Image.BICUBIC)
    off = (big.width - size) // 2
    return big.crop((off, off, off + size, off + size)).convert("RGBA")


def radial_glow(base, center, radius, color, alpha):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    cx, cy = center
    ImageDraw.Draw(layer).ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(*color, alpha))
    base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius * 0.6)))


def mask_of(draw_fn):
    mask = Image.new("L", (S, S), 0)
    draw_fn(ImageDraw.Draw(mask))
    return mask


def paint(base, mask, fill):
    """Заливает маску цветом или картинкой-градиентом."""
    layer = fill if isinstance(fill, Image.Image) else Image.new("RGBA", (S, S), (*fill, 255))
    base.paste(layer, (0, 0), mask)


def shadow(base, mask, offset=(0, 40), blur=60, color=(0, 0, 0), alpha=150):
    soft = Image.new("RGBA", (S, S), (*color, 0))
    shifted = ImageChops.offset(mask, *offset).point(lambda v: v * alpha // 255)
    soft.putalpha(shifted.filter(ImageFilter.GaussianBlur(blur)))
    base.alpha_composite(soft)


def star_points(cx, cy, outer, inner, rotation=-90, points=5):
    out = []
    for i in range(points * 2):
        r = outer if i % 2 == 0 else inner
        a = math.radians(rotation + i * 180 / points)
        out.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return out


def faceted_star(base, cx, cy, outer, inner, light, mid, dark):
    """Гранёная звезда: каждый луч из светлой и тёмной половинки, как кристалл."""
    points = star_points(cx, cy, outer, inner)
    shadow(base, mask_of(lambda d: d.polygon(points, fill=255)), (0, 50), 70, (0, 0, 0), 170)
    draw = ImageDraw.Draw(base)
    for i in range(10):
        a, b = points[i], points[(i + 1) % 10]
        draw.polygon([(cx, cy), a, b], fill=(*(light if i % 2 == 0 else dark), 255))
    # Тонкая светлая кромка и блик сверху.
    draw.line(points + [points[0]], fill=(*mid, 255), width=10, joint="curve")
    shine = Image.new("RGBA", (S, S), (255, 255, 255, 0))
    top = mask_of(lambda d: d.polygon(points, fill=255))
    cut = mask_of(lambda d: d.rectangle((0, 0, S, cy - outer * 0.15), fill=60))
    shine.putalpha(ImageChops.multiply(top, cut))
    base.alpha_composite(shine)
    return points


def bolt_points(cx, cy, scale):
    shape = [(0.12, -0.50), (-0.26, 0.05), (-0.02, 0.05), (-0.14, 0.50), (0.28, -0.08), (0.04, -0.08), (0.20, -0.50)]
    return [(cx + x * scale, cy + y * scale) for x, y in shape]


def faceted_bolt(base, cx, cy, scale, light, dark, glow=None):
    points = bolt_points(cx, cy, scale)
    mask = mask_of(lambda d: d.polygon(points, fill=255))
    if glow:
        halo = Image.new("RGBA", (S, S), (*glow, 0))
        halo.putalpha(mask.filter(ImageFilter.GaussianBlur(70)))
        base.alpha_composite(halo)
        base.alpha_composite(halo)
    shadow(base, mask, (0, 40), 50, (0, 0, 0), 140)
    paint(base, mask, gradient([light, dark], 120))
    # Светлая грань по левой половине молнии.
    facet = mask_of(lambda d: d.polygon([points[0], points[1], points[2], (cx, cy - 0.08 * scale)], fill=110))
    shine = Image.new("RGBA", (S, S), (255, 255, 255, 0))
    shine.putalpha(ImageChops.multiply(mask, facet))
    base.alpha_composite(shine)
    return points


def text_fill(base, xy, text, face, fill, anchor="mm", tracking=0, shadow_alpha=140):
    """Текст с градиентной или цветной заливкой, мягкой тенью и разрядкой букв."""
    mask = Image.new("L", (S, S), 0)
    draw = ImageDraw.Draw(mask)
    if tracking:
        widths = [draw.textlength(ch, font=face) for ch in text]
        total = sum(widths) + tracking * (len(text) - 1)
        x = xy[0] - total / 2
        for ch, w in zip(text, widths):
            draw.text((x, xy[1]), ch, font=face, fill=255, anchor="lm")
            x += w + tracking
    else:
        draw.text(xy, text, font=face, fill=255, anchor=anchor)
    if shadow_alpha:
        shadow(base, mask, (0, 22), 30, (0, 0, 0), shadow_alpha)
    paint(base, mask, fill)


def dust(base, count, color, seed, box, size=(4, 10), alpha=(80, 200)):
    rng = random.Random(seed)
    draw = ImageDraw.Draw(base)
    for _ in range(count):
        x, y = rng.uniform(box[0], box[2]), rng.uniform(box[1], box[3])
        r = rng.uniform(*size)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(*color, int(rng.uniform(*alpha))))


def sparkle(base, x, y, r, color=(255, 255, 255)):
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(layer).polygon(star_points(x, y, r, r * 0.18, rotation=-90, points=4), fill=(*color, 255))
    base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(r * 0.25)))
    base.alpha_composite(layer)


# ---------- Варианты ----------


def logo_gold():
    """Премиум: глубокий ночной синий, гранёная золотая звезда, белое BRAWL."""
    base = gradient([(10, 14, 40), (22, 32, 92), (8, 10, 30)], 90)
    radial_glow(base, (S / 2, S * 0.40), S * 0.42, (70, 100, 255), 120)
    radial_glow(base, (S / 2, S * 0.40), S * 0.22, (255, 190, 60), 60)
    dust(base, 90, (255, 255, 255), 4, (120, 120, S - 120, S - 120), (2, 6), (40, 160))
    ring = mask_of(lambda d: d.ellipse((90, 90, S - 90, S - 90), outline=255, width=14))
    paint(base, ring, gradient([(255, 226, 140), (196, 132, 30), (255, 226, 140)], 45))
    faceted_star(base, S / 2, S * 0.40, 560, 235, (255, 214, 92), (255, 236, 170), (214, 140, 20))
    sparkle(base, S * 0.70, S * 0.20, 60)
    text_fill(base, (S / 2, S * 0.705), "ALL ABOUT", font("Unbounded.ttf", 80, "SemiBold"), (255, 214, 120),
              tracking=24, shadow_alpha=0)
    text_fill(base, (S / 2, S * 0.785), "BRAWL", font("Unbounded.ttf", 205, "Black"),
              gradient([(255, 255, 255), (214, 222, 255)], 90))
    return base


def hexagon(cx, cy, r, rotation=0):
    return [(cx + r * math.cos(math.radians(rotation + 60 * i)), cy + r * math.sin(math.radians(rotation + 60 * i)))
            for i in range(6)]


def logo_cyber():
    """Киберспорт: тёмно-фиолетовый фон, циан и маджента, гранёная молния в шестиугольнике."""
    base = gradient([(16, 6, 38), (34, 10, 72), (10, 4, 26)], 135)
    radial_glow(base, (S * 0.28, S * 0.30), S * 0.30, (0, 220, 255), 110)
    radial_glow(base, (S * 0.76, S * 0.68), S * 0.30, (255, 40, 170), 110)
    grid = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    for k in range(0, S, 96):
        gd.line((k, 0, k, S), fill=(255, 255, 255, 10), width=2)
        gd.line((0, k, S, k), fill=(255, 255, 255, 10), width=2)
    base.alpha_composite(grid)
    hexa = hexagon(S / 2, S * 0.42, 560, 30)
    shadow(base, mask_of(lambda d: d.polygon(hexa, fill=255)), (0, 40), 70, (0, 0, 0), 150)
    paint(base, mask_of(lambda d: d.polygon(hexa, fill=255)), gradient([(24, 12, 60), (44, 16, 92)], 90))
    stroke = mask_of(lambda d: d.line(hexa + [hexa[0]], fill=255, width=26, joint="curve"))
    glow = Image.new("RGBA", (S, S), (120, 200, 255, 0))
    glow.putalpha(stroke.filter(ImageFilter.GaussianBlur(30)))
    base.alpha_composite(glow)
    paint(base, stroke, gradient([(0, 230, 255), (150, 90, 255), (255, 40, 170)], 45))
    faceted_bolt(base, S / 2, S * 0.42, 740, (255, 240, 120), (255, 170, 0), glow=(255, 200, 40))
    text_fill(base, (S / 2, S * 0.80), "BRAWL", font("Exo2.ttf", 300, "Black"),
              gradient([(0, 230, 255), (170, 110, 255), (255, 60, 180)], 0))
    text_fill(base, (S / 2, S * 0.885), "NEWS · ГАЙДЫ · МЕМЫ", font("Exo2.ttf", 74, "Bold"), (210, 220, 255),
              tracking=10, shadow_alpha=0)
    return base


def logo_pop():
    """Современная иконка: сочный градиент, крупная белая монограмма AB со звёздочкой."""
    base = gradient([(255, 70, 120), (140, 50, 245), (40, 170, 255)], 135)
    radial_glow(base, (S * 0.25, S * 0.20), S * 0.35, (255, 200, 120), 120)
    radial_glow(base, (S * 0.80, S * 0.85), S * 0.35, (20, 40, 160), 140)
    glass = mask_of(lambda d: d.ellipse((S * 0.17, S * 0.17, S * 0.83, S * 0.83), fill=255))
    pane = Image.new("RGBA", (S, S), (255, 255, 255, 0))
    pane.putalpha(glass.point(lambda v: v * 34 // 255))
    base.alpha_composite(pane)
    rim = mask_of(lambda d: d.ellipse((S * 0.17, S * 0.17, S * 0.83, S * 0.83), outline=255, width=8))
    paint(base, rim, (255, 255, 255))
    text_fill(base, (S / 2, S * 0.48), "AB", font("Unbounded.ttf", 540, "Black"),
              gradient([(255, 255, 255), (236, 230, 255)], 90), shadow_alpha=170)
    faceted_star(base, S * 0.735, S * 0.30, 150, 64, (255, 222, 90), (255, 244, 190), (240, 150, 20))
    text_fill(base, (S / 2, S * 0.775), "ALL ABOUT BRAWL", font("Unbounded.ttf", 66, "Bold"), (255, 255, 255),
              tracking=12, shadow_alpha=90)
    return base


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "branding")
    out.mkdir(parents=True, exist_ok=True)
    for name, make in (("gold", logo_gold), ("cyber", logo_cyber), ("pop", logo_pop)):
        make().convert("RGB").resize((1024, 1024), Image.LANCZOS).save(out / f"logo-{name}.png", optimize=True)
        print(out / f"logo-{name}.png")


if __name__ == "__main__":
    main()
