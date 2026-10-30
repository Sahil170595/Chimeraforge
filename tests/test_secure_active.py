"""Authenticated active operations and native SDK privacy boundaries."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler
import logging

import pytest

from chimeraforge.bench import backends
from chimeraforge.monitor import MonitorRequest, run_monitor
from chimeraforge.monitor_connection import MonitorConnection, MonitorConnectionError
from test_secure_monitor import certs as certs, fixture
from test_fleet_monitor import native_fleet as native_fleet


@pytest.mark.parametrize("backend", ["vllm", "sglang"])
def test_secure_factory_rejects_replaced_builtin_before_construction(monkeypatch, backend):
    constructed = []

    class Replacement:
        def __init__(self, **kwargs):
            constructed.append(kwargs)

    monkeypatch.setitem(backends.BACKEND_REGISTRY, backend, Replacement)
    connection = MonitorConnection("https://example.test")
    with pytest.raises(MonitorConnectionError):
        backends.get_backend(backend, base_url="https://example.test", connection=connection)
    assert constructed == []


def test_secure_factory_refuses_plugin_before_discovery(monkeypatch):
    from chimeraforge.bench.backends import plugin

    discovered = []

    def discover():
        discovered.append(True)
        return []

    monkeypatch.setattr(plugin, "discover_plugins", discover)
    connection = MonitorConnection("https://example.test")
    with pytest.raises(MonitorConnectionError):
        backends.get_backend(
            "fixture-plugin", base_url="https://example.test", connection=connection
        )
    assert discovered == []


def test_native_secure_monitor_hides_provider_echo_before_prior_factory(monkeypatch, certs):
    canary = "FictionalProviderEcho82"
    prior = logging.getLogRecordFactory()
    observed = []
    send_response = BaseHTTPRequestHandler.send_response

    def echo(self, code, message=None):
        send_response(self, code, canary)
        self.send_header("X-Fictional-Provider", canary)

    def record_factory(*args, **kwargs):
        if args[0] == "httpx" or args[0].startswith("httpcore."):
            observed.append((args[0], args[4:], kwargs))
        return prior(*args, **kwargs)

    monkeypatch.setattr(BaseHTTPRequestHandler, "send_response", echo)
    for name in ("httpx", "httpcore"):
        monkeypatch.setattr(logging.getLogger(name), "level", logging.DEBUG)
    logging.setLogRecordFactory(record_factory)
    try:
        with fixture.server(certs, token=canary) as (url, calls):
            connection = MonitorConnection(url, ca_bundle=certs["ca"], bearer_token=canary)
            result = run_monitor(
                MonitorRequest("vllm", url, "ci/manual-fleet", ttft_slo=500, interval=0.01),
                connection=connection,
            )
            assert result.exit_code == 0
            assert len(calls) == 2 and all(row["authorized"] for row in calls)
        assert observed, "native SDK log path must execute"
        assert canary not in repr(observed)
    finally:
        logging.setLogRecordFactory(prior)


@pytest.mark.asyncio
async def test_second_cancel_waits_for_actual_secure_client_close(monkeypatch, certs):
    import asyncio

    import httpx

    from chimeraforge.bench.backends.base import backend_lifecycle
    from chimeraforge.bench.backends.vllm import VLLMBackend

    entered, closing, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    native_close = httpx.AsyncClient.aclose
    owner = None
    backend = None
    with fixture.server(certs) as (url, calls):
        connection = MonitorConnection(url, ca_bundle=certs["ca"])
        backend = VLLMBackend(url, connection=connection)

        async def gated_close(client):
            if client is backend._client:
                closing.set()
                await release.wait()
            await native_close(client)

        async def consume():
            async with backend_lifecycle(backend, _secure=True):
                assert await backend.get_version() == "0.30.0"
                entered.set()
                await asyncio.Event().wait()

        monkeypatch.setattr(httpx.AsyncClient, "aclose", gated_close)
        owner = asyncio.create_task(consume())
        try:
            await asyncio.wait_for(entered.wait(), 5)
            assert len(calls) == 1
            assert owner.cancel()
            await asyncio.wait_for(closing.wait(), 5)
            assert owner.cancel()
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            assert not owner.done(), "secure owner must retain actual client close ownership"
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await owner
            assert backend._client.is_closed
        finally:
            release.set()
            if not owner.done():
                owner.cancel()
            await asyncio.gather(owner, return_exceptions=True)
            if backend._client is not None:
                await native_close(backend._client)


@pytest.fixture(scope="module")
def active_plan():
    from chimeraforge import api

    saved = api.plan(
        api.PlanRequest(
            models=["ci/manual-active"],
            overrides={"params_b": 3.0, "n_layers": 28, "n_kv_heads": 8, "d_head": 128},
            hardware="RTX 4090 24GB",
            request_rate=0.1,
            latency_slo=100000,
            avg_tokens=4,
            prompt_tokens=8,
            quality_target=0,
            budget=1e8,
            allow_network=False,
        )
    )
    candidates = saved.to_dict()["result"]["candidates"]
    indices = {
        backend: next(
            i
            for i, row in enumerate(candidates)
            if row["backend"] == backend
            and row["quant"] == "FP16"
            and row["n_agents"] == 1
            and row["tensor_parallel"] == row["pipeline_parallel"] == 1
        )
        for backend in ("vllm", "sglang")
    }
    return saved, indices


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["vllm", "sglang"])
@pytest.mark.parametrize("mode", ["bench", "trace", "saved-bench", "saved-trace"])
async def test_actual_secure_active_api_complete_paths(active_plan, certs, backend, mode):
    import json

    from chimeraforge import api
    from chimeraforge.bench.runner import run_benchmark
    from chimeraforge.bench.trace_workload import TraceRequest
    from test_ci_acceptance import load_script

    wire = load_script("ci_secure_active")
    saved, indices = active_plan
    original = saved.to_dict()
    with wire.server(certs, backend=backend, token="FictionalActive82", mtls=True) as (url, calls):
        connection = MonitorConnection(
            url,
            ca_bundle=certs["ca"],
            bearer_token="FictionalActive82",
            client_cert=certs["client"],
            client_key=certs["client_key"],
        )
        args = {"base_url": url, "connection": connection}
        rows = [TraceRequest("one", "fictional prompt", 4, 0)]
        if mode == "bench":
            result = await run_benchmark(
                wire.MODEL,
                backend,
                runs=1,
                prompt="fictional prompt",
                options={"max_tokens": 4},
                **args,
            )
            assert result.aggregate.count == 1 and result.individual_runs[0].tokens_generated == 4
            from chimeraforge.bench.metrics import result_to_dict

            report = result_to_dict(result)
        elif mode == "trace":
            result = await api.replay_trace(rows, model=wire.MODEL, backend=backend, **args)
            report = result.to_dict()
            assert report["exit_code"] == 0 and report["execution"]["completed"] == 1
        elif mode == "saved-bench":
            result = await api.benchmark_plan(
                saved, candidate_index=indices[backend], model=wire.MODEL, runs=1, **args
            )
            report = result.to_dict()
            assert report["execution"]["successful_count"] == 1
        else:
            result = await api.replay_plan_trace(
                saved, rows, candidate_index=indices[backend], model=wire.MODEL, **args
            )
            report = result.to_dict()
            assert report["native_trace"]["execution"]["completed"] == 1
        assert all(row["authorized"] and row["client_certificate"] for row in calls)
        assert any(row["method"] == "POST" for row in calls)
        assert "FictionalActive82" not in json.dumps(report)
    assert saved.to_dict() == original


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["trace", "saved-trace", "saved-bench"])
@pytest.mark.parametrize("role", ["ca", "client", "client_key"])
async def test_secure_receipt_save_refuses_each_tls_input(active_plan, certs, mode, role):
    from chimeraforge import api
    from chimeraforge.bench.trace_workload import TraceRequest
    from test_ci_acceptance import load_script

    wire = load_script("ci_secure_active")
    saved, indices = active_plan
    before = {key: certs[key].read_bytes() for key in ("ca", "client", "client_key")}
    with wire.server(certs, backend="vllm", mtls=True) as (url, calls):
        connection = MonitorConnection(
            url, ca_bundle=certs["ca"], client_cert=certs["client"], client_key=certs["client_key"]
        )
        args = {"base_url": url, "connection": connection}
        rows = [TraceRequest("one", "fictional prompt", 4, 0)]
        if mode == "trace":
            receipt = await api.replay_trace(rows, model=wire.MODEL, backend="vllm", **args)
        elif mode == "saved-trace":
            receipt = await api.replay_plan_trace(
                saved, rows, candidate_index=indices["vllm"], model=wire.MODEL, **args
            )
        else:
            receipt = await api.benchmark_plan(
                saved, candidate_index=indices["vllm"], model=wire.MODEL, runs=1, **args
            )
        contacts = len(calls)
        with pytest.raises((api.PlanError, MonitorConnectionError)):
            receipt.save(certs[role])
        assert len(calls) == contacts
        assert all(certs[key].read_bytes() == value for key, value in before.items())


@pytest.mark.asyncio
async def test_secure_save_protects_effective_default_ca(active_plan, certs, monkeypatch):
    import certifi

    from chimeraforge import api
    from chimeraforge.bench.trace_workload import TraceRequest
    from test_ci_acceptance import load_script

    monkeypatch.setattr(certifi, "where", lambda: str(certs["ca"]))
    before = certs["ca"].read_bytes()
    wire = load_script("ci_secure_active")
    with wire.server(certs, backend="vllm") as (url, _):
        connection = MonitorConnection(url)
        receipt = await api.replay_trace(
            [TraceRequest("one", "fixture", 4, 0)],
            model=wire.MODEL,
            backend="vllm",
            base_url=url,
            connection=connection,
        )
        with pytest.raises((api.PlanError, MonitorConnectionError)):
            receipt.save(certs["ca"])
    assert certs["ca"].read_bytes() == before


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["vllm", "sglang"])
async def test_direct_secure_model_refusal_is_categorical(certs, backend):
    from test_ci_acceptance import load_script

    wire = load_script("ci_secure_active")
    with wire.server(certs, backend=backend) as (url, _):
        connection = MonitorConnection(url, ca_bundle=certs["ca"])
        adapter = backends.get_backend(backend, base_url=url, connection=connection)
        try:
            ok, message = await adapter.check_model("PrivateModelCanary82")
            assert not ok
            assert "PrivateModelCanary82" not in message and wire.MODEL not in message
        finally:
            await adapter.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["vllm", "sglang"])
async def test_secure_identity_exception_never_reaches_project_log(caplog, backend):
    import httpx

    from chimeraforge.bench.backends.sglang import SGLangBackend
    from chimeraforge.bench.backends.vllm import VLLMBackend

    def fail(request):
        raise httpx.ReadError("PrivateIdentityFailure82")

    connection = MonitorConnection("https://example.test")
    cls = VLLMBackend if backend == "vllm" else SGLangBackend
    adapter = cls(
        "https://example.test", connection=connection, transport=httpx.MockTransport(fail)
    )
    with caplog.at_level(logging.DEBUG, logger="chimeraforge"):
        try:
            assert await adapter.get_version() is None
        finally:
            await adapter.close()
    assert "PrivateIdentityFailure82" not in caplog.text


@pytest.mark.asyncio
async def test_original_fleet_active_owner_redacts_sdk_before_prior_factory(
    active_plan, certs, monkeypatch
):
    import json
    from chimeraforge import api
    from chimeraforge.bench.trace_workload import TraceRequest
    from test_ci_acceptance import load_script

    wire = load_script("ci_secure_active")
    saved, indices = active_plan
    previous = logging.getLogRecordFactory()
    seen = []
    token = "FictionalFleetOwner82"

    def factory(*args, **kwargs):
        if args[0] in {"httpx", "httpcore"} or args[0].startswith(("httpx.", "httpcore.")):
            seen.append((args[4:], kwargs))
        return previous(*args, **kwargs)

    for name in ("httpx", "httpcore"):
        monkeypatch.setattr(logging.getLogger(name), "level", logging.DEBUG)
    logging.setLogRecordFactory(factory)
    try:
        with wire.server(certs, backend="vllm", token=token, echo=token) as (url, calls):
            connection = MonitorConnection(url, ca_bundle=certs["ca"], bearer_token=token)
            receipt = await api.replay_fleet_trace(
                saved,
                [TraceRequest("one", "fixture", 4, 0)],
                (api.FleetEndpoint("member", url),),
                [api.TraceRoute("one", "member")],
                candidate_index=indices["vllm"],
                model=wire.MODEL,
                connections={"member": connection},
            )
            report = receipt.to_dict()
            assert (
                report["native_trace"]["execution"]["completed"] == 1
                and report["cleanup"]["state"] == "completed"
            ), report
            assert calls and all(row["authorized"] for row in calls)
        assert seen and token not in repr(seen) + json.dumps(report)
        assert logging.getLogRecordFactory() is factory
    finally:
        logging.setLogRecordFactory(previous)


def test_passive_fleet_owner_redacts_sdk_and_closes_both_transport_pools(
    native_fleet, certs, monkeypatch
):
    import asyncio
    import json
    from chimeraforge import api
    from test_fleet_monitor import request

    saved, indices = native_fleet
    previous = logging.getLogRecordFactory()
    native_response = BaseHTTPRequestHandler.send_response
    token = "FictionalPassiveFleet82"
    seen = []

    def echo(self, code, message=None):
        native_response(self, code, token)
        self.send_header("X-Fictional-Provider", token)

    def factory(*args, **kwargs):
        if args[0] in {"httpx", "httpcore"} or args[0].startswith(("httpx.", "httpcore.")):
            seen.append((args[4:], kwargs))
        return previous(*args, **kwargs)

    for name in ("httpx", "httpcore"):
        monkeypatch.setattr(logging.getLogger(name), "level", logging.DEBUG)
    monkeypatch.setattr(BaseHTTPRequestHandler, "send_response", echo)
    logging.setLogRecordFactory(factory)
    try:
        with fixture.server(certs, token=token) as (url, calls):
            connection = MonitorConnection(url, ca_bundle=certs["ca"], bearer_token=token)
            report = asyncio.run(
                api.monitor_fleet(
                    saved,
                    request([url + f"/r{i}/metrics" for i in range(1, 4)]),
                    candidate_index=indices["vllm"],
                    connections={f"replica-{i}": connection for i in range(1, 4)},
                )
            )
            assert (
                report.exit_code == 0
                and report.cleanup["closed_pools"] == report.cleanup["owned_pools"] == 6
            )
            assert calls and all(row["authorized"] for row in calls)
        assert seen and token not in repr(seen) + json.dumps(report.to_dict())
        assert logging.getLogRecordFactory() is factory
    finally:
        logging.setLogRecordFactory(previous)
