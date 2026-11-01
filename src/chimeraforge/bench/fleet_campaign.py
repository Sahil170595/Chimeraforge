"""Serial original-fleet executions over one held native preparation."""

from __future__ import annotations

import asyncio
from dataclasses import replace
import logging
from pathlib import Path
import time
from collections.abc import Mapping
from typing import Any

from chimeraforge.bench import fleet_trace, trace
from chimeraforge.bench.fleet_campaign_types import (
    FleetTraceCampaign,
    KIND,
    MANIFEST_KIND,
    CAMPAIGN_LIMITS,
    canonical_hash,
)
from chimeraforge.bench.fleet_trace_inputs import prepare, prepare_connections, _PreparedFleetTrace
from chimeraforge.bench.fleet_trace_types import FleetTraceReplay, TraceRoute
from chimeraforge.bench.metrics import now_iso
from chimeraforge.bench.trace_campaign import (
    DEFAULT_CAMPAIGN_TIMEOUT_SECONDS,
    DEFAULT_REPLICATES,
    MAX_CAMPAIGN_REQUESTS,
    MAX_REPLICATES,
)
from chimeraforge.bench.trace_workload import MAX_TIMEOUT_SECONDS, TraceRequest, descriptor, number
from chimeraforge.fleet_monitor_types import FleetEndpoint
from chimeraforge.monitor_connection import MonitorConnection
from chimeraforge.plan_check import identity

DEFAULT_EXECUTIONS = DEFAULT_REPLICATES
MAX_EXECUTIONS = MAX_REPLICATES
_clock = time.perf_counter
LOG = logging.getLogger(__name__)
STATES = ("completed", "incomplete", "failed", "not_started")


def manifest_for(prepared: _PreparedFleetTrace, executions: int, timeout: float) -> dict:
    from chimeraforge import __version__

    plan = prepared.plan
    manifest = {
        "schema_version": 1,
        "kind": MANIFEST_KIND,
        "prepared_at": now_iso(),
        "tool": {"name": "chimeraforge", "version": __version__},
        "plan": {
            "snapshot": plan.data,
            "fingerprint": plan.data["fingerprint"],
            "raw_sha256": plan.plan_raw_sha256,
            "candidate_index": plan.candidate_index,
            "candidate_sha256": canonical_hash(plan.candidate),
            "identity": identity(plan.candidate),
            "served_model": plan.served_model,
            "model_override": plan.model_override,
        },
        "workload": plan.workload,
        "ordered_descriptors": [descriptor(row) for row in plan.requests],
        "endpoints": [{"id": row.id, "url": row.url} for row in prepared.endpoints],
        "routes": {
            **prepared.route_identity,
            "rows": [
                {"request_id": row.request_id, "endpoint_id": row.endpoint_id}
                for row in prepared.routes
            ],
        },
        "population": {
            "executions": executions,
            "original_replicas": len(prepared.endpoints),
            "requests_per_execution": len(plan.requests),
            "total_requests": len(plan.requests) * executions,
        },
        "controls": {
            "backend": plan.backend,
            "model": plan.served_model,
            "output_cap_tokens": plan.candidate["decode_tokens_per_req"],
            "concurrency": plan.concurrency,
            "request_timeout_seconds": plan.request_timeout,
            "trace_timeout_seconds": plan.trace_timeout,
            "cleanup_timeout_seconds": prepared.cleanup_timeout,
            "targets": {
                name: getattr(plan.slos, name)
                for name in ("latency_ms", "first_output_ms", "tpot_ms")
            },
            "replica_scope": "declared_member",
            "declared_original_replicas": len(prepared.endpoints),
            "physical_independence": "unverified",
            "campaign_timeout_seconds": timeout,
        },
        "policy": {
            "execution": "serial",
            "retries": 0,
            "warmup_executions": 0,
            "stop_after_first_unavailable_execution": True,
        },
        "scope": (
            "Client-recorded intent; external preregistration, traffic "
            "and independence unauthenticated."
        ),
    }
    manifest["fingerprint"] = canonical_hash(manifest)
    return manifest


def native_complete(data: dict, count: int) -> bool:
    native = data["native_trace"]
    return (
        data["status"] == "completed"
        and data["cleanup"]["state"] == "completed"
        and native["exit_code"] == 0
        and native["error"] is None
        and native["stop_reason"] is None
        and native["resource_cleanup"]["state"] == "completed"
        and native["execution"]["planned"] == native["execution"]["completed"] == count
        and len(native["requests"]) == count
        and all(row["state"] == "completed" for row in native["requests"])
    )


