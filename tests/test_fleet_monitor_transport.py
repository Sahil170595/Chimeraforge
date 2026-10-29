"""Controlled public HTTPX transports falsify aggregate and ownership boundaries."""

import asyncio
import json
import logging
import time
from dataclasses import replace

import httpx
import pytest

from chimeraforge import api
from chimeraforge.fleet_monitor_transport import BorrowedTransport, OwnedPool, SharedBudget
from test_fleet_monitor import MODEL, native_fleet as native_fleet, request
from test_monitor_slo import pair

MAX_READY_WORK_TURNS = 10000


class Stream(httpx.AsyncByteStream):
    def __init__(self, chunks=(), gate=None):
        self.chunks, self.gate = chunks, gate
        self.closed = 0

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk
        if self.gate is not None:
            await self.gate.wait()

    async def aclose(self):
        self.closed += 1


class Transport(httpx.AsyncBaseTransport):
    def __init__(self, handler):
        self.handler = handler
        self.closed = 0

    async def handle_async_request(self, value):
        return await self.handler(value)

    async def aclose(self):
        self.closed += 1


class NativeScene:
    def __init__(
        self,
        monkeypatch,
        *,
        encoded=False,
        oversize=False,
        stall=False,
        close_gate=None,
        ttft=0.05,
        metadata_stall=False,
    ):
        self.calls, self.pools, self.streams = [], [], []
        self.metrics = {}
        self.started = asyncio.Event()
        self.metadata_started = asyncio.Event()
        self.close_started = asyncio.Event()
        self.stall_gate = asyncio.Event()
        first, second = (text.replace("org/model", MODEL) for text in pair(ttft=ttft))

        async def handler(value):
            self.calls.append(str(value.url))
            assert value.headers["Accept-Encoding"] == "identity"
            route = value.url.path
            headers = {}
            if route == "/metrics":
                count = self.metrics.get(value.url.host, 0)
                self.metrics[value.url.host] = count + 1
                body = (first if count == 0 else second).encode()
                gate = self.stall_gate if stall else None
                self.started.set()
            else:
                gate = self.stall_gate if metadata_stall else None
                self.metadata_started.set()
                if route == "/version":
                    data = {"version": "0.30.0"}
                elif route == "/v1/models":
                    data = {"data": [{"id": MODEL}]}
                else:
                    data = {}
                    if encoded:
                        headers["Content-Encoding"] = "gzip"
                body = (
                    b"x" * (1024 * 1024 + 1)
                    if oversize and route == "/server_info"
                    else json.dumps(data).encode()
                )
            stream = Stream([body], gate)
            self.streams.append(stream)
            return httpx.Response(200, headers=headers, stream=stream)

        scene = self

        class PoolTransport(Transport):
            async def aclose(self):
                self.closed += 1
                scene.close_started.set()
                if close_gate is not None:
                    await close_gate.wait()
                self.finished = True

        def owned(pool):
            if pool.inner is None:
                pool.inner = PoolTransport(handler)
                scene.pools.append(pool.inner)
            return pool.inner

        monkeypatch.setattr(OwnedPool, "_transport", owned)


def urls():
    return ["http://one/metrics", "http://two/metrics", "http://three/metrics"]


