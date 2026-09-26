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

Measurements are sourced records, not bare numbers (P8.5). Each cell names who
measured it (:data:`EVIDENCE_CLASSES`), where the figure is published, when it
was captured, and which quantity it is (:data:`METRIC_DEFINITIONS`). Four more
ways an audit lies, and what stops each:

4. **Blending evidence.** A third-party figure (different silicon, driver, engine
   build) is not an own-rig figure. Evidence is a scorecard dimension; rows are
   never averaged across it.
5. **Grading against the training set.** A third-party cell that cites the TR
   corpus the planner was fitted on is refused at load.
6. **Metric mismatch.** "tokens/sec" can be decode, end-to-end or aggregate. A
   definition the planner does not predict is kept in the raw output but never
   scored, and ``ambiguous`` does not load.
7. **Underspecified sources.** A cell whose source omits the serving config is
   published but kept out of the headline rows.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path

from chimeraforge.planner.provenance import PROV_EXTRAPOLATED, PROV_MEASURED, prov_class

# Provenance classes, in the order the report presents them. The estimated paths
# lead because they are the only ones making an out-of-sample claim.
CLASS_ROOFLINE = "roofline-estimate"
CLASS_PARALLEL = "parallel-estimate"
# A corpus row scaled to a GPU it was never measured on. This is the audit's
# sharpest class -- the prediction is genuinely out-of-sample for THIS card, and
# the only thing being tested is the bandwidth-ratio assumption. Folding it into
# `measured-lookup` filed the most out-of-sample predictions in the tool under
# the heading that says they are not predictions at all.
CLASS_EXTRAPOLATED = "bandwidth-extrapolated"
CLASS_LOOKUP = "measured-lookup"
CLASS_ORDER = (CLASS_ROOFLINE, CLASS_PARALLEL, CLASS_EXTRAPOLATED, CLASS_LOOKUP)
LEAD_CLASS = CLASS_ROOFLINE

# Metrics compared when both sides report them.
# `e2e_latency_ms` is one request at batch 1 with no queue: the planner's own
# service time, ttft + avg_tokens / throughput (models.py LatencyModel).
METRICS = ("throughput_tps", "ttft_ms", "e2e_latency_ms", "p95_latency_ms")

# Below this many cells a percentage error is anecdote, not a rate. Rows smaller
# than this are still published -- they are labeled, not hidden.
MIN_CELLS_FOR_RATE = 5

# Measurement file schema. v1 was `{cell_key: {metric: float}}` -- bare numbers
# with nowhere to put a source, and it is no longer accepted.
MEASUREMENT_SCHEMA_VERSION = 2

# Who measured the ground truth. Separate from provenance class (what kind of
# prediction was made): a cell has one of each, and neither is ever averaged
# across the other's values.
EVIDENCE_OWN_RIG = "own-rig-measured"
EVIDENCE_THIRD_PARTY = "third-party-measured"
EVIDENCE_ORDER = (EVIDENCE_OWN_RIG, EVIDENCE_THIRD_PARTY)
EVIDENCE_CLASSES = frozenset(EVIDENCE_ORDER)

# What a measured number IS. A published "tokens/sec" can be any of the first
# three, and they differ by the prefill share -- comparing the wrong one to a
# decode prediction fabricates an error rate in either direction.
DEF_DECODE = "decode_tps_single_stream"
DEF_E2E_TPS = "e2e_tps_single_stream"
DEF_AGGREGATE = "aggregate_tps_at_concurrency"
DEF_PREFILL = "prefill_tps"
DEF_TTFT = "ttft_ms"
DEF_E2E_LATENCY = "e2e_latency_ms"
DEF_E2E_P95 = "e2e_latency_p95_ms"
METRIC_DEFINITIONS = frozenset(
    {
        DEF_DECODE,
        DEF_E2E_TPS,
        DEF_AGGREGATE,
        DEF_PREFILL,
        DEF_TTFT,
        DEF_E2E_LATENCY,
        DEF_E2E_P95,
    }
)
DEF_AMBIGUOUS = "ambiguous"