async def _join_owned(child: asyncio.Task, waiter: asyncio.Task | None) -> None:
    await asyncio.gather(child, *([waiter] if waiter is not None else []), return_exceptions=True)


async def _execution(
    prepared: _PreparedFleetTrace,
    connections: Mapping[str, MonitorConnection] | None,
    caller_stop: asyncio.Event | None,
    deadline: float,
    children: list,
    waiters: list,
) -> tuple[FleetTraceReplay | None, dict | None, str | None]:
    stopped = asyncio.Event()
    current = replace(prepared, plan=replace(prepared.plan, stop_event=stopped))
    child = asyncio.create_task(
        fleet_trace._replay_prepared(current, connections), name="fleet-campaign-execution"
    )
    children.append(child)
    waiter = (
        asyncio.create_task(caller_stop.wait(), name="fleet-campaign-stop") if caller_stop else None
    )
    if waiter is not None:
        waiters.append(waiter)
    reason, cancelled, cancel_sent = None, False, False
    try:
        while not child.done():
            if caller_stop is not None and caller_stop.is_set():
                reason = "caller_stop"
                break
            remaining = deadline - _clock()
            if remaining <= 0:
                reason = "campaign_deadline"
                break
            await asyncio.wait(
                {child} | ({waiter} if waiter is not None else set()),
                timeout=remaining,
                return_when=asyncio.FIRST_COMPLETED,
            )
        if reason is None and _clock() >= deadline:
            reason = "campaign_deadline"
    except asyncio.CancelledError:
        cancelled = True
        child.cancel()
        cancel_sent = True
    finally:
        if reason is not None or cancelled:
            stopped.set()
        if waiter is not None and not waiter.done():
            waiter.cancel()
        drain = asyncio.create_task(_join_owned(child, waiter), name="fleet-campaign-owned-drain")
        while True:
            try:
                await asyncio.shield(drain)
                break
            except asyncio.CancelledError:
                cancelled = True
                stopped.set()
                if not cancel_sent and not child.done():
                    child.cancel()
                    cancel_sent = True
    if cancelled:
        raise asyncio.CancelledError
    if reason is None:
        reason = (
            "caller_stop"
            if caller_stop is not None and caller_stop.is_set()
            else ("campaign_deadline" if _clock() >= deadline else None)
        )
    if child.cancelled():
        LOG.warning("fleet campaign native result unavailable (CancelledError)")
        return None, {"stage": "native_result", "type": "CancelledError"}, reason
    try:
        result = child.result()
        if type(result) is not FleetTraceReplay:
            raise ValueError("native fleet receipt unavailable")
        return result, None, reason
    except Exception as exc:
        return None, trace._error(exc, "native_result"), reason


def prepare_campaign(
    saved: Any,
    requests: list[TraceRequest] | str | Path,
    endpoints: tuple[FleetEndpoint, ...],
    routes: list[TraceRoute] | str | Path,
    *,
    executions: int = DEFAULT_EXECUTIONS,
    candidate_index: int = 0,
    model: str | None = None,
    concurrency: int = 1,
    request_timeout: float = 300,
    trace_timeout: float = 600,
    cleanup_timeout: float = 2,
    campaign_timeout: float = DEFAULT_CAMPAIGN_TIMEOUT_SECONDS,
    stop_event: asyncio.Event | None = None,
    connections: Mapping[str, MonitorConnection] | None = None,
    _origin: float | None = None,
) -> tuple:
    from chimeraforge.api import PlanError

    if (
        type(executions) is not int
        or not 1 <= executions <= MAX_EXECUTIONS
        or not number(campaign_timeout, positive=True)
        or campaign_timeout > MAX_TIMEOUT_SECONDS
        or stop_event is not None
        and not isinstance(stop_event, asyncio.Event)
    ):
        raise PlanError("invalid fleet campaign population, budget or caller event")
    origin = _clock() if _origin is None else _origin
    deadline = origin + campaign_timeout
    prepared = prepare(
        saved,
        requests,
        endpoints,
        routes,
        candidate_index=candidate_index,
        model=model,
        concurrency=concurrency,
        request_timeout=request_timeout,
        trace_timeout=trace_timeout,
        cleanup_timeout=cleanup_timeout,
        stop_event=None,
    )
    if len(prepared.plan.requests) * executions > MAX_CAMPAIGN_REQUESTS:
        raise PlanError("fleet campaign declared request population exceeds its limit")
    secure = prepare_connections(prepared, connections) if connections is not None else None
    protected = tuple(
        dict.fromkeys(
            (
                *prepared.protected_paths,
                *(
                    path
                    for connection in (secure or {}).values()
                    for path in connection._input_paths()
                ),
            )
        )
    )
    manifest = manifest_for(prepared, executions, campaign_timeout)
    return prepared, secure, protected, manifest, origin, deadline