@pytest.mark.asyncio
async def test_window_timestamps_use_real_monotonic_measurement_with_ready_work(
    native_fleet, monkeypatch
):
    from chimeraforge import fleet_monitor

    saved, indices = native_fleet
    scene = NativeScene(monkeypatch)
    native_metrics = fleet_monitor._metrics
    measurements = {}
    before_tasks = asyncio.all_tasks()
    stop = asyncio.Event()

    async def measure(resources):
        before = time.perf_counter()
        payload, timestamp = await native_metrics(resources)
        after = time.perf_counter()
        measurements.setdefault(resources.slot.id, []).append((before, timestamp, after))
        return payload, timestamp

    async def ready():
        for _ in range(MAX_READY_WORK_TURNS):
            if stop.is_set():
                break
            await asyncio.sleep(0)

    monkeypatch.setattr(fleet_monitor, "_metrics", measure)
    worker = asyncio.create_task(ready())
    start = time.perf_counter()
    try:
        report = await api.monitor_fleet(saved, request(urls()), candidate_index=indices["vllm"])
    finally:
        stop.set()
        if not worker.done():
            worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
    elapsed = time.perf_counter() - start
    assert report.exit_code == 0, {
        "exit": report.exit_code,
        "actual_sample_deltas": [rows[1][1] - rows[0][1] for rows in measurements.values()],
    }
    assert all(len(rows) == 2 for rows in measurements.values())
    assert all(
        before <= stamp <= after for rows in measurements.values() for before, stamp, after in rows
    )
    assert all(0 < slot.windows[0].seconds <= elapsed for slot in report.slots)
    assert report.cleanup["resources_closed"] and report.cleanup["closed_pools"] == 6
    assert all(pool.closed == 1 for pool in scene.pools)
    assert all(stream.closed == 1 for stream in scene.streams)
    assert asyncio.all_tasks() == before_tasks


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind,fail_after,expected_exit", [("initial", 0, 4), ("mismatch", 2, 5), ("breach", 2, 3)]
)
async def test_unexpected_metrics_stream_failure_retains_context_and_owned_cleanup(
    native_fleet, monkeypatch, caplog, kind, fail_after, expected_exit
):
    saved, indices = native_fleet
    original = saved.to_dict()
    scene = NativeScene(monkeypatch)
    clients, failed_streams = [], []
    original_client = httpx.AsyncClient
    original_handle = Transport.handle_async_request
    secret = "PRIVATE_METRICS_STREAM_FAILURE_CANARY"
    breach = [text.replace("org/model", MODEL).encode() for text in pair(ttft=0.7)]

    class UnexpectedStream(httpx.AsyncByteStream):
        def __init__(self, inner):
            self.inner, self.closed = inner, 0

        async def __aiter__(self):
            async for chunk in self.inner:
                yield chunk
            raise RuntimeError(secret)

        async def aclose(self):
            self.closed += 1
            await self.inner.aclose()

    def client(*args, **kwargs):
        value = original_client(*args, **kwargs)
        clients.append(value)
        return value

    async def handle(transport, value):
        response = await original_handle(transport, value)
        if value.url.host == "one":
            if value.url.path == "/metrics":
                count = scene.metrics["one"] - 1
                if kind == "breach":
                    response.stream.chunks = [breach[min(count, 1)]]
                if count == fail_after:
                    response.stream = UnexpectedStream(response.stream)
                    failed_streams.append(response.stream)
            elif kind == "mismatch" and value.url.path == "/server_info":
                response.stream.chunks = [
                    json.dumps({"vllm_config": {"model_config": {"dtype": "Q8_0"}}}).encode()
                ]
        return response

    monkeypatch.setattr(httpx, "AsyncClient", client)
    monkeypatch.setattr(Transport, "handle_async_request", handle)
    caplog.set_level(logging.INFO, logger="chimeraforge.fleet_monitor")
    before_tasks = asyncio.all_tasks()
    report = await api.monitor_fleet(
        saved, request(urls(), windows=2), candidate_index=indices["vllm"]
    )
    await asyncio.sleep(0)

    assert [slot.id for slot in report.slots] == ["replica-1", "replica-2", "replica-3"]
    assert scene.metrics["one"] == fail_after + 1, report.to_dict()
    assert report.budget["requests"] == len(scene.calls) and report.budget["termination"] is None
    assert report.exit_code == expected_exit
    assert report.cleanup["state"] == "completed" and report.cleanup["resources_closed"]
    assert report.cleanup["owned_pools"] == report.cleanup["closed_pools"] == 6
    assert report.cleanup["joined_endpoint_tasks"] == 3 and report.cleanup["close_errors"] == 0
    assert len(clients) == (5 if kind == "initial" else 6)
    assert all(value.is_closed for value in clients)
    assert len(failed_streams) == 1 and failed_streams[0].closed == 1
    assert all(pool.closed == 1 for pool in scene.pools)
    assert all(stream.closed == 1 for stream in scene.streams)
    assert asyncio.all_tasks() == before_tasks
    assert saved.to_dict() == original
    failed = report.slots[0]
    assert len(failed.windows) == (0 if kind == "initial" else 1)
    assert len(failed.observations) == (0 if kind == "initial" else 2)
    if kind == "mismatch":
        assert failed.binding["configuration"]["state"] == "mismatch"
    if kind == "breach":
        assert failed.slo == "breach" and failed.windows[0].outcome == "breach"
    assert secret not in json.dumps(report.to_dict()) and secret not in caplog.text
    assert failed.state == "error", report.to_dict()
    assert failed.error == "RuntimeError"
    assert "fleet endpoint replica-1 observation failed (RuntimeError)" in caplog.messages


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["encoded", "oversize"])
async def test_optional_metadata_cannot_swallow_transport_contract_violation(
    native_fleet, monkeypatch, kind
):
    saved, indices = native_fleet
    scene = NativeScene(monkeypatch, **{kind: True})
    report = await api.monitor_fleet(saved, request(urls()), candidate_index=indices["vllm"])
    assert report.exit_code == 4
    assert all(row.state == "error" for row in report.slots)
    assert all(row.binding["identity"]["state"] == "matched" for row in report.slots)
    assert report.cleanup["resources_closed"] and all(pool.closed == 1 for pool in scene.pools)
    assert all(stream.closed == 1 for stream in scene.streams)


