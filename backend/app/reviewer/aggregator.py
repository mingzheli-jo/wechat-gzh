from typing import Any


def aggregate(reports: dict[str, Any]) -> int:
    """Compute overall_score as weighted mean of dimensions present."""
    weights = {
        "compliance": 0.35,
        "originality": 0.25,
        "quality": 0.25,
        "clickbait": 0.15,
    }
    total = 0.0
    weight_sum = 0.0
    for key, w in weights.items():
        block = reports.get(key)
        if block and "score" in block:
            total += block["score"] * w
            weight_sum += w
    if weight_sum == 0:
        return 0
    return int(total / weight_sum)
