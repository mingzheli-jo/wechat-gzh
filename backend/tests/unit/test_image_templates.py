import pytest

from app.image_posts.models import ImagePostTemplate
from app.image_posts.templates import TEMPLATES, TemplateConfig


def test_templates_has_two_panel_contrast():
    assert ImagePostTemplate.two_panel_contrast in TEMPLATES
    cfg = TEMPLATES[ImagePostTemplate.two_panel_contrast]
    assert isinstance(cfg, TemplateConfig)
    assert cfg.panel_count == 2
    assert cfg.caption_count == 2


def test_templates_has_single_panel_caption():
    assert ImagePostTemplate.single_panel_caption in TEMPLATES
    cfg = TEMPLATES[ImagePostTemplate.single_panel_caption]
    assert cfg.panel_count == 1
    assert cfg.caption_count == 1


def test_caption_prompt_format_contains_topic_and_tone():
    cfg = TEMPLATES[ImagePostTemplate.two_panel_contrast]
    prompt = cfg.caption_prompt_template.format(topic="测试主题", tone="自嘲")
    assert "测试主题" in prompt
    assert "自嘲" in prompt


def test_template_config_is_frozen():
    cfg = TEMPLATES[ImagePostTemplate.two_panel_contrast]
    with pytest.raises((AttributeError, Exception)):
        cfg.panel_count = 99  # type: ignore[misc]
