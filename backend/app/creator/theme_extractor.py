"""Distill a source article into a ~100 character theme using the lite role."""
from app.ai_providers.base import BaseProvider, Message, TokenUsage

PROMPT = """你是一名资深内容编辑。请阅读下面的文章，提炼它的核心主题。
要求：
1) 用一段约 100 字（80-120 字）的中文概括文章的核心议题、立场与关键看点；
2) 只概括主题，不要复述全文，不要加标题、不要加引号、不要分点；
3) 直接输出这段主题文字，不要任何额外说明。"""

# Cap the source text fed to the model; theme extraction needs the gist, not
# the full article, and over-long input wastes tokens.
MAX_SOURCE_CHARS = 6000


async def extract_theme(
    *,
    provider: BaseProvider,
    model: str,
    content: str,
) -> tuple[str, TokenUsage]:
    truncated = content[:MAX_SOURCE_CHARS]
    result = await provider.chat(
        [
            Message(role="system", content=PROMPT),
            Message(role="user", content=f"【文章原文】\n{truncated}"),
        ],
        model=model,
        temperature=0.3,
    )
    theme = (result.content or "").strip()
    if not theme:
        raise ValueError("主题提炼返回为空")
    return theme, result.usage
