import pytest

from app.reviewer.sensitive_words import SensitiveWordChecker


@pytest.fixture
def checker(tmp_path):
    words = tmp_path / "words.txt"
    words.write_text("最佳\n包治\n", encoding="utf-8")
    return SensitiveWordChecker.from_file(words)


def test_check_finds_hits(checker):
    hits = checker.check("这是最佳的产品，包治百病。")
    assert sorted(hits) == ["包治", "最佳"]


def test_check_no_hits_returns_empty(checker):
    assert checker.check("这是普通的产品。") == []


def test_from_file_skips_blanks_and_comments(tmp_path):
    f = tmp_path / "w.txt"
    f.write_text("\n# comment\n禁词\n", encoding="utf-8")
    checker = SensitiveWordChecker.from_file(f)
    assert checker.check("这里有禁词存在") == ["禁词"]
