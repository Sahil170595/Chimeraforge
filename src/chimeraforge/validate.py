"""Prediction-vs-measured falsification audit.

The trust principle is asserted per number: each prediction is labeled
``measured`` / ``estimated`` / ``unknown``. This module makes that claim
*falsifiable* -- it runs the planner's predictions against live measurements over
a config matrix and reports how wrong each provenance class actually is.

Every published planner accuracy audit is datacenter-only (Vidur <9% on A100/H100,
DistServe <2% on 32xA100, Splitwise MAPE <3%). None covers consumer GPUs, PCIe, or
per-quantization behaviour, which is exactly the tier this corpus is fit on.

Three ways an audit like this lies, and what stops each here:

1. **Cherry-picking the matrix after seeing results.** The matrix is fingerprinted
   (:func:`Matrix.fingerprint`) and the audit records the hash it ran against, so
   a matrix edited after the fact does not match its own report.
2. **Passing off in-corpus lookups as predictions.** A ``measured``-provenance cell
   is not a prediction -- the corpus *is* the answer. Cells are split by provenance
   class and :data:`LEAD_CLASS` (the estimated path) is what the summary leads with.
3. **Dropping the embarrassing cells.** Every cell is retained in the raw output and
   each scorecard row carries its own worst case, so a bad cell cannot be averaged
   out of sight.

Scoring is pure and offline: measurements can come from a live run or from a
previously captured file, so the arithmetic is testable without a GPU.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Provenance classes, in the order the report presents them. The estimated paths
# lead because they are the only ones making an out-of-sample claim.
CLASS_ROOFLINE = "roofline-estimate"
CLASS_PARALLEL = "parallel-estimate"
CLASS_LOOKUP = "measured-lookup"
CLASS_ORDER = (CLASS_ROOFLINE, CLASS_PARALLEL, CLASS_LOOKUP)
LEAD_CLASS = CLASS_ROOFLINE

# Metrics compared when both sides report them.
METRICS = ("throughput_tps", "ttft_ms", "p95_latency_ms")

# Below this many cells a percentage error is anecdote, not a rate. Rows smaller
# than this are still published -- they are labeled, not hidden.
MIN_CELLS_FOR_RATE = 5


class ValidationError(RuntimeError):
    """Raised when a matrix or measurement file cannot be used."""


@dataclass(frozen=True)
class MatrixCell:
    """One (model x quant x backend x shape) configuration to audit."""

    model: str
    quant: str
    backend: str
    context_length: int = 2048
    prompt_tokens: int = 512
    avg_tokens: int = 128
    batch: int = 1

    @property
    def key(self) -> str:
        """Stable identity used to join predictions to measurements."""
        return (
            f"{self.model}|{self.quant}|{self.backend}|"
            f"c{self.context_length}|p{self.prompt_tokens}|o{self.avg_tokens}|b{self.batch}"
        )


@dataclass
class Matrix:
    """A pre-registered set of cells, plus the context it was registered in."""

    hardware: str
    registered_at: str
    cells: list[MatrixCell] = field(default_factory=list)
    notes: str = ""

    def fingerprint(self) -> str:
        """SHA-256 over the canonical cell list, hardware and registration date.

        This is what makes pre-registration checkable rather than a promise: the
        audit output records the fingerprint it ran against, so a matrix edited
        after results were seen no longer matches the report that cites it.
        """
        payload = json.dumps(
            {
                "hardware": self.hardware,
                "registered_at": self.registered_at,
                "cells": sorted(c.key for c in self.cells),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, data: dict) -> Matrix:
        for key in ("hardware", "registered_at", "cells"):
            if key not in data:
                raise ValidationError(f"matrix is missing required field {key!r}")
        try:
            _dt.date.fromisoformat(data["registered_at"])
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                f"registered_at {data['registered_at']!r} is not an ISO date"
            ) from exc
        if not data["cells"]:
            raise ValidationError("matrix declares no cells")
        cells = []
        for raw in data["cells"]:
            for key in ("model", "quant", "backend"):
                if key not in raw:
                    raise ValidationError(f"cell is missing required field {key!r}: {raw}")
            cells.append(MatrixCell(**raw))
        keys = [c.key for c in cells]
        if len(set(keys)) != len(keys):
            raise ValidationError("matrix contains duplicate cells")
        return cls(
            hardware=data["hardware"],
            registered_at=data["registered_at"],
            cells=cells,
            notes=data.get("notes", ""),
        )

    @classmethod
    def load(cls, path: str | Path) -> Matrix:
        p = Path(path)
        if not p.exists():
            raise ValidationError(f"matrix file not found: {p}")
        try:
            return cls.from_dict(json.loads(p.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            raise ValidationError(f"matrix file is not valid JSON: {exc}") from exc


def classify(
    provenance: dict[str, str], tensor_parallel: int = 1, pipeline_parallel: int = 1
) -> str:
    """Bucket a candidate by the strongest claim its prediction is making.

    A multi-GPU prediction layers a comms model on top of whatever the throughput
    basis was, so it is reported separately rather than folded into either.
    """
    if max(tensor_parallel, 1) > 1 or max(pipeline_parallel, 1) > 1:
        return CLASS_PARALLEL
    return CLASS_LOOKUP if provenance.get("throughput") == "measured" else CLASS_ROOFLINE


def relative_error(predicted: float, measured: float) -> float | None:
    """Signed relative error, ``(predicted - measured) / measured``.

    Positive means the planner was optimistic. ``None`` when the measurement is
    absent or zero -- an undefined error is reported as undefined, never as 0.
    """
    if measured is None or predicted is None:
        return None
    if measured == 0:
        return None
    return (predicted - measured) / measured


@dataclass
class CellOutcome:
    """One cell's prediction, measurement, and the gap between them."""

    key: str
    cell: MatrixCell
    provenance_class: str
    predicted: dict[str, float] = field(default_factory=dict)
    measured: dict[str, float] = field(default_factory=dict)
    errors: dict[str, float] = field(default_factory=dict)
    skipped: str | None = None

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "cell": asdict(self.cell),
            "provenance_class": self.provenance_class,
            "predicted": self.predicted,
            "measured": self.measured,
            "errors": {k: round(v, 6) for k, v in self.errors.items()},
            "skipped": self.skipped,
        }


