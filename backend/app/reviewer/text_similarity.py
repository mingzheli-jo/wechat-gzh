"""确定性文本相似度计算（不依赖模型估计）。

改写流水线原先只有 reviewer 模型"估"一个 similarity，数值噪声大：
同一素材两次改写、人物情节已明显不同，模型仍给同一个 0.8。
本模块用字符 n-gram 给出可复现的数字，作为原创度判定的硬依据。

选字符 n-gram 而非分词：中文洗稿多为同义替换与语序调整，
字符级 shingle 对这类改动敏感且无需分词依赖。
"""

import re
from typing import Any

# 只保留中日韩文字、字母、数字；标点与空白对相似度无贡献且会稀释信号
_KEEP = re.compile(r"[^一-鿿぀-ヿa-zA-Z0-9]+")

NGRAM_SIZE = 3


def _normalize(text: str) -> str:
    return _KEEP.sub("", text or "")


def _shingles(text: str, n: int = NGRAM_SIZE) -> set[str]:
    norm = _normalize(text)
    if len(norm) < n:
        return {norm} if norm else set()
    return {norm[i : i + n] for i in range(len(norm) - n + 1)}


def compute_similarity(original: str, rewritten: str) -> dict[str, Any]:
    """返回原文与改写稿的相似度指标。

    - jaccard: 交集 / 并集。受两文长度差影响，仅作参考。
    - containment: 交集 / 改写稿的 shingle 数。
      含义是"改写稿里有多大比例的片段能在原文中找到"，
      这是洗稿判定的主指标——改写稿越是照抄，该值越高。
    """
    a = _shingles(original)
    b = _shingles(rewritten)
    if not a or not b:
        return {
            "jaccard": 0.0,
            "containment": 0.0,
            "original_ngrams": len(a),
            "rewritten_ngrams": len(b),
        }
    inter = len(a & b)
    return {
        "jaccard": round(inter / len(a | b), 4),
        "containment": round(inter / len(b), 4),
        "original_ngrams": len(a),
        "rewritten_ngrams": len(b),
    }
