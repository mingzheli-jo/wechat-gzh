from dataclasses import dataclass, field
from typing import Any

from lxml import html as lxml_html  # type: ignore[import-untyped]


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
