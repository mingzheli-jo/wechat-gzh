from pathlib import Path

import pytest

from app.crawler.parser import (
    ParseError,
    parse_generic_article,
    parse_wechat_article,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_article.html"

# 一篇像样的新闻页：导航/页脚样板 + 真正文，正文中文字数过线。
_NEWS_BODY = "养老金上调的通知已经下发，各地正在按新的计发办法执行。" * 8
NEWS_HTML = f"""<html><head><title>养老金上调通知下发_财经频道</title></head>
<body>
  <div class="nav"><a href="/">首页</a><a href="/finance">财经</a></div>
  <div class="article">
    <h1>养老金上调通知下发</h1>
    <p>{_NEWS_BODY}</p>
    <p>{_NEWS_BODY}</p>
    <img src="https://inews.qq.com/pic1.jpg" alt="配图"/>
    <img src="/relative/pic2.jpg" alt="相对路径"/>
    <img src="data:image/png;base64,AAAA" alt="内联"/>
  </div>
  <div class="footer">版权所有 京ICP备00000000号</div>
</body></html>"""


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


def test_generic_parse_extracts_title_content_and_absolute_images():
    result = parse_generic_article(NEWS_HTML)
    assert result.title is not None
    assert "养老金上调" in result.title
    assert "计发办法" in result.content_text
    # 导航和页脚样板不该混进正文
    assert "京ICP备" not in result.content_text
    # 只收绝对地址的图：相对路径和 data: 内联图下载不了
    assert [img["url"] for img in result.images] == [
        "https://inews.qq.com/pic1.jpg"
    ]
    assert result.images[0]["position"] == 0
    # 各站署名位置不统一，通用解析一律不猜作者
    assert result.author is None


def test_generic_parse_rejects_boilerplate_only_page():
    html = (
        "<html><body><div class='nav'>首页 财经 体育</div>"
        "<div class='footer'>版权所有</div></body></html>"
    )
    with pytest.raises(ParseError):
        parse_generic_article(html)


def test_generic_parse_rejects_unparseable_input():
    with pytest.raises(ParseError):
        parse_generic_article("")


def test_generic_parse_keeps_protocol_relative_images():
    """//host/x.jpg 是新闻站常见写法，补协议后能下载，不该被当相对路径丢掉。"""
    body = "养老金上调的通知已经下发，各地正在按新的计发办法执行。" * 8
    html = (
        f"<html><body><div class='article'><p>{body}</p><p>{body}</p>"
        "<img src='//img.inews.qq.com/pic.jpg'/></div></body></html>"
    )
    result = parse_generic_article(html)
    assert [i["url"] for i in result.images] == ["https://img.inews.qq.com/pic.jpg"]
