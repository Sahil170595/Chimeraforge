"""Hold complete original fleet inputs and opaque runtime connections before contact."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

import httpx

from chimeraforge.bench import plan_trace
from chimeraforge.bench.fleet_trace_types import MAX_ROUTE_BYTES, TraceRoute
from chimeraforge.bench.trace_workload import TraceRequest, number
from chimeraforge.fleet_monitor_types import (
    MAX_CLEANUP_SECONDS,
    MAX_ENDPOINTS,
    MAX_ID_CHARS,
    MAX_URL_CHARS,
    FleetEndpoint,
)
from chimeraforge.monitor_connection import MonitorConnection, admit_connection
from chimeraforge.planner.replay import digest

if TYPE_CHECKING:
    from chimeraforge.api import PlanArtifact
    from chimeraforge.plan_bundle import PlanBundle

ENDPOINT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


@dataclass(frozen=True)
class _PreparedFleetTrace:
    plan: plan_trace._PreparedPlanTrace
    endpoints: tuple[FleetEndpoint, ...]
    routes: tuple[TraceRoute, ...]
    route_identity: dict
    cleanup_timeout: float
    protected_paths: tuple[Path, ...]


def admit_endpoints(values: tuple[FleetEndpoint, ...], count: int) -> tuple[FleetEndpoint, ...]:
    from chimeraforge.api import PlanError

    if (
        type(count) is not int
        or not 1 <= count <= MAX_ENDPOINTS
        or type(values) is not tuple
        or len(values) != count
    ):
        raise PlanError("exactly one endpoint per original saved replica is required")
    admitted, ids, urls = [], set(), set()
    for value in values:
        if (
            type(value) is not FleetEndpoint
            or type(value.id) is not str
            or len(value.id) > MAX_ID_CHARS
            or not ENDPOINT_ID.fullmatch(value.id)
            or value.id in ids
            or type(value.url) is not str
            or len(value.url) > MAX_URL_CHARS
            or any(ord(char) <= 32 or ord(char) == 127 for char in value.url)
            or "?" in value.url
            or "#" in value.url
        ):
            raise PlanError("invalid or duplicate active endpoint declaration")
        try:
            parts = urlsplit(value.url)
            parsed = httpx.URL(value.url)
            if (
                parts.username is not None
                or parts.password is not None
                or not parsed.host
                or parsed.scheme not in ("http", "https")
                or parsed.port == 0
                or parsed.path.endswith("//")
            ):
                raise ValueError
            normalized = str(parsed).rstrip("/")
        except (ValueError, TypeError, httpx.InvalidURL):
            raise PlanError("active endpoints require direct HTTP(S) base URLs") from None
        if normalized in urls:
            raise PlanError("normalized active endpoints must be distinct")
        ids.add(value.id)
        urls.add(normalized)
        admitted.append(FleetEndpoint(value.id, normalized))
    return tuple(admitted)


def hold_routes(
    source: list[TraceRoute] | str | Path,
    requests: tuple[TraceRequest, ...],
    endpoints: tuple[FleetEndpoint, ...],
) -> tuple[tuple[TraceRoute, ...], dict, tuple[Path, ...]]:
    from chimeraforge.api import PlanError, _unique_object
    from chimeraforge.plan_bundle import _read

    protected: tuple[Path, ...] = ()
    raw_sha: str | None = None
    try:
        if type(source) is list:
            if len(source) != len(requests):
                raise ValueError
            routes = list(source)
        else:
            if not isinstance(source, (str, Path)):
                raise ValueError
            path = Path(source).absolute()
            raw = _read(path, MAX_ROUTE_BYTES)
            values = json.loads(raw, object_pairs_hook=_unique_object)
            if (
                type(values) is not list
                or len(values) != len(requests)
                or any(
                    type(row) is not dict or set(row) != {"request_id", "endpoint_id"}
                    for row in values
                )
            ):
                raise ValueError
            routes = [TraceRoute(**row) for row in values]
            raw_sha, protected = hashlib.sha256(raw).hexdigest(), (path,)
        expected, members = {row.request_id for row in requests}, {row.id for row in endpoints}
        if len(routes) != len(requests):
            raise ValueError
        by_id = {}
        for route in routes:
            if (
                type(route) is not TraceRoute
                or type(route.request_id) is not str
                or type(route.endpoint_id) is not str
                or route.request_id not in expected
                or route.request_id in by_id
                or route.endpoint_id not in members
            ):
                raise ValueError
            by_id[route.request_id] = route
        ordered = tuple(by_id[row.request_id] for row in requests)
        canonical = [asdict(row) for row in ordered]
        if len(json.dumps(canonical).encode()) > MAX_ROUTE_BYTES:
            raise ValueError
        return ordered, {"canonical_sha256": digest(canonical), "raw_sha256": raw_sha}, protected
    except (PlanError, OSError, ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise PlanError("invalid bounded one-to-one fleet route map") from None


def prepare(
    saved: PlanArtifact | PlanBundle | str | Path,
    requests: list[TraceRequest] | str | Path,
    endpoints: tuple[FleetEndpoint, ...],
    routes: list[TraceRoute] | str | Path,
    *,
    candidate_index: int,
    model: str | None,
    concurrency: int,
    request_timeout: float,
    trace_timeout: float,
    cleanup_timeout: float,
    stop_event: asyncio.Event | None,
) -> _PreparedFleetTrace:
    from chimeraforge.api import PlanError

    plan = plan_trace._prepare(
        saved,
        requests,
        candidate_index=candidate_index,
        model=model,
        concurrency=concurrency,
        request_timeout=request_timeout,
        trace_timeout=trace_timeout,
        stop_event=stop_event,
    )
    if plan.backend not in {"ollama", "vllm", "sglang"}:
        raise PlanError("original fleet trace supports Ollama, vLLM and SGLang")
    if not number(cleanup_timeout, positive=True) or cleanup_timeout > MAX_CLEANUP_SECONDS:
        raise PlanError("cleanup_timeout must be positive and at most 10 seconds")
    admitted = admit_endpoints(endpoints, plan.candidate["n_agents"])
    ordered, route_identity, route_paths = hold_routes(routes, plan.requests, admitted)
    return _PreparedFleetTrace(
        plan,
        admitted,
        ordered,
        route_identity,
        cleanup_timeout,
        tuple(dict.fromkeys((*plan.protected_paths, *route_paths))),
    )


def prepare_connections(
    prepared: _PreparedFleetTrace, connections: Mapping[str, MonitorConnection] | None
) -> dict[str, MonitorConnection]:
    from chimeraforge.api import PlanError

    if connections is None:
        return {}
    endpoints = prepared.endpoints
    if prepared.plan.backend == "ollama":
        raise PlanError("secure Ollama fleet connections are not qualified")
    if not isinstance(connections, Mapping) or len(connections) > len(endpoints):
        raise PlanError("invalid fleet connection mapping")
    snapshot = {}
    members = {row.id for row in endpoints}
    for index, key in enumerate(connections):
        if index >= len(endpoints) or type(key) is not str or key not in members or key in snapshot:
            raise PlanError("invalid fleet connection mapping")
        value = connections[key]
        if type(value) is not MonitorConnection:
            raise PlanError("invalid fleet connection mapping")
        snapshot[key] = value
    result = {}
    for endpoint in endpoints:
        connection = snapshot.get(endpoint.id) or MonitorConnection(endpoint.url)
        admit_connection(connection, endpoint.url)
        result[endpoint.id] = connection
    return result
