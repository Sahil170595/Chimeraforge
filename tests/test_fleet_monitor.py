"""A declared native fleet is observed passively, with aggregate bounded work."""

from __future__ import annotations

import asyncio
import json
import threading
from contextlib import contextmanager
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from chimeraforge import api
from test_monitor_slo import pair

MODEL = "ci/manual-fleet"


@pytest.fixture
def native_fleet():
    saved = api.plan(
        api.PlanRequest(
            models=[MODEL],
            overrides={"params_b": 3.0, "n_layers": 28, "n_kv_heads": 8, "d_head": 128},
            hardware="RTX 4090 24GB",
            platform="linux",
            tensor_parallel=2,
            request_rate=128,
            latency_slo=10000,
            quality_target=0,
            budget=1e8,
            allow_network=False,
        )
    )
    indices = {
        row["backend"]: i
        for i, row in enumerate(saved.to_dict()["result"]["candidates"])
        if row["backend"] in ("vllm", "sglang")
        and row["quant"] == "FP16"
        and row["n_agents"] == 3
        and row["gpus_total"] == 6
    }
    assert set(indices) == {"vllm", "sglang"}
    return saved, indices


@contextmanager
def fleet_server(
    *,
    backend="vllm",
    broken=None,
    quant=None,
    missing_identity=False,
    ttft=0.05,
    no_traffic=False,
    fail_after=1,
    fallback=False,
    native_mode=None,
):
    """Three paths represent declared endpoints, not authenticated separate engines."""
    counts = {}
    calls = []
    first, second = (text.replace("org/model", MODEL) for text in pair(backend, ttft=ttft))
    if native_mode == "missing":
        second = "# no matching histograms\n"
    elif native_mode == "reset":
        first, second = second, first

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(self.path)
            prefix, _, route = self.path[1:].partition("/")
            if route == "metrics":
                count = counts.get(prefix, 0)
                counts[prefix] = count + 1
                if broken == prefix and count >= fail_after:
                    self.send_error(503)
                    return
                body = (first if count == 0 or no_traffic else second).encode()
                content_type = "text/plain"
            else:
                if fallback and route == "server_info":
                    self.send_error(503)
                    return
                if route == "version":
                    absent = (
                        missing_identity is True
                        or missing_identity == "first"
                        and counts.get(prefix, 0) <= 1
                    )
                    data = {} if absent else {"version": "0.30.0"}
                elif route == "v1/models":
                    absent = (
                        missing_identity is True
                        or missing_identity == "first"
                        and counts.get(prefix, 0) <= 1
                    )
                    data = {"data": [] if absent else [{"id": MODEL}]}
                elif route.startswith("server_info") or route == "get_server_info":
                    data = {
                        "version": "0.5.20",
                        "served_model_name": MODEL,
                        "dtype": "float16",
                        "tp_size": 2,
                        "pp_size": 1,
                    }
                    if backend == "vllm":
                        data = {
                            "vllm_config": {
                                "model_config": {
                                    "dtype": quant or "torch.float16",
                                    "max_model_len": 2048,
                                },
                                "parallel_config": {
                                    "tensor_parallel_size": 2,
                                    "pipeline_parallel_size": 1,
                                    "data_parallel_size": 1,
                                },
                            }
                        }
                elif route == "model_info":
                    data = {"served_model_name": MODEL}
                else:
                    self.send_error(404)
                    return
                body = json.dumps(data).encode()
                content_type = "application/json"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    worker.start()
    try:
        yield [f"http://127.0.0.1:{server.server_port}/r{i}/metrics" for i in range(3)], calls
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
        assert not worker.is_alive()


def request(urls, **kwargs):
    from chimeraforge.fleet_monitor import FleetEndpoint, FleetMonitorRequest

    return FleetMonitorRequest(
        tuple(FleetEndpoint(f"replica-{i + 1}", url) for i, url in enumerate(urls)),
        interval=0.01,
        timeout=1,
        observation_seconds=3,
        cleanup_seconds=1,
        ttft_slo=500,
        **kwargs,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["vllm", "sglang"])
