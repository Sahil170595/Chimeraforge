"""Quality metric computation for LLM output evaluation.

Computes BERTScore, ROUGE-L, exact match, and coherence metrics.
Heavy optional dependencies (``evaluate``, ``bert-score``, ``rouge-score``)
are imported lazily and degrade gracefully when unavailable.
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass

log = logging.getLogger("chimeraforge.eval.metrics")


# ---------------------------------------------------------------------------
# Quality tiers (percentage-point drop from FP16 baseline)
# ---------------------------------------------------------------------------

_TIER_THRESHOLDS: dict[str, float] = {
    "negligible": -3.0,
    "acceptable": -10.0,
    "concerning": -15.0,
}


# ---------------------------------------------------------------------------
# QualityScore dataclass
# ---------------------------------------------------------------------------


@dataclass
class QualityScore:
    """Quality evaluation result for one (model, quant) configuration."""

    model: str
    quant: str
    exact_match: float  # 0-1, fraction of exact matches
    rouge_l: float  # 0-1, ROUGE-L F1
    bert_score: float  # 0-1, BERTScore F1
    coherence: float  # 0-1, simple length-ratio heuristic
    composite: float  # weighted average of above
    tier: str  # negligible/acceptable/concerning/unacceptable
    n_samples: int


# ---------------------------------------------------------------------------
# Individual metric functions
# ---------------------------------------------------------------------------


def compute_exact_match(predictions: list[str], references: list[str]) -> float:
    """Fraction of exact string matches (case-insensitive, stripped).

    Args:
        predictions: Model-generated answers.
        references: Gold-standard reference answers.

    Returns:
        Float in [0, 1] representing the fraction of exact matches.
    """
    if not predictions or not references:
        return 0.0
    n = min(len(predictions), len(references))
    matches = sum(
        1 for p, r in zip(predictions[:n], references[:n]) if p.strip().lower() == r.strip().lower()
    )
    return matches / n


def _lcs_length(a: str, b: str) -> int:
    """Compute length of the longest common subsequence of two strings.

    Uses a space-optimised DP approach (two rows).

    Args:
        a: First string.
        b: Second string.

    Returns:
        Length of the LCS.
    """
    if not a or not b:
        return 0
    # Work on word tokens for ROUGE-style comparison
    a_tokens = a.split()
    b_tokens = b.split()
    m, n = len(a_tokens), len(b_tokens)
    prev = [0] * (n + 1)
    curr = [0] * (n + 1)
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a_tokens[i - 1] == b_tokens[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        prev, curr = curr, [0] * (n + 1)
    return prev[n]


def _rouge_l_f1(prediction: str, reference: str) -> float:
    """Compute ROUGE-L F1 for a single prediction/reference pair.

    Args:
        prediction: Model output text.
        reference: Gold-standard reference text.

    Returns:
        ROUGE-L F1 score in [0, 1].
    """
    pred_tokens = prediction.split()
    ref_tokens = reference.split()
    if not pred_tokens or not ref_tokens:
        return 0.0
    lcs = _lcs_length(prediction, reference)
    precision = lcs / len(pred_tokens)
    recall = lcs / len(ref_tokens)
    if precision + recall == 0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def compute_rouge_l(predictions: list[str], references: list[str]) -> float:
    """ROUGE-L F1 score averaged across all pairs.

    Uses the ``evaluate`` library if available, otherwise falls back to a
    simple LCS-based implementation with no external dependencies.

    Args:
        predictions: Model-generated answers.
        references: Gold-standard reference answers.

    Returns:
        Mean ROUGE-L F1 score in [0, 1].
    """
    if not predictions or not references:
        return 0.0
    n = min(len(predictions), len(references))

    try:
        import evaluate  # type: ignore[import-untyped]

        rouge = evaluate.load("rouge")
        result = rouge.compute(
            predictions=predictions[:n],
            references=references[:n],
            rouge_types=["rougeL"],
        )
        return float(result["rougeL"])
    except (ImportError, ValueError, FileNotFoundError):
        log.debug("evaluate library unavailable for ROUGE-L; using LCS fallback")

    scores = [_rouge_l_f1(p, r) for p, r in zip(predictions[:n], references[:n])]
    return sum(scores) / len(scores) if scores else 0.0


def compute_bert_score(predictions: list[str], references: list[str]) -> float:
    """BERTScore F1 averaged across all pairs.

    Uses the ``evaluate`` library with ``bert-score`` if available.
    Returns 0.0 with a warning when the dependency is missing.

    Args:
        predictions: Model-generated answers.
        references: Gold-standard reference answers.

    Returns:
        Mean BERTScore F1 in [0, 1], or 0.0 if unavailable.
    """
    if not predictions or not references:
        return 0.0
    n = min(len(predictions), len(references))

    try:
        import evaluate  # type: ignore[import-untyped]

        bertscore = evaluate.load("bertscore")
        result = bertscore.compute(
            predictions=predictions[:n],
            references=references[:n],
            lang="en",
        )
        f1_scores: list[float] = result["f1"]
        return sum(f1_scores) / len(f1_scores) if f1_scores else 0.0
    except (ImportError, ValueError, FileNotFoundError, OSError):
        warnings.warn(
            "BERTScore unavailable (install `evaluate` and `bert-score`). "
            "Returning 0.0; composite will redistribute weight to ROUGE-L.",
            stacklevel=2,
        )
        log.debug("BERTScore unavailable; returning 0.0")
        return 0.0


def compute_coherence(predictions: list[str], references: list[str]) -> float:
    """Simple coherence heuristic based on length ratio.

    Measures how close the prediction length is to the reference length.
    Penalises both too-short and too-long responses using:

        ratio = min(len_pred, len_ref) / max(len_pred, len_ref)

    Averaged across all pairs, clamped to [0, 1].

    Args:
        predictions: Model-generated answers.
        references: Gold-standard reference answers.

    Returns:
        Mean coherence score in [0, 1].
    """
    if not predictions or not references:
        return 0.0
    n = min(len(predictions), len(references))
    scores: list[float] = []
    for p, r in zip(predictions[:n], references[:n]):
        len_p = len(p.strip())
        len_r = len(r.strip())
        if len_r == 0 and len_p == 0:
            scores.append(1.0)
        elif len_r == 0 or len_p == 0:
            scores.append(0.0)
        else:
            ratio = min(len_p, len_r) / max(len_p, len_r)
            scores.append(max(0.0, min(1.0, ratio)))
    return sum(scores) / len(scores) if scores else 0.0


def compute_composite(
    exact_match: float,
    rouge_l: float,
    bert_score: float,
    coherence: float,
) -> float:
    """Weighted composite quality score.

    Default weights: 0.2 * exact_match + 0.3 * rouge_l + 0.3 * bert_score + 0.2 * coherence.

    When ``bert_score`` is 0.0 (unavailable), its weight is redistributed
    to ROUGE-L: 0.2 * exact_match + 0.6 * rouge_l + 0.2 * coherence.

    Args:
        exact_match: Exact match score in [0, 1].
        rouge_l: ROUGE-L F1 score in [0, 1].
        bert_score: BERTScore F1 in [0, 1] (0.0 if unavailable).
        coherence: Coherence score in [0, 1].

    Returns:
        Composite score in [0, 1].
    """
    if bert_score == 0.0:
        # Redistribute bert_score weight (0.3) to rouge_l
        return 0.2 * exact_match + 0.6 * rouge_l + 0.2 * coherence
    return 0.2 * exact_match + 0.3 * rouge_l + 0.3 * bert_score + 0.2 * coherence


def classify_tier(composite: float, fp16_composite: float) -> str:
    """Classify quality drop into a tier based on percentage-point difference.

    Tiers (from TR125):
        - negligible: drop >= -3 pp
        - acceptable: drop >= -10 pp
        - concerning: drop >= -15 pp
        - unacceptable: drop < -15 pp

    If ``fp16_composite`` is zero or negative, returns ``"unknown"``.

    Args:
        composite: Composite score for the evaluated configuration.
        fp16_composite: Composite score for the FP16 baseline.

    Returns:
        Tier string: negligible, acceptable, concerning, unacceptable, or unknown.
    """
    if fp16_composite <= 0:
        return "unknown"
    drop_pp = round((composite - fp16_composite) * 100, 6)
    if drop_pp >= _TIER_THRESHOLDS["negligible"]:
        return "negligible"
    if drop_pp >= _TIER_THRESHOLDS["acceptable"]:
        return "acceptable"
    if drop_pp >= _TIER_THRESHOLDS["concerning"]:
        return "concerning"
    return "unacceptable"


def evaluate_quality(
    predictions: list[str],
    references: list[str],
    model: str,
    quant: str,
    fp16_composite: float | None = None,
) -> QualityScore:
    """Top-level evaluation function computing all metrics.

    Computes exact match, ROUGE-L, BERTScore, and coherence, then
    derives the weighted composite and quality tier.

    Args:
        predictions: Model-generated answers.
        references: Gold-standard reference answers.
        model: Model name identifier.
        quant: Quantization level (e.g., ``"Q4_K_M"``, ``"FP16"``).
        fp16_composite: FP16 baseline composite for tier classification.
            If ``None``, the tier defaults to ``"unknown"``.

    Returns:
        Populated ``QualityScore`` with all metrics and tier.
    """
    n = min(len(predictions), len(references))

    em = compute_exact_match(predictions, references)
    rl = compute_rouge_l(predictions, references)
    bs = compute_bert_score(predictions, references)
    co = compute_coherence(predictions, references)
    comp = compute_composite(em, rl, bs, co)

    if fp16_composite is not None:
        tier = classify_tier(comp, fp16_composite)
    else:
        tier = "unknown"

    return QualityScore(
        model=model,
        quant=quant,
        exact_match=round(em, 4),
        rouge_l=round(rl, 4),
        bert_score=round(bs, 4),
        coherence=round(co, 4),
        composite=round(comp, 4),
        tier=tier,
        n_samples=n,
    )
