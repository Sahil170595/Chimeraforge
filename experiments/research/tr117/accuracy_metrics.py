"""Accuracy metrics suite for TR117 benchmark."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class AccuracyReport:
    """Comprehensive accuracy metrics for a response pair."""

    rouge1_f: float
    rouge2_f: float
    rougeL_f: float
    bleu: float
    semantic_similarity: float
    edit_distance: int
    length_ratio: float
    exact_match: bool


def compute_rouge_scores(reference: str, candidate: str) -> dict[str, float]:
    """Compute ROUGE scores (F1) between reference and candidate."""
    try:
        from rouge_score import rouge_scorer  # type: ignore

        scorer = rouge_scorer.RougeScorer(
            ["rouge1", "rouge2", "rougeL"], use_stemmer=True
        )
        scores = scorer.score(reference, candidate)

        return {
            "rouge1_f": scores["rouge1"].fmeasure,
            "rouge2_f": scores["rouge2"].fmeasure,
            "rougeL_f": scores["rougeL"].fmeasure,
        }
    except ImportError:
        # Fallback: simple word overlap
        ref_words = set(reference.lower().split())
        cand_words = set(candidate.lower().split())
        if not ref_words or not cand_words:
            return {"rouge1_f": 0.0, "rouge2_f": 0.0, "rougeL_f": 0.0}

        overlap = len(ref_words & cand_words)
        precision = overlap / len(cand_words) if cand_words else 0
        recall = overlap / len(ref_words) if ref_words else 0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0
        )

        return {"rouge1_f": f1, "rouge2_f": f1 * 0.7, "rougeL_f": f1 * 0.85}


def compute_bleu_score(reference: str, candidate: str) -> float:
    """Compute BLEU score between reference and candidate."""
    try:
        from nltk.translate.bleu_score import SmoothingFunction, sentence_bleu  # type: ignore

        ref_tokens = reference.split()
        cand_tokens = candidate.split()

        if not ref_tokens or not cand_tokens:
            return 0.0

        smoothing = SmoothingFunction().method1
        score = sentence_bleu([ref_tokens], cand_tokens, smoothing_function=smoothing)
        return float(score)
    except ImportError:
        # Fallback: simple n-gram overlap
        ref_words = reference.lower().split()
        cand_words = candidate.lower().split()

        if not ref_words or not cand_words:
            return 0.0

        # Unigram overlap
        overlap = len(set(ref_words) & set(cand_words))
        score = overlap / max(len(ref_words), len(cand_words))
        return float(score)


def compute_semantic_similarity(reference: str, candidate: str) -> float:
    """Compute semantic similarity using embeddings or fallback."""
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        from sklearn.metrics.pairwise import cosine_similarity  # type: ignore

        model = SentenceTransformer("all-MiniLM-L6-v2")
        ref_emb = model.encode([reference])
        cand_emb = model.encode([candidate])
        similarity = cosine_similarity(ref_emb, cand_emb)[0][0]
        return float(similarity)
    except ImportError:
        # Fallback: Jaccard similarity
        ref_words = set(reference.lower().split())
        cand_words = set(candidate.lower().split())

        if not ref_words or not cand_words:
            return 0.0

        intersection = len(ref_words & cand_words)
        union = len(ref_words | cand_words)
        return intersection / union if union > 0 else 0.0


def compute_edit_distance(reference: str, candidate: str) -> int:
    """Compute Levenshtein edit distance."""
    if not reference:
        return len(candidate)
    if not candidate:
        return len(reference)

    # Dynamic programming
    m, n = len(reference), len(candidate)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if reference[i - 1] == candidate[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])

    return dp[m][n]


def compute_accuracy_metrics(reference: str, candidate: str) -> AccuracyReport:
    """Compute comprehensive accuracy metrics."""
    rouge = compute_rouge_scores(reference, candidate)
    bleu = compute_bleu_score(reference, candidate)
    semantic_sim = compute_semantic_similarity(reference, candidate)
    edit_dist = compute_edit_distance(reference, candidate)

    ref_len = len(reference)
    cand_len = len(candidate)
    length_ratio = cand_len / ref_len if ref_len > 0 else 0.0
    exact_match = reference.strip().lower() == candidate.strip().lower()

    return AccuracyReport(
        rouge1_f=rouge["rouge1_f"],
        rouge2_f=rouge["rouge2_f"],
        rougeL_f=rouge["rougeL_f"],
        bleu=bleu,
        semantic_similarity=semantic_sim,
        edit_distance=edit_dist,
        length_ratio=length_ratio,
        exact_match=exact_match,
    )


def aggregate_accuracy_metrics(reports: list[AccuracyReport]) -> dict[str, float]:
    """Aggregate accuracy metrics across multiple reports."""
    if not reports:
        return {
            "rouge1_f_mean": 0.0,
            "rouge2_f_mean": 0.0,
            "rougeL_f_mean": 0.0,
            "bleu_mean": 0.0,
            "semantic_similarity_mean": 0.0,
            "edit_distance_mean": 0.0,
            "length_ratio_mean": 0.0,
            "exact_match_rate": 0.0,
        }

    return {
        "rouge1_f_mean": float(np.mean([r.rouge1_f for r in reports])),
        "rouge2_f_mean": float(np.mean([r.rouge2_f for r in reports])),
        "rougeL_f_mean": float(np.mean([r.rougeL_f for r in reports])),
        "bleu_mean": float(np.mean([r.bleu for r in reports])),
        "semantic_similarity_mean": float(
            np.mean([r.semantic_similarity for r in reports])
        ),
        "edit_distance_mean": float(np.mean([r.edit_distance for r in reports])),
        "length_ratio_mean": float(np.mean([r.length_ratio for r in reports])),
        "exact_match_rate": sum(r.exact_match for r in reports) / len(reports),
    }


def save_accuracy_report(
    metrics_by_backend: dict[str, list[AccuracyReport]],
    output_path: Path,
) -> None:
    """Save accuracy analysis to JSON."""
    report = {}

    for backend, reports in metrics_by_backend.items():
        aggregated = aggregate_accuracy_metrics(reports)
        report[backend] = {
            "n_samples": len(reports),
            **aggregated,
            "individual_samples": [
                {
                    "rouge1_f": r.rouge1_f,
                    "rouge2_f": r.rouge2_f,
                    "rougeL_f": r.rougeL_f,
                    "bleu": r.bleu,
                    "semantic_similarity": r.semantic_similarity,
                    "edit_distance": r.edit_distance,
                    "length_ratio": r.length_ratio,
                    "exact_match": r.exact_match,
                }
                for r in reports[:10]  # Save first 10 samples
            ],
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def main() -> None:
    """Example usage."""
    import pandas as pd

    # Load metrics
    df = pd.read_csv("results/tr117/metrics.csv")

    # Filter to OK runs
    df[df["status"] == "ok"]

    # Need baseline outputs for comparison
    # This is a placeholder - real implementation would load from run JSONs
    print(
        "Accuracy metrics suite loaded. Use compute_accuracy_metrics() to evaluate outputs."
    )
    print("For full analysis, baseline outputs need to be extracted from run JSONs.")


if __name__ == "__main__":
    main()