async def test_native_three_replica_fleet_all_slots_and_native_windows(native_fleet, backend):
    saved, indices = native_fleet
    original = saved.to_dict()
    with fleet_server(backend=backend) as (urls, calls):
        result = await api.monitor_fleet(saved, request(urls), candidate_index=indices[backend])
    data = result.to_dict()
    assert result.exit_code == 0, data
    assert data["declared_coverage"] == {"expected": 3, "complete": 3, "state": "complete"}
    assert [slot["id"] for slot in data["slots"]] == ["replica-1", "replica-2", "replica-3"]
    assert all(slot["state"] == "complete" and slot["slo"] == "pass" for slot in data["slots"])
    assert all(
        len(slot["windows"]) == 1 and len(slot["observations"]) == 2 for slot in data["slots"]
    )
    assert all(slot["binding"]["identity"]["state"] == "matched" for slot in data["slots"])
    assert all(
        slot["binding"]["configuration"]["fields"]["replicas"]["expected"] == 3
        for slot in data["slots"]
    )
    assert all(
        slot["binding"]["configuration"]["fields"]["serving_data_parallel_size"]["observed"]
        in (1, None)
        for slot in data["slots"]
    )
    assert data["cleanup"]["state"] == "completed" and len(calls) >= 18
    assert saved.to_dict() == original


@pytest.mark.asyncio
async def test_precancel_retains_population_and_contacts_nothing(native_fleet):
    saved, indices = native_fleet
    stop = asyncio.Event()
    stop.set()
    with fleet_server() as (urls, calls):
        result = await api.monitor_fleet(
            saved, request(urls), candidate_index=indices["vllm"], stop_event=stop
        )
    assert not calls and result.exit_code == 4
    assert [row["state"] for row in result.to_dict()["slots"]] == ["unstarted"] * 3


@pytest.mark.asyncio
@pytest.mark.parametrize("cap", [1, 8, 15])
async def test_global_attempt_cap_counts_across_endpoints_and_stays_nonpass(native_fleet, cap):
    saved, indices = native_fleet
    with fleet_server() as (urls, calls):
        result = await api.monitor_fleet(
            saved, request(urls, max_requests=cap), candidate_index=indices["vllm"]
        )
    data = result.to_dict()
    assert result.exit_code == 4 and data["budget"]["termination"] == "request_limit"
    assert data["budget"]["requests"] == cap and len(calls) <= cap
    assert len(data["slots"]) == 3 and data["cleanup"]["state"] == "completed"
    if cap == 1:
        assert sum(slot["state"] == "unstarted" for slot in data["slots"]) >= 1


@pytest.mark.asyncio
async def test_complete_exact_request_cap_may_pass(native_fleet):
    saved, indices = native_fleet
    with fleet_server() as (urls, calls):
        result = await api.monitor_fleet(
            saved, request(urls, max_requests=24), candidate_index=indices["vllm"]
        )
    assert result.exit_code == 0 and len(calls) == 24
    assert result.to_dict()["budget"]["termination"] is None


@pytest.mark.asyncio
async def test_later_transport_failure_preserves_observation_prefix(native_fleet):
    saved, indices = native_fleet
    with fleet_server(broken="r0", quant="Q8_0") as (urls, calls):
        result = await api.monitor_fleet(saved, request(urls), candidate_index=indices["vllm"])
    data = result.to_dict()
    assert len(data["slots"]) == 3
    slot = data["slots"][0]
    assert slot["state"] == "error" and len(slot["observations"]) == 1 and not slot["windows"]
    assert slot["binding"]["configuration"]["state"] == "mismatch" and result.exit_code == 5
    assert data["cleanup"]["state"] == "completed"


