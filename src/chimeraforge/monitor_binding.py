"""Pure saved-target and passive observation binding assembly."""

from __future__ import annotations

from typing import Any

from chimeraforge import __version__
from chimeraforge.bench import serving
from chimeraforge.bench.serving_binding import bind, serving_binding
from chimeraforge.monitor import MonitorRequest
from chimeraforge.plan_check import identity

IDENTITY_FIELDS = ("backend", "model", "metric_backend", "metric_model")


def _aggregate(rows: list[dict], fields: tuple[str, ...], *, configuration: bool = False) -> str:
    states = [row[name]["state"] for row in rows for name in fields]
    if "mismatch" in states:
        return "mismatch"
    if configuration:
        return "unverified"
    return "matched" if states and all(state == "matched" for state in states) else "unavailable"


def _comparison(
    data: dict[str, Any],
    candidate: dict[str, Any],
    effective: MonitorRequest,
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    fields = serving_binding(data, candidate, before, after)
    fields["metric_backend"] = bind(
        candidate["backend"], effective.backend, source="selected histogram contract"
    )
    fields["metric_model"] = bind(
        candidate["model"], effective.model, source="exact model_name histogram selection"
    )
    for name in ("metric_backend", "metric_model"):
        fields[name]["scope"] = "operator-selected histogram evidence"
    fields["immutable_weights"] = bind(
        None,
        after.get("model_digest"),
        state="unavailable",
        source=after.get("source"),
        detail="Saved ModelSpec does not bind immutable weights/revision.",
    )
    fields["immutable_weights"]["scope"] = "model weights/revision"
    fields["workload"] = bind(
        {
            name: data["inputs"][name]
            for name in ("prompt_tokens", "avg_tokens", "request_rate", "prefix_cache_hit_rate")
        },
        None,
        source="passive histograms",
        detail="Histograms do not attest live token lengths, concurrency or cache-hit rate.",
    )
    fields["workload"]["scope"] = "live serving traffic"
    # Required identity must be known throughout the window, not just afterward.
    for name in ("backend", "model"):
        prior = serving_binding(data, candidate, before, before)[name]
        if prior["state"] == "mismatch" or fields[name]["state"] == "mismatch":
            fields[name] = prior if prior["state"] == "mismatch" else fields[name]
        elif prior["state"] != "matched":
            fields[name] = prior
    prior_fields = serving_binding(data, candidate, before, before)
    for name, prior in prior_fields.items():
        if prior["state"] == "mismatch":
            fields[name] = prior
    return fields


def assemble_binding(
    data: dict[str, Any],
    candidate: dict[str, Any],
    candidate_index: int,
    effective: MonitorRequest,
    sources: dict[str, str],
    observations: list[dict[str, Any]],
    *,
    retain_prefix: bool = False,
    producer_version: str | None = None,
) -> dict[str, Any]:
    comparisons = [
        _comparison(data, candidate, effective, before, after)
        for before, after in zip(observations, observations[1:])
    ]
    evidence = list(comparisons)
    if retain_prefix:
        for snapshot in observations:
            evidence.append(_comparison(data, candidate, effective, snapshot, snapshot))
    config_fields = (
        tuple(name for name in evidence[0] if name not in IDENTITY_FIELDS) if evidence else ()
    )
    latest = dict(evidence[-1]) if evidence else serving_binding(data, candidate, {}, {})
    for fields in evidence:
        for name, row in fields.items():
            if row["state"] == "mismatch":
                latest[name] = row
    binding = {
        "schema_version": 1,
        "plan": {
            "fingerprint": data["fingerprint"],
            "candidate_index": candidate_index,
            "identity": identity(candidate),
            "tool_version": data["tool"]["version"],
        },
        "monitor_tool_version": __version__ if producer_version is None else producer_version,
        "endpoint": serving.sanitize_message(effective.url),
        "target_sources": sources,
        "identity": {
            "state": _aggregate(evidence, IDENTITY_FIELDS),
            "fields": {name: latest[name] for name in IDENTITY_FIELDS if name in latest},
        },
        "configuration": {
            "state": _aggregate(evidence, config_fields, configuration=True),
            "fields": {name: row for name, row in latest.items() if name not in IDENTITY_FIELDS},
        },
        "windows": [
            {
                "window_index": index,
                "before": observations[index],
                "after": observations[index + 1],
                "fields": fields,
            }
            for index, fields in enumerate(comparisons)
        ],
        "limits": [
            "Matched endpoint model/backend is not full deployment qualification.",
            "Serving engine DP size does not attest endpoint/load-balancer fleet replicas.",
            "GPU geometry, live workload, LoRA/offload and immutable weights remain unverified "
            "when not observed.",
            "Histogram SLO outcomes describe passive traffic; "
            "no benchmark or planner accuracy claim is made.",
            "Metadata observations bracket scrapes approximately; "
            "they are not atomic server snapshots.",
        ],
    }
    return binding
