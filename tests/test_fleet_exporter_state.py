"""Native controlled wire states, real cached HTTP, and precontact admission."""

from __future__ import annotations

import asyncio
from dataclasses import replace
import json
import socket
import threading

import httpx
import pytest
import uvicorn

from chimeraforge import api
from chimeraforge.fleet_monitor_transport import OwnedPool
from test_fleet_monitor import MODEL, native_fleet as native_fleet, request
from test_fleet_monitor_transport import Stream, Transport, urls
from test_monitor_slo import pair


class Scene:
    def __init__(self, monkeypatch):
        self.mode = "pass"
        self.calls, self.pools, self.streams = [], [], []
        self.counts = {}
        self.stalled = threading.Event()
        first, second = [s.replace("org/model", MODEL).encode() for s in pair()]

        async def handler(value):
            self.calls.append((value.url.host, value.url.path))
            mode = self.mode
            if mode == "raise":
                raise RuntimeError("PrivateFailureSecret")
            if mode == "stall":
                self.stalled.set()
                await asyncio.Event().wait()
            if value.url.path == "/metrics":
                number = self.counts.get(value.url.host, 0)
                self.counts[value.url.host] = number + 1
                bodies = (second, first) if mode == "reset" else (first, second)
                raw = bodies[number % 2]
                if mode == "missing":
                    raw = b"# unavailable histograms\n"
            else:
                data = (
                    {"version": "0.30.0"}
                    if value.url.path == "/version"
                    else {"data": [{"id": MODEL}]}
                    if value.url.path == "/v1/models"
                    else {}
                )
                if mode == "mismatch" and value.url.path == "/server_info":
                    data = {
                        "vllm_config": {
                            "model_config": {"dtype": "Q8_0", "max_model_len": 2048},
                            "parallel_config": {
                                "tensor_parallel_size": 2,
                                "pipeline_parallel_size": 1,
                                "data_parallel_size": 1,
                            },
                        }
                    }
                raw = json.dumps(data).encode()
            stream = Stream([raw])
            self.streams.append(stream)
            return httpx.Response(200, stream=stream)

        def owned(pool):
            if pool.inner is None:
                pool.inner = Transport(handler)
                self.pools.append(pool.inner)
            return pool.inner

        monkeypatch.setattr(OwnedPool, "_transport", owned)


async def changed(running, sequence=0, *, state="fresh"):
    for _ in range(500):
        value = running.snapshot()
        if value.sequence > sequence and value.state == state:
            return value
        await asyncio.sleep(0.01)
    pytest.fail("bounded native exporter did not publish expected state")


def controls():
    return replace(request(urls()), interval=0.01, observation_seconds=0.5)


@pytest.mark.asyncio
async def test_initial_and_expiry_omit_unknown_numbers_even_when_poll_stalls(
    native_fleet, monkeypatch
):
    scene = Scene(monkeypatch)
    saved, indices = native_fleet
    config = api.FleetExporterConfig(port=0, poll_seconds=0.02, stale_after_seconds=0.1)
    value = replace(controls(), interval=0.05, observation_seconds=2)
    async with api.serve_fleet_exporter(
        saved, value, config=config, candidate_index=indices["vllm"]
    ) as running:
        initial = running.snapshot()
        assert initial.state == "initial" and initial.age_seconds is None
        assert b"chimeraforge_fleet_slot_p95_lower_ms{" not in initial.body
        good = await changed(running)
        assert good.native_exit_code == 0
        assert b"chimeraforge_fleet_slot_p95_lower_ms{" in good.body
        scene.mode = "stall"
        for _ in range(200):
            if scene.stalled.is_set():
                break
            await asyncio.sleep(0.01)
        assert scene.stalled.is_set()
        await asyncio.sleep(0.12)
        before = len(scene.calls)
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.get(running.metrics_url)
        stale = running.snapshot()
        assert stale.state == "stale" and stale.native_exit_code == 4
        assert response.content == stale.body and len(scene.calls) == before
        assert b"chimeraforge_fleet_slot_p95_lower_ms{" not in stale.body
        assert b"chimeraforge_fleet_slot_samples{" not in stale.body
        assert b'chimeraforge_fleet_qualification{outcome="pass"} 0' in stale.body
        assert all(f'replica="replica-{i}"'.encode() in stale.body for i in (1, 2, 3))
    assert all(p.closed == 1 for p in scene.pools)
    assert all(s.closed == 1 for s in scene.streams)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode,code", [("raise", 4), ("missing", 4), ("reset", 4), ("mismatch", 5)])
async def test_new_native_nonpass_replaces_old_pass_without_population_loss(
    native_fleet, monkeypatch, mode, code
):
    scene = Scene(monkeypatch)
    saved, indices = native_fleet
    config = api.FleetExporterConfig(port=0, poll_seconds=0.1, stale_after_seconds=3)
    async with api.serve_fleet_exporter(
        saved, controls(), config=config, candidate_index=indices["vllm"]
    ) as running:
        good = await changed(running)
        assert good.native_exit_code == 0
        scene.mode = mode
        later = await changed(running, good.sequence)
        assert later.native_exit_code == code and later.original_replicas == 3
        assert b'chimeraforge_fleet_qualification{outcome="pass"} 0' in later.body
        if mode in ("raise", "missing", "reset"):
            assert b"chimeraforge_fleet_slot_p95_lower_ms{" not in later.body
        assert all(f'replica="replica-{i}"'.encode() in later.body for i in (1, 2, 3))
        assert b"PrivateFailureSecret" not in later.body
    assert all(p.closed == 1 for p in scene.pools)


