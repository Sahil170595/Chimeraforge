"""Serial campaigns over one frozen private workload and unmodified native receipts."""

from __future__ import annotations

import asyncio
import copy
from dataclasses import asdict, dataclass, field
from pathlib import Path
import time

from chimeraforge.bench.metrics import now_iso
from chimeraforge.bench.serving import sanitize_message
from chimeraforge.bench.trace import TraceReplay, _error
from chimeraforge.bench.trace_workload import (
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_TRACE_TIMEOUT_SECONDS,
    MAX_TIMEOUT_SECONDS,
    TraceRequest,
    TraceSLO,
    descriptor,
    load_workload,
    number,
    validate_options,
)
from chimeraforge.planner.replay import digest

DEFAULT_REPLICATES = 3
MAX_REPLICATES = 16
MAX_CAMPAIGN_REQUESTS = 4096
DEFAULT_CAMPAIGN_TIMEOUT_SECONDS = 1800
_clock = time.perf_counter


@dataclass(frozen=True)
class TraceCampaign:
    """Defensive complete declared population; no physical independence claim."""

    _data: dict
    _protected_paths: tuple[Path, ...] = field(default=(), repr=False)

    def to_dict(self) -> dict:
        return copy.deepcopy(self._data)

    def save(self, path: str | Path) -> None:
        from chimeraforge.api import PlanArtifact
        from chimeraforge.plan_study import protect_output

        protect_output(path, self._protected_paths)
        PlanArtifact(self.to_dict()).save(path)


def _prepare(
    source: list[TraceRequest] | str | Path,
    *,
    model: str,
    backend: str,
    base_url: str | None,
    replicates: int,
    concurrency: int,
    request_timeout: float,
    trace_timeout: float,
    campaign_timeout: float,
    slos: TraceSLO,
    stop_event: asyncio.Event | None,
) -> tuple[list[TraceRequest], dict, tuple[Path, ...]]:
    from chimeraforge import __version__
    from chimeraforge.api import PlanError

    try:
        rows, binding, protected = load_workload(source)
        validate_options(
            rows, model, backend, concurrency, request_timeout, trace_timeout, slos, base_url
        )
        if (
            type(replicates) is not int
            or not 1 <= replicates <= MAX_REPLICATES
            or len(rows) * replicates > MAX_CAMPAIGN_REQUESTS
            or not number(campaign_timeout, positive=True)
            or campaign_timeout > MAX_TIMEOUT_SECONDS
            or stop_event is not None
            and not isinstance(stop_event, asyncio.Event)
        ):
            raise PlanError("invalid campaign population, timeout or caller event")
    except PlanError:
        raise PlanError("invalid trace campaign workload or controls") from None
    manifest = {
        "schema_version": 1,
        "kind": "chimeraforge.trace-campaign-manifest",
        "prepared_at": now_iso(),
        "tool": {"name": "chimeraforge", "version": __version__},
        "workload": binding,
        "ordered_descriptors": [descriptor(row) for row in rows],
        "population": {
            "replicates": replicates,
            "requests_per_replicate": len(rows),
            "total_requests": len(rows) * replicates,
        },
        "controls": {
            "model": model,
            "backend": backend,
            "endpoint": sanitize_message(base_url) if base_url else None,
            "concurrency": concurrency,
            "request_timeout_seconds": request_timeout,
            "trace_timeout_seconds": trace_timeout,
            "campaign_timeout_seconds": campaign_timeout,
            "targets": asdict(slos),
        },
        "policy": {
            "execution": "serial",
            "retries": 0,
            "warmup_executions": 0,
            "stop_after_first_incomplete_replicate": True,
        },
        "scope": (
            "client-recorded preparation; external preregistration/time authentication unverified"
        ),
    }
    manifest["fingerprint"] = digest(manifest)
    return rows, manifest, protected


def _native_result(result: TraceReplay, manifest: dict) -> tuple[dict, str]:
    """Bind a native producer snapshot without rewriting its raw hash or fingerprint."""
    if type(result) is not TraceReplay:
        raise ValueError("native replay receipt unavailable")
    native = result.to_dict()
    if (
        native.get("workload")
        != {"canonical_sha256": manifest["workload"]["canonical_sha256"], "raw_sha256": None}
        or type(native.get("requests")) is not list
        or digest([row.get("descriptor") for row in native["requests"]])
        != digest(manifest["ordered_descriptors"])
        or native.get("fingerprint")
        != digest({k: v for k, v in native.items() if k != "fingerprint"})
    ):
        raise ValueError("native replay workload binding unavailable")
    count = manifest["population"]["requests_per_replicate"]
    completed = (
        type(native.get("exit_code")) is int
        and native["exit_code"] == 0
        and native.get("error") is None
        and native.get("stop_reason") is None
        and native.get("resource_cleanup", {}).get("state") == "completed"
        and native.get("execution", {}).get("planned") == count
        and native["execution"].get("completed") == count
        and len(native["requests"]) == count
        and all(row.get("state") == "completed" for row in native["requests"])
    )
    return native, "completed" if completed else "incomplete"


async def _drain_waiter(waiter: asyncio.Task | None) -> None:
    if waiter is not None:
        waiter.cancel()
        await asyncio.gather(waiter, return_exceptions=True)


