import pytest

from app.creator.citations import strip_citation_markers


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # 最常见：句末单个 / 连续多个标记
        ("产量增长了三成[1]。", "产量增长了三成。"),
        ("产量增长了三成[1][2]。", "产量增长了三成。"),
        ("产量增长了三成 [1] [2]。", "产量增长了三成。"),
        # 标记在句号之后，摘掉后不留空格
        ("这是结论。[3] 下一句继续。", "这是结论。下一句继续。"),
        # 区间与顿号/逗号连接
        ("有多份材料提到[1-3]。", "有多份材料提到。"),
        ("有多份材料提到[1,2]。", "有多份材料提到。"),
        ("有多份材料提到[1、2]。", "有多份材料提到。"),
        # 全角与中文括号变体
        ("模型也可能这么写［1］。", "模型也可能这么写。"),
        ("模型也可能这么写【2】。", "模型也可能这么写。"),
        # 英文语境保留词间空格
        ("Fig [1] shows the trend.", "Fig shows the trend."),
        # 行首标记
        ("[1] 这段话开头带标记。", "这段话开头带标记。"),
    ],
)
def test_strips_source_markers(raw: str, expected: str) -> None:
    assert strip_citation_markers(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        # Markdown 链接：剥掉 [1] 会留下裸露的 (url)
        "详见[1](https://example.com/a)。",
        # 引用式链接定义
        "[1]: https://example.com/a",
        # 脚注语法不是纯数字
        "这里有脚注[^1]。",
        # 方括号里不是纯数字的正常内容
        "封面用了[图片]占位。",
        "型号是 [A1] 那一款。",
        # 列表序号不受影响
        "1. 第一点\n2. 第二点",
    ],
)
def test_leaves_non_citation_brackets_alone(raw: str) -> None:
    assert strip_citation_markers(raw) == raw


def test_preserves_paragraph_breaks() -> None:
    raw = "第一段结尾[1]。\n\n第二段开头[2]，继续写。"
    assert strip_citation_markers(raw) == "第一段结尾。\n\n第二段开头，继续写。"


def test_strips_trailing_whitespace_left_behind() -> None:
    assert strip_citation_markers("一句话 [1]\n下一行") == "一句话\n下一行"


@pytest.mark.parametrize("raw", ["", "没有任何标记的正文。"])
def test_noop_inputs(raw: str) -> None:
    assert strip_citation_markers(raw) == raw