@dataclass
class ScorecardRow:
    """Error statistics for one (provenance class, metric) pair."""

    provenance_class: str
    metric: str
    n: int
    mape: float
    median_signed: float
    p90_abs: float
    worst_key: str
    worst_error: float
    underpowered: bool

    def to_dict(self) -> dict:
        return {
            "provenance_class": self.provenance_class,
            "metric": self.metric,
            "n": self.n,
            "mape": round(self.mape, 4),
            "median_signed_error": round(self.median_signed, 4),
            "p90_abs_error": round(self.p90_abs, 4),
            "worst_cell": self.worst_key,
            "worst_error": round(self.worst_error, 4),
            # True when n is too small for the percentage to be a rate rather than
            # an anecdote. Published either way, labeled rather than dropped.
            "underpowered": self.underpowered,
        }


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(int(round((pct / 100.0) * (len(ordered) - 1))), len(ordered) - 1)
    return ordered[idx]


def score(outcomes: list[CellOutcome]) -> list[ScorecardRow]:
    """Aggregate per (provenance class, metric). Never drops a class or a worst case."""
    rows: list[ScorecardRow] = []
    for cls in CLASS_ORDER:
        for metric in METRICS:
            errs = [
                (o.key, o.errors[metric])
                for o in outcomes
                if o.provenance_class == cls and not o.skipped and metric in o.errors
            ]
            if not errs:
                continue
            abs_errs = [abs(e) for _, e in errs]
            worst_key, worst_err = max(errs, key=lambda kv: abs(kv[1]))
            rows.append(
                ScorecardRow(
                    provenance_class=cls,
                    metric=metric,
                    n=len(errs),
                    mape=sum(abs_errs) / len(abs_errs),
                    median_signed=statistics.median([e for _, e in errs]),
                    p90_abs=_percentile(abs_errs, 90),
                    worst_key=worst_key,
                    worst_error=worst_err,
                    underpowered=len(errs) < MIN_CELLS_FOR_RATE,
                )
            )
    return rows


