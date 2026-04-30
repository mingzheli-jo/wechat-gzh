from pathlib import Path

from app.crawler.parser import parse_wechat_article

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_article.html"


def test_parse_extracts_title_author_content_images():
    html = FIXTURE.read_text(encoding="utf-8")
    result = parse_wechat_article(html)
    assert result.title == "真实测试标题"
    assert result.author == "公众号作者名"
    assert "第一段正文" in result.content_text
    assert len(result.images) == 2
    assert result.images[0]["url"] == "https://mmbiz.qpic.cn/img1.jpg"
    assert result.images[0]["position"] == 0
    assert result.images[1]["position"] == 1
    assert "<p>" in result.content_html


def test_parse_handles_missing_title():
    html = "<html><body><div id='js_content'><p>x</p></div></body></html>"
    result = parse_wechat_article(html)
    assert result.title is None
    assert "x" in result.content_text
