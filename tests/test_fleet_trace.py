"""Original fleet replay uses one population and retains every declared member."""

from __future__ import annotations

import asyncio
import copy
from dataclasses import asdict, replace
import json

import pytest

from chimeraforge import api
from chimeraforge.bench.backends.base import Backend, GenerationObservation
from chimeraforge.bench.trace_workload import TraceRequest
from chimeraforge.fleet_monitor_types import FleetEndpoint
from test_fleet_monitor import native_fleet as native_fleet


class Scene:
    def __init__(self, saved, index):
        self.saved, self.index = saved, index
        self.created = []
        self.active = self.peak = 0
        self.gate = None
        self.entered = asyncio.Event()
        self.preflight_failure = None
        self.observations = []

    def factory(self, name, *, base_url, **kwargs):
        node = Node(self, name, base_url)
        self.created.append(node)
        return node


class Node(Backend):
    def __init__(self, scene, name, url):
        self.scene, self.name, self.url = scene, name, url
        self.calls = []
        self.closed = False
        data = scene.saved.to_dict()
        selected = data["result"]["candidates"][scene.index]
        self.observed = {
            "backend": name,
            "execution_engine": name,
            "model": selected["model"],
            "quant": selected["quant"],
            "context_length": data["inputs"]["context_length"],
            "tensor_parallel": selected["tensor_parallel"],
            "pipeline_parallel": selected["pipeline_parallel"],
            "replicas": 1,
            "serving_data_parallel_size": 1,
            "model_spec": data["result"]["replay_context"]["model_specs"][selected["model"]],
            "hardware": data["result"]["replay_context"]["hardware"]["effective"],
            "version": "controlled-source",
            "device": "gpu",
            "source": "protocol fixture",
        }

    async def health_check(self):
        return self.scene.preflight_failure != self.url, "PRIVATE PREFLIGHT CANARY"

    async def check_model(self, model):
        return True, ""

    async def get_version(self):
        return "controlled-source"

    async def observe_serving(self, model):
        self.scene.observations.append(self.url)
        return copy.deepcopy(self.observed)

    async def generate(self, model, prompt, options=None):
        raise AssertionError("native observed capability must be used")

    async def generate_observed(self, model, prompt, options, on_first_output):
        self.scene.active += 1
        self.scene.peak = max(self.scene.peak, self.scene.active)
        self.scene.entered.set()
        self.calls.append((model, prompt, options))
        try:
            on_first_output()
            if self.scene.gate is not None:
                await self.scene.gate.wait()
            cap = options["max_tokens"]
            return GenerationObservation(
                {
                    "tokens_generated": cap,
                    "prompt_tokens": 512,
                    "eval_duration_ms": cap - 1,
                    "throughput_tps": 1000,
                    "ttft_basis": "client-stream-first-content",
                },
                1,
                "client-first-to-last-content/(server-output-count-1)",
            )
        finally:
            self.scene.active -= 1

    async def close(self):
        assert self.scene.active == 0
        self.closed = True


def workload(saved, index):
    cap = saved.to_dict()["result"]["candidates"][index]["decode_tokens_per_req"]
    return [TraceRequest(f"r{i}", f"PRIVATE PROMPT {i}", cap, 0) for i in range(6)]


def endpoints():
    return tuple(FleetEndpoint(f"member-{i}", f"http://member-{i}.invalid") for i in range(3))


def routes(requests, *, empty_last=False):
    return [
        api.TraceRoute(row.request_id, f"member-{i % (2 if empty_last else 3)}")
        for i, row in enumerate(requests)
    ]


@pytest.fixture
def scene(native_fleet, monkeypatch):
    saved, indices = native_fleet
    value = Scene(saved, indices["vllm"])
    from chimeraforge.bench import trace

    monkeypatch.setattr(trace, "get_backend", value.factory)
    return value


@pytest.mark.asyncio
async def test_one_original_population_and_member_scope(native_fleet, scene):
    saved, indices = native_fleet
    before = saved.to_dict()
    requests = workload(saved, indices["vllm"])
    report = (
        await api.replay_fleet_trace(
            saved,
            requests,
            endpoints(),
            routes(requests),
            candidate_index=indices["vllm"],
            concurrency=3,
        )
    ).to_dict()
    assert saved.to_dict() == before
    assert report["plan"]["snapshot"] == before
    assert len(report["slots"]) == 3
    assert report["native_trace"]["execution"]["planned"] == 6
    assert [row["endpoint_id"] for row in report["native_trace"]["requests"]] == [
        f"member-{i % 3}" for i in range(6)
    ]
    assert [slot["row_indices"] for slot in report["slots"]] == [[0, 3], [1, 4], [2, 5]]
    assert report["exit_code"] == 0 and all(node.closed for node in scene.created)
    assert all(slot["binding"]["summary"]["replicas"]["expected"] == 1 for slot in report["slots"])
    assert all(
        slot["binding"]["summary"]["serving_data_parallel_size"]["observed"] == 1
        for slot in report["slots"]
    )
    assert "PRIVATE" not in json.dumps(report)
    assert api.load_fleet_trace(report).to_dict() == report


