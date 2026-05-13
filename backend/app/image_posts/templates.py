"""Image post template configurations (caption prompts + composition layout)."""
from dataclasses import dataclass
from typing import Literal

from app.image_posts.models import ImagePostTemplate


@dataclass(frozen=True)
class TemplateConfig:
    key: ImagePostTemplate
    panel_count: int
    caption_count: int
    caption_max_chars: int
    caption_prompt_template: str
    composition: Literal["vertical_stack", "single"]
    caption_position: Literal["top_of_each_panel", "top_of_image"]
    output_size: tuple[int, int]      # (width, height)
    font_size_ratio: float


TWO_PANEL_CONTRAST_PROMPT = """你是一名公众号表情包文案作者。基于主题，生成两条对比/反差文案。

主题：{topic}
语气：{tone}
要求：
- 每条 8-14 个汉字
- 上下两条形成「前后/对立/反讽」结构
- 通俗、口语化、有梗
- 同时给出每格的英文场景描述（用于 AI 出图，要包含角色、动作、环境）

输出 JSON：
{{
  "captions": ["上文案", "下文案"],
  "scene_prompts": ["panel 1 scene in English", "panel 2 scene in English"]
}}
"""

SINGLE_PANEL_CAPTION_PROMPT = """你是一名公众号金句作者。基于主题，生成一句扎心/共鸣/自嘲的金句。

主题：{topic}
语气：{tone}
要求：
- 12-20 个汉字
- 单句独立成立，无需对仗
- 适合做封面大字
- 同时给出对应英文场景描述（用于 AI 出图，要包含角色、动作、情绪）

输出 JSON：
{{
  "captions": ["金句"],
  "scene_prompts": ["scene in English"]
}}
"""


TEMPLATES: dict[ImagePostTemplate, TemplateConfig] = {
    ImagePostTemplate.two_panel_contrast: TemplateConfig(
        key=ImagePostTemplate.two_panel_contrast,
        panel_count=2,
        caption_count=2,
        caption_max_chars=14,
        caption_prompt_template=TWO_PANEL_CONTRAST_PROMPT,
        composition="vertical_stack",
        caption_position="top_of_each_panel",
        output_size=(750, 1600),
        font_size_ratio=0.06,
    ),
    ImagePostTemplate.single_panel_caption: TemplateConfig(
        key=ImagePostTemplate.single_panel_caption,
        panel_count=1,
        caption_count=1,
        caption_max_chars=20,
        caption_prompt_template=SINGLE_PANEL_CAPTION_PROMPT,
        composition="single",
        caption_position="top_of_image",
        output_size=(1024, 1280),
        font_size_ratio=0.10,
    ),
}