# Which planner prediction each definition is evidence about. Anything absent is
# retained in the raw output and reported as unscored, with the reason.
SCORED_AS = {
    DEF_DECODE: "throughput_tps",
    DEF_TTFT: "ttft_ms",
    # Prefill throughput at the cell's prompt length is TTFT by arithmetic:
    # prompt_tokens / prefill_tps. The basis is recorded so the conversion is
    # visible in every outcome that uses it.
    DEF_PREFILL: "ttft_ms",
    # A single request at the cell's prompt/output lengths, batch 1.
    DEF_E2E_LATENCY: "e2e_latency_ms",
    DEF_E2E_P95: "p95_latency_ms",
}
UNSCORED_REASON = {
    DEF_E2E_TPS: "end-to-end rate includes prefill; the planner predicts decode only",
    DEF_AGGREGATE: "aggregate throughput at concurrency; the planner audit predicts a "
    "single stream",
}

# A third-party cell citing any of these is grading the planner against the TR
# corpus it was fitted on (fitted_models.json cites TR108-TR137, which are
# published from these repositories). Matched case-insensitively on the URL.
OWN_CORPUS_MARKERS = ("sahil170595", "chimeraforge", "banterhearts")

_HTTP_SCHEMES = ("http://", "https://")


class ValidationError(RuntimeError):
    """Raised when a matrix or measurement file cannot be used."""


@dataclass(frozen=True)
class MatrixCell:
    """One (model x quant x backend x shape) configuration to audit.

    ``spec`` optionally pins the architecture (``params_b``, ``n_layers``,
    ``n_kv_heads``, ``d_head``, ...) so an off-registry model is predicted from
    the same numbers on every machine, offline. Stored as sorted pairs so the
    cell stays hashable.
    """

    model: str
    quant: str
    backend: str
    context_length: int = 2048
    prompt_tokens: int = 512
    avg_tokens: int = 128
    batch: int = 1
    spec: tuple = ()

    @property
    def key(self) -> str:
        """Stable identity used to join predictions to measurements."""
        return (
            f"{self.model}|{self.quant}|{self.backend}|"
            f"c{self.context_length}|p{self.prompt_tokens}|o{self.avg_tokens}|b{self.batch}"
        )

    @property
    def spec_dict(self) -> dict:
        return dict(self.spec)

    def _canonical(self) -> str:
        # The spec is part of what was registered -- editing an architecture after
        # seeing results moves every prediction -- but a cell without one hashes
        # exactly as it did before specs existed.
        if not self.spec:
            return self.key
        return f"{self.key}|spec={json.dumps(self.spec_dict, sort_keys=True)}"


def _cell_from_raw(raw: dict) -> MatrixCell:
    raw = dict(raw)
    spec = raw.pop("spec", None) or {}
    if not isinstance(spec, dict):
        raise ValidationError(f"cell spec must be an object: {raw}")
    return MatrixCell(**raw, spec=tuple(sorted(spec.items())))


