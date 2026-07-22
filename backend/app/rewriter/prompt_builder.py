from app.ai_providers.base import Message

SYSTEM_BASE = (
    "你在为一个中文公众号改写文章。请遵循以下要求："
    "1) 保持原文核心信息和事实准确；"
    "2) 调整结构和措辞，避免与原文相似度过高；"
    "3) 严格遵守相关法规、避免广告法违禁词、避免医疗保健夸大。"
    "\n注意：【正文改写要求】里可能给你设定了具体身份和口吻（例如'你不是编辑，"
    "你是一个普通人'）。若与本段有冲突，一律以【正文改写要求】为准。"
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
    rewritten_content: str = "",
    override: str | None = None,
    max_content_chars: int = 4000,
) -> list[Message]:
    system = "\n\n".join(
        [
            SYSTEM_BASE,
            _account_block(category, style_desc),
            (
                "你现在的任务是给一篇【已改写好的正文】起标题。\n"
                "标题必须概括这篇正文实际写了什么，而不是改写原标题——"
                "原标题只作参考，正文才是准绳。\n"
                "如果正文讲了好几件事，标题不要只咬住其中一件，"
                "要么提炼共同的主线，要么落在最有代表性、最能勾人的那个点上，"
                "但不能让读者点进来发现正文跟标题对不上。"
            ),
        ]
    )
    user_parts: list[str] = [f"【标题创作要求】{account_title_prompt}"]
    if override:
        user_parts.append(f"【本次额外要求】{override}")
    user_parts.append(f"【原标题（仅供参考，不要照搬其框架）】{original_title}")
    if rewritten_content.strip():
        body = rewritten_content.strip()[:max_content_chars]
        user_parts.append(f"【已改写好的正文】\n{body}")
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
    corrections: str = "",
    max_chars: int = 8000,
) -> list[Message]:
    truncated = original_content[:max_chars]
    if len(original_content) > max_chars:
        truncated += "\n[...原文截断]"
    system = "\n\n".join(
        [
            SYSTEM_BASE,
            _account_block(category, style_desc),
            (
                "你现在的任务是改写文章【正文】，输出 Markdown 格式。\n"
                "排版一律以【正文改写要求】为准：那里规定或禁止了什么结构，就照它执行。\n"
                "【正文改写要求】没有提到的部分，默认保持克制——以自然段为主，"
                "不主动添加小标题、导语引用块、加粗和列表。\n"
                "注意：不要为了『看起来有层次』而套用编号小标题，"
                "多数公众号文体靠自然段推进即可。"
            ),
        ]
    )
    user_parts: list[str] = [f"【正文改写要求】{account_content_prompt}"]
    if override:
        user_parts.append(f"【本次额外要求】{override}")
    if corrections.strip():
        # 自动重试时回灌上一稿的审核问题。放在原文之前，确保模型先看到禁令。
        user_parts.append(
            "【上一稿被判定违规，必须修正】\n"
            f"{corrections.strip()}\n"
            "重写时务必避开以上问题。这是硬性要求，优先级高于其他表达偏好。"
        )
    user_parts.append("【原文】")
    user_parts.append(truncated)
    user_parts.append("请直接输出改写后的 Markdown 正文，不要包裹在 ```markdown 代码块中。")
    return [
        Message(role="system", content=system),
        Message(role="user", content="\n".join(user_parts)),
    ]
