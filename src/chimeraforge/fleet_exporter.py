"""Owned loopback ASGI listener with one sequential native fleet poll task."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
import json
import logging
import math
from pathlib import Path
import threading
from types import MappingProxyType
from typing import Any, TYPE_CHECKING

from chimeraforge.fleet_exporter_cache import SnapshotCache, _CapturedSnapshot, _PopulationBinding
from chimeraforge.fleet_exporter_types import (
    FleetExporterConfig,
    FleetExporterError,
    FleetExporterSnapshot,
    FleetExporterRunResult,
    MAX_READINESS_BYTES,
    MAX_REQUEST_BYTES,
    MAX_REQUEST_PATH,
    STARTUP_POLL_SECONDS,
)
from chimeraforge.fleet_monitor import _admit, _source, _targets, monitor_fleet
from chimeraforge.fleet_monitor_types import FleetMonitorRequest, MAX_ENDPOINTS
from chimeraforge.monitor_connection import (
    MonitorConnection,
    MonitorConnectionError,
    admit_connection,
)

if TYPE_CHECKING:
    from chimeraforge.api import PlanArtifact

LOG = logging.getLogger(__name__)


class FleetExporter:
    def __init__(
        self,
        saved: Any,
        request: FleetMonitorRequest,
        config: FleetExporterConfig,
        index: int,
        connections: Mapping[str, MonitorConnection] | None,
        cache: SnapshotCache,
        uvicorn: Any,
        starlette: Any,
        response: Any,
        route: Any,
    ) -> None:
        self._saved, self._request, self._config = saved, request, config
        self._index, self._connections, self._cache = index, connections, cache
        self._closing, self._ready = threading.Event(), threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop: asyncio.Event | None = None
        self._worker: asyncio.Task[None] | None = None
        self._failed = False
        self.closed = self.worker_joined = self.listener_joined = False

        async def scrape(value: Any) -> Any:
            scope = value.scope
            if len(scope.get("raw_path", b"")) > MAX_REQUEST_PATH:
                return response(status_code=414)
            path = scope.get("raw_path")
            if scope.get("query_string") or path not in (b"/metrics", b"/readyz"):
                return response(status_code=404)
            if sum(len(k) + len(v) for k, v in scope["headers"]) > MAX_REQUEST_BYTES:
                return response(status_code=431)
            if (
                value.headers.get("content-length", "0") != "0"
                or "transfer-encoding" in value.headers
            ):
                return response(status_code=400)
            snapshot = self.snapshot()
            headers = {"cache-control": "no-store", "x-chimeraforge-snapshot-state": snapshot.state}
            if snapshot.age_seconds is not None:
                headers["x-chimeraforge-snapshot-age-seconds"] = f"{snapshot.age_seconds:.6f}"
            if path == b"/readyz":
                ready = snapshot.state == "fresh"
                body = (
                    json.dumps(
                        {
                            "schema_version": 1,
                            "kind": "chimeraforge.fleet-exporter-readiness",
                            "ready": ready,
                            "state": snapshot.state,
                            "age_seconds": snapshot.age_seconds,
                            "sequence": snapshot.sequence,
                            "native_exit_code": snapshot.native_exit_code,
                        },
                        allow_nan=False,
                        separators=(",", ":"),
                    ).encode("utf-8")
                    + b"\n"
                )
                if len(body) > MAX_READINESS_BYTES:
                    LOG.warning("exporter readiness response exceeds byte bound")
                    return response(status_code=503, headers=headers)
                return response(
                    body,
                    status_code=200 if ready else 503,
                    media_type="application/json",
                    headers=headers,
                )
            return response(snapshot.body, media_type="text/plain; version=0.0.4", headers=headers)

        @asynccontextmanager
        async def lifespan(application: Any) -> AsyncIterator[None]:
            self._stop = asyncio.Event()
            if self._closing.is_set():
                self._stop.set()
            self._worker = asyncio.create_task(self._poll())
            try:
                yield
            finally:
                self._stop.set()
                await self._worker
                self.worker_joined = True

        app = starlette(
            routes=[route("/{remaining:path}", scrape, methods=["GET", "HEAD"])],
            lifespan=lifespan,
            max_body_size=1,
        )
        self._server = uvicorn.Server(
            uvicorn.Config(
                app,
                host=config.host,
                port=config.port,
                workers=1,
                loop="asyncio",
                http="h11",
                ws="none",
                lifespan="on",
                log_config=None,
                log_level="warning",
                access_log=False,
                proxy_headers=False,
                server_header=False,
                date_header=False,
                limit_concurrency=config.max_clients,
                backlog=config.max_clients,
                timeout_keep_alive=1,
                timeout_graceful_shutdown=config.shutdown_seconds,
                h11_max_incomplete_event_size=MAX_REQUEST_BYTES,
            )
        )
        bound = None
        try:
            bound = self._server.config.bind_socket()
            bound.set_inheritable(False)
        except (OSError, SystemExit):
            if bound is not None:
                bound.close()
            raise FleetExporterError("exporter loopback listener unavailable") from None
        self._socket = bound
        port = self._socket.getsockname()[1]
        host = "[::1]" if config.host == "::1" else config.host
        self.metrics_url = f"http://{host}:{port}/metrics"
        self._readiness_url = f"http://{host}:{port}/readyz"
        self._thread = threading.Thread(
            target=self._thread_main, name="fleet-exporter", daemon=False
        )

    def snapshot(self) -> FleetExporterSnapshot:
        return self._cache.snapshot()

    @property
    def _clean_close(self) -> bool:
        worker = self._worker
        return (
            self.closed
            and self.listener_joined
            and self.worker_joined
            and not self._thread.is_alive()
            and not self._failed
            and (
                worker is None
                or worker.done()
                and not worker.cancelled()
                and worker.exception() is None
            )
        )

    @property
    def readiness_url(self) -> str:
        return self._readiness_url

    async def _poll(self) -> None:
        assert self._stop is not None
        try:
            while not self._stop.is_set():
                try:
                    report = await monitor_fleet(
                        self._saved,
                        self._request,
                        candidate_index=self._index,
                        stop_event=self._stop,
                        connections=self._connections,
                    )
                    if not self._stop.is_set():
                        self._cache.publish(report)
                except Exception as exc:
                    LOG.warning("exporter native poll unavailable (%s)", type(exc).__name__)
                    self._cache.publish(None, "unavailable")
                if not self._stop.is_set():
                    try:
                        await asyncio.wait_for(self._stop.wait(), self._config.poll_seconds)
                    except asyncio.TimeoutError:
                        pass  # Normal bounded pause between completed native polls.
        finally:
            self._cache.publish(None, "stopped")

    async def _serve(self) -> None:
        self._loop = asyncio.get_running_loop()
        task = asyncio.create_task(self._server.serve(sockets=[self._socket]))
        try:
            while not task.done():
                if self._server.started:
                    self._ready.set()
                    if self._closing.is_set():
                        if self._stop is not None:
                            self._stop.set()
                        self._server.should_exit = True
                await asyncio.sleep(STARTUP_POLL_SECONDS)
            await task
        finally:
            if self._stop is not None:
                self._stop.set()
            if self._worker is not None:
                await self._worker
                self.worker_joined = True

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._serve())
        except BaseException as exc:
            self._failed = True
            LOG.warning("exporter listener unavailable (%s)", type(exc).__name__)
        finally:
            self._socket.close()

    async def start(self) -> None:
        try:
            self._thread.start()
        except RuntimeError:
            raise FleetExporterError("exporter listener thread unavailable") from None
        deadline = asyncio.get_running_loop().time() + self._config.startup_seconds
        while not self._ready.is_set():
            if not self._thread.is_alive() or asyncio.get_running_loop().time() >= deadline:
                raise FleetExporterError("exporter listener startup unavailable")
            await asyncio.sleep(STARTUP_POLL_SECONDS)
        if self._failed:
            raise FleetExporterError("exporter listener startup unavailable")

    async def _close_owned(self) -> None:
        self._closing.set()
        if self._loop is not None and self._stop is not None and self._loop.is_running():
            try:
                self._loop.call_soon_threadsafe(self._stop.set)
            except RuntimeError as exc:
                # The owned coordinator also observes _closing; a closing loop may reject callbacks.
                LOG.info("exporter shutdown signal raced loop closure (%s)", type(exc).__name__)
        while self._thread.is_alive():
            await asyncio.sleep(STARTUP_POLL_SECONDS)
        if self._thread.ident is not None:
            self._thread.join()
        self._socket.close()
        self.worker_joined = self._worker is None or self._worker.done()
        self.listener_joined = self.closed = True

    async def aclose(self) -> None:
        closer = asyncio.create_task(self._close_owned())
        cancelled = False
        while True:
            try:
                await asyncio.shield(closer)
                break
            except asyncio.CancelledError:
                cancelled = True
        if cancelled:
            raise asyncio.CancelledError


@asynccontextmanager
async def serve_fleet_exporter(
    saved: PlanArtifact | str | Path,
    request: FleetMonitorRequest,
    *,
    config: FleetExporterConfig = FleetExporterConfig(),
    candidate_index: int = 0,
    connections: Mapping[str, MonitorConnection] | None = None,
) -> AsyncIterator[FleetExporter]:
    if type(config) is not FleetExporterConfig:
        raise FleetExporterError("invalid exporter configuration")
    config.validate()
    if type(request) is not FleetMonitorRequest or request.windows != 1:
        raise FleetExporterError("exporter requires one native window per poll")
    try:
        import uvicorn
        from starlette.applications import Starlette
        from starlette.responses import Response
        from starlette.routing import Route
    except ImportError:
        raise FleetExporterError("exporter requires chimeraforge[exporter]") from None
    from chimeraforge.deployment_verify import _source as held_plan

    held, _, _ = held_plan(saved)
    data, candidate = _source(held, candidate_index)
    endpoints = _admit(request, candidate["n_agents"])
    held_request = replace(request, endpoints=endpoints)
    prepared = None
    if connections is not None:
        if not isinstance(connections, Mapping) or len(connections) > MAX_ENDPOINTS:
            raise FleetExporterError("invalid exporter connection mapping")
        values = {}
        ids = {endpoint.id for endpoint in endpoints}
        for number, key in enumerate(connections):
            if (
                number >= MAX_ENDPOINTS
                or type(key) is not str
                or key not in ids
                or key in values
                or type(connections[key]) is not MonitorConnection
            ):
                raise MonitorConnectionError("invalid fleet monitor connection mapping")
            values[key] = connections[key]
        for endpoint in endpoints:
            if endpoint.id not in values:
                values[endpoint.id] = MonitorConnection(endpoint.url)
            admit_connection(values[endpoint.id], endpoint.url)
        prepared = MappingProxyType(values)
    stop = asyncio.Event()
    stop.set()
    template = await monitor_fleet(
        held, held_request, candidate_index=candidate_index, stop_event=stop, connections=prepared
    )
    from chimeraforge import __version__
    from chimeraforge.plan_check import identity

    targets, sources = _targets(data, held_request)
    binding = _PopulationBinding(
        candidate["backend"],
        candidate["model"],
        tuple((e.id, e.url) for e in endpoints),
        {
            "fingerprint": data["fingerprint"],
            "candidate_index": candidate_index,
            "identity": identity(candidate),
            "tool_version": data["tool"]["version"],
        },
        __version__,
        {
            "schema_version": 1,
            "endpoints": [{"id": e.id, "url": e.url} for e in endpoints],
            **{
                name: getattr(held_request, name)
                for name in (
                    "interval",
                    "windows",
                    "timeout",
                    "observation_seconds",
                    "cleanup_seconds",
                    "concurrency",
                    "max_requests",
                    "max_body_bytes",
                )
            },
            "targets": {"ttft_ms": targets["ttft_slo"], "tpot_ms": targets["tpot_slo"]},
            "target_sources": dict(sources),
        },
        dict(sources),
    )
    cache = SnapshotCache(template, config.stale_after_seconds, binding=binding)
    service = FleetExporter(
        held,
        held_request,
        config,
        candidate_index,
        prepared,
        cache,
        uvicorn,
        Starlette,
        Response,
        Route,
    )
    try:
        await service.start()
        yield service
    finally:
        closer = asyncio.create_task(service.aclose())
        cancelled = False
        while True:
            try:
                await asyncio.shield(closer)
                break
            except asyncio.CancelledError:
                cancelled = True
        if cancelled:
            raise asyncio.CancelledError


@dataclass(frozen=True)
class _RunBoundary:
    deadline_reached: bool
    run_seconds: float
    observation: _CapturedSnapshot


async def _await_run_boundary(
    running: FleetExporter, run_seconds: float, stop: asyncio.Event
) -> _RunBoundary:
    deadline = False
    try:
        await asyncio.wait_for(stop.wait(), run_seconds)
    except asyncio.TimeoutError:
        deadline = True
    return _RunBoundary(deadline, run_seconds, running._cache._capture())


def _finish_run(
    running: FleetExporter, boundary: _RunBoundary, required: bool
) -> FleetExporterRunResult:
    if not running._clean_close:
        raise FleetExporterError("exporter startup or shutdown unavailable")
    captured = boundary.observation
    snapshot, fact, raw_age = captured.snapshot, captured.observation, captured.raw_age
    valid_age = raw_age is not None and math.isfinite(raw_age) and raw_age >= 0
    state = (
        snapshot.state
        if snapshot.state in ("initial", "fresh", "stale", "unavailable", "stopped")
        else "unavailable"
    )
    if raw_age is not None and not valid_age:
        state = "invalid_clock"
    bound = (
        fact is not None
        and fact.bound
        and fact.expected == captured.expected
        and fact.observed == captured.expected
    )
    observed_code = (
        captured.native_code
        if fact is not None
        and type(captured.native_code) is int
        and captured.native_code in (0, 3, 4, 5)
        else None
    )
    qualified_code = (
        observed_code
        if boundary.deadline_reached
        and snapshot.sequence > 0
        and state == "fresh"
        and valid_age
        and raw_age is not None
        and raw_age < captured.ttl
        and bound
        and observed_code is not None
        else 4
    )
    return FleetExporterRunResult(
        qualification_requested=required,
        qualification_met=qualified_code == 0 if required else None,
        exit_code=qualified_code if required else 0,
        run_seconds=boundary.run_seconds,
        boundary="deadline" if boundary.deadline_reached else "stopped",
        snapshot_state=state,
        age_seconds=raw_age if valid_age else None,
        sequence=snapshot.sequence,
        observed_native_exit_code=observed_code,
        expected_replicas=captured.expected,
        observed_replicas=fact.observed if fact is not None else 0,
        population_bound=bound,
        closed=running.closed,
        listener_joined=running.listener_joined,
        worker_joined=running.worker_joined,
    )