@pytest.mark.asyncio
async def test_global_cross_member_queue_and_whole_before_barrier(native_fleet, scene):
    saved, indices = native_fleet
    requests = workload(saved, indices["vllm"])
    scene.gate = asyncio.Event()
    task = asyncio.create_task(
        api.replay_fleet_trace(
            saved,
            requests,
            endpoints(),
            routes(requests),
            candidate_index=indices["vllm"],
            concurrency=1,
        )
    )
    try:
        await asyncio.wait_for(scene.entered.wait(), 5)
        assert len(scene.created) == 3 and len(scene.observations) == 3
        assert sum(len(node.calls) for node in scene.created) == 1
        scene.gate.set()
        report = (await task).to_dict()
    finally:
        scene.gate.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert scene.peak == 1
    assert report["native_trace"]["requests"][1]["timing"]["client_queue_ms"] > 0


@pytest.mark.asyncio
async def test_failed_member_preflight_prevents_all_generation(native_fleet, scene):
    saved, indices = native_fleet
    requests = workload(saved, indices["vllm"])
    scene.preflight_failure = endpoints()[1].url
    report = (
        await api.replay_fleet_trace(
            saved, requests, endpoints(), routes(requests), candidate_index=indices["vllm"]
        )
    ).to_dict()
    assert not any(node.calls for node in scene.created)
    assert report["native_trace"]["execution"]["not_started"] == 6
    assert len(report["slots"]) == 3 and all(node.closed for node in scene.created)
    assert report["exit_code"] == 1


def test_declared_member_scope_does_not_change_original_n(native_fleet):
    from chimeraforge.bench.serving_binding import serving_binding

    saved, indices = native_fleet
    data = saved.to_dict()
    selected = data["result"]["candidates"][indices["vllm"]]
    observed = Node(Scene(saved, indices["vllm"]), "vllm", endpoints()[0].url).observed
    assert serving_binding(data, selected, observed, observed)["replicas"]["state"] == "mismatch"
    member = serving_binding(data, selected, observed, observed, replica_scope="declared_member")
    assert selected["n_agents"] == 3 and member["replicas"]["state"] == "matched"
    assert member["replicas"]["expected"] == 1
    assert member["replicas"]["scope"] == "declared_member"
    with pytest.raises(ValueError):
        serving_binding(data, selected, observed, observed, replica_scope="unbounded")


def test_empty_member_never_vacuously_matches_token_lengths_or_slos(native_fleet):
    from chimeraforge.bench import plan_trace

    saved, indices = native_fleet
    prepared = plan_trace._prepare(
        saved, workload(saved, indices["vllm"]), candidate_index=indices["vllm"]
    )
    empty = {
        "requests": [],
        "serving_before": None,
        "serving_after": None,
        "goodput": {"joint_outcomes": {"breach": 0, "unknown": 0, "not_completed": 0}},
    }
    bindings = plan_trace._bindings(prepared, empty)
    assert all(value["state"] == "unavailable" for value in bindings["token_lengths"].values())


def test_empty_member_requested_slo_is_unavailable_and_absent_targets_not_requested(native_fleet):
    from chimeraforge.bench import plan_trace
    from chimeraforge.bench.trace_workload import TraceSLO

    saved, indices = native_fleet
    prepared = plan_trace._prepare(
        saved, workload(saved, indices["vllm"]), candidate_index=indices["vllm"]
    )
    empty = {
        "requests": [],
        "goodput": {"joint_outcomes": {"breach": 0, "unknown": 0, "not_completed": 0}},
    }
    assert (
        plan_trace._slo(replace(prepared, slos=TraceSLO()), empty, complete=True)["state"]
        == "not_requested"
    )
    assert any(value is not None for value in asdict(prepared.slos).values())
    assert plan_trace._slo(prepared, empty, complete=True)["state"] == "unavailable"
