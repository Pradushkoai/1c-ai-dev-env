#!/usr/bin/env python3
"""
img_grid.py — Наложение сетки на изображение для определения пропорций колонок.

Полезно при анализе печатных форм (MXL-макетов): LLM может "посчитать квадраты"
и определить точные ширины колонок для генерации макета по скриншоту.

Позаимствовано из 1c-ai-development-kit (skill /img-grid).

Использование:
    python3 scripts/img_grid.py <image> [-c COLS] [-r ROWS] [-o OUTPUT]

Пример:
    python3 scripts/img_grid.py form.png -c 50 -o form-grid.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

MARGIN_TOP = 20
MARGIN_LEFT = 24


def overlay_grid(
    image_path: Path,
    cols: int = 50,
    rows: int = 0,
    output_path: Path | None = None,
) -> Path:
    """Наложить пронумерованную сетку на изображение.

    Args:
        image_path: путь к исходному изображению (PNG, JPG)
        cols: количество вертикальных делений (default: 50)
        rows: количество горизонтальных делений (0 = авто, квадратные ячейки)
        output_path: путь для результата (default: <name>-grid.<ext>)

    Returns:
        Путь к созданному изображению с сеткой
    """
    if not HAS_PIL:
        raise ImportError("Pillow не установлен. Установите: pip install Pillow")

    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Изображение не найдено: {image_path}")

    src = Image.open(image_path).convert("RGBA")
    sw, sh = src.size

    cols = max(2, cols)
    step_x = sw / cols
    rows = rows if rows > 0 else round(sh / step_x)
    rows = max(2, rows)
    step_y = sh / rows

    # Холст с полями для меток
    cw = MARGIN_LEFT + sw
    ch = MARGIN_TOP + sh
    canvas = Image.new("RGBA", (cw, ch), (255, 255, 255, 255))
    canvas.paste(src, (MARGIN_LEFT, MARGIN_TOP))

    overlay = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Шрифт для меток
    label_font_size = 12
    try:
        # Пробуем разные шрифты
        for font_name in ["arial.ttf", "DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
            try:
                label_font = ImageFont.truetype(font_name, label_font_size)
                break
            except OSError:
                continue
        else:
            label_font = ImageFont.load_default()
    except Exception:
        label_font = ImageFont.load_default()

    # Вертикальные линии + числа в верхнем поле
    for i in range(cols + 1):
        x = MARGIN_LEFT + round(i * step_x)
        major = i % 10 == 0
        mid = i % 5 == 0

        alpha = 160 if major else (110 if mid else 40)
        lw = 2 if major else 1
        draw.line([(x, MARGIN_TOP), (x, ch)], fill=(255, 0, 0, alpha), width=lw)

        show_label = major or mid or step_x >= 20
        if show_label:
            label = str(i)
            bbox = label_font.getbbox(label)
            tw = bbox[2] - bbox[0]
            tx = x - tw // 2
            ty = 2
            color = (200, 0, 0, 255) if (major or mid) else (200, 0, 0, 180)
            draw.text((tx, ty), label, fill=color, font=label_font)

    # Горизонтальные линии + числа в левом поле
    for j in range(rows + 1):
        y = MARGIN_TOP + round(j * step_y)
        major = j % 10 == 0
        mid = j % 5 == 0

        alpha = 160 if major else (110 if mid else 40)
        lw = 2 if major else 1
        draw.line([(0, y), (cw, y)], fill=(0, 0, 255, alpha), width=lw)

        show_label = major or mid or step_y >= 20
        if show_label:
            label = str(j)
            try:
                bbox = label_font.getbbox(label)
                th = bbox[3] - bbox[1]
                ty = y - th // 2
            except Exception:
                ty = y - 6
            tx = 2
            color = (0, 0, 200, 255) if (major or mid) else (0, 0, 200, 180)
            draw.text((tx, ty), label, fill=color, font=label_font)

    # Комбинируем
    result = Image.alpha_composite(canvas, overlay).convert("RGB")

    # Выходной путь
    if output_path is None:
        output_path = image_path.parent / f"{image_path.stem}-grid{image_path.suffix}"
    else:
        output_path = Path(output_path)

    result.save(output_path)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Наложить пронумерованную сетку на изображение")
    parser.add_argument("image", help="Путь к изображению (PNG, JPG)")
    parser.add_argument("-c", "--cols", type=int, default=50, help="Количество вертикальных делений (default: 50)")
    parser.add_argument("-r", "--rows", type=int, default=0, help="Количество горизонтальных делений (0 = авто)")
    parser.add_argument("-o", "--output", help="Путь для результата")
    args = parser.parse_args()

    try:
        result = overlay_grid(
            Path(args.image),
            cols=args.cols,
            rows=args.rows,
            output_path=Path(args.output) if args.output else None,
        )
        print(f"✅ Сетка наложена: {result}")
        print(f"   Делений: {args.cols} вертикальных")
    except FileNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
    except ImportError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
