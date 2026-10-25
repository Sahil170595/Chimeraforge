"""Cooperative, bounded passive observation of all explicitly declared replicas."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Sequence, Mapping
from dataclasses import dataclass
import logging
import math
from pathlib import Path
import re
from typing import Any, TYPE_CHECKING

import httpx

from chimeraforge import __version__
from chimeraforge.bench import serving
from chimeraforge.bench.backends import get_backend
from chimeraforge.bench.backends.base import Backend
from chimeraforge.fleet_monitor_transport import BorrowedTransport, OwnedPool, SharedBudget
from chimeraforge.fleet_monitor_types import (
    MAX_BODY_BYTES,
    MAX_CLEANUP_SECONDS,
    MAX_ENDPOINTS,
    MAX_ID_CHARS,
    MAX_MODEL_CHARS,
    MAX_OBSERVATION_SECONDS,
    MAX_REQUESTS,
    MAX_TOTAL_WINDOWS,
    MAX_URL_CHARS,
    FleetEndpoint,
    FleetMonitorError,
    FleetMonitorReport,
    FleetMonitorRequest,
    FleetSlot,
)
from chimeraforge.monitor import MAX_METRICS_BYTES, MonitorRequest, evaluate_window
from chimeraforge.monitor_connection import (
    MonitorConnection,
    MonitorConnectionError,
    admit_connection,
)
from chimeraforge.monitor_binding import assemble_binding
from chimeraforge.plan_check import identity

if TYPE_CHECKING:
    from chimeraforge.api import PlanArtifact

logger = logging.getLogger(__name__)
POLL_SECONDS = 0.02
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")


def _endpoint(value: FleetEndpoint) -> FleetEndpoint:
    if type(value) is not FleetEndpoint or type(value.id) is not str or not _ID.fullmatch(value.id):
        raise FleetMonitorError(f"endpoint IDs require 1..{MAX_ID_CHARS} ASCII letters/digits/_.-")
    if (
        type(value.url) is not str
        or not 0 < len(value.url) <= MAX_URL_CHARS
        or "#" in value.url
        or any(ord(char) <= 32 or ord(char) == 127 for char in value.url)
    ):
        raise FleetMonitorError("endpoint URL exceeds fleet admission bounds")
    try:
        url = httpx.URL(value.url)
        if (
            url.scheme not in ("http", "https")
            or not url.host
            or url.userinfo
            or url.query
            or url.fragment
            or url.port == 0
        ):
            raise ValueError
        path = url.raw_path
        if path in (b"", b"/"):
            url = url.copy_with(raw_path=b"/metrics")
        elif not path.endswith(b"/metrics") or path[: -len(b"/metrics")].endswith(b"/"):
            raise ValueError
    except (ValueError, httpx.InvalidURL):
        raise FleetMonitorError(
            "endpoint must be a credential-free root or terminal /metrics URL"
        ) from None
    return FleetEndpoint(value.id, str(url))


def _admit(request: FleetMonitorRequest, population: int) -> tuple[FleetEndpoint, ...]:
    if (
        type(request) is not FleetMonitorRequest
        or type(request.endpoints) is not tuple
        or not 1 <= len(request.endpoints) <= MAX_ENDPOINTS
        or len(request.endpoints) != population
    ):
        raise FleetMonitorError("one endpoint is required per original saved replica (1..16)")
    for name, cap in (
        ("windows", MAX_TOTAL_WINDOWS),
        ("concurrency", MAX_ENDPOINTS),
        ("max_requests", MAX_REQUESTS),
        ("max_body_bytes", MAX_BODY_BYTES),
    ):
        value = getattr(request, name)
        if type(value) is not int or not 1 <= value <= cap:
            raise FleetMonitorError(f"{name} must be an integer in 1..{cap}")
    if population * request.windows > MAX_TOTAL_WINDOWS:
        raise FleetMonitorError("total requested fleet windows exceed 256")
    for name, ceiling in (
        ("interval", MAX_OBSERVATION_SECONDS),
        ("timeout", MAX_OBSERVATION_SECONDS),
        ("observation_seconds", MAX_OBSERVATION_SECONDS),
        ("cleanup_seconds", MAX_CLEANUP_SECONDS),
    ):
        value = getattr(request, name)
        if type(value) not in (int, float) or not 0 < value <= ceiling or not math.isfinite(value):
            raise FleetMonitorError(f"{name} must be finite and positive, at most {ceiling:g}")
    endpoints = tuple(_endpoint(value) for value in request.endpoints)
    if (
        len({value.id for value in endpoints}) != population
        or len({value.url for value in endpoints}) != population
    ):
        raise FleetMonitorError("endpoint IDs and normalized URLs must be distinct")
    return endpoints


def _source(saved: PlanArtifact | str | Path, index: int) -> tuple[dict[str, Any], dict[str, Any]]:
    # The offline verifier already supplies strict held-byte/node/depth admission.
    from chimeraforge.deployment_verify import _source as held_plan

    try:
        artifact, _, _ = held_plan(saved)
        artifact.candidate(index)
        data = artifact.to_dict()
        candidate = data["result"]["candidates"][index]
        if (
            candidate["backend"] not in ("vllm", "sglang")
            or type(candidate["n_agents"]) is not int
            or not 1 <= candidate["n_agents"] <= MAX_ENDPOINTS
        ):
            raise ValueError
        model = candidate["model"]
        if type(model) is not str or not 0 < len(model) <= MAX_MODEL_CHARS:
            raise ValueError
        return data, candidate
    except (ValueError, OSError, TypeError, KeyError, RecursionError):
        raise FleetMonitorError("invalid or unsupported original saved fleet candidate") from None


def _targets(
    data: dict[str, Any], request: FleetMonitorRequest
) -> tuple[dict[str, Any], dict[str, str]]:
    targets, sources = {}, {}
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
    return targets, sources


@dataclass
class _Resources:
    slot: FleetSlot
    effective: MonitorRequest
    metrics_pool: OwnedPool
    metadata_pool: OwnedPool
    client: httpx.AsyncClient | None = None
    backend: Backend | None = None

    @property
    def contacted(self) -> bool:
        return self.metrics_pool.requests + self.metadata_pool.requests > 0


async def _metrics(resources: _Resources) -> tuple[str, float]:
    assert resources.client is not None
    content = bytearray()
    async with resources.client.stream("GET", resources.effective.url) as response:
        response.raise_for_status()
        async for chunk in response.aiter_bytes():
            content.extend(chunk)
    return content.decode("utf-8"), asyncio.get_running_loop().time()


async def _worker(resources: _Resources, request: FleetMonitorRequest) -> None:
    slot, effective = resources.slot, resources.effective
    assert resources.backend is not None
    try:
        first, start = await _metrics(resources)
        slot.observations.append(await serving.observe_backend(resources.backend, effective.model))
        for _ in range(request.windows):
            await asyncio.sleep(request.interval)
            second, end = await _metrics(resources)
            slot.windows.append(
                evaluate_window(
                    first,
                    second,
                    backend=effective.backend,
                    model=effective.model,
                    seconds=end - start,
                    ttft_slo=effective.ttft_slo,
                    tpot_slo=effective.tpot_slo,
                )
            )
            slot.slo = (
                "breach"
                if any(row.outcome == "breach" for row in slot.windows)
                else "unknown"
                if any(row.outcome == "unknown" for row in slot.windows)
                else "pass"
            )
            slot.observations.append(
                await serving.observe_backend(resources.backend, effective.model)
            )
            first, start = second, end
        violations = [
            pool.violation
            for pool in (resources.metrics_pool, resources.metadata_pool)
            if pool.violation
        ]
        if violations:
            slot.state, slot.error = "error", violations[0]
        else:
            slot.state = "complete"
    except asyncio.CancelledError:
        slot.state = "cancelled" if resources.contacted else "unstarted"
        raise
    except Exception as exc:
        slot.state = "error" if resources.contacted else "unstarted"
        slot.error = type(exc).__name__
        logger.info("fleet endpoint %s observation failed (%s)", slot.id, slot.error)


async def _cleanup(
    tasks: list[asyncio.Task[None]], resources: list[_Resources], seconds: float
) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds
    exceeded, failures = False, 0

    async def phase(operations: Sequence[Awaitable[None]]) -> None:
        nonlocal exceeded, failures
        leaves = [asyncio.ensure_future(value) for value in operations]
        if not leaves:
            return
        # Even an exhausted allowance must attempt every owner's close callback.
        await asyncio.sleep(0)
        _, pending = await asyncio.wait(leaves, timeout=max(0, deadline - loop.time()))
        if pending:
            exceeded = True
        outcomes = await asyncio.gather(*leaves, return_exceptions=True)
        failures += sum(isinstance(value, BaseException) for value in outcomes)

    for task in tasks:
        if not task.done():
            task.cancel()
    # Expected cancellation of endpoint tasks is not a resource-close failure.
    done, pending = (
        await asyncio.wait(tasks, timeout=max(0, deadline - loop.time()))
        if tasks
        else (set(), set())
    )
    if pending:
        exceeded = True
    await asyncio.gather(*tasks, return_exceptions=True)
    await phase(
        [row.client.aclose() for row in resources if row.client is not None]
        + [row.backend.close() for row in resources if row.backend is not None]
    )
    pools = [pool for row in resources for pool in (row.metrics_pool, row.metadata_pool)]
    await phase([pool.aclose() for pool in pools])
    stream_tasks = [
        stream.closing for pool in pools for stream in pool.streams if stream.closing is not None
    ]
    if stream_tasks:
        await phase(stream_tasks)
    if loop.time() > deadline:
        exceeded = True
    closed = all(pool.closed for pool in pools) and all(
        row.client is None or row.client.is_closed for row in resources
    )
    return {
        "state": "completed" if closed and not exceeded and not failures else "incomplete",
        "budget_seconds": seconds,
        "allowance_exceeded": exceeded,
        "resources_closed": closed,
        "close_errors": failures,
        "owned_pools": len(pools),
        "closed_pools": sum(pool.closed for pool in pools),
        "joined_endpoint_tasks": sum(task.done() for task in tasks),
    }


async def monitor_fleet(
    saved: PlanArtifact | str | Path,
    request: FleetMonitorRequest,
    *,
    candidate_index: int = 0,
    stop_event: asyncio.Event | None = None,
    connections: Mapping[str, MonitorConnection] | None = None,
) -> FleetMonitorReport:
    if stop_event is not None and not isinstance(stop_event, asyncio.Event):
        raise FleetMonitorError("stop_event must be an asyncio.Event or None")
    data, candidate = _source(saved, candidate_index)
    endpoints = _admit(request, candidate["n_agents"])
    targets, sources = _targets(data, request)
    effective = [
        MonitorRequest(
            candidate["backend"],
            endpoint.url,
            candidate["model"],
            interval=request.interval,
            windows=request.windows,
            timeout=request.timeout,
            **targets,
        )
        for endpoint in endpoints
    ]
    try:
        for value in effective:
            value.validate()
    except ValueError:
        raise FleetMonitorError("invalid fleet histogram targets or request controls") from None
    prepared: dict[str, MonitorConnection] = {}
    if connections is not None:
        if not isinstance(connections, Mapping) or len(connections) > len(endpoints):
            raise MonitorConnectionError("invalid fleet monitor connection mapping")
        ids = {endpoint.id for endpoint in endpoints}
        snapshot = {}
        for number, key in enumerate(connections):
            if (
                number >= len(endpoints)
                or type(key) is not str
                or key not in ids
                or key in snapshot
            ):
                raise MonitorConnectionError("invalid fleet monitor connection mapping")
            snapshot[key] = connections[key]
        for endpoint in endpoints:
            connection = snapshot.get(endpoint.id)
            if endpoint.id in snapshot:
                if type(connection) is not MonitorConnection:
                    raise MonitorConnectionError("invalid fleet monitor connection mapping")
            else:
                connection = MonitorConnection(endpoint.url)
            admit_connection(connection, endpoint.url)
            assert connection is not None
            prepared[endpoint.id] = connection
    loop = asyncio.get_running_loop()
    budget = SharedBudget(
        loop.time() + request.observation_seconds,
        request.max_requests,
        request.max_body_bytes,
        request.concurrency,
    )
    resources: list[_Resources] = []
    tasks: list[asyncio.Task[None]] = []
    direct_cancel = False
    setup_failed = False
    cancelled = bool(stop_event and stop_event.is_set())
    try:
        for endpoint, value in zip(endpoints, effective):
            connection = prepared.get(endpoint.id)
            options = {"connection": connection} if connection is not None else {}
            metrics_pool = OwnedPool(budget, MAX_METRICS_BYTES, request.timeout, **options)
            metadata_pool = OwnedPool(
                budget, serving.MAX_METADATA_BYTES, request.timeout, **options
            )
            row = _Resources(
                FleetSlot(endpoint.id, endpoint.url), value, metrics_pool, metadata_pool
            )
            resources.append(row)
            row.client = httpx.AsyncClient(
                transport=BorrowedTransport(metrics_pool),
                timeout=request.timeout,
                **(connection._client_kwargs() if connection is not None else {"trust_env": False}),
            )
            row.backend = get_backend(
                candidate["backend"],
                base_url=endpoint.url.removesuffix("/metrics"),
                transport=BorrowedTransport(metadata_pool),
                **options,
            )
        if not cancelled:
            tasks = [asyncio.create_task(_worker(row, request)) for row in resources]
        while tasks and any(not task.done() for task in tasks):
            if stop_event and stop_event.is_set():
                cancelled = True
                break
            if budget.termination is not None:
                break
            remaining = budget.deadline - loop.time()
            if remaining <= 0:
                budget.termination = "observation_deadline"
                break
            await asyncio.wait(
                [task for task in tasks if not task.done()], timeout=min(POLL_SECONDS, remaining)
            )
    except asyncio.CancelledError:
        direct_cancel = True
    except Exception as exc:
        setup_failed = True
        logger.warning("fleet observation setup/coordination failed (%s)", type(exc).__name__)
    finally:
        if (
            not cancelled
            and not direct_cancel
            and not setup_failed
            and loop.time() >= budget.deadline
            and budget.termination is None
        ):
            budget.termination = "observation_deadline"
        closer = asyncio.create_task(_cleanup(tasks, resources, request.cleanup_seconds))
        while True:
            try:
                cleanup = await asyncio.shield(closer)
                break
            except asyncio.CancelledError:
                direct_cancel = True
    if direct_cancel:
        raise asyncio.CancelledError
    if setup_failed:
        raise FleetMonitorError(
            "fleet observation resources could not be initialized or coordinated"
        ) from None
    for row in resources:
        row.slot.binding = assemble_binding(
            data,
            candidate,
            candidate_index,
            row.effective,
            sources,
            row.slot.observations,
            retain_prefix=True,
        )
    return FleetMonitorReport(
        candidate["backend"],
        candidate["model"],
        tuple(row.slot for row in resources),
        {
            "fingerprint": data["fingerprint"],
            "candidate_index": candidate_index,
            "identity": identity(candidate),
            "tool_version": data["tool"]["version"],
        },
        sources,
        budget.to_dict(),
        cleanup,
        cancelled,
        __version__,
    )


from chimeraforge.fleet_monitor_output import prometheus_text, write_prometheus  # noqa: E402,F401
