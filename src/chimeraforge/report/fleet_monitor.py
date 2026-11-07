"""Static ordinal diagnostics from a strictly received passive fleet."""

from __future__ import annotations

from collections.abc import Iterator
import hashlib

from chimeraforge.fleet_monitor_types import FleetMonitorReport, FleetSlot
from chimeraforge.monitor import MetricAssessment, MonitorWindow
from chimeraforge.report.trace import TraceReport, admit_title, materialize
from chimeraforge.report.trace_formats import escape, markdown_text, number
from chimeraforge.workload import ENGINE_METRICS

PROFILE = "fleet monitor report"
OUTCOMES = {0: "pass", 3: "breach", 4: "unknown", 5: "mismatch"}
METRICS = ("ttft", "tpot", "itl")
COLUMNS = ("Window", "Evidence", "SLO", "Seconds", "TTFT", "TPOT", "ITL")
SCOPE = (
    "Descriptive native histogram windows for declared members. "
    "Null values remain unavailable, and observed zeros remain zero. "
    "An unbounded P95 upper bucket has no finite upper bound. "
    "No pooled metrics, regression gate, traffic authentication or capacity assessment."
)


def _reset(window: MonitorWindow) -> bool:
    families = [ENGINE_METRICS[window.backend]["requests_total"]]
    families.extend(metric.metric for metric in window.metrics.values() if metric.metric)
    for metric in window.metrics.values():
        if metric.samples is not None:
            continue
        if metric.reason == "process start time changed: engine restart invalidates this window":
            return True
        for suffix in (
            " reset or changed lifetime: window is unknown",
            " counter reset invalidates this window",
        ):
            if metric.reason.endswith(suffix):
                name = metric.reason.removesuffix(suffix)
                if any(name == family or name.startswith(family + "_") for family in families):
                    return True
    return False


def _metric(metric: MetricAssessment) -> str:
    upper = (
        "unbounded"
        if metric.samples is not None and metric.p95_upper_ms is None
        else number(metric.p95_upper_ms)
    )
    return (
        f"{metric.outcome} / samples: {number(metric.samples)} / "
        f"P95 ms: {number(metric.p95_lower_ms)} to {upper} / "
        f"target ms: {number(metric.target_ms)}"
    )


def _rows(slot: FleetSlot, requested: int | None) -> Iterator[tuple[str, ...]]:
    for index in range(requested if requested is not None else len(slot.windows)):
        if index >= len(slot.windows):
            yield (str(index + 1), "missing", *("unavailable",) * (len(COLUMNS) - 2))
            continue
        window = slot.windows[index]
        state = "observed"
        if _reset(window):
            state = "reset"
        elif all(metric.samples is None for metric in window.metrics.values()):
            state = "unavailable"
        yield (
            str(index + 1),
            state,
            window.outcome,
            number(window.seconds),
            *(_metric(window.metrics[name]) for name in METRICS),
        )


def _summary(report: FleetMonitorReport, requested: int | None, source_sha: str) -> Iterator[str]:
    code = report.exit_code
    yield f"Native receipt schema: {report.schema_version} / source SHA-256: {source_sha}"
    yield (
        f"Original plan fingerprint: {report.plan['fingerprint']} / "
        f"candidate index: {report.plan['candidate_index']} / backend: {report.backend}"
    )
    yield (
        f"Original members: {len(report.slots)} / requested windows per member: {number(requested)}"
    )
    yield (
        f"Native outcome: {OUTCOMES[code]} / native exit: {code} / "
        f"cleanup: {report.cleanup['state']} / cancelled: {str(report.cancelled).lower()}"
    )
    yield (
        f"Native budget: requests {report.budget['requests']} / "
        f"accepted body bytes {report.budget['accepted_body_bytes']} / "
        f"termination: {report.budget['termination'] or 'none'}"
    )
    yield (
        f"Native target sources: TTFT {report.target_sources['ttft']} / "
        f"TPOT {report.target_sources['tpot']}"
    )
    yield SCOPE


def _member(slot: FleetSlot) -> str:
    return (
        f"State: {slot.state} / SLO: {slot.slo} / "
        f"identity: {slot.binding['identity']['state']} / "
        f"configuration: {slot.binding['configuration']['state']} / "
        f"observed windows: {len(slot.windows)}"
    )


def _chunks(
    report: FleetMonitorReport, requested: int | None, source_sha: str, title: str, fmt: str
) -> Iterator[str]:
    if fmt == "markdown":
        yield f"# {markdown_text(title)}\n\n"
        yield "\n\n".join(_summary(report, requested, source_sha)) + "\n\n"
        for ordinal, slot in enumerate(report.slots, 1):
            yield f"### Member {ordinal}\n\n{_member(slot)}\n\n"
            yield "| " + " | ".join(COLUMNS) + " |\n"
            yield "|" + "---|" * len(COLUMNS) + "\n"
            for row in _rows(slot, requested):
                yield "| " + " | ".join(row) + " |\n"
            yield "\n"
        return
    yield (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(title)}</title></head><body><main><h1>{escape(title)}</h1>\n"
    )
    for line in _summary(report, requested, source_sha):
        yield f"<p>{escape(line)}</p>\n"
    for ordinal, slot in enumerate(report.slots, 1):
        yield f'<section data-member="{ordinal}"><h2>Member {ordinal}</h2>'
        yield f"<p>{escape(_member(slot))}</p>\n<table><thead><tr>"
        yield "".join(f'<th scope="col">{column}</th>' for column in COLUMNS)
        yield "</tr></thead><tbody>\n"
        for row in _rows(slot, requested):
            yield f'<tr data-window="{row[0]}" data-window-state="{row[1]}">'
            yield "".join(f"<td>{escape(value)}</td>" for value in row)
            yield "</tr>\n"
        yield "</tbody></table></section>\n"
    yield "</main></body></html>\n"


def render(report: FleetMonitorReport, *, format: str, title: str) -> TraceReport:
    """Present a native receipt returned by the strict loader without recalculation."""
    from chimeraforge.api import PlanError

    if type(format) is not str or format not in {"html", "markdown"}:
        raise PlanError("unsupported fleet monitor report format")
    admit_title(title, PROFILE)
    raw = report._held_bytes
    assert raw is not None  # The strict native loader always holds the admitted bytes.
    requested = report.effective_controls["windows"] if report.effective_controls else None
    stream = _chunks(report, requested, hashlib.sha256(raw).hexdigest(), title, format)
    return TraceReport(materialize(stream, PROFILE), "fleet-monitor", format, report._input_paths)
