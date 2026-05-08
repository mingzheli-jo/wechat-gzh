from app.rewriter.renderer import render_markdown


def test_paragraph_gets_inline_style():
    html = render_markdown("一段普通的正文。")
    assert "<p" in html
    assert 'style="' in html
    assert "line-height" in html
    assert "一段普通的正文。" in html


def test_h2_uses_accent_blue_for_section_headings():
    html = render_markdown("## 一、先说一个职场真相")
    assert "<h2" in html
    assert 'style="' in html
    # accent color and bold for section headings (image 2 reference)
    assert "color:" in html
    assert "bold" in html or "700" in html
    assert "一、先说一个职场真相" in html


def test_h3_uses_bold_subheading_style():
    html = render_markdown("### 1. 能扛事")
    assert "<h3" in html
    assert "bold" in html or "700" in html
    assert "1. 能扛事" in html


def test_blockquote_renders_as_intro_box():
    html = render_markdown("> 导语：去年我以为非我莫属。")
    assert "<blockquote" in html
    # left bar + light background characteristic of the 导语 box
    assert "border-left" in html
    assert "background" in html
    assert "导语：去年我以为非我莫属。" in html


def test_strong_emphasis_styled():
    html = render_markdown("领导要的是把**模糊需求**变成确定结果。")
    assert "<strong" in html
    assert "模糊需求" in html


def test_unordered_list_items_styled():
    md = "- 场景1：上线前出 bug。\n- 场景2：领导提了一句。"
    html = render_markdown(md)
    assert "<ul" in html
    assert html.count("<li") == 2
    assert "场景1" in html
    assert "场景2" in html


def test_ordered_list_items_styled():
    md = "1. 第一点\n2. 第二点"
    html = render_markdown(md)
    assert "<ol" in html
    assert html.count("<li") == 2


def test_full_article_structure_matches_reference_layout():
    md = (
        "> 导语：开篇。\n\n"
        "## 一、第一节\n\n"
        "正文段落一。\n\n"
        "### 1. 子标题\n\n"
        "正文段落二，**重点**在此。\n\n"
        "- 要点 A\n"
        "- 要点 B\n"
    )
    html = render_markdown(md)
    # ordering: blockquote -> h2 -> p -> h3 -> p -> ul
    assert html.index("<blockquote") < html.index("<h2")
    assert html.index("<h2") < html.index("<h3")
    assert html.index("<h3") < html.index("<ul")
    # every block carries an inline style
    for tag in ("<blockquote", "<h2", "<h3", "<p", "<ul", "<li", "<strong"):
        idx = html.index(tag)
        # closing of opening tag must include style="
        head = html[idx : idx + 200]
        assert 'style="' in head, f"no inline style on {tag}: {head!r}"


def test_no_class_or_external_style_blocks():
    """WeChat strips <style> blocks and class attributes; everything must be inline."""
    md = "## 标题\n\n段落。\n\n> 引用"
    html = render_markdown(md)
    assert "<style" not in html
    assert " class=" not in html


def test_empty_input_returns_empty_string():
    assert render_markdown("") == ""


def test_whitespace_only_input_returns_empty_string():
    assert render_markdown("   \n\n  \n").strip() == ""
