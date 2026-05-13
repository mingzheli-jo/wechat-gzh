from pathlib import Path

import pytest
from PIL import Image

from app.image_composer.compose import compose
from app.image_posts.models import ImagePostTemplate
from app.image_posts.templates import TEMPLATES


@pytest.fixture
def font_path() -> Path:
    return Path("app/image_composer/fonts/SourceHanSansSC-Bold.otf")


@pytest.fixture
def fake_panel(tmp_path) -> Path:
    """Create a simple solid-color square as a fake panel image."""
    img = Image.new("RGB", (1024, 1024), color=(200, 150, 100))
    p = tmp_path / "panel.png"
    img.save(p)
    return p


def test_compose_two_panel_contrast_produces_output(
    tmp_path, fake_panel, font_path
):
    template = TEMPLATES[ImagePostTemplate.two_panel_contrast]
    panel_paths = [fake_panel, fake_panel]
    captions = ["上文案", "下文案"]
    output = tmp_path / "out.png"
    compose(
        template=template,
        panel_paths=panel_paths,
        captions=captions,
        watermark="公众号·测试",
        font_path=font_path,
        output_path=output,
    )
    assert output.exists()
    img = Image.open(output)
    assert img.size == template.output_size
    assert img.mode == "RGB"


def test_compose_truncates_overly_long_caption(
    tmp_path, fake_panel, font_path
):
    template = TEMPLATES[ImagePostTemplate.two_panel_contrast]
    long_caption = "这是一个特别长的文案" * 10  # 100 字
    output = tmp_path / "long.png"
    # 不应抛异常
    compose(
        template=template,
        panel_paths=[fake_panel, fake_panel],
        captions=[long_caption, "短"],
        watermark="wm",
        font_path=font_path,
        output_path=output,
    )
    assert output.exists()


def test_compose_single_panel_caption(tmp_path, fake_panel, font_path):
    template = TEMPLATES[ImagePostTemplate.single_panel_caption]
    output = tmp_path / "single.png"
    compose(
        template=template,
        panel_paths=[fake_panel],
        captions=["还没下班 但已经累了"],
        watermark="公众号·测试",
        font_path=font_path,
        output_path=output,
    )
    assert output.exists()
    img = Image.open(output)
    assert img.size == template.output_size
