"""Strip the internal source-citation markers before the article goes public.

The generator prompt asks the writer to tag borrowed facts with the source
number it was given (``[1]``, ``[2]`` …, see ``creator/generator.py``). Those
numbers are an internal grounding device: they keep the writer honest and let
``reviewer/grounding.py`` line claims up against the retrieved excerpts. They
are meaningless to a 公众号 reader — the source list is never published — so
they must be removed on the way out.

The raw Markdown is kept as-is in ``generated_content_md`` (fact-check input
and audit trail); only the rendered HTML is cleaned.
"""
import re

# 一组引用标记：方括号内只允许纯数字，以及数字之间的连接符（1-3 / 1,2 / 1、2）。
# 半角 []、全角 ［］、中文 【】 都收，模型输出这三种都见过。
# 负向前瞻排除 Markdown 链接 `[1](url)` 和引用式定义 `[1]: url`，
# 避免把正常链接拆成裸露的 `(url)`。
_GROUP = (
    r"[\[［【]\s*\d+(?:\s*[-–—,，、]\s*\d+)*\s*[\]］】]"
    r"(?![(（:：])"
)
# 连续多组（[1][2][3]）一并吃掉，前后的行内空白也一起处理，
# 但不吃换行——否则会把段落粘连起来。
_CITATION_RE = re.compile(rf"[ \t]*(?:{_GROUP})+[ \t]*")


def _is_ascii_word(ch: str) -> bool:
    return bool(ch) and ch.isascii() and ch.isalnum()


def _replace(match: re.Match[str]) -> str:
    """Drop the marker, keeping a single space only between ASCII words.

    ``结论。[1] 下一句`` -> ``结论。下一句``（中文之间不留空格）
    ``Fig [1] shows``   -> ``Fig shows``（英文之间必须留一个空格）
    """
    text = match.string
    start, end = match.span()
    prev_ch = text[start - 1] if start > 0 else ""
    next_ch = text[end] if end < len(text) else ""
    if _is_ascii_word(prev_ch) and _is_ascii_word(next_ch):
        return " "
    return ""


def strip_citation_markers(md: str) -> str:
    """Remove ``[n]`` style source markers from generated Markdown."""
    if not md:
        return md
    cleaned = _CITATION_RE.sub(_replace, md)
    # 标记常挂在句末，摘掉后可能留下行尾空白。
    return re.sub(r"[ \t]+$", "", cleaned, flags=re.MULTILINE)