@pytest.mark.asyncio
async def test_global_accepted_bytes_are_not_per_endpoint(native_fleet, monkeypatch):
    saved, indices = native_fleet
    scene = NativeScene(monkeypatch)
    result = await api.monitor_fleet(
        saved, request(urls(), max_body_bytes=100), candidate_index=indices["vllm"]
    )
    assert result.exit_code == 4 and result.budget["termination"] == "body_limit"
    assert result.budget["accepted_body_bytes"] <= 100
    assert all(pool.closed == 1 for pool in scene.pools)


@pytest.mark.asyncio
async def test_cross_pool_budget_admits_each_body_but_not_cumulative_metrics_plus_metadata(
    native_fleet, monkeypatch
):
    saved, indices = native_fleet
    scene = NativeScene(monkeypatch)
    first = pair()[0].replace("org/model", MODEL).encode()
    metadata_size = len(json.dumps({"version": "0.30.0"}).encode())
    cap = 3 * len(first) + metadata_size
    result = await api.monitor_fleet(
        saved, request(urls(), max_body_bytes=cap), candidate_index=indices["vllm"]
    )
    assert result.budget["termination"] == "body_limit" and result.exit_code == 4
    assert result.budget["accepted_body_bytes"] == cap
    assert any(value.endswith("/version") for value in scene.calls)
    assert all(pool.closed == 1 for pool in scene.pools)


@pytest.mark.asyncio
async def test_stalled_stream_and_semaphore_backlog_share_deadline(native_fleet, monkeypatch):
    saved, indices = native_fleet
    scene = NativeScene(monkeypatch, stall=True)
    value = replace(request(urls()), observation_seconds=0.03, concurrency=1)
    result = await api.monitor_fleet(saved, value, candidate_index=indices["vllm"])
    assert result.exit_code == 4 and result.budget["termination"] == "observation_deadline"
    assert result.budget["requests"] == len(scene.calls) == 1
    assert [row.state for row in result.slots] == ["cancelled", "unstarted", "unstarted"]
    assert all(stream.closed == 1 for stream in scene.streams)


@pytest.mark.asyncio
async def test_stop_during_stream_returns_population_after_closure(native_fleet, monkeypatch):
    saved, indices = native_fleet
    scene = NativeScene(monkeypatch, stall=True)
    stop = asyncio.Event()
    task = asyncio.create_task(
        api.monitor_fleet(saved, request(urls()), candidate_index=indices["vllm"], stop_event=stop)
    )
    await scene.started.wait()
    stop.set()
    result = await task
    assert result.cancelled and result.exit_code == 4 and len(result.slots) == 3
    assert all(stream.closed == 1 for stream in scene.streams)
    assert result.cleanup["state"] == "completed"


