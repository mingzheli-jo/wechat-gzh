"""Pillow-based composition for AI image posts."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.image_posts.templates import TemplateConfig

_PANEL_MARGIN_RATIO = 0.03
_CAPTION_VERTICAL_PADDING_RATIO = 0.02
_WATERMARK_FONT_RATIO = 0.018


def compose(
    *,
    template: TemplateConfig,
    panel_paths: list[Path],
    captions: list[str],
    watermark: str,
    font_path: Path,
    output_path: Path,
) -> None:
    if template.composition == "vertical_stack":
        _compose_vertical_stack(
            template, panel_paths, captions, watermark, font_path, output_path
        )
    elif template.composition == "single":
        _compose_single(
            template, panel_paths[0], captions[0], watermark, font_path, output_path
        )
    else:
        raise ValueError(f"unknown composition: {template.composition}")


def _measure_text_width(font: ImageFont.FreeTypeFont, text: str) -> int:
    bbox = font.getbbox(text)
    return int(bbox[2] - bbox[0])


def _fit_caption_to_width(
    font_path: Path, base_size: int, text: str, max_width: int
) -> tuple[ImageFont.FreeTypeFont, str]:
    """Shrink font and/or truncate so text fits in max_width."""
    size = base_size
    while size > 14:
        font = ImageFont.truetype(str(font_path), size)
        if _measure_text_width(font, text) <= max_width:
            return font, text
        size -= 2
    font = ImageFont.truetype(str(font_path), size)
    while text and _measure_text_width(font, text + "…") > max_width:
        text = text[:-1]
    return font, (text + "…" if text else "")


def _compose_vertical_stack(
    template: TemplateConfig,
    panel_paths: list[Path],
    captions: list[str],
    watermark: str,
    font_path: Path,
    output_path: Path,
) -> None:
    """[caption1][panel1][caption2][panel2][watermark]"""
    width, height = template.output_size
    panel_count = template.panel_count
    base_font_size = int(width * template.font_size_ratio)

    margin = int(width * _PANEL_MARGIN_RATIO)
    panel_w = width - 2 * margin
    panel_h = panel_w  # 正方形 panel
    caption_band_h = int(base_font_size * 2.2)  # 留单行余量
    watermark_h = int(base_font_size * 1.2)

    total_content_h = (caption_band_h + panel_h) * panel_count + watermark_h
    bg_color = (255, 255, 255)
    canvas = Image.new("RGB", (width, height), bg_color)

    if total_content_h > height:
        # 等比缩 panel
        avail_for_panels = height - watermark_h - caption_band_h * panel_count
        panel_h = max(50, avail_for_panels // panel_count)
        total_content_h = (caption_band_h + panel_h) * panel_count + watermark_h

    start_y = (height - total_content_h) // 2
    y = max(0, start_y)
    draw = ImageDraw.Draw(canvas)

    for i in range(panel_count):
        caption = captions[i] if i < len(captions) else ""
        font, fitted = _fit_caption_to_width(
            font_path, base_font_size, caption, int(width * 0.9)
        )
        text_w = _measure_text_width(font, fitted)
        text_x = (width - text_w) // 2
        text_y = y + (caption_band_h - font.size) // 2
        draw.text((text_x, text_y), fitted, font=font, fill=(20, 20, 20))
        y += caption_band_h

        panel = Image.open(panel_paths[i]).convert("RGB")
        panel = panel.resize((panel_w, panel_h), Image.Resampling.LANCZOS)
        canvas.paste(panel, (margin, y))
        y += panel_h

    # Watermark — half-transparent gray
    wm_size = max(10, int(width * _WATERMARK_FONT_RATIO))
    wm_font = ImageFont.truetype(str(font_path), wm_size)
    wm_w = _measure_text_width(wm_font, watermark)
    wm_x = (width - wm_w) // 2
    wm_y = height - watermark_h + (watermark_h - wm_size) // 2
    draw.text((wm_x, wm_y), watermark, font=wm_font, fill=(160, 160, 160))

    canvas.save(output_path, format="PNG")


def _compose_single(
    template: TemplateConfig,
    panel_path: Path,
    caption: str,
    watermark: str,
    font_path: Path,
    output_path: Path,
) -> None:
    """[big caption][panel][watermark]"""
    width, height = template.output_size
    base_font_size = int(width * template.font_size_ratio)

    margin = int(width * _PANEL_MARGIN_RATIO)
    panel_w = width - 2 * margin
    panel_h = panel_w
    caption_band_h = int(base_font_size * 2.5)
    watermark_h = int(base_font_size * 0.8)

    total_h = caption_band_h + panel_h + watermark_h
    if total_h > height:
        panel_h = max(50, height - caption_band_h - watermark_h)
        total_h = caption_band_h + panel_h + watermark_h

    start_y = (height - total_h) // 2
    y = max(0, start_y)

    canvas = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    font, fitted = _fit_caption_to_width(
        font_path, base_font_size, caption, int(width * 0.9)
    )
    text_w = _measure_text_width(font, fitted)
    text_x = (width - text_w) // 2
    text_y = y + (caption_band_h - font.size) // 2
    draw.text((text_x, text_y), fitted, font=font, fill=(20, 20, 20))
    y += caption_band_h

    panel = Image.open(panel_path).convert("RGB")
    panel = panel.resize((panel_w, panel_h), Image.Resampling.LANCZOS)
    canvas.paste(panel, (margin, y))
    y += panel_h

    wm_size = max(10, int(width * _WATERMARK_FONT_RATIO))
    wm_font = ImageFont.truetype(str(font_path), wm_size)
    wm_w = _measure_text_width(wm_font, watermark)
    wm_x = (width - wm_w) // 2
    wm_y = y + (watermark_h - wm_size) // 2
    draw.text((wm_x, wm_y), watermark, font=wm_font, fill=(160, 160, 160))

    canvas.save(output_path, format="PNG")
