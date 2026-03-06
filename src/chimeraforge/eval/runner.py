"""Eval orchestrator — run quality evaluation on model outputs.

Provides functions to evaluate predictions against references,
load from files, and format results as Rich tables or JSON.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from typing import TYPE_CHECKING

from chimeraforge.eval.metrics import QualityScore, evaluate_quality

if TYPE_CHECKING:
    from rich.console import Console

log = logging.getLogger("chimeraforge.eval.runner")


@dataclass
class EvalResult:
    """Complete evaluation result with metadata.

    Attributes:
        model: Model name identifier.
        backend: Serving backend name.
        quant: Quantization level, or ``None`` for default.
        task: Task name (built-in or ``"custom"``).
        scores: Computed quality metrics.
        timestamp: ISO 8601 UTC timestamp.
        warnings: Any warnings generated during evaluation.
    """

    model: str
    backend: str
    quant: str | None
    task: str
    scores: QualityScore
    timestamp: str
    warnings: list[str] = field(default_factory=list)


def _now_iso() -> str:
    """Return current UTC timestamp as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def run_eval(
    predictions: list[str],
    references: list[str],
    model: str = "unknown",
    backend: str = "unknown",
    quant: str | None = None,
    task: str = "custom",
    fp16_composite: float | None = None,
) -> EvalResult:
    """Run quality evaluation on predictions vs references.

    Args:
        predictions: Model-generated answers.
        references: Gold-standard reference answers.
        model: Model name identifier.
        backend: Serving backend name.
        quant: Quantization level (e.g., ``"Q4_K_M"``).
        task: Task name for labelling results.
        fp16_composite: FP16 baseline composite for tier classification.

    Returns:
        Populated ``EvalResult`` with scores and metadata.
    """
    warn_list: list[str] = []

    if len(predictions) != len(references):
        warn_list.append(
            f"Length mismatch: {len(predictions)} predictions vs "
            f"{len(references)} references. Using min({len(predictions)}, "
            f"{len(references)}) = {min(len(predictions), len(references))} pairs."
        )

    if not predictions or not references:
        warn_list.append("Empty predictions or references; all scores will be 0.")

    quant_label = quant if quant is not None else "FP16"
    scores = evaluate_quality(
        predictions=predictions,
        references=references,
        model=model,
        quant=quant_label,
        fp16_composite=fp16_composite,
    )

    if scores.bert_score == 0.0 and predictions and references:
        warn_list.append("BERTScore unavailable; composite redistributed weight to ROUGE-L.")

    return EvalResult(
        model=model,
        backend=backend,
        quant=quant,
        task=task,
        scores=scores,
        timestamp=_now_iso(),
        warnings=warn_list,
    )


def run_eval_from_file(
    predictions_path: Path,
    references_path: Path,
    model: str = "unknown",
    quant: str | None = None,
) -> EvalResult:
    """Load predictions and references from text files and evaluate.

    Each file should contain one answer per line.

    Args:
        predictions_path: Path to predictions text file.
        references_path: Path to references text file.
        model: Model name identifier.
        quant: Quantization level.

    Returns:
        ``EvalResult`` from the loaded data.

    Raises:
        FileNotFoundError: If either file does not exist.
    """
    predictions_path = Path(predictions_path)
    references_path = Path(references_path)

    if not predictions_path.is_file():
        raise FileNotFoundError(f"Predictions file not found: {predictions_path}")
    if not references_path.is_file():
        raise FileNotFoundError(f"References file not found: {references_path}")

    predictions = predictions_path.read_text(encoding="utf-8").strip().splitlines()
    references = references_path.read_text(encoding="utf-8").strip().splitlines()

    return run_eval(
        predictions=predictions,
        references=references,
        model=model,
        quant=quant,
        task=f"file:{predictions_path.name}",
    )


def format_eval_table(results: list[EvalResult], console: Console) -> None:
    """Print a Rich table with quality scores for each result.

    Args:
        results: List of evaluation results to display.
        console: Rich ``Console`` instance for output.
    """
    from rich.table import Table

    table = Table(title="Quality Evaluation Results")
    table.add_column("Model", style="bold")
    table.add_column("Quant")
    table.add_column("Task")
    table.add_column("EM", justify="right")
    table.add_column("ROUGE-L", justify="right")
    table.add_column("BERTScore", justify="right")
    table.add_column("Coherence", justify="right")
    table.add_column("Composite", justify="right", style="bold")
    table.add_column("Tier")
    table.add_column("N", justify="right")

    tier_styles: dict[str, str] = {
        "negligible": "green",
        "acceptable": "yellow",
        "concerning": "red",
        "unacceptable": "bold red",
        "unknown": "dim",
    }

    for r in results:
        s = r.scores
        tier_style = tier_styles.get(s.tier, "white")
        table.add_row(
            s.model,
            r.quant or "default",
            r.task,
            f"{s.exact_match:.3f}",
            f"{s.rouge_l:.3f}",
            f"{s.bert_score:.3f}",
            f"{s.coherence:.3f}",
            f"{s.composite:.3f}",
            f"[{tier_style}]{s.tier}[/]",
            str(s.n_samples),
        )

    console.print()
    console.print(table)

    # Print warnings if any
    for r in results:
        if r.warnings:
            for w in r.warnings:
                console.print(f"  [yellow]Warning:[/] {w}")


def format_eval_json(results: list[EvalResult]) -> str:
    """Serialise evaluation results as a JSON string.

    Args:
        results: List of evaluation results.

    Returns:
        Indented JSON string.
    """
    return json.dumps([asdict(r) for r in results], indent=2)
