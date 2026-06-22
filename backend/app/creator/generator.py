"""Build prompts for grounded, divergent article generation.

The writer is given the distilled theme plus numbered excerpts from real
library articles. It is instructed to write expansively but to ground every
fact and figure in the supplied material, cite source numbers, and never invent
data. When no sources were retrieved the prompt switches to a constrained mode
that forbids fabricated specifics.
"""
from typing import Any

from app.ai_providers.base import Message

SYSTEM_BASE = (
    "你是一名资深公众号主笔，擅长围绕一个主题写出有信息量、有观点、能发散展开的深度文章。"
    "你的核心铁律是：所有事实、数据、事件、引述都必须来自下方提供的【参考素材】，"
    "不得凭空编造任何数字、时间、人物或事件。可以发散地组织结构、提出观点和分析，"
    "但具体事实必须有素材支撑；当某个论点缺少素材支撑时，用一般性表述带过，绝不杜撰细节。"
)

GROUNDED_TASK = (
    "请围绕【主题】，结合下方真实【参考素材】（含历史与近期内容）写一篇结构完整的公众号文章。\n"
    "要求：\n"
    "1) 结合素材里的事实与数据展开，引用素材内容时在句末标注来源编号，如 [1][2]；\n"
    "2) 可以纵向结合历史背景、横向结合近期情况，做有深度的发散与分析；\n"
    "3) 不得编造素材中没有的数字、时间、机构或事件；\n"
    "4) 输出 Markdown 格式，可使用 `## 一、`、`### 1.`、`> 导语`、`**强调**`、列表等结构。"
)

NO_SOURCE_TASK = (
    "注意：本次未检索到相关的库内素材。请围绕【主题】写一篇文章，"
    "但只做概念性、框架性的论述，严禁编造任何具体的数字、时间、机构、人物或事件。\n"
    "输出 Markdown 格式。"
)

MAX_THEME_CHARS = 2000


def _account_block(category: str, style_desc: str) -> str:
    parts = [f"【公众号定位】类型：{category}"]
    if style_desc:
        parts.append(f"【公众号风格】{style_desc}")
    return "\n".join(parts)


def _sources_block(sources: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for idx, src in enumerate(sources, start=1):
        title = src.get("title") or "（无标题）"
        excerpt = src.get("excerpt") or ""
        blocks.append(f"[{idx}] 标题：{title}\n内容：{excerpt}")
    return "\n\n".join(blocks)


def build_content_messages(
    *,
    theme: str,
    sources: list[dict[str, Any]],
    category: str = "",
    style_desc: str = "",
    content_prompt: str = "",
) -> list[Message]:
    has_sources = bool(sources)
    system_parts = [SYSTEM_BASE]
    if category or style_desc:
        system_parts.append(_account_block(category, style_desc))
    system_parts.append(GROUNDED_TASK if has_sources else NO_SOURCE_TASK)
    system = "\n\n".join(system_parts)

    user_parts: list[str] = [f"【主题】\n{theme[:MAX_THEME_CHARS]}"]
    if content_prompt:
        user_parts.append(f"【写作要求】{content_prompt}")
    if has_sources:
        user_parts.append("【参考素材】\n" + _sources_block(sources))
    user_parts.append("请直接输出 Markdown 正文，不要包裹在 ```markdown 代码块中。")
    return [
        Message(role="system", content=system),
        Message(role="user", content="\n\n".join(user_parts)),
    ]


def build_title_messages(*, theme: str, style_desc: str = "") -> list[Message]:
    system_parts = [
        "你是一名公众号标题编辑，请为给定主题拟一个有吸引力但不夸张、不做标题党的中文标题。"
    ]
    if style_desc:
        system_parts.append(f"【公众号风格】{style_desc}")
    return [
        Message(role="system", content="\n\n".join(system_parts)),
        Message(
            role="user",
            content=(
                f"【主题】{theme[:MAX_THEME_CHARS]}\n"
                "请直接输出一个标题，不要解释、不要引号包裹。"
            ),
        ),
    ]