@dataclass
class Audit:
    """A complete audit: what was registered, what ran, and how wrong it was."""

    fingerprint: str
    registered_at: str
    generated_at: str
    hardware: str
    outcomes: list[CellOutcome] = field(default_factory=list)
    rows: list[ScorecardRow] = field(default_factory=list)
    notes: str = ""

    @property
    def skipped(self) -> list[CellOutcome]:
        return [o for o in self.outcomes if o.skipped]

    def to_dict(self) -> dict:
        return {
            "schema_version": 1,
            "matrix_fingerprint": self.fingerprint,
            "registered_at": self.registered_at,
            "generated_at": self.generated_at,
            "hardware": self.hardware,
            "notes": self.notes,
            "lead_class": LEAD_CLASS,
            "scorecard": [r.to_dict() for r in self.rows],
            # Every cell, including skips and the worst performers. The raw record
            # is what lets someone else re-derive the table.
            "cells": [o.to_dict() for o in self.outcomes],
        }


def build_audit(
    matrix: Matrix,
    outcomes: list[CellOutcome],
    generated_at: str | None = None,
) -> Audit:
    return Audit(
        fingerprint=matrix.fingerprint(),
        registered_at=matrix.registered_at,
        generated_at=generated_at or _dt.date.today().isoformat(),
        hardware=matrix.hardware,
        outcomes=outcomes,
        rows=score(outcomes),
        notes=matrix.notes,
    )


def load_measurements(path: str | Path) -> dict[str, dict[str, float]]:
    """Load ``{cell_key: {metric: value}}`` captured from a previous live run.

    Lets the scoring half run offline -- and lets a published audit be re-derived
    from its own raw output without re-running the benchmarks.
    """
    p = Path(path)
    if not p.exists():
        raise ValidationError(f"measurements file not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"measurements file is not valid JSON: {exc}") from exc
    # Accept either a bare mapping or a previous audit's own output.
    if isinstance(data, dict) and "cells" in data:
        return {
            c["key"]: c.get("measured", {})
            for c in data["cells"]
            if isinstance(c, dict) and c.get("measured")
        }
    if not isinstance(data, dict):
        raise ValidationError("measurements must be an object keyed by cell")
    return data


def format_markdown(audit: Audit) -> str:
    """Render the audit as a report, leading with the class that makes a claim."""
    out: list[str] = [
        "# ChimeraForge prediction-vs-measured audit",
        "",
        f"- **Hardware:** {audit.hardware}",
        f"- **Matrix registered:** {audit.registered_at}",
        f"- **Matrix fingerprint:** `{audit.fingerprint[:16]}`",
        f"- **Generated:** {audit.generated_at}",
        f"- **Cells:** {len(audit.outcomes)} ({len(audit.skipped)} skipped)",
        "",
    ]
    if audit.notes:
        out += [audit.notes, ""]

    scored = {(r.provenance_class, r.metric): r for r in audit.rows}
    for cls in CLASS_ORDER:
        rows = [r for r in audit.rows if r.provenance_class == cls]
        if not rows:
            continue
        out.append(f"## {cls}")
        if cls == CLASS_LOOKUP:
            out += [
                "",
                "_Not an out-of-sample test: for these cells the measured corpus **is** "
                "the prediction. Reported for completeness, not as evidence of "
                "predictive accuracy._",
            ]
        elif cls == LEAD_CLASS:
            out += [
                "",
                "_The out-of-sample path: no measured row exists, so the "
                "planner is predicting from first principles._",
            ]
        out += [
            "",
            "| Metric | n | MAPE | Median signed | p90 abs | Worst cell | Worst |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in rows:
            flag = " *" if r.underpowered else ""
            out.append(
                f"| {r.metric} | {r.n}{flag} | {r.mape:.1%} | {r.median_signed:+.1%} | "
                f"{r.p90_abs:.1%} | `{r.worst_key}` | {r.worst_error:+.1%} |"
            )
        out.append("")
    if any(r.underpowered for r in audit.rows):
        out += [
            f"`*` fewer than {MIN_CELLS_FOR_RATE} cells -- treat as an anecdote, not a rate.",
            "",
        ]
    if audit.skipped:
        out += ["## Skipped cells", ""]
        out += [f"- `{o.key}` -- {o.skipped}" for o in audit.skipped]
        out.append("")
    out += [
        "Positive error means the planner was **optimistic** (predicted above measured).",
        "",
        "Every cell, including the worst, is retained in the raw JSON alongside this "
        "report so the table can be re-derived independently.",
    ]
    _ = scored
    return "\n".join(out)
