#!/usr/bin/env python3
"""Обложка поста на фоне официального арта Supercell.

python3 tools/make_cover.py images/post.png --bg art.jpg --kind news --title "Заголовок" \
    --subtitle "Подзаголовок" --stat 5000 --stat-label "кубков"
python3 tools/make_cover.py images/meme.png --bg art.jpg --meme "Верх" "Низ"

Фон: кадр из официального ролика или картинка из статьи Supercell (art.py скачивает их
на GitHub). Без --bg получается фирменный градиент. На фоне ставится подпись «Арт: Supercell».
"""
import argparse
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_image import BOLD, HANDLE, KINDS, REGULAR, background  # noqa: E402

W, H = 1280, 720
S = 2  # Рисуем в двойном размере и уменьшаем: края букв получаются гладкими.
NOT_DRAWABLE = re.compile("[\U00010000-\U0010ffff☀-➿️‍]")
CREDIT = ["Арт: Supercell"]  # Подпись источника фона; меняется флагом --credit.


def face(path, size):
    return ImageFont.truetype(path, int(size * S))


def clean(text):
    """Без эмодзи и значков: шрифт их не рисует и вместо них были бы квадратики."""
    import unicodedata

    text = NOT_DRAWABLE.sub("", text or "")
    text = "".join(c for c in text if unicodedata.category(c) not in ("So", "Sk", "Cf", "Co", "Cs", "Mn", "Me"))
    return " ".join(text.split())


def wrap(draw, text, font, width):
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if draw.textlength(candidate, font=font) <= width or not line:
            line = candidate
        else:
            lines.append(line)
            line = word
    return lines + ([line] if line else [])


def fit(draw, text, path, width, max_lines, largest, smallest):
    for size in range(largest, smallest - 1, -4):
        font = face(path, size)
        lines = wrap(draw, text, font, width)
        if len(lines) <= max_lines and all(draw.textlength(l, font=font) <= width for l in lines):
            return font, lines, int(size * 1.12 * S)
    font = face(path, smallest)
    return font, wrap(draw, text, font, width)[:max_lines], int(smallest * 1.12 * S)


FOCUS = [0.5]  # Сдвиг кадрирования по горизонтали: одна и та же картинка выглядит по-разному.


def cover_crop(image, width, height):
    """Кадрирование с лёгким приближением, чтобы при сдвиге было что двигать."""
    image = image.convert("RGB")
    zoom = 1.18
    big = ImageOps.fit(image, (int(width * zoom), int(height * zoom)), Image.LANCZOS, centering=(0.5, 0.4))
    left = int((big.width - width) * FOCUS[0])
    top = int((big.height - height) * 0.4)
    return big.crop((left, top, left + width, top + height))


def art_background(path, width, height, accent):
    """Фото на весь кадр: чуть размыто и затемнено, слева плотнее под текст."""
    photo = cover_crop(Image.open(path), width, height)
    photo = photo.filter(ImageFilter.GaussianBlur(0.5 * S))
    photo = ImageOps.autocontrast(photo, cutoff=1)
    canvas = photo.convert("RGBA")
    shade = Image.new("L", (width, 1))
    for x in range(width):
        t = x / width
        shade.putpixel((x, 0), int(230 - 195 * min(t / 0.7, 1)))
    shade = shade.resize((width, height))
    dark = Image.new("RGBA", (width, height), (8, 6, 22, 255))
    canvas = Image.composite(dark, canvas, shade)
    # Снизу виньетка и лёгкий цветной оттенок рубрики.
    bottom = Image.linear_gradient("L").resize((width, height))
    canvas = Image.composite(Image.new("RGBA", (width, height), (5, 4, 15, 255)), canvas,
                             bottom.point(lambda v: int(v * 0.55)))
    tint = Image.new("RGBA", (width, height), (*accent, 255))
    return Image.blend(canvas, tint, 0.10)


def gradient_background(kind):
    image = background(kind).convert("RGBA")
    return image.resize((W * S, H * S)) if image.size != (W * S, H * S) else image


