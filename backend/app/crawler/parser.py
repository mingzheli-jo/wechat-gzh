import re
from dataclasses import dataclass, field
from typing import Any

from lxml import html as lxml_html  # type: ignore[import-untyped]
from readability import Document  # type: ignore[import-untyped]


class ParseError(Exception):
    """正文解析失败：页面结构不认识，或抽出来的正文短到不像文章。"""


@dataclass
class ParsedArticle:
    title: str | None
    author: str | None
    content_html: str
    content_text: str
    images: list[dict[str, Any]] = field(default_factory=list)


def parse_wechat_article(html_text: str) -> ParsedArticle:
    tree = lxml_html.fromstring(html_text)

    title_node = tree.xpath("//*[@id='activity-name']")
    title = title_node[0].text_content().strip() if title_node else None

    author_node = tree.xpath("//*[@id='js_name']")
    author = author_node[0].text_content().strip() if author_node else None

    content_node = tree.xpath("//*[@id='js_content']")
    if not content_node:
        return ParsedArticle(
            title=title,
            author=author,
            content_html="",
            content_text="",
            images=[],
        )

    container = content_node[0]
    images: list[dict[str, Any]] = []
    for idx, img in enumerate(container.xpath(".//img")):
        url = img.get("data-src") or img.get("src")
        if not url:
            continue
        images.append({"url": url, "alt": img.get("alt", ""), "position": idx})

    content_html = lxml_html.tostring(container, encoding="unicode")
    content_text = container.text_content().strip()
    return ParsedArticle(
        title=title,
        author=author,
        content_html=content_html,
        content_text=content_text,
        images=images,
    )


# 通用解析判定为「真正文」的最低中文字符数。导航栏、版权样板、
# 反爬提示页都过不了这条线；宁可判失败，也不要把空壳素材写进素材库
# ——检索到空素材比检索不到更糟。
MIN_GENERIC_CHINESE_CHARS = 100

_CHINESE_RE = re.compile(r"[一-鿿]")


def parse_generic_article(html_text: str) -> ParsedArticle:
    """解析非微信的普通新闻页（腾讯新闻/搜狐/政府网等）。

    微信文章结构固定，有专用 xpath；普通新闻站每家都不一样，交给
    readability 的通用正文抽取。作者一律留空——各站署名位置不统一，
    与其猜错不如不写。
    """
    try:
        doc = Document(html_text)
        summary_html = doc.summary(html_partial=True)
        title = (doc.short_title() or "").strip() or None
    except Exception as exc:  # readability 对畸形页面会抛 Unparseable 等
        raise ParseError(f"通用正文抽取失败: {exc!r}") from exc

    try:
        container = lxml_html.fromstring(summary_html)
    except Exception as exc:
        raise ParseError(f"正文 HTML 无法解析: {exc!r}") from exc

    images: list[dict[str, Any]] = []
    for idx, img in enumerate(container.xpath(".//img")):
        url = img.get("data-src") or img.get("src") or ""
        # 只要绝对 http(s) 地址：相对路径和 data: 内联图下载不了。
        if not url.startswith(("http://", "https://")):
            continue
        images.append({"url": url, "alt": img.get("alt", ""), "position": idx})

    content_text = re.sub(r"\n{3,}", "\n\n", container.text_content()).strip()
    chinese_chars = len(_CHINESE_RE.findall(content_text))
    if chinese_chars < MIN_GENERIC_CHINESE_CHARS:
        raise ParseError(
            f"正文过短（中文字符 {chinese_chars} < {MIN_GENERIC_CHINESE_CHARS}），"
            "多半没抽到真正文"
        )

    return ParsedArticle(
        title=title,
        author=None,
        content_html=lxml_html.tostring(container, encoding="unicode"),
        content_text=content_text,
        images=images,
    )
