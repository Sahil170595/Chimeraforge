"""Bind bounded, passive monitoring to an immutable saved candidate."""

from __future__ import annotations

import asyncio
from dataclasses import replace
import logging
from pathlib import Path
import threading
from typing import TYPE_CHECKING, Callable
from urllib.parse import urlsplit, urlunsplit

from chimeraforge import __version__
from chimeraforge.bench import serving
from chimeraforge.bench.backends import get_backend
from chimeraforge.bench.backends.base import backend_lifecycle
from chimeraforge.bench.serving_binding import bind, serving_binding
from chimeraforge.monitor import MonitorReport, MonitorRequest, MonitorWindow, run_monitor
from chimeraforge.plan_check import identity

if TYPE_CHECKING:
    from chimeraforge.api import PlanArtifact

logger = logging.getLogger(__name__)
CANCELLATION_POLL_SECONDS = 0.05
MAX_CLEANUP_SECONDS = (
    1.0  # HTTPX pool closure needs no server round trip; cap cancellation cleanup.
)
IDENTITY_FIELDS = ("backend", "model", "metric_backend", "metric_model")


def _serving_url(url: str) -> str | None:
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    if path.endswith("/metrics"):
        path = path.removesuffix("/metrics")
    elif path:
        return None
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


async def _observe(request: MonitorRequest, stop: threading.Event) -> dict:
    """Bound metadata traffic and cooperative cleanup separately, with explicit limits."""
    url = _serving_url(request.url)
    if url is None:
        return {"source": "custom metrics route does not establish a serving metadata base URL"}

    cleanup = {
        "state": "not_started",
        "metadata_budget_seconds": request.timeout,
        "budget_seconds": min(request.timeout, MAX_CLEANUP_SECONDS),
    }

    async def operation() -> dict:
        backend = get_backend(request.backend, base_url=url)
        async with backend_lifecycle(backend, _cleanup=cleanup):
            return await serving.observe_backend(backend, request.model)

    task = asyncio.create_task(operation())
    loop = asyncio.get_running_loop()
    deadline = loop.time() + request.timeout
    result = {}
    try:
        while True:
            remaining = deadline - loop.time()
            if stop.is_set() or remaining <= 0:
                logger.info("monitor metadata observation cancelled or exceeded its total deadline")
                result = {
                    "source": "metadata cancelled" if stop.is_set() else "metadata total timeout"
                }
                break
            done, _ = await asyncio.wait({task}, timeout=min(remaining, CANCELLATION_POLL_SECONDS))
            if done:
                result = serving.safe_observation(task.result())
                break
    except Exception as exc:
        logger.warning(
            "monitor metadata unavailable (%s): %s",
            type(exc).__name__,
            serving.sanitize_message(str(exc)),
        )
        result = {"source": "metadata observation unavailable", "limitations": [type(exc).__name__]}
    finally:
        if not task.done():
            task.cancel()
        try:
            await asyncio.wait_for(task, cleanup["budget_seconds"])
        except (asyncio.CancelledError, asyncio.TimeoutError):
            if cleanup["state"] != "completed":
                logger.warning(
                    "monitor adapter cleanup incomplete within its bounded cancellation budget"
                )
        except Exception as exc:
            logger.warning(
                "monitor adapter operation failed during closure (%s): %s",
                type(exc).__name__,
                serving.sanitize_message(str(exc)),
            )
    result["resource_cleanup"] = cleanup
    return result


def _aggregate(rows: list[dict], fields: tuple[str, ...], *, configuration: bool = False) -> str:
    states = [row[name]["state"] for row in rows for name in fields]
    if "mismatch" in states:
        return "mismatch"
    if configuration:
        return "unverified"
    return "matched" if states and all(state == "matched" for state in states) else "unavailable"


def monitor_saved(
    saved: PlanArtifact | str | Path,
    request: MonitorRequest,
    *,
    candidate_index: int = 0,
    stop_event: threading.Event | None = None,
    on_window: Callable[[MonitorWindow], None] | None = None,
) -> MonitorReport:
    from chimeraforge.api import PlanArtifact, artifact_from_dict, load_plan

    artifact = (
        artifact_from_dict(saved.to_dict()) if isinstance(saved, PlanArtifact) else load_plan(saved)
    )
    artifact.candidate(candidate_index)
    data = artifact.to_dict()
    candidate = data["result"]["candidates"][candidate_index]
    sources = {}
    targets = {}
    for name in ("ttft", "tpot"):
        field = name + "_slo"
        explicit = getattr(request, field)
        targets[field] = explicit if explicit is not None else data["inputs"][field]
        sources[name] = (
            "explicit_override"
            if explicit is not None
            else "saved_request"
            if targets[field] is not None
            else "not_set"
        )
    effective = replace(request, **targets)
    effective.validate()
    stop = stop_event if stop_event is not None else threading.Event()
    observations: list[dict] = []

    def observe() -> None:
        if not stop.is_set():
            observations.append(asyncio.run(_observe(effective, stop)))

    report = run_monitor(effective, stop_event=stop, on_window=on_window, _on_scrape=observe)
    comparisons = []
    for before, after in zip(observations, observations[1:]):
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
        comparisons.append(fields)
    config_fields = (
        tuple(name for name in comparisons[0] if name not in IDENTITY_FIELDS) if comparisons else ()
    )
    latest = dict(comparisons[-1]) if comparisons else serving_binding(data, candidate, {}, {})
    for fields in comparisons:
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
        "monitor_tool_version": __version__,
        "endpoint": serving.sanitize_message(effective.url),
        "target_sources": sources,
        "identity": {
            "state": _aggregate(comparisons, IDENTITY_FIELDS),
            "fields": {name: latest[name] for name in IDENTITY_FIELDS if name in latest},
        },
        "configuration": {
            "state": _aggregate(comparisons, config_fields, configuration=True),
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
    return replace(report, plan_binding=binding)