def pill(draw, x, y, text, fill, ink, size=22):
    font = face(BOLD, size)
    width = draw.textlength(text, font=font)
    pad, height = 22 * S, int(size * 2.0 * S)
    draw.rounded_rectangle((x, y, x + width + 2 * pad, y + height), radius=height // 2, fill=fill)
    draw.text((x + pad, y + height / 2), text, font=font, fill=ink, anchor="lm")
    return x + width + 2 * pad


def shadow_text(draw, xy, text, font, fill, offset=3):
    x, y = xy
    draw.text((x + offset * S, y + offset * S), text, font=font, fill=(0, 0, 0, 160))
    draw.text((x, y), text, font=font, fill=fill)


def photo_background(path, width, height, mode):
    """Кадр для макетов bottom (затемнение снизу) и center (равномерное затемнение)."""
    photo = ImageOps.autocontrast(cover_crop(Image.open(path), width, height), cutoff=1).convert("RGBA")
    if mode == "center":
        return Image.alpha_composite(photo, Image.new("RGBA", (width, height), (8, 6, 22, 150)))
    fade = Image.new("L", (1, height))
    for y in range(height):
        t = max(0.0, (y / height - 0.35) / 0.65)
        fade.putpixel((0, y), int(235 * t ** 1.3))
    shade = Image.new("RGBA", (width, height), (6, 5, 18, 255))
    return Image.composite(shade, photo, fade.resize((width, height)))


def card_alt(output, kind, title, subtitle, stat, stat_label, bg, layout):
    """Макеты bottom (текст на плашке снизу) и center (крупный заголовок по центру)."""
    label, start, end, accent = KINDS.get(kind, KINDS["news"])
    base = photo_background(bg, W * S, H * S, layout) if bg else gradient_background(kind)
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    side = 72 * S
    extra = f"★ {clean(stat)} {clean(stat_label)}".strip() if stat else ""
    if layout == "center":
        width = W * S - 2 * side
        title_font, lines, line_height = fit(draw, clean(title).upper(), BOLD, width, 3, 88, 44)
        sub_font, sub_lines, sub_height = fit(draw, clean(subtitle), REGULAR, width, 2, 32, 24)
        block = len(lines) * line_height + (20 * S + len(sub_lines) * sub_height if sub_lines else 0)
        y = (H * S - block) // 2 + 20 * S
        badge_font = face(BOLD, 22)
        badge_w = draw.textlength(label, font=badge_font) + 44 * S
        pill(draw, int((W * S - badge_w) / 2), y - 90 * S, label, (*accent, 255), (17, 12, 40))
        for line in lines:
            draw.text((W * S // 2, y), line, font=title_font, fill=(255, 255, 255, 255), anchor="ma",
                      stroke_width=4 * S, stroke_fill=(0, 0, 0, 220))
            y += line_height
        y += 20 * S
        for line in sub_lines:
            draw.text((W * S // 2, y), line, font=sub_font, fill=(*accent, 255), anchor="ma",
                      stroke_width=2 * S, stroke_fill=(0, 0, 0, 200))
            y += sub_height
        if extra:
            draw.text((W * S // 2, y + 10 * S), extra, font=face(BOLD, 28), fill=(255, 255, 255, 240), anchor="ma")
        draw.text((W * S // 2, H * S - 40 * S), HANDLE, font=face(BOLD, 20), fill=(255, 255, 255, 200), anchor="ms")
    else:
        width = W * S - 2 * side
        pill(draw, side, 48 * S, label, (*accent, 255), (17, 12, 40))
        draw.text((W * S - side, 48 * S + 22 * S), HANDLE, font=face(BOLD, 22), fill=(255, 255, 255, 230), anchor="rm")
        title_font, lines, line_height = fit(draw, clean(title).upper(), BOLD, width, 2, 72, 40)
        sub_text = " · ".join(filter(None, [clean(subtitle), extra]))
        sub_font, sub_lines, sub_height = fit(draw, sub_text, REGULAR, width, 2, 30, 22)
        y = H * S - 70 * S - len(sub_lines) * sub_height - 14 * S - len(lines) * line_height
        draw.rectangle((side, y - 22 * S, side + 120 * S, y - 14 * S), fill=(*accent, 255))
        for line in lines:
            shadow_text(draw, (side, y), line, title_font, (255, 255, 255, 255))
            y += line_height
        y += 14 * S
        for line in sub_lines:
            shadow_text(draw, (side, y), line, sub_font, (*accent, 255), 2)
            y += sub_height
    if bg:
        anchor_x = W * S - side
        draw.text((anchor_x, H * S - 24 * S), CREDIT[0], font=face(REGULAR, 16), fill=(255, 255, 255, 180), anchor="rs")
    save(Image.alpha_composite(base, layer), output, (W, H))


def card(output, kind, title, subtitle="", stat="", stat_label="", bg=None, layout="left"):
    if layout in ("bottom", "center"):
        return card_alt(output, kind, title, subtitle, stat, stat_label, bg, layout)
    label, start, end, accent = KINDS.get(kind, KINDS["news"])
    base = art_background(bg, W * S, H * S, end) if bg else gradient_background(kind)
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    left = 72 * S
    text_width = int((760 if stat else 900) * S)

    # Верх: рубрика и канал.
    pill(draw, left, 56 * S, label, (*accent, 255), (17, 12, 40))
    handle_font = face(BOLD, 22)
    draw.text((W * S - left, 56 * S + 22 * S), HANDLE, font=handle_font, fill=(255, 255, 255, 230), anchor="rm")

    # Заголовок с акцентной полосой слева.
    title_font, lines, line_height = fit(draw, clean(title).upper(), BOLD, text_width, 3, 76, 40)
    sub_font, sub_lines, sub_height = fit(draw, clean(subtitle), REGULAR, text_width, 2, 32, 24)
    block = len(lines) * line_height + (18 * S + len(sub_lines) * sub_height if sub_lines else 0)
    y = max(170 * S, (H * S - block) // 2 + 10 * S)
    draw.rounded_rectangle((left - 26 * S, y + 8 * S, left - 16 * S, y + block - 6 * S),
                           radius=5 * S, fill=(*accent, 255))
    for line in lines:
        shadow_text(draw, (left, y), line, title_font, (255, 255, 255, 255))
        y += line_height
    if sub_lines:
        y += 18 * S
        for line in sub_lines:
            shadow_text(draw, (left, y), line, sub_font, (235, 235, 245, 255), 2)
            y += sub_height

    # Число в стеклянной плашке справа.
    if stat:
        stat_font, _, _ = fit(draw, clean(stat), BOLD, 300 * S, 1, 92, 40)
        label_font, label_lines, label_height = fit(draw, clean(stat_label), BOLD, 260 * S, 2, 24, 18)
        box = (W * S - 400 * S, H * S // 2 - 120 * S, W * S - 72 * S, H * S // 2 + 120 * S)
        draw.rounded_rectangle(box, radius=28 * S, fill=(10, 8, 30, 170), outline=(*accent, 255), width=3 * S)
        cx = (box[0] + box[2]) // 2
        draw.text((cx, box[1] + 95 * S), clean(stat), font=stat_font, fill=(*accent, 255), anchor="mm")
        ly = box[1] + 165 * S
        for line in label_lines:
            draw.text((cx, ly), line.upper(), font=label_font, fill=(255, 255, 255, 235), anchor="mm")
            ly += label_height

    # Низ: тонкая полоса и подпись арта.
    draw.rectangle((0, H * S - 10 * S, W * S, H * S), fill=(*accent, 255))
    if bg:
        draw.text((W * S - left, H * S - 34 * S), CREDIT[0], font=face(REGULAR, 18),
                  fill=(255, 255, 255, 200), anchor="rm")
    save(Image.alpha_composite(base, layer), output, (W, H))


def meme(output, top, bottom, bg=None, kind="meme"):
    size = 1080 * S
    label, start, end, accent = KINDS["meme"]
    if bg:
        base = cover_crop(Image.open(bg), size, size).filter(ImageFilter.GaussianBlur(0.6 * S)).convert("RGBA")
        fade = Image.new("L", (1, size))
        for yy in range(size):
            t = abs(yy - size / 2) / (size / 2)
            fade.putpixel((0, yy), int(40 + 170 * t ** 1.6))
        base = Image.composite(Image.new("RGBA", (size, size), (0, 0, 0, 255)), base, fade.resize((size, size)))
    else:
        base = gradient_background(kind).resize((size, size))
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    margin = 60 * S
    for text, area_top in ((top, 40 * S), (bottom, size - 360 * S)):
        font, lines, line_height = fit(draw, clean(text).upper(), BOLD, size - 2 * margin, 4, 84, 40)
        y = area_top + (320 * S - len(lines) * line_height) // 2
        for line in lines:
            x = size // 2
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 255), anchor="ma",
                      stroke_width=6 * S, stroke_fill=(0, 0, 0, 255))
            y += line_height
    draw.text((margin, size - 40 * S), HANDLE, font=face(BOLD, 24), fill=(*accent, 255), anchor="ls",
              stroke_width=2 * S, stroke_fill=(0, 0, 0, 255))
    if bg:
        draw.text((size - margin, size - 40 * S), CREDIT[0], font=face(REGULAR, 20), fill=(255, 255, 255, 210),
                  anchor="rs", stroke_width=2 * S, stroke_fill=(0, 0, 0, 255))
    save(Image.alpha_composite(base, layer), output, (1080, 1080))


def save(image, output, size):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").resize(size, Image.LANCZOS).save(output, quality=90, optimize=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--bg")
    parser.add_argument("--kind", default="news", choices=sorted(KINDS))
    parser.add_argument("--title", default="")
    parser.add_argument("--subtitle", default="")
    parser.add_argument("--stat", default="")
    parser.add_argument("--stat-label", default="")
    parser.add_argument("--meme", nargs=2, metavar=("TOP", "BOTTOM"))
    parser.add_argument("--focus", type=float, default=0.5, help="0 левый край кадра, 1 правый")
    parser.add_argument("--credit", default="Арт: Supercell", help="подпись источника фона")
    parser.add_argument("--layout", default="left", choices=["left", "bottom", "center"],
                        help="left: текст слева, bottom: плашка снизу, center: крупно по центру")
    args = parser.parse_args()
    CREDIT[0] = args.credit[:60]
    FOCUS[0] = min(max(args.focus, 0.0), 1.0)
    if args.meme:
        meme(args.output, *args.meme, bg=args.bg)
    else:
        card(args.output, args.kind, args.title, args.subtitle, args.stat, args.stat_label, args.bg, args.layout)


if __name__ == "__main__":
    main()