@pytest.mark.asyncio
@pytest.mark.parametrize("condition", ["no_traffic", "missing_identity"])
async def test_unknown_native_or_required_identity_cannot_pass(native_fleet, condition):
    saved, indices = native_fleet
    with fleet_server(**{condition: True}) as (urls, calls):
        result = await api.monitor_fleet(saved, request(urls), candidate_index=indices["vllm"])
    assert result.exit_code == 4


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        "population",
        "duplicate-id",
        "url-alias",
        "query",
        "fragment",
        "credentials",
        "custom-path",
        "nonfinite",
        "bool-count",
        "workcap",
    ],
)
async def test_invalid_shape_and_transport_aliases_refused_before_contact(native_fleet, change):
    from chimeraforge.fleet_monitor import FleetEndpoint, FleetMonitorError

    saved, indices = native_fleet
    with fleet_server() as (urls, calls):
        value = request(urls)
        endpoints = list(value.endpoints)
        if change == "population":
            endpoints.pop()
        elif change == "duplicate-id":
            endpoints[1] = replace(endpoints[1], id=endpoints[0].id)
        elif change == "url-alias":
            endpoints[1] = replace(endpoints[1], url=urls[0].removesuffix("/metrics"))
        elif change in ("query", "fragment", "credentials", "custom-path"):
            suffix = {
                "query": "?secret=x",
                "fragment": "#x",
                "credentials": "",
                "custom-path": "/custom",
            }[change]
            altered = urls[0] + suffix
            if change == "credentials":
                altered = urls[0].replace("http://", "http://private:secret@")
            endpoints[0] = FleetEndpoint(endpoints[0].id, altered)
        elif change == "nonfinite":
            value = replace(value, observation_seconds=float("nan"))
        elif change == "bool-count":
            value = replace(value, concurrency=True)
        elif change == "workcap":
            value = replace(value, windows=86)
        value = replace(value, endpoints=tuple(endpoints))
        with pytest.raises(FleetMonitorError):
            await api.monitor_fleet(saved, value, candidate_index=indices["vllm"])
        assert not calls


@pytest.mark.asyncio
async def test_short_positive_deadline_returns_all_partial_slots(native_fleet):
    saved, indices = native_fleet
    with fleet_server() as (urls, calls):
        value = replace(request(urls), observation_seconds=0.001, interval=1)
        result = await api.monitor_fleet(saved, value, candidate_index=indices["vllm"])
    assert result.exit_code == 4 and len(result.to_dict()["slots"]) == 3
    assert result.to_dict()["budget"]["termination"] == "observation_deadline"


@pytest.mark.asyncio
async def test_prometheus_has_one_family_header_and_per_slot_labels(native_fleet):
    from chimeraforge.fleet_monitor import prometheus_text

    saved, indices = native_fleet
    with fleet_server() as (urls, calls):
        result = await api.monitor_fleet(saved, request(urls), candidate_index=indices["vllm"])
    text = prometheus_text(result)
    headers = [line for line in text.splitlines() if line.startswith("# TYPE")]
    assert len(headers) == len(set(headers)) and 'replica="replica-1"' in text
    assert 'replica="replica-3"' in text and "fleet" in text


def test_cli_output_alias_refuses_before_network(native_fleet, tmp_path):
    from chimeraforge.cli import app
    from typer.testing import CliRunner

    saved, indices = native_fleet
    source = tmp_path / "plan.json"
    saved.save(source)
    original = source.read_bytes()
    with fleet_server() as (urls, calls):
        args = [
            "monitor-fleet",
            "--from-plan",
            str(source),
            "--candidate-index",
            str(indices["vllm"]),
            "--ttft-slo",
            "500",
            "--prometheus",
            str(source),
        ]
        for i, url in enumerate(urls):
            args += ["--endpoint", f"r{i}={url}"]
        result = CliRunner().invoke(app, args)
    assert result.exit_code == 1 and not calls and source.read_bytes() == original


@pytest.mark.asyncio
async def test_invalid_stop_object_is_refused_before_resource_creation(native_fleet, monkeypatch):
    from chimeraforge.fleet_monitor import FleetMonitorError, OwnedPool

    saved, indices = native_fleet

    def fail(*args):
        pytest.fail("resources allocated before stop-event admission")

    monkeypatch.setattr(OwnedPool, "__init__", fail)
    with pytest.raises(FleetMonitorError):
        await api.monitor_fleet(
            saved,
            request(["http://one", "http://two", "http://three"]),
            candidate_index=indices["vllm"],
            stop_event=True,
        )


