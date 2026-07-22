"""Markdown -> inline-styled HTML for the WeChat 公众号 draft box.

The WeChat editor strips ``<style>`` blocks and ``class`` attributes, so all
typography must live in inline ``style="..."`` attributes. 模板经草稿箱真机
预览定稿（2026-07-22）：17px 正文、1.85 行高、0.6px 字距、两端对齐、22px 段距、
左色条小标题、蓝色加粗强调。全部公众号共用这一套模板。
"""

from typing import Any

import mistune

ACCENT = "#2f6bd8"  # 主色：小标题色条、加粗强调、链接
TEXT = "#3f3f3f"  # 正文柔和黑（比纯黑不刺眼）
HEAD = "#1a1a1a"  # 标题深色
QUOTE_BG = "#f5f7fa"
QUOTE_TEXT = "#555555"

# 外层容器：兜底字号/行距/字距，两端对齐让中文段落边缘整齐
WRAP_STYLE = (
    f"font-size:17px;line-height:1.85;color:{TEXT};letter-spacing:0.6px;"
    "text-align:justify;word-break:break-word;"
)
PARAGRAPH_STYLE = (
    f"margin:22px 0;color:{TEXT};font-size:17px;"
    "line-height:1.85;letter-spacing:0.6px;"
)
H2_STYLE = (
    f"font-size:20px;font-weight:bold;color:{HEAD};line-height:1.5;"
    f"margin:38px 0 18px;padding-left:12px;border-left:4px solid {ACCENT};"
)
H3_STYLE = (
    f"font-size:17px;font-weight:bold;color:{HEAD};"
    "margin:28px 0 14px;line-height:1.6;"
)
BLOCKQUOTE_STYLE = (
    f"border-left:3px solid {ACCENT};background:{QUOTE_BG};"
    f"padding:14px 18px;margin:24px 0;color:{QUOTE_TEXT};"
    "font-size:16px;line-height:1.8;letter-spacing:0.4px;border-radius:4px;"
)
UL_STYLE = "padding-left:1.3em;margin:20px 0;"
OL_STYLE = "padding-left:1.5em;margin:20px 0;"
LI_STYLE = (
    f"font-size:17px;line-height:1.85;color:{TEXT};"
    "margin:10px 0;letter-spacing:0.6px;"
)
STRONG_STYLE = f"color:{ACCENT};font-weight:bold;"
# 中文没有斜体传统，*emphasis* 渲染为深色加粗而非 italic
EMPHASIS_STYLE = "font-style:normal;font-weight:bold;color:#222222;"
LINK_STYLE = f"color:{ACCENT};text-decoration:underline;"
HR_STYLE = (
    "border:none;border-top:1px solid #e6e6e6;width:60px;"
    "margin:34px auto;height:0;"
)


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

    def thematic_break(self) -> str:
        return f'<hr style="{HR_STYLE}"/>\n'

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
    body = out if isinstance(out, str) else "".join(str(x) for x in out)
    return f'<section style="{WRAP_STYLE}">\n{body}</section>'
