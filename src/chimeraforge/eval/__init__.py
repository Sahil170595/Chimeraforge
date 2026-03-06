"""ChimeraForge Quality Evaluation — text-similarity metrics for LLM outputs.

Public API:
    evaluate_quality    Compute all quality metrics for predictions vs references
    run_eval            Run evaluation and return structured EvalResult
    run_eval_from_file  Load predictions/references from files and evaluate
    QualityScore        Per-config quality evaluation result
    EvalResult          Complete evaluation container with metadata
    EvalTask            Built-in evaluation task definition
    get_task            Retrieve a built-in task by name
    list_tasks          List available built-in task names
"""

from chimeraforge.eval.metrics import (
    QualityScore,
    classify_tier,
    compute_bert_score,
    compute_coherence,
    compute_composite,
    compute_exact_match,
    compute_rouge_l,
    evaluate_quality,
)
from chimeraforge.eval.runner import (
    EvalResult,
    format_eval_json,
    format_eval_table,
    run_eval,
    run_eval_from_file,
)
from chimeraforge.eval.tasks import (
    BUILTIN_TASKS,
    EvalTask,
    get_task,
    list_tasks,
)

__all__ = [
    "BUILTIN_TASKS",
    "EvalResult",
    "EvalTask",
    "QualityScore",
    "classify_tier",
    "compute_bert_score",
    "compute_coherence",
    "compute_composite",
    "compute_exact_match",
    "compute_rouge_l",
    "evaluate_quality",
    "format_eval_json",
    "format_eval_table",
    "get_task",
    "list_tasks",
    "run_eval",
    "run_eval_from_file",
]
