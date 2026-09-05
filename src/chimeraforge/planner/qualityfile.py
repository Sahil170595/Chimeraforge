"""Ingest a real eval harness's output as the quality basis.

P8.4, item 3. The bundled composite is 20 items and cannot resolve anything
smaller than ~21 percentage points. The fix for that is not a better prior, it is
more items -- so the planner reads the output of a harness that ran them.

`lm-evaluation-harness` is the target, on evidence rather than taste: it is what
the industrial quantization-recovery literature emits (every Red Hat AI model
card reproduces its numbers with `lm_eval --model vllm`), and it writes a
versioned machine-readable schema. HELM entered maintenance mode on 2026-06-01
and names lm-eval as a successor; `openai/evals` redirects to a dashboard.
Neither is worth building on.

Two rules shape the reader, and both exist to stop a fabricated comparison:

* **The metric name travels with the score.** An MMLU accuracy and the bundled
  composite are different scales. Averaging them, or ranking one against the
  other, would manufacture a result -- so a plan uses one metric or the other,
  says which, and interprets ``--quality-target`` against the metric in force.
* **An unrecognised file is an error, not an empty ingest.** Silently reading
  zero cells and carrying on with the bundled corpus would leave the user
  believing their eval was in force when it was not.
"""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass, field
from pathlib import Path

from chimeraforge.planner.evalstats import QualityCell

HARNESS_LM_EVAL = "lm-evaluation-harness"

# Score keys, in preference order. lm-eval writes `"<metric>,<filter>"` pairs, so
# the lookup is by prefix rather than by exact key.
_PREFERRED_METRICS = ("acc_norm", "acc", "exact_match", "f1", "pass@1")


class QualityFileError(ValueError):
    """The quality file cannot be read as a harness result."""


@dataclass
class IngestedQuality:
    """Per-task scores from one harness run, with everything that identifies it."""

    harness: str
    harness_version: str | None
    date: str | None
    metric: str
    cells: dict[str, QualityCell] = field(default_factory=dict)
    tasks: list[str] = field(default_factory=list)

    def describe(self) -> str:
        version = f" {self.harness_version}" if self.harness_version else ""
        when = f", run {self.date}" if self.date else ""
        return (
            f"{self.harness}{version}{when}: {len(self.cells)} task(s) "
            f"[{', '.join(self.tasks)}] scored on {self.metric}"
        )


def _split_metric_key(key: str) -> tuple[str, str]:
    """``"acc,none"`` -> ``("acc", "none")``. A key with no filter keeps ``""``."""
    name, _, filt = key.partition(",")
    return name, filt


def _numeric(value: object) -> float | None:
    """A float, or None.

    `acc_stderr,none` is legitimately the **string** `"N/A"` in real lm-eval
    output when a task's stderr cannot be computed. Coercing that to 0.0 would
    turn "we could not measure the uncertainty" into "there is none".
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _pick_metric(task_result: dict) -> tuple[str, float] | None:
    """The task's headline score and the metric it is on."""
    scored: dict[str, tuple[str, float]] = {}
    for key, value in task_result.items():
        name, _ = _split_metric_key(key)
        if name.endswith("_stderr") or name == "alias":
            continue
        number = _numeric(value)
        if number is not None:
            scored.setdefault(name, (key, number))
    for preferred in _PREFERRED_METRICS:
        if preferred in scored:
            return scored[preferred][0], scored[preferred][1]
    if scored:
        # Deterministic rather than dict-order dependent: two runs of the same
        # file must pick the same metric.
        first = sorted(scored)[0]
        return scored[first]
    return None


def _effective_n(payload: dict, task: str) -> int | None:
    samples = payload.get("n-samples") or payload.get("n_samples")
    if not isinstance(samples, dict):
        return None
    entry = samples.get(task)
    if isinstance(entry, dict):
        for key in ("effective", "original"):
            value = _numeric(entry.get(key))
            if value:
                return int(value)
    value = _numeric(entry)
    return int(value) if value else None


def load_quality_file(path: str | Path) -> IngestedQuality:
    """Read a harness results file into per-task quality cells.

    Raises:
        QualityFileError: the file is missing, is not JSON, is not a shape this
            reader recognises, or contains no scoreable task. Every one of those
            is an error rather than an empty ingest -- a silent zero-cell read
            would leave the caller believing their eval was in force.
    """
    p = Path(path)
    if not p.exists():
        raise QualityFileError(f"quality file not found: {p}")
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise QualityFileError(f"quality file is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise QualityFileError(f"quality file must be a JSON object, got {type(payload).__name__}")

    results = payload.get("results")
    if not isinstance(results, dict) or not results:
        raise QualityFileError(
            f"{p} has no `results` object -- this reader understands "
            f"{HARNESS_LM_EVAL} output (and Inspect AI via `inspect log dump`). "
            "It is not a recognised harness result."
        )

    cells: dict[str, QualityCell] = {}
    tasks: list[str] = []
    metrics_seen: set[str] = set()
    for task, task_result in results.items():
        if not isinstance(task_result, dict):
            continue
        picked = _pick_metric(task_result)
        if picked is None:
            continue
        metric_key, score = picked
        n = _effective_n(payload, task)
        if not n:
            raise QualityFileError(
                f"task {task!r} has a score but no sample count (`n-samples`). "
                "A score without an n cannot carry an interval, and reporting it "
                "without one is the defect this flag exists to fix."
            )
        metric_name, _ = _split_metric_key(metric_key)
        metrics_seen.add(metric_name)
        tasks.append(task)
        cells[task] = QualityCell(
            score=score,
            n=n,
            metric=f"{HARNESS_LM_EVAL}:{task}:{metric_name}",
            source=str(p),
        )

    if not cells:
        raise QualityFileError(
            f"{p} has a `results` object but no task in it carries a numeric score. "
            "Nothing was ingested; the plan would silently have used the bundled "
            "20-item composite instead."
        )

    date = payload.get("date")
    if isinstance(date, (int, float)):
        date = _dt.datetime.fromtimestamp(date, _dt.timezone.utc).date().isoformat()
    elif not isinstance(date, str):
        date = None

    return IngestedQuality(
        harness=HARNESS_LM_EVAL,
        harness_version=_harness_version(payload),
        date=date,
        # One metric name for the run when the tasks agree on one, else a
        # composite label that cannot be mistaken for a single benchmark.
        metric=(
            f"{HARNESS_LM_EVAL}:{next(iter(metrics_seen))}"
            if len(metrics_seen) == 1
            else f"{HARNESS_LM_EVAL}:mixed({','.join(sorted(metrics_seen))})"
        ),
        cells=cells,
        tasks=sorted(tasks),
    )


def _harness_version(payload: dict) -> str | None:
    for key in ("git_hash", "lm_eval_version", "transformers_version"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    config = payload.get("config")
    if isinstance(config, dict):
        value = config.get("lm_eval_version") or config.get("git_hash")
        if isinstance(value, str) and value:
            return value
    return None


def aggregate(ingested: IngestedQuality) -> QualityCell:
    """One score for the run: the mean over tasks, with the total sample count.

    Averaging across tasks within one harness run is a stated aggregation of the
    same metric, not a cross-metric comparison -- and the composite metric name
    says so when the tasks did not agree on a metric.
    """
    if not ingested.cells:
        raise QualityFileError("nothing to aggregate")
    scores = [c.score for c in ingested.cells.values()]
    return QualityCell(
        score=sum(scores) / len(scores),
        n=sum(c.n for c in ingested.cells.values()),
        metric=ingested.metric,
        source=next(iter(ingested.cells.values())).source,
    )