@pytest.mark.asyncio
async def test_second_caller_cancel_does_not_orphan_cleanup(native_fleet, monkeypatch):
    saved, indices = native_fleet
    gate = asyncio.Event()
    scene = NativeScene(monkeypatch, stall=True, close_gate=gate)
    task = asyncio.create_task(
        api.monitor_fleet(saved, request(urls()), candidate_index=indices["vllm"])
    )
    await scene.started.wait()
    task.cancel()
    for _ in range(100):
        if any(pool.closed for pool in scene.pools):
            break
        await asyncio.sleep(0)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    gate.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert all(pool.closed == 1 for pool in scene.pools)
    assert all(stream.closed == 1 for stream in scene.streams)


@pytest.mark.asyncio
@pytest.mark.parametrize("slow_observation", [False, True])
async def test_cleanup_allowance_overrun_is_sticky_even_after_all_owners_attempted(
    native_fleet, monkeypatch, slow_observation
):
    from chimeraforge.bench import serving

    saved, indices = native_fleet
    gate = asyncio.Event()
    scene = NativeScene(monkeypatch, close_gate=gate)
    if slow_observation:
        original = serving.observe_backend

        async def delayed(*args):
            result = await original(*args)
            await asyncio.sleep(0.035)
            return result

        monkeypatch.setattr(serving, "observe_backend", delayed)
    value = replace(request(urls()), cleanup_seconds=0.001)
    task = asyncio.create_task(api.monitor_fleet(saved, value, candidate_index=indices["vllm"]))
    await scene.close_started.wait()
    await asyncio.sleep(0.05)
    gate.set()
    result = await task
    assert result.exit_code == 4 and result.cleanup["allowance_exceeded"]
    assert result.cleanup["state"] == "incomplete" and all(pool.closed == 1 for pool in scene.pools)
    assert result.cleanup["resources_closed"] and all(pool.finished for pool in scene.pools)


@pytest.mark.asyncio
async def test_borrowed_client_close_does_not_close_owned_or_sibling_pool():
    budget = SharedBudget(asyncio.get_running_loop().time() + 2, 10, 100, 1)
    first, second = OwnedPool(budget, 100), OwnedPool(budget, 100)

    async def handler(value):
        return httpx.Response(200, stream=Stream([b"ok"]))

    first.inner, second.inner = Transport(handler), Transport(handler)
    a = httpx.AsyncClient(transport=BorrowedTransport(first))
    b = httpx.AsyncClient(transport=BorrowedTransport(second))
    await a.aclose()
    assert first.inner.closed == 0 and second.inner.closed == 0
    assert (await b.get("http://two")).content == b"ok"
    await b.aclose()
    await first.aclose()
    await second.aclose()
    assert first.inner.closed == second.inner.closed == 1


@pytest.mark.asyncio
async def test_attempts_charged_at_inner_contact_not_semaphore_queue():
    budget = SharedBudget(asyncio.get_running_loop().time() + 2, 1, 100, 1)
    first, second = OwnedPool(budget, 100), OwnedPool(budget, 100)
    gate, started = asyncio.Event(), asyncio.Event()

    async def handler(value):
        started.set()
        return httpx.Response(200, stream=Stream([b"ok"], gate))

    first.inner, second.inner = Transport(handler), Transport(handler)
    a, b = (
        httpx.AsyncClient(transport=BorrowedTransport(first)),
        httpx.AsyncClient(transport=BorrowedTransport(second)),
    )
    task = asyncio.create_task(a.get("http://one"))
    await started.wait()
    waiting = asyncio.create_task(b.get("http://two"))
    await asyncio.sleep(0)
    assert budget.requests == 1 and budget.termination is None
    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting
    gate.set()
    await task
    await a.aclose()
    await b.aclose()
    await first.aclose()
    await second.aclose()