async def _replicate(
    rows: list[TraceRequest],
    manifest: dict,
    options: dict,
    caller_stop: asyncio.Event | None,
    deadline: float,
) -> tuple[dict | None, dict | None, str, str | None]:
    from chimeraforge.bench import trace

    child_stop = asyncio.Event()
    child = asyncio.create_task(
        trace.replay(rows, **options, stop_event=child_stop), name="trace-campaign-replay"
    )
    waiter = (
        asyncio.create_task(caller_stop.wait(), name="trace-campaign-stop")
        if caller_stop is not None
        else None
    )
    reason = None
    try:
        tasks = {child} | ({waiter} if waiter is not None else set())
        done, _ = await asyncio.wait(
            tasks, timeout=max(0, deadline - _clock()), return_when=asyncio.FIRST_COMPLETED
        )
        reason = (
            "caller_stop"
            if caller_stop is not None and caller_stop.is_set()
            else "campaign_deadline"
            if not done or _clock() >= deadline
            else None
        )
        if reason is not None:
            child_stop.set()
        # Cancel the owned control waiter before cooperatively draining native replay.
        await _drain_waiter(waiter)
        waiter = None
        result = await child
        native, state = _native_result(result, manifest)
        return native, None, state, reason
    except asyncio.CancelledError:
        child.cancel()
        await _drain_waiter(waiter)
        waiter = None
        await asyncio.gather(child, return_exceptions=True)
        raise
    except Exception as exc:
        return None, _error(exc, "campaign_replay"), "failed", reason
    finally:
        await _drain_waiter(waiter)
        if not child.done():
            child.cancel()
            await asyncio.gather(child, return_exceptions=True)


async def replay_campaign(
    source: list[TraceRequest] | str | Path,
    *,
    model: str,
    backend: str = "ollama",
    base_url: str | None = None,
    replicates: int = DEFAULT_REPLICATES,
    concurrency: int = 1,
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    trace_timeout: float = DEFAULT_TRACE_TIMEOUT_SECONDS,
    campaign_timeout: float = DEFAULT_CAMPAIGN_TIMEOUT_SECONDS,
    slos: TraceSLO | None = None,
    stop_event: asyncio.Event | None = None,
) -> TraceCampaign:
    targets = slos if slos is not None else TraceSLO()
    rows, manifest, protected = _prepare(
        source,
        model=model,
        backend=backend,
        base_url=base_url,
        replicates=replicates,
        concurrency=concurrency,
        request_timeout=request_timeout,
        trace_timeout=trace_timeout,
        campaign_timeout=campaign_timeout,
        slos=targets,
        stop_event=stop_event,
    )
    options = {
        "model": model,
        "backend_name": backend,
        "base_url": base_url,
        "concurrency": concurrency,
        "request_timeout": request_timeout,
        "trace_timeout": trace_timeout,
        "slos": targets,
    }
    origin = _clock()
    deadline = origin + campaign_timeout
    replicas = []
    stop_reason = None
    for index in range(replicates):
        if stop_reason is None:
            stop_reason = (
                "caller_stop"
                if stop_event is not None and stop_event.is_set()
                else "campaign_deadline"
                if _clock() >= deadline
                else None
            )
        replica = {
            "index": index,
            "manifest_fingerprint": manifest["fingerprint"],
            "workload_ref": manifest["workload"]["canonical_sha256"],
            "start_s": None,
            "end_s": None,
            "state": "not_started",
            "receipt": None,
            "error": None,
            "reason": stop_reason,
        }
        if stop_reason is None:
            admission = _clock()
            stop_reason = (
                "caller_stop"
                if stop_event is not None and stop_event.is_set()
                else "campaign_deadline"
                if admission >= deadline
                else None
            )
            replica["reason"] = stop_reason
        if stop_reason is None:
            replica["start_s"] = admission - origin
            native, error, state, stopped = await _replicate(
                rows, manifest, options, stop_event, deadline
            )
            replica.update(
                receipt=native,
                error=error,
                state=state,
                end_s=_clock() - origin,
                reason=None
                if state == "completed"
                else "native_incomplete"
                if state == "incomplete"
                else "replay_failed",
            )
            stop_reason = stopped or (
                "first_incomplete_replicate" if state != "completed" else None
            )
        replicas.append(replica)
    counts = {
        state: sum(r["state"] == state for r in replicas)
        for state in ("completed", "incomplete", "failed", "not_started")
    }
    complete = counts["completed"] == replicates
    report = {
        "schema_version": 1,
        "kind": "chimeraforge.trace-campaign",
        "created_at": now_iso(),
        "manifest": manifest,
        "replicas": replicas,
        "execution": {"planned": replicates, **counts},
        "clock": {
            "basis": "client time.perf_counter monotonic offsets in seconds",
            "origin": origin,
            "elapsed_seconds": _clock() - origin,
        },
        "stop_reason": stop_reason,
        "state": "completed" if complete else "incomplete",
        "exit_code": 0 if complete else 1,
        "assurance": {
            "external_preregistration": "unverified",
            "time_authentication": "unverified",
            "independent_cold_executions": "unverified",
            "cache_independence": "unverified",
            "gpu_geometry": "unverified",
            "served_weights": "unverified",
            "provider_termination": "unverified",
        },
        "limits": (
            "Serial client-recorded campaign; no retries/warmup/survivor aggregation. "
            "Deadline stops admission and signals native replay; adapter drain is cooperative "
            "and may be unbounded, not guaranteed wall return or physical provider termination. "
            "Population limits are not a serialization-byte ceiling or independence proof."
        ),
    }
    report["fingerprint"] = digest(report)
    return TraceCampaign(report, protected)
