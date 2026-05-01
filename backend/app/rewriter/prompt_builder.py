from app.ai_providers.base import Message

SYSTEM_BASE = (
    "你是一名资深公众号内容编辑，专长是改写爆款文章。"
    "请遵循以下要求："
    "1) 保持原文核心信息和事实准确；"
    "2) 调整结构和措辞，避免与原文相似度过高；"
    "3) 使用符合中文公众号读者习惯的表达；"
    "4) 严格遵守相关法规、避免广告法违禁词、避免医疗保健夸大。"
)


def _account_block(category: str, style_desc: str) -> str:
    parts = [f"【公众号定位】类型：{category}"]
    if style_desc:
        parts.append(f"【公众号风格】{style_desc}")
    return "\n".join(parts)


def build_title_messages(
    *,
    account_title_prompt: str,
    category: str,
    style_desc: str,
    original_title: str,
    override: str | None = None,
) -> list[Message]:
    system = "\n\n".join(
        [
            SYSTEM_BASE,
            _account_block(category, style_desc),
            "你现在的任务是改写文章【标题】。",
        ]
    )
    user_parts: list[str] = [f"【标题改写要求】{account_title_prompt}"]
    if override:
        user_parts.append(f"【本次额外要求】{override}")
    user_parts.append(f"【原标题】{original_title}")
    user_parts.append("请直接输出新标题，不要解释、不要引号包裹。")
    return [
        Message(role="system", content=system),
        Message(role="user", content="\n".join(user_parts)),
    ]


def build_content_messages(
    *,
    account_content_prompt: str,
    category: str,
    style_desc: str,
    original_content: str,
    override: str | None = None,
    max_chars: int = 8000,
) -> list[Message]:
    truncated = original_content[:max_chars]
    if len(original_content) > max_chars:
        truncated += "\n[...原文截断]"
    system = "\n\n".join(
        [
            SYSTEM_BASE,
            _account_block(category, style_desc),
            "你现在的任务是改写文章【正文】，输出 HTML 格式（仅段落 <p> 和强调 <strong>）。",
        ]
    )
    user_parts: list[str] = [f"【正文改写要求】{account_content_prompt}"]
    if override:
        user_parts.append(f"【本次额外要求】{override}")
    user_parts.append("【原文】")
    user_parts.append(truncated)
    user_parts.append("请直接输出改写后的 HTML，不要包裹在 ```html 代码块中。")
    return [
        Message(role="system", content=system),
        Message(role="user", content="\n".join(user_parts)),
    ]