@dataclass
class Matrix:
    """A pre-registered set of cells, plus the context it was registered in.

    ``bands`` is the in-band tolerance per metric (a fraction, 0.25 = +-25%) and
    ``sources`` is every source consulted while assembling the matrix, including
    those that yielded nothing and why. Both are fingerprinted: a band chosen
    after seeing the errors, or a source list trimmed to the flattering ones, is
    the same cherry-pick the cell fingerprint exists to stop.
    """

    hardware: str
    registered_at: str
    cells: list[MatrixCell] = field(default_factory=list)
    notes: str = ""
    bands: dict[str, float] = field(default_factory=dict)
    sources: list[dict] = field(default_factory=list)

    def fingerprint(self) -> str:
        """SHA-256 over the canonical cell list, hardware and registration date.

        This is what makes pre-registration checkable rather than a promise: the
        audit output records the fingerprint it ran against, so a matrix edited
        after results were seen no longer matches the report that cites it.
        Bands and sources enter the payload only when declared, so a matrix that
        uses neither hashes exactly as it did before they existed.
        """
        body: dict = {
            "hardware": self.hardware,
            "registered_at": self.registered_at,
            "cells": sorted(c._canonical() for c in self.cells),
        }
        if self.bands:
            body["bands"] = self.bands
        if self.sources:
            body["sources"] = self.sources
        payload = json.dumps(body, sort_keys=True, separators=(",", ":"))
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
            cells.append(_cell_from_raw(raw))
        keys = [c.key for c in cells]
        if len(set(keys)) != len(keys):
            raise ValidationError("matrix contains duplicate cells")
        bands = data.get("bands") or {}
        for metric, band in bands.items():
            if metric not in METRICS:
                raise ValidationError(
                    f"band declared for {metric!r}, which the audit does not score "
                    f"(one of: {', '.join(METRICS)})"
                )
            if not _is_positive_number(band):
                raise ValidationError(f"band for {metric} must be a positive fraction: {band!r}")
        sources = data.get("sources") or []
        for s in sources:
            if not isinstance(s, dict) or not s.get("url") or not s.get("status"):
                raise ValidationError(f"each source needs a url and a status: {s!r}")
        return cls(
            hardware=data["hardware"],
            registered_at=data["registered_at"],
            cells=cells,
            notes=data.get("notes", ""),
            bands={k: float(v) for k, v in bands.items()},
            sources=list(sources),
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
    cls = prov_class(provenance.get("throughput"))
    if cls == PROV_MEASURED:
        return CLASS_LOOKUP
    if cls == PROV_EXTRAPOLATED:
        return CLASS_EXTRAPOLATED
    return CLASS_ROOFLINE


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


def _is_positive_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


@dataclass(frozen=True)
class MeasuredMetric:
    """One measured quantity, stated with what it is and where it was read."""

    definition: str
    value: float
    quote: str = ""
    # Only meaningful for prefill throughput: the prompt length it was measured at.
    prompt_tokens: int | None = None

    def to_dict(self) -> dict:
        out: dict = {"definition": self.definition, "value": self.value}
        if self.quote:
            out["quote"] = self.quote
        if self.prompt_tokens is not None:
            out["prompt_tokens"] = self.prompt_tokens
        return out


@dataclass(frozen=True)
class MeasuredCell:
    """A sourced measurement of one matrix cell."""

    key: str
    evidence: str
    captured_at: str
    underspecified: bool
    metrics: tuple[MeasuredMetric, ...]
    source_url: str | None = None
    environment: dict | None = None
    config_quote: str = ""
    engine_version: str | None = None
    notes: str = ""

    @classmethod
    def from_dict(cls, key: str, raw: object) -> MeasuredCell:
        """Validate one cell. Every rejection names the cell and the field."""

        def bad(msg: str) -> ValidationError:
            return ValidationError(f"measurement {key!r}: {msg}")

        if not isinstance(raw, dict):
            raise bad("must be an object")
        evidence = raw.get("evidence")
        if evidence not in EVIDENCE_CLASSES:
            raise bad(f"evidence must be one of {sorted(EVIDENCE_CLASSES)}, got {evidence!r}")
        captured = raw.get("captured_at")
        try:
            _dt.date.fromisoformat(captured)
        except (TypeError, ValueError) as exc:
            raise bad(f"captured_at {captured!r} is not an ISO date") from exc
        if not isinstance(raw.get("underspecified"), bool):
            raise bad(
                "underspecified must be stated true/false: a source that omits its "
                "serving config is published but kept out of the headline, and that "
                "is a decision, not a default"
            )

        url = raw.get("source_url")
        env = raw.get("environment")
        if url is not None and not (isinstance(url, str) and url.startswith(_HTTP_SCHEMES)):
            raise bad(f"source_url must be an http(s) URL, got {url!r}")
        if evidence == EVIDENCE_THIRD_PARTY:
            if not url:
                raise bad("a third-party measurement needs a source_url")
            if any(m in url.lower() for m in OWN_CORPUS_MARKERS):
                raise bad(
                    f"source_url {url} is the TR corpus the planner was fitted on; "
                    "grading against it is not a test"
                )
        elif not url and not (isinstance(env, dict) and env):
            raise bad("an own-rig measurement needs a source_url or an environment record")

        raw_metrics = raw.get("metrics")
        if not isinstance(raw_metrics, list) or not raw_metrics:
            raise bad("metrics must be a non-empty list")
        metrics = []
        for rm in raw_metrics:
            if not isinstance(rm, dict) or "definition" not in rm:
                raise bad(f"every metric needs a definition: {rm!r}")
            definition = rm["definition"]
            if definition == DEF_AMBIGUOUS:
                raise bad(
                    "a metric whose definition is ambiguous cannot be scored against "
                    "anything; exclude it at the source"
                )
            if definition not in METRIC_DEFINITIONS:
                raise bad(
                    f"unknown metric definition {definition!r} "
                    f"(one of: {', '.join(sorted(METRIC_DEFINITIONS))})"
                )
            if not _is_positive_number(rm.get("value")):
                raise bad(f"{definition} value must be a positive number, got {rm.get('value')!r}")
            pt = rm.get("prompt_tokens")
            if definition == DEF_PREFILL and not (isinstance(pt, int) and pt > 0):
                raise bad("prefill_tps must state the prompt_tokens it was measured at")
            metrics.append(
                MeasuredMetric(
                    definition=definition,
                    value=float(rm["value"]),
                    quote=str(rm.get("quote", "")),
                    prompt_tokens=pt,
                )
            )
        scored = [SCORED_AS[m.definition] for m in metrics if m.definition in SCORED_AS]
        dupes = sorted({s for s in scored if scored.count(s) > 1})
        if dupes:
            raise bad(
                f"two measurements of {', '.join(dupes)}; supply one rather than "
                "letting the audit pick"
            )

        return cls(
            key=key,
            evidence=evidence,
            captured_at=captured,
            underspecified=raw["underspecified"],
            metrics=tuple(metrics),
            source_url=url,
            environment=env if isinstance(env, dict) else None,
            config_quote=str(raw.get("config_quote", "")),
            engine_version=raw.get("engine_version"),
            notes=str(raw.get("notes", "")),
        )

    def to_dict(self) -> dict:
        out: dict = {
            "evidence": self.evidence,
            "captured_at": self.captured_at,
            "underspecified": self.underspecified,
            "metrics": [m.to_dict() for m in self.metrics],
        }
        for name in ("source_url", "environment", "engine_version"):
            if getattr(self, name):
                out[name] = getattr(self, name)
        for name in ("config_quote", "notes"):
            if getattr(self, name):
                out[name] = getattr(self, name)
        return out


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
    evidence: str | None = None
    underspecified: bool = False
    # Which measured definition each scored metric came from.
    measured_basis: dict[str, str] = field(default_factory=dict)
    # Measured definitions retained but not scored, with the reason.
    unscored: dict[str, str] = field(default_factory=dict)
    measurement: MeasuredCell | None = None

    def to_dict(self) -> dict:
        cell = asdict(self.cell)
        cell["spec"] = self.cell.spec_dict
        return {
            "key": self.key,
            "cell": cell,
            "provenance_class": self.provenance_class,
            "evidence": self.evidence,
            "underspecified": self.underspecified,
            "predicted": self.predicted,
            "measured": self.measured,
            "measured_basis": self.measured_basis,
            "errors": {k: round(v, 6) for k, v in self.errors.items()},
            "unscored": self.unscored,
            "skipped": self.skipped,
            # The full sourced record, so the audit can be re-scored from its own
            # output without the original measurement file.
            "measurement": self.measurement.to_dict() if self.measurement else None,
        }


def outcome_from_measurement(
    cell: MatrixCell,
    provenance_class: str,
    predicted: dict[str, float],
    measurement: MeasuredCell,
) -> CellOutcome:
    """Join a prediction to a sourced measurement, comparing like with like only.

    Raises:
        ValidationError: A prefill figure measured at a different prompt length
            than the cell registers -- converting it would compare two prompts.
    """
    measured: dict[str, float] = {}
    basis: dict[str, str] = {}
    unscored: dict[str, str] = {}
    for m in measurement.metrics:
        target = SCORED_AS.get(m.definition)
        if target is None:
            unscored[m.definition] = UNSCORED_REASON.get(m.definition, "no planner prediction")
            continue
        value = m.value
        if m.definition == DEF_PREFILL:
            if m.prompt_tokens != cell.prompt_tokens:
                raise ValidationError(
                    f"measurement {cell.key!r}: prefill measured at {m.prompt_tokens} prompt "
                    f"tokens but the cell registers {cell.prompt_tokens}"
                )
            value = cell.prompt_tokens / m.value * 1000.0
        measured[target] = value
        basis[target] = m.definition

    errors = {}
    for metric, pred in predicted.items():
        err = relative_error(pred, measured.get(metric))
        if err is not None:
            errors[metric] = err
    return CellOutcome(
        key=cell.key,
        cell=cell,
        provenance_class=provenance_class,
        predicted=predicted,
        measured=measured,
        errors=errors,
        evidence=measurement.evidence,
        underspecified=measurement.underspecified,
        measured_basis=basis,
        unscored=unscored,
        measurement=measurement,
        skipped=None if errors else "no measured quantity the planner predicts",
    )


@dataclass
class ScorecardRow:
    """Error statistics for one (evidence, provenance class, metric) triple."""

    provenance_class: str
    metric: str
    n: int
    mape: float
    median_signed: float
    p90_abs: float
    worst_key: str
    worst_error: float
    underpowered: bool
    evidence: str | None = None
    median_abs: float = 0.0
    # Geometric mean fold error, exp(mean |ln(pred/meas)|): 2x high and 2x low
    # are the same size of mistake, which a signed percentage cannot say.
    gmfe: float | None = None
    # Share of cells inside the pre-registered band; None when no band was
    # registered -- a band picked after seeing the errors is not a pass rate.
    pass_rate: float | None = None
    band: float | None = None

    def to_dict(self) -> dict:
        return {
            "evidence": self.evidence,
            "provenance_class": self.provenance_class,
            "metric": self.metric,
            "n": self.n,
            "in_band_pass_rate": None if self.pass_rate is None else round(self.pass_rate, 4),
            "band": self.band,
            "median_abs_error": round(self.median_abs, 4),
            "gmfe": None if self.gmfe is None else round(self.gmfe, 4),
            "mape": round(self.mape, 4),
            # Signed, so systemic optimism is visible rather than averaged away.
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


def _gmfe(errors: list[float]) -> float | None:
    ratios = [1.0 + e for e in errors]
    if any(r <= 0 for r in ratios):
        return None  # a non-positive prediction has no fold error
    return math.exp(sum(abs(math.log(r)) for r in ratios) / len(ratios))


def score(outcomes: list[CellOutcome], bands: dict[str, float] | None = None) -> list[ScorecardRow]:
    """Aggregate per (evidence, provenance class, metric).

    Never drops a class or a worst case, never pools evidence classes, and keeps
    underspecified cells out of the rows (they are published in the raw output
    and listed in the report instead).
    """
    bands = bands or {}
    evidences = list(EVIDENCE_ORDER)
    if any(o.evidence is None for o in outcomes):
        evidences.append(None)  # outcomes built without a sourced measurement
    rows: list[ScorecardRow] = []
    for evidence in evidences:
        for cls in CLASS_ORDER:
            for metric in METRICS:
                errs = [
                    (o.key, o.errors[metric])
                    for o in outcomes
                    if o.evidence == evidence
                    and o.provenance_class == cls
                    and not o.skipped
                    and not o.underspecified
                    and metric in o.errors
                ]
                if not errs:
                    continue
                signed = [e for _, e in errs]
                abs_errs = [abs(e) for e in signed]
                worst_key, worst_err = max(errs, key=lambda kv: abs(kv[1]))
                band = bands.get(metric)
                rows.append(
                    ScorecardRow(
                        evidence=evidence,
                        provenance_class=cls,
                        metric=metric,
                        n=len(errs),
                        mape=sum(abs_errs) / len(abs_errs),
                        median_signed=statistics.median(signed),
                        median_abs=statistics.median(abs_errs),
                        gmfe=_gmfe(signed),
                        pass_rate=(
                            None
                            if band is None
                            else sum(1 for e in abs_errs if e <= band) / len(abs_errs)
                        ),
                        band=band,
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
    bands: dict[str, float] = field(default_factory=dict)
    sources: list[dict] = field(default_factory=list)
    # Which planner corpus produced the predictions ("bundled", or a path).
    models_basis: str = "bundled"

    @property
    def skipped(self) -> list[CellOutcome]:
        return [o for o in self.outcomes if o.skipped]

    @property
    def underspecified(self) -> list[CellOutcome]:
        return [o for o in self.outcomes if o.underspecified and not o.skipped]

    def to_dict(self) -> dict:
        return {
            "schema_version": MEASUREMENT_SCHEMA_VERSION,
            "matrix_fingerprint": self.fingerprint,
            "registered_at": self.registered_at,
            "generated_at": self.generated_at,
            "hardware": self.hardware,
            "models_basis": self.models_basis,
            "notes": self.notes,
            "lead_class": LEAD_CLASS,
            "bands": self.bands,
            "sources": self.sources,
            "scorecard": [r.to_dict() for r in self.rows],
            # Every cell, including skips and the worst performers. The raw record
            # is what lets someone else re-derive the table.
            "cells": [o.to_dict() for o in self.outcomes],
        }


def build_audit(
    matrix: Matrix,
    outcomes: list[CellOutcome],
    generated_at: str | None = None,
    models_basis: str = "bundled",
) -> Audit:
    return Audit(
        fingerprint=matrix.fingerprint(),
        registered_at=matrix.registered_at,
        generated_at=generated_at or _dt.date.today().isoformat(),
        hardware=matrix.hardware,
        outcomes=outcomes,
        rows=score(outcomes, matrix.bands),
        notes=matrix.notes,
        bands=matrix.bands,
        sources=matrix.sources,
        models_basis=models_basis,
    )


def load_measurements(path: str | Path) -> MeasurementSet:
    """Load sourced measurements, keyed by cell.

    Accepts a schema-v2 measurement file, or a previous v2 audit's own output
    (whose cells carry their full sourced record), so a published audit can be
    re-derived from its raw JSON without the original file, a GPU or a network.

    Raises:
        ValidationError: Missing/malformed file, the unsourced v1 shape, or any
            cell failing :meth:`MeasuredCell.from_dict`.
    """
    p = Path(path)
    if not p.exists():
        raise ValidationError(f"measurements file not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"measurements file is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValidationError("measurements must be a JSON object")
    if data.get("schema_version") != MEASUREMENT_SCHEMA_VERSION:
        raise ValidationError(
            f"measurements must be schema_version {MEASUREMENT_SCHEMA_VERSION}: every cell "
            "carries its evidence class, a source (URL or own-rig environment), a "
            "captured_at date and a definition per metric. Bare {metric: value} numbers "
            "(v1) have no source and are not accepted -- the schema is in the README's "
            "`validate` section"
        )
    if not data.get("hardware"):
        raise ValidationError("measurements must name the hardware they were taken on")

    out = MeasurementSet(hardware=data["hardware"])
    cells = data.get("cells")
    if "matrix_fingerprint" in data and isinstance(cells, list):
        # A previous audit: each cell carries its own sourced record.
        for c in cells:
            if isinstance(c, dict) and c.get("measurement"):
                out[c["key"]] = MeasuredCell.from_dict(c["key"], c["measurement"])
        return out
    if not isinstance(cells, dict):
        raise ValidationError("measurements must hold a `cells` object keyed by cell")
    for key, raw in cells.items():
        out[key] = MeasuredCell.from_dict(key, raw)
    return out


class MeasurementSet(dict):
    """``{cell_key: MeasuredCell}`` plus the hardware the file says it was taken on."""

    def __init__(self, hardware: str) -> None:
        super().__init__()
        self.hardware = hardware


def format_markdown(audit: Audit) -> str:
    """Render the audit as a report, leading with the class that makes a claim."""
    out: list[str] = [
        "# ChimeraForge prediction-vs-measured audit",
        "",
        f"- **Hardware:** {audit.hardware}",
        f"- **Matrix registered:** {audit.registered_at}",
        f"- **Matrix fingerprint:** `{audit.fingerprint[:16]}`",
        f"- **Generated:** {audit.generated_at}",
        f"- **Cells:** {len(audit.outcomes)} ({len(audit.skipped)} skipped, "
        f"{len(audit.underspecified)} underspecified)",
        f"- **Predictions from:** {audit.models_basis} planner corpus",
        "",
    ]
    if audit.bands:
        bands = ", ".join(f"{m} +-{b:.0%}" for m, b in audit.bands.items())
        out += [f"- **Pre-registered bands:** {bands}", ""]
    if audit.notes:
        out += [audit.notes, ""]

    evidences = [e for e in (*EVIDENCE_ORDER, None) if any(r.evidence == e for r in audit.rows)]
    for evidence in evidences:
        if evidence is not None:
            out += [f"# Evidence: {evidence}", ""]
            out += [_EVIDENCE_NOTE[evidence], ""]
        for cls in CLASS_ORDER:
            rows = [r for r in audit.rows if r.provenance_class == cls and r.evidence == evidence]
            if not rows:
                continue
            out.append(f"## {cls}")
            out += ["", _CLASS_NOTE[cls]] if cls in _CLASS_NOTE else []
            out += [
                "",
                "| Metric | n | In-band | Median abs | GMFE | Bias (median signed) | "
                "Worst cell | Worst |",
                "|---|---|---|---|---|---|---|---|",
            ]
            for r in rows:
                flag = " *" if r.underpowered else ""
                in_band = "n/a" if r.pass_rate is None else f"{r.pass_rate:.0%}"
                gmfe = "n/a" if r.gmfe is None else f"{r.gmfe:.2f}x"
                # Cell keys are pipe-delimited; unescaped, they split the table row.
                worst = r.worst_key.replace("|", "\\|")
                out.append(
                    f"| {r.metric} | {r.n}{flag} | {in_band} | {r.median_abs:.1%} | {gmfe} | "
                    f"{r.median_signed:+.1%} | `{worst}` | {r.worst_error:+.1%} |"
                )
            out.append("")
    if any(r.underpowered for r in audit.rows):
        out += [
            f"`*` fewer than {MIN_CELLS_FOR_RATE} cells -- treat as an anecdote, not a rate.",
            "",
        ]
    if any(r.pass_rate is None for r in audit.rows):
        out += ["In-band `n/a`: no band was pre-registered for that metric.", ""]
    if audit.underspecified:
        out += [
            "## Underspecified cells (published, not scored)",
            "",
            "_The source omits its engine version or serving flags, so these are kept "
            "out of every row above. Their errors are listed here rather than hidden._",
            "",
        ]
        for o in audit.underspecified:
            errs = ", ".join(f"{m} {e:+.1%}" for m, e in o.errors.items())
            src = o.measurement.source_url if o.measurement and o.measurement.source_url else ""
            out.append(f"- `{o.key}` -- {errs} {src}".rstrip())
        out.append("")
    unscored = [o for o in audit.outcomes if o.unscored]
    if unscored:
        out += ["## Measured but not comparable", ""]
        for o in unscored:
            for definition, reason in o.unscored.items():
                out.append(f"- `{o.key}` -- {definition}: {reason}")
        out.append("")
    if audit.skipped:
        out += ["## Skipped cells", ""]
        out += [f"- `{o.key}` -- {o.skipped}" for o in audit.skipped]
        out.append("")
    if audit.sources:
        out += ["## Sources consulted (pre-registered)", ""]
        for s in audit.sources:
            reason = f" -- {s['reason']}" if s.get("reason") else ""
            out.append(f"- [{s['status']}] {s['url']}{reason}")
        out.append("")
    out += [
        "Positive error means the planner was **optimistic** (predicted above measured).",
        "GMFE is the geometric mean fold error: 2x too high and 2x too low both score 2.0x.",
        "",
        "Every cell, including the worst, is retained in the raw JSON alongside this "
        "report so the table can be re-derived independently.",
    ]
    return "\n".join(out)


_EVIDENCE_NOTE = {
    EVIDENCE_OWN_RIG: (
        "_Ground truth measured on this project's own hardware with `bench`, "
        "environment recorded per cell._"
    ),
    EVIDENCE_THIRD_PARTY: (
        "_Ground truth from published third-party benchmarks: different silicon, "
        "driver and engine build than any own-rig cell, each cell quoting its source "
        "and serving config. Reported on its own and never averaged with own-rig "
        "cells._"
    ),
}

_CLASS_NOTE = {
    CLASS_LOOKUP: (
        "_Not an out-of-sample test of the planner's model: for these cells the "
        "measured corpus **is** the prediction. Against third-party evidence it tests "
        "how well one rig's row transfers to another's._"
    ),
    CLASS_EXTRAPOLATED: (
        "_Out-of-sample for this GPU: a corpus row measured on the reference rig, "
        "scaled by memory bandwidth. What is under test here is the extrapolation, "
        "not the measurement._"
    ),
    LEAD_CLASS: (
        "_The out-of-sample path: no measured row exists, so the planner is "
        "predicting from first principles._"
    ),
}
