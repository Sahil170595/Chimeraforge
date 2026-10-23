"""Bind bounded, passive monitoring to an immutable saved candidate."""

from __future__ import annotations

import asyncio
from dataclasses import replace
import logging
from pathlib import Path
import threading
from typing import TYPE_CHECKING, Callable, Any
from urllib.parse import urlsplit, urlunsplit

from chimeraforge.bench import serving
from chimeraforge.bench.backends import get_backend
from chimeraforge.bench.backends.base import backend_lifecycle
from chimeraforge.monitor import MonitorReport, MonitorRequest, MonitorWindow, run_monitor

if TYPE_CHECKING:
    from chimeraforge.api import PlanArtifact

logger = logging.getLogger(__name__)
CANCELLATION_POLL_SECONDS = 0.05
MAX_CLEANUP_SECONDS = (
    1.0  # HTTPX pool closure needs no server round trip; cap cancellation cleanup.
)


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

    cleanup_seconds = min(request.timeout, MAX_CLEANUP_SECONDS)
    cleanup: dict[str, Any] = {
        "state": "not_started",
        "metadata_budget_seconds": request.timeout,
        "budget_seconds": cleanup_seconds,
    }

    async def operation() -> dict:
        backend = get_backend(request.backend, base_url=url)
        async with backend_lifecycle(backend, _cleanup=cleanup):
            return await serving.observe_backend(backend, request.model)

    task = asyncio.create_task(operation())
    loop = asyncio.get_running_loop()
    deadline = loop.time() + request.timeout
    result: dict[str, Any] = {}
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
            await asyncio.wait_for(task, cleanup_seconds)
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
    from chimeraforge.monitor_binding import assemble_binding

    binding = assemble_binding(data, candidate, candidate_index, effective, sources, observations)
    return replace(report, plan_binding=binding)