async def _replay_campaign_prepared(
    held: tuple, stop_event: asyncio.Event | None
) -> FleetTraceCampaign:
    prepared, secure, protected, manifest, origin, deadline = held
    executions = manifest["population"]["executions"]
    slots: list[dict] = []
    children: list[asyncio.Task] = []
    waiters: list[asyncio.Task] = []
    stop_reason = None
    for index in range(executions):
        if stop_reason is None:
            stop_reason = (
                "caller_stop"
                if stop_event is not None and stop_event.is_set()
                else ("campaign_deadline" if _clock() >= deadline else None)
            )
        slot = {
            "index": index,
            "manifest_fingerprint": manifest["fingerprint"],
            "state": "not_started",
            "execution_complete": None,
            "reason": stop_reason,
            "error": None,
            "start_s": None,
            "end_s": None,
            "receipt": None,
        }
        if stop_reason is None:
            slot["start_s"] = _clock() - origin
            if _clock() >= deadline:
                slot.update(start_s=None, reason="campaign_deadline")
                stop_reason = "campaign_deadline"
            else:
                result, error, stopped = await _execution(
                    prepared, secure, stop_event, deadline, children, waiters
                )
                data = result._data if result is not None else None
                complete = (
                    native_complete(data, len(prepared.plan.requests)) if data is not None else None
                )
                state = "failed" if data is None else "completed" if complete else "incomplete"
                slot.update(
                    receipt=data,
                    error=error,
                    state=state,
                    execution_complete=complete,
                    end_s=_clock() - origin,
                    reason=stopped
                    if complete
                    else ("native_receipt_unavailable" if data is None else "native_incomplete"),
                )
                stop_reason = stopped or (
                    "native_receipt_unavailable"
                    if data is None
                    else ("first_incomplete_execution" if not complete else None)
                )
        slots.append(slot)
    completed_at = _clock()
    if stop_reason is None:
        stop_reason = (
            "caller_stop"
            if stop_event is not None and stop_event.is_set()
            else ("campaign_deadline" if completed_at >= deadline else None)
        )
    counts = {state: sum(row["state"] == state for row in slots) for state in STATES}
    complete = counts["completed"] == executions and stop_reason is None
    mismatch = any(
        slot["receipt"] is not None and slot["receipt"]["configuration_status"] == "mismatch"
        for slot in slots
    )
    data = {
        "schema_version": 1,
        "kind": KIND,
        "created_at": now_iso(),
        "tool": manifest["tool"],
        "manifest": manifest,
        "executions": slots,
        "execution": {"planned": executions, **counts},
        "clock": {
            "basis": "client time.perf_counter monotonic offsets in seconds",
            "origin": origin,
            "elapsed_seconds": completed_at - origin,
        },
        "stop_reason": stop_reason,
        "state": "completed" if complete else "incomplete",
        "configuration_status": "mismatch" if mismatch else "unverified",
        "exit_code": int(not complete or mismatch),
        "cleanup": {
            "state": "completed",
            "owned_children": len(children),
            "joined_children": sum(task.done() for task in children),
            "owned_waiters": len(waiters),
            "joined_waiters": sum(task.done() for task in waiters),
        },
        "limits": CAMPAIGN_LIMITS,
    }
    data["fingerprint"] = canonical_hash(data)
    return FleetTraceCampaign(data, protected)


async def replay_fleet_trace_campaign(
    saved: Any,
    requests: list[TraceRequest] | str | Path,
    endpoints: tuple[FleetEndpoint, ...],
    routes: list[TraceRoute] | str | Path,
    *,
    executions: int = DEFAULT_EXECUTIONS,
    candidate_index: int = 0,
    model: str | None = None,
    concurrency: int = 1,
    request_timeout: float = 300,
    trace_timeout: float = 600,
    cleanup_timeout: float = 2,
    campaign_timeout: float = DEFAULT_CAMPAIGN_TIMEOUT_SECONDS,
    stop_event: asyncio.Event | None = None,
    connections: Mapping[str, MonitorConnection] | None = None,
) -> FleetTraceCampaign:
    held = prepare_campaign(
        saved,
        requests,
        endpoints,
        routes,
        executions=executions,
        candidate_index=candidate_index,
        model=model,
        concurrency=concurrency,
        request_timeout=request_timeout,
        trace_timeout=trace_timeout,
        cleanup_timeout=cleanup_timeout,
        campaign_timeout=campaign_timeout,
        stop_event=stop_event,
        connections=connections,
    )
    return await _replay_campaign_prepared(held, stop_event)
