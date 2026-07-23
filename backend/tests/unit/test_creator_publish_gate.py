import uuid
from types import SimpleNamespace
from typing import Any

from app.creator.models import CreationStatus
from app.creator.service import check_auto_publish_gate


def _creation(**overrides: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "status": CreationStatus.done,
        "account_id": uuid.uuid4(),
        "generated_title": "标题",
        "generated_content_html": "<p>正文</p>",
        "fact_check": {"score": 90},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_gate_passes_when_all_conditions_met():
    ok, reason = check_auto_publish_gate(_creation(), min_score=80)
    assert ok is True
    assert reason is None


def test_gate_rejects_when_not_done():
    ok, reason = check_auto_publish_gate(
        _creation(status=CreationStatus.reviewing), min_score=80
    )
    assert ok is False
    assert reason is not None


def test_gate_rejects_when_no_account():
    ok, reason = check_auto_publish_gate(
        _creation(account_id=None), min_score=80
    )
    assert ok is False
    assert reason is not None


def test_gate_rejects_when_title_empty():
    ok, _ = check_auto_publish_gate(
        _creation(generated_title="  "), min_score=80
    )
    assert ok is False


def test_gate_rejects_when_content_empty():
    ok, _ = check_auto_publish_gate(
        _creation(generated_content_html=None), min_score=80
    )
    assert ok is False


def test_gate_rejects_no_sources_mode():
    ok, reason = check_auto_publish_gate(
        _creation(fact_check={"mode": "no_sources", "score": 100}),
        min_score=80,
    )
    assert ok is False
    assert reason is not None


def test_gate_rejects_missing_fact_check():
    ok, _ = check_auto_publish_gate(_creation(fact_check=None), min_score=80)
    assert ok is False


def test_gate_rejects_when_score_none():
    ok, _ = check_auto_publish_gate(
        _creation(fact_check={"score": None}), min_score=80
    )
    assert ok is False


def test_gate_rejects_when_score_below_threshold():
    ok, reason = check_auto_publish_gate(
        _creation(fact_check={"score": 79}), min_score=80
    )
    assert ok is False
    assert reason is not None


def test_gate_passes_when_score_equals_threshold():
    ok, _ = check_auto_publish_gate(
        _creation(fact_check={"score": 80}), min_score=80
    )
    assert ok is True
