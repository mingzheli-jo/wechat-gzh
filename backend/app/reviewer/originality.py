# ruff: noqa: E501
from typing import Any

from app.ai_providers.base import BaseProvider, Message
from app.reviewer.compliance import _parse_json_safe
from app.reviewer.text_similarity import compute_similarity

PROMPT = """你是一名公众号原创度审核员。比较【原文】与【改写】，指出改写稿中直接沿用原文的地方。
重点看：有没有照搬原文的比喻、小标题、分类方式、论述顺序、金句。
输出严格 JSON：{"score": 0-100，越高越原创, "issues": [...]}。
issues 每条要指出具体沿用了什么，并引用原文与改写稿的对应片段。
注意：人物姓名、故事细节不同不代表原创度高，要看骨架是否照搬。"""

# 分数完全由程序计算，不采纳模型打分。
#
# 起因：模型多次把【原文】的句子填进"改写稿照搬了什么"的举证里——实测某篇
# 4 条举证的片段全部只存在于原文、一条都不在改写稿中，却给出 10 分，而程序
# 算得的实际重合仅 1.66%。模型举证不可靠，其分数自然也不可用。
#
# 阈值依据实测标定（多篇成稿 vs 各自素材）：
# 真实改写的 containment 落在 0.004~0.247；同义替换式洗稿实测约 0.67。
# 两者之间有明显空档，故以 0.25 起警戒、0.50 判洗稿。
_SCORE_BANDS = (
    (0.10, 90, "与原文几乎无片段重合"),
    (0.25, 80, "与原文有少量片段重合，属正常改写范围"),
    (0.35, 60, "与原文片段重合偏高，骨架可能沿用了原文"),
    (0.50, 40, "与原文片段重合较高，接近洗稿"),
)
_SCORE_FLOOR = (20, "改写稿有一半以上片段能在原文中找到，属于洗稿级别")


def _score_from_containment(containment: float) -> tuple[int, str]:
    for threshold, score, note in _SCORE_BANDS:
        if containment < threshold:
            return score, note
    return _SCORE_FLOOR


async def review_originality(
    *,
    provider: BaseProvider,
    model: str,
    original_text: str,
    rewritten_text: str,
) -> dict[str, Any]:
    user = f"【原文】{original_text[:4000]}\n【改写】{rewritten_text[:4000]}"
    result = await provider.chat(
        [
            Message(role="system", content=PROMPT),
            Message(role="user", content=user),
        ],
        model=model,
        json_mode=True,
        temperature=0.1,
    )
    parsed = _parse_json_safe(result.content)

    metrics = compute_similarity(original_text, rewritten_text)
    containment = metrics["containment"]
    score, note = _score_from_containment(containment)

    issues: list[Any] = [f"{note}（实测片段重合率 {containment:.1%}）"]
    # 模型的定性举证留作人工参考，但不参与评分——它有把原文片段误报成
    # "改写稿照搬"的既往记录，看报告时需自行核对片段是否真在成稿里。
    model_issues = list(parsed.get("issues") or [])
    if model_issues:
        issues.append("以下为模型举证，未经校验，可能把原文片段误报为照搬：")
        issues.extend(model_issues)

    return {
        "score": score,
        "similarity": containment,
        "jaccard": metrics["jaccard"],
        "model_score_unused": int(parsed.get("score", -1)),
        "issues": issues,
        "model": model,
    }