def test_prometheus_family_rename_never_rewrites_native_labels():
    from chimeraforge.fleet_monitor import prometheus_text
    from chimeraforge.fleet_monitor_types import FleetMonitorReport, FleetSlot

    slot = FleetSlot(
        "replica-1",
        "http://one",
        binding={
            "plan": {"fingerprint": "a", "candidate_index": 1},
            "identity": {"state": "matched"},
            "configuration": {"state": "unverified"},
        },
    )
    model = 'org/chimeraforge_monitor_model\\\\quote"'
    report = FleetMonitorReport(
        "vllm", model, (slot,), {}, {}, {"termination": None}, {"state": "completed"}, False, "test"
    )
    text = prometheus_text(report)
    assert 'model="org/chimeraforge_monitor_model' in text
    assert 'model="org/chimeraforge_fleet_slot_model' not in text


@pytest.mark.asyncio
async def test_earlier_breach_survives_later_failed_window(native_fleet):
    saved, indices = native_fleet
    with fleet_server(broken="r0", fail_after=2, ttft=0.7) as (urls, calls):
        result = await api.monitor_fleet(
            saved, request(urls, windows=2), candidate_index=indices["vllm"]
        )
    assert result.exit_code == 3 and result.slots[0].state == "error"
    assert len(result.slots[0].windows) == 1 and result.slots[0].slo == "breach"


@pytest.mark.asyncio
async def test_later_matched_identity_does_not_repair_missing_boundary(native_fleet):
    saved, indices = native_fleet
    with fleet_server(missing_identity="first") as (urls, calls):
        result = await api.monitor_fleet(saved, request(urls), candidate_index=indices["vllm"])
    assert result.exit_code == 4
    assert all(slot.binding["identity"]["state"] == "unavailable" for slot in result.slots)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "left,right",
    [
        ("HTTP://EXAMPLE.COM:80/", "http://example.com/metrics"),
        ("http://example.com/x/../metrics", "http://example.com/metrics"),
        ("http://b\u00fccher.example/", "http://xn--bcher-kva.example/metrics"),
    ],
)
async def test_httpx_canonical_url_aliases_are_refused_before_contact(native_fleet, left, right):
    from chimeraforge.fleet_monitor import FleetMonitorError

    saved, indices = native_fleet
    with pytest.raises(FleetMonitorError, match="distinct"):
        await api.monitor_fleet(
            saved, request([left, right, "http://third"]), candidate_index=indices["vllm"]
        )


@pytest.mark.asyncio
async def test_huge_integer_control_is_sanitized_no_contact(native_fleet):
    from chimeraforge.fleet_monitor import FleetMonitorError

    saved, indices = native_fleet
    value = replace(
        request(["http://one", "http://two", "http://three"]), observation_seconds=10**1000
    )
    with pytest.raises(FleetMonitorError):
        await api.monitor_fleet(saved, value, candidate_index=indices["vllm"])


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["missing", "reset"])
async def test_native_missing_histograms_and_resets_never_pass_fleet(native_fleet, mode):
    saved, indices = native_fleet
    with fleet_server(native_mode=mode) as (urls, calls):
        report = await api.monitor_fleet(saved, request(urls), candidate_index=indices["vllm"])
    assert report.exit_code == 4 and all(slot.slo == "unknown" for slot in report.slots)
    assert all(len(slot.windows) == 1 for slot in report.slots)


@pytest.mark.asyncio
async def test_native_sglang_failed_route_and_fallback_both_count(native_fleet):
    saved, indices = native_fleet
    with fleet_server(backend="sglang", fallback=True) as (urls, calls):
        report = await api.monitor_fleet(
            saved, request(urls, max_requests=24), candidate_index=indices["sglang"]
        )
    assert report.exit_code == 0 and report.budget["requests"] == len(calls) == 24
    assert len([value for value in calls if value.endswith("/get_server_info")]) == 6