@pytest.mark.asyncio
async def test_partial_resource_construction_failure_closes_every_registered_owner(
    native_fleet, monkeypatch
):
    import chimeraforge.fleet_monitor as core

    saved, indices = native_fleet
    clients, backends = [], []
    original_client = httpx.AsyncClient

    def client(*args, **kwargs):
        value = original_client(*args, **kwargs)
        clients.append(value)
        return value

    class Backend:
        closed = False

        async def close(self):
            self.closed = True

    def backend(*args, **kwargs):
        if backends:
            raise ValueError("constructor refusal")
        value = Backend()
        backends.append(value)
        return value

    monkeypatch.setattr(core.httpx, "AsyncClient", client)
    monkeypatch.setattr(core, "get_backend", backend)
    with pytest.raises(ValueError):
        await api.monitor_fleet(saved, request(urls()), candidate_index=indices["vllm"])
    assert clients and all(value.is_closed for value in clients)
    assert backends and all(value.closed for value in backends)


@pytest.mark.asyncio
async def test_late_final_metadata_processing_cannot_pass_after_observation_deadline(
    native_fleet, monkeypatch
):
    from chimeraforge.bench import serving
    from chimeraforge import fleet_monitor

    saved, indices = native_fleet
    scene = NativeScene(monkeypatch)
    original = serving.observe_backend
    original_budget = fleet_monitor.SharedBudget
    budgets = []
    count = 0

    def capture_budget(*args):
        budget = original_budget(*args)
        budgets.append(budget)
        return budget

    monkeypatch.setattr(fleet_monitor, "SharedBudget", capture_budget)

    async def delayed(*args):
        nonlocal count
        result = await original(*args)
        count += 1
        if count == 6:
            assert len(budgets) == 1 and budgets[0].termination is None
            budgets[0].deadline = asyncio.get_running_loop().time() - 1
        return result

    monkeypatch.setattr(serving, "observe_backend", delayed)
    result = await api.monitor_fleet(
        saved, replace(request(urls()), observation_seconds=10), candidate_index=indices["vllm"]
    )
    assert count == 6 and len(budgets) == 1
    assert result.exit_code == 4 and result.budget["termination"] == "observation_deadline"
    assert all(
        slot.state == "complete" and len(slot.windows) == 1 and len(slot.observations) == 2
        for slot in result.slots
    )
    assert all(stream.closed == 1 for stream in scene.streams)
    assert all(pool.closed == 1 and pool.finished for pool in scene.pools)


@pytest.mark.asyncio
async def test_stop_during_native_metadata_awaits_stream_and_backend_closure(
    native_fleet, monkeypatch
):
    saved, indices = native_fleet
    scene = NativeScene(monkeypatch, metadata_stall=True)
    stop = asyncio.Event()
    task = asyncio.create_task(
        api.monitor_fleet(saved, request(urls()), candidate_index=indices["vllm"], stop_event=stop)
    )
    await scene.metadata_started.wait()
    stop.set()
    result = await task
    assert result.exit_code == 4 and result.cancelled and len(result.slots) == 3
    assert result.cleanup["state"] == "completed" and all(
        stream.closed == 1 for stream in scene.streams
    )
    assert all(not slot.windows and not slot.observations for slot in result.slots)


@pytest.mark.asyncio
async def test_trickling_body_cannot_extend_global_observation_deadline(native_fleet, monkeypatch):
    saved, indices = native_fleet
    streams, pools = [], []

    class Trickle(Stream):
        async def __aiter__(self):
            for _ in range(100):
                yield b"x"
                await asyncio.sleep(0.005)

    async def handler(value):
        stream = Trickle()
        streams.append(stream)
        return httpx.Response(200, stream=stream)

    def owned(pool):
        if pool.inner is None:
            pool.inner = Transport(handler)
            pools.append(pool.inner)
        return pool.inner

    monkeypatch.setattr(OwnedPool, "_transport", owned)
    value = replace(request(urls()), observation_seconds=0.03, concurrency=1)
    result = await api.monitor_fleet(saved, value, candidate_index=indices["vllm"])
    assert result.exit_code == 4 and result.budget["termination"] == "observation_deadline"
    assert 0 < result.budget["accepted_body_bytes"] < 100
    assert result.cleanup["state"] == "completed" and all(stream.closed == 1 for stream in streams)
