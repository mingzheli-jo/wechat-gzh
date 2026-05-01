from app.rewriter.prompt_builder import build_content_messages, build_title_messages


def test_build_title_includes_account_prompt_and_original():
    msgs = build_title_messages(
        account_title_prompt="改写得更吸引人但不夸张",
        category="职场",
        style_desc="专业克制",
        original_title="十大职场陷阱",
        override="加点紧迫感",
    )
    assert any("改写得更吸引人" in m.content for m in msgs)
    assert any("职场" in m.content for m in msgs)
    assert any("专业克制" in m.content for m in msgs)
    assert any("十大职场陷阱" in m.content for m in msgs)
    assert any("加点紧迫感" in m.content for m in msgs)


def test_build_content_truncates_long_input():
    long_text = "x" * 50_000
    msgs = build_content_messages(
        account_content_prompt="保持原意改写",
        category="职场",
        style_desc="",
        original_content=long_text,
        override=None,
        max_chars=8000,
    )
    user_msg = next(m for m in msgs if m.role == "user")
    assert len(user_msg.content) <= 8500
