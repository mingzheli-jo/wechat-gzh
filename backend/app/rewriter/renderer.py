"""Markdown -> inline-styled HTML for the WeChat 公众号 draft box.

The WeChat editor strips ``<style>`` blocks and ``class`` attributes, so all
typography must live in inline ``style="..."`` attributes. The theme below
matches the reference 公众号 layout: blue accent section headings, a light
blue intro/quote box, generously spaced paragraphs, and emphasis tied to the
accent color.
"""

from typing import Any

import mistune

ACCENT = "#3b82f6"
TEXT = "#333333"
QUOTE_BG = "#eef5fb"
QUOTE_BAR = "#5b9bd5"

PARAGRAPH_STYLE = (
    f"font-size:16px;line-height:1.75;color:{TEXT};margin:14px 0;"
)
H2_STYLE = (
    f"font-size:20px;font-weight:bold;color:{ACCENT};"
    "margin:32px 0 16px;line-height:1.4;"
)
H3_STYLE = (
    f"font-size:17px;font-weight:bold;color:{TEXT};"
    "margin:24px 0 12px;line-height:1.5;"
)
BLOCKQUOTE_STYLE = (
    f"border-left:4px solid {QUOTE_BAR};background:{QUOTE_BG};"
    f"padding:12px 16px;margin:18px 0;color:{TEXT};"
    "font-size:15px;line-height:1.7;border-radius:2px;"
)
UL_STYLE = "padding-left:1.4em;margin:14px 0;"
OL_STYLE = "padding-left:1.6em;margin:14px 0;"
LI_STYLE = f"font-size:16px;line-height:1.75;color:{TEXT};margin:6px 0;"
STRONG_STYLE = f"color:{ACCENT};font-weight:bold;"
EMPHASIS_STYLE = "font-style:italic;"
LINK_STYLE = f"color:{ACCENT};text-decoration:underline;"


class _WeChatRenderer(mistune.HTMLRenderer):
    def paragraph(self, text: str) -> str:
        return f'<p style="{PARAGRAPH_STYLE}">{text}</p>\n'

    def heading(self, text: str, level: int, **attrs: Any) -> str:
        if level <= 2:
            return f'<h2 style="{H2_STYLE}">{text}</h2>\n'
        return f'<h3 style="{H3_STYLE}">{text}</h3>\n'

    def block_quote(self, text: str) -> str:
        return f'<blockquote style="{BLOCKQUOTE_STYLE}">{text}</blockquote>\n'

    def list(self, text: str, ordered: bool, **attrs: Any) -> str:
        tag = "ol" if ordered else "ul"
        style = OL_STYLE if ordered else UL_STYLE
        return f'<{tag} style="{style}">\n{text}</{tag}>\n'

    def list_item(self, text: str) -> str:
        return f'<li style="{LI_STYLE}">{text}</li>\n'

    def strong(self, text: str) -> str:
        return f'<strong style="{STRONG_STYLE}">{text}</strong>'

    def emphasis(self, text: str) -> str:
        return f'<em style="{EMPHASIS_STYLE}">{text}</em>'

    def link(self, text: str, url: str, title: str | None = None) -> str:
        safe_url = mistune.escape_url(url)
        title_attr = f' title="{mistune.escape(title)}"' if title else ""
        return (
            f'<a href="{safe_url}"{title_attr} '
            f'style="{LINK_STYLE}">{text}</a>'
        )


_markdown = mistune.create_markdown(
    renderer=_WeChatRenderer(escape=False),
    plugins=["strikethrough"],
)


def render_markdown(md: str) -> str:
    """Convert Markdown to inline-styled HTML suitable for WeChat draft push."""
    if not md or not md.strip():
        return ""
    out = _markdown(md)
    return out if isinstance(out, str) else "".join(str(x) for x in out)