@pytest.mark.asyncio
async def test_fixed_startup_plan_path_is_never_reloaded(native_fleet, monkeypatch, tmp_path):
    scene = Scene(monkeypatch)
    saved, indices = native_fleet
    path = tmp_path / "saved.json"
    saved.save(path)
    config = api.FleetExporterConfig(port=0, poll_seconds=0.05, stale_after_seconds=3)
    async with api.serve_fleet_exporter(
        path, controls(), config=config, candidate_index=indices["vllm"]
    ) as running:
        first = await changed(running)
        path.write_text("changed after startup", encoding="utf-8")
        second = await changed(running, first.sequence)
        assert second.native_exit_code == 0
    assert running.closed and scene.calls


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault", ["host", "windows", "last-url", "duplicate-url", "bad-target", "foreign-connection"]
)
async def test_late_configuration_error_before_bind_or_backend(native_fleet, monkeypatch, fault):
    scene = Scene(monkeypatch)
    saved, indices = native_fleet
    value = controls()
    config = api.FleetExporterConfig(port=0)
    connections = None
    if fault == "host":
        config = replace(config, host="0.0.0.0")
    elif fault == "windows":
        value = replace(value, windows=2)
    elif fault == "last-url":
        value = replace(
            value,
            endpoints=(
                *value.endpoints[:-1],
                replace(value.endpoints[-1], url="http://private/?token=x"),
            ),
        )
    elif fault == "duplicate-url":
        value = replace(
            value,
            endpoints=(
                *value.endpoints[:-1],
                replace(value.endpoints[-1], url=value.endpoints[0].url),
            ),
        )
    elif fault == "bad-target":
        value = replace(value, ttft_slo=float("nan"))
    else:
        connections = {"foreign": api.MonitorConnection("https://private.invalid/metrics")}
    binds = []

    def refuse(*args):
        binds.append(True)
        raise AssertionError("bind reached")

    monkeypatch.setattr(uvicorn.Config, "bind_socket", refuse)
    with pytest.raises(ValueError):
        async with api.serve_fleet_exporter(
            saved, value, config=config, candidate_index=indices["vllm"], connections=connections
        ):
            pytest.fail("invalid configuration admitted")
    assert not binds and not scene.calls


@pytest.mark.asyncio
async def test_unavailable_port_makes_zero_backend_requests(native_fleet, monkeypatch):
    scene = Scene(monkeypatch)
    saved, indices = native_fleet
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen(1)
        config = api.FleetExporterConfig(port=occupied.getsockname()[1])
        with pytest.raises(api.FleetExporterError):
            async with api.serve_fleet_exporter(
                saved, controls(), config=config, candidate_index=indices["vllm"]
            ):
                pass
    assert not scene.calls


@pytest.mark.asyncio
async def test_bound_socket_closed_if_post_bind_admission_fails(native_fleet, monkeypatch):
    scene = Scene(monkeypatch)
    saved, indices = native_fleet
    bound = []

    class FailingSocket:
        def __init__(self):
            self.socket = socket.socket()
            self.socket.bind(("127.0.0.1", 0))
            bound.append(self.socket)

        def set_inheritable(self, value):
            raise OSError("controlled after-bind failure")

        def close(self):
            self.socket.close()

    monkeypatch.setattr(uvicorn.Config, "bind_socket", lambda _: FailingSocket())
    try:
        with pytest.raises(api.FleetExporterError):
            async with api.serve_fleet_exporter(
                saved,
                controls(),
                config=api.FleetExporterConfig(port=0),
                candidate_index=indices["vllm"],
            ):
                pass
        assert bound and all(s.fileno() == -1 for s in bound)
    finally:
        for s in bound:
            s.close()
    assert not scene.calls


@pytest.mark.asyncio
async def test_thread_start_failure_closes_owned_socket_without_masking(native_fleet, monkeypatch):
    scene = Scene(monkeypatch)
    saved, indices = native_fleet
    native = threading.Thread.start
    bound = []
    bind = uvicorn.Config.bind_socket

    def record(self):
        s = bind(self)
        bound.append(s)
        return s

    def fail(self):
        if self.name == "fleet-exporter":
            raise RuntimeError("controlled start failure")
        return native(self)

    monkeypatch.setattr(uvicorn.Config, "bind_socket", record)
    monkeypatch.setattr(threading.Thread, "start", fail)
    try:
        with pytest.raises(api.FleetExporterError):
            async with api.serve_fleet_exporter(
                saved,
                controls(),
                config=api.FleetExporterConfig(port=0),
                candidate_index=indices["vllm"],
            ):
                pass
        assert all(s.fileno() == -1 for s in bound)
    finally:
        for s in bound:
            s.close()
    assert not scene.calls


@pytest.mark.asyncio
async def test_repeat_close_tolerates_loop_closed_between_check_and_signal(
    native_fleet, monkeypatch
):
    Scene(monkeypatch)
    saved, indices = native_fleet
    async with api.serve_fleet_exporter(
        saved, controls(), config=api.FleetExporterConfig(port=0), candidate_index=indices["vllm"]
    ) as running:
        await asyncio.gather(*(running.aclose() for _ in range(3)))

        class ClosedLoopRace:
            def is_running(self):
                return True

            def is_closed(self):
                return True

            def call_soon_threadsafe(self, *args):
                raise RuntimeError("Event loop is closed")

        running._loop = ClosedLoopRace()
        await running.aclose()
    assert running.closed and running.worker_joined and running.listener_joined
