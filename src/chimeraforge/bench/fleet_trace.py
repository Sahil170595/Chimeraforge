"""One original fleet, one native schedule, and one cooperative resource owner."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from chimeraforge.transport_logging import sdk_logging
from chimeraforge.bench import trace
from chimeraforge.bench.backends.base import Backend
from chimeraforge.bench.fleet_trace_inputs import _PreparedFleetTrace, prepare, prepare_connections
from chimeraforge.bench.fleet_trace_receipt import make_report
from chimeraforge.bench.fleet_trace_types import FleetTraceReplay, TraceRoute
from chimeraforge.bench.serving import observe_backend
from chimeraforge.bench.trace_workload import TraceRequest
from chimeraforge.fleet_monitor_types import FleetEndpoint
from chimeraforge.monitor_connection import MonitorConnection
from chimeraforge.planner.replay import digest

if TYPE_CHECKING:
    from chimeraforge.api import PlanArtifact
    from chimeraforge.plan_bundle import PlanBundle

# Bound phase concurrency independently of the one global generation semaphore.
MAX_PREFLIGHT_FANOUT = 4


async def _phase(
    prepared: _PreparedFleetTrace,
    resources: list[dict],
    owner: trace._TraceOwnership,
    stopped: asyncio.Event,
    *,
    before: bool,
) -> None:
    semaphore = asyncio.Semaphore(MAX_PREFLIGHT_FANOUT)

    async def member(resource: dict) -> None:
        async with semaphore:
            stage = "preflight" if before else "metadata_after"
            try:
                backend = resource["backend"]
                if before:
                    for probe in (
                        backend.health_check,
                        lambda: backend.check_model(prepared.plan.served_model),
                    ):
                        ok, _ = await probe()
                        if not ok:
                            raise RuntimeError("preflight refused")
                    stage = "metadata_before"
                resource["before" if before else "after"] = await observe_backend(
                    backend, prepared.plan.served_model
                )
            except Exception as exc:
                resource["error"] = trace._error(exc, stage)

    if stopped.is_set():
        raise trace._TraceStopped
    tasks = [owner.task(member(resource)) for resource in resources]
    finished = asyncio.gather(*tasks)
    owner.joins.append(finished)
    control = owner.task(stopped.wait())
    done, _ = await asyncio.wait(
        (finished, control),
        timeout=prepared.plan.request_timeout,
        return_when=asyncio.FIRST_COMPLETED,
    )
    if control in done:
        raise trace._TraceStopped
    if finished not in done:
        for resource, task in zip(resources, tasks):
            if not task.done():
                resource["error"] = trace._error(
                    asyncio.TimeoutError(), "preflight" if before else "metadata_after"
                )
        raise asyncio.TimeoutError
    finished.result()
    if any(resource["error"] is not None for resource in resources):
        raise RuntimeError("fleet phase refused")


async def _close(resources: list[dict], owner: trace._TraceOwnership, allowance: float) -> dict:
    loop = asyncio.get_running_loop()
    # Start the allowance before the first final cancellation or drain.
    deadline = loop.time() + allowance
    owner.cancel_pending()
    work = tuple(owner.tasks)
    exceeded = False

    async def wait_remaining(tasks: tuple | list) -> None:
        nonlocal exceeded
        pending = {task for task in tasks if not task.done()}
        # Event-loop timeout callbacks can run before the clock deadline.
        while pending and (remaining := deadline - loop.time()) > 0:
            _, pending = await asyncio.wait(pending, timeout=remaining)
        if pending:
            exceeded = True

    await wait_remaining(work)
    errors = 0
    closed = 0
    backends = [resource["backend"] for resource in resources if resource["backend"] is not None]

    async def close_backend(backend: Backend) -> None:
        nonlocal errors, closed
        try:
            await backend.close()
            closed += 1
        except Exception as exc:
            errors += 1
            trace._error(exc, "cleanup")

    # A pending generation may need its client's close to finish. Attempt every
    # close before an unbounded cooperative join, including after budget expiry.
    closers = [owner.task(close_backend(backend)) for backend in backends]
    await wait_remaining(closers)
    joined = asyncio.gather(*owner.tasks, return_exceptions=True)
    await joined
    # Workers register their generation joins while unwinding cancellation.
    if owner.joins:
        await asyncio.gather(*owner.joins, return_exceptions=True)
    exceeded = exceeded or loop.time() > deadline
    complete = closed == len(backends) and not errors and not exceeded
    return {
        "state": "completed" if complete else "incomplete",
        "budget_seconds": allowance,
        "allowance_exceeded": exceeded,
        "resources_closed": closed == len(backends),
        "close_errors": errors,
        "owned_backends": len(backends),
        "closed_backends": closed,
        "owned_tasks": len(owner.tasks),
        "joined_tasks": sum(task.done() for task in owner.tasks),
    }


async def _replay_prepared(
    prepared: _PreparedFleetTrace, connections: Mapping[str, MonitorConnection] | None = None
) -> FleetTraceReplay:
    with sdk_logging(connections is not None):
        from chimeraforge.api import PlanError

        secure = prepare_connections(prepared, connections)
        plan = prepared.plan
        stopped = plan.stop_event if plan.stop_event is not None else asyncio.Event()
        owner = trace._TraceOwnership()
        resources: list[dict] = [
            {"backend": None, "before": None, "after": None, "error": None}
            for _ in prepared.endpoints
        ]
        rows = trace._initial_rows(list(plan.requests))
        cancelled = False
        configuration_error = False
        origin, elapsed, stop_reason, error = None, 0.0, None, None
        stage = "preflight"
        try:
            for endpoint, resource in zip(prepared.endpoints, resources):
                kwargs: dict[str, object] = {"base_url": endpoint.url}
                if endpoint.id in secure:
                    kwargs["connection"] = secure[endpoint.id]
                try:
                    resource["backend"] = trace.get_backend(plan.backend, **kwargs)
                except (ValueError, TypeError):
                    configuration_error = True
                    raise
            await _phase(prepared, resources, owner, stopped, before=True)
            stage = "scheduled_replay"
            origin = trace._clock()
            by_id = {
                endpoint.id: resource["backend"]
                for endpoint, resource in zip(prepared.endpoints, resources)
            }
            dispatch = {route.request_id: by_id[route.endpoint_id] for route in prepared.routes}
            stop_reason = await trace._execute(
                resources[0]["backend"],
                plan.backend,
                plan.served_model,
                list(plan.requests),
                rows,
                origin,
                plan.concurrency,
                plan.request_timeout,
                plan.trace_timeout,
                stopped,
                backends=dispatch,
                ownership=owner,
            )
            elapsed = trace._clock() - origin
            if stop_reason is None:
                stage = "metadata_after"
                await _phase(prepared, resources, owner, stopped, before=False)
        except asyncio.CancelledError:
            cancelled = True
        except trace._TraceStopped:
            stop_reason = "cancelled"
        except Exception as exc:
            error = trace._error(exc, stage)
        finally:
            closer = asyncio.create_task(_close(resources, owner, prepared.cleanup_timeout))
            while True:
                try:
                    cleanup = await asyncio.shield(closer)
                    break
                except asyncio.CancelledError:
                    cancelled = True
        if cancelled:
            raise asyncio.CancelledError
        if configuration_error:
            raise PlanError("fleet backend configuration is unavailable")
        if cleanup["state"] != "completed":
            error = trace._error(RuntimeError(), "cleanup")
        if origin is not None:
            # Retain late terminals from cooperative cancellation in the common horizon.
            elapsed = max(elapsed, *(row["times"]["terminal_s"] or 0.0 for row in rows))
        native = trace._report(
            list(plan.requests),
            rows,
            workload=plan.workload,
            targets=plan.slos,
            model=plan.served_model,
            backend_name=plan.backend,
            base_url=None,
            concurrency=plan.concurrency,
            request_timeout=plan.request_timeout,
            trace_timeout=plan.trace_timeout,
            cleanup={"state": cleanup["state"]},
            observation={},
            stop_reason=stop_reason,
            error=error,
            elapsed=elapsed,
            origin=origin,
        )
        for row, route in zip(native["requests"], prepared.routes):
            row["endpoint_id"] = route.endpoint_id
        native["fingerprint"] = digest(
            {key: value for key, value in native.items() if key != "fingerprint"}
        )
        report = make_report(prepared, native, resources, cleanup)
        return FleetTraceReplay(report, prepared.protected_paths)


async def replay_fleet_trace(
    saved: PlanArtifact | PlanBundle | str | Path,
    requests: list[TraceRequest] | str | Path,
    endpoints: tuple[FleetEndpoint, ...],
    routes: list[TraceRoute] | str | Path,
    *,
    candidate_index: int = 0,
    model: str | None = None,
    concurrency: int = 1,
    request_timeout: float = 300,
    trace_timeout: float = 600,
    cleanup_timeout: float = 2,
    stop_event: asyncio.Event | None = None,
    connections: Mapping[str, MonitorConnection] | None = None,
) -> FleetTraceReplay:
    """Replay one complete admitted route map against its original saved fleet."""
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
        stop_event=stop_event,
    )
    return await _replay_prepared(prepared, connections)
