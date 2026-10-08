"""A real run receipt is distinct from qualification of the modeled deployment."""

import asyncio
import copy
from dataclasses import asdict
import hashlib
import json

import pytest

from chimeraforge.api import PlanRequest, plan
from chimeraforge.bench.backends.base import Backend
from chimeraforge.bench.metrics import RunMetrics


def saved_plan():
    return plan(PlanRequest(allow_network=False, budget=100000, avg_tokens=4, prompt_tokens=8))


class ObservedBackend(Backend):
    name = "ollama"

    def __init__(self, saved, *, fail_one=False, device="cpu", quant=None):
        self.saved = saved
        self.options = []
        self.closed = False
        self.fail_one = fail_one
        self.device = device
        self.quant = quant or saved.candidate().quant

    async def health_check(self):
        return True, "Ollama is running"

    async def check_model(self, model):
        return True, ""

    async def get_version(self):
        return "0.35.1"

    async def observe_serving(self, model):
        return {
            "backend": "ollama",
            "version": "0.35.1",
            "model": model,
            "quant": self.quant,
            "model_digest": "a" * 64,
            "context_length": self.saved.to_dict()["inputs"]["context_length"],
            "device": self.device,
            "tensor_parallel": None,
            "pipeline_parallel": None,
            "replicas": None,
            "hardware": None,
            "prefix_cache": None,
            "model_spec": None,
            "source": "observed serving API",
        }

    async def generate(self, model, prompt, options=None):
        self.options.append(copy.deepcopy(options))
        if self.fail_one and len(self.options) == 1:
            raise RuntimeError("one request failed")
        return RunMetrics(
            4, 40.0, 2.0, 102.0, 2.0, 100.0, prompt_tokens=8, ttft_basis="server-prefill-duration"
        )

    async def close(self):
        self.closed = True


def execute(saved, backend, monkeypatch, **options):
    from chimeraforge.api import benchmark_plan
    from chimeraforge.bench import runner

    monkeypatch.setattr(runner, "get_backend", lambda *args, **kwargs: backend)
    return asyncio.run(
        benchmark_plan(
            saved,
            model=saved.candidate().model,
            workload="single",
            runs=3,
            prompt="Observed prompt",
            **options,
        )
    ).to_dict()


def test_selected_plan_benchmark_uses_runner_applied_workload_and_preserves_plan(monkeypatch):
    saved = saved_plan()
    before = saved.to_dict()
    backend = ObservedBackend(saved)
    report = execute(saved, backend, monkeypatch)
    assert saved.to_dict() == before and backend.closed
    assert report["plan"]["fingerprint"] == before["fingerprint"]
    assert report["plan"]["candidate_index"] == 0
    assert (
        report["execution"]["request"]["prompt_sha256"]
        == hashlib.sha256(b"Observed prompt").hexdigest()
    )
    assert report["execution"]["request"]["requested_count"] == 3
    assert report["execution"]["request"]["concurrency"] == 1
    assert backend.options and all(o["num_predict"] == 4 for o in backend.options)
    assert all(o["num_ctx"] == before["inputs"]["context_length"] for o in backend.options)
    assert report["measurement"]["aggregate"]["count"] == 3
    assert report["audit"]["metrics"]["base_decode_tps"]["unit"] == "tokens/second"
    assert report["audit"]["metrics"]["base_decode_tps"]["measured"] == 40


def test_client_gpu_and_quant_labels_do_not_verify_remote_configuration(monkeypatch):
    saved = saved_plan()
    report = execute(saved, ObservedBackend(saved), monkeypatch)
    assert report["binding"]["hardware"]["state"] == "mismatch"
    assert report["binding"]["tensor_parallel"]["state"] == "unavailable"
    assert report["binding"]["pipeline_parallel"]["state"] == "unavailable"
    assert report["binding"]["backend"]["state"] == "matched"
    assert report["binding"]["execution_engine"]["state"] == "unavailable"
    assert report["audit"]["metrics"]["base_decode_tps"]["delta"] is None
    assert report["audit"]["selected_configuration"]["state"] == "unverified"
    assert report["audit"]["slo"]["state"] == "unverified"


def test_observed_quant_mismatch_is_distinct_from_measured_rate(monkeypatch):
    saved = saved_plan()
    report = execute(saved, ObservedBackend(saved, quant="FP16"), monkeypatch)
    assert report["binding"]["quant"]["state"] == "mismatch"
    assert report["measurement"]["aggregate"]["count"] == 3
    assert report["audit"]["metrics"]["base_decode_tps"]["delta"] is None


def test_partial_runs_never_become_slo_success(monkeypatch):
    saved = saved_plan()
    report = execute(saved, ObservedBackend(saved, fail_one=True), monkeypatch)
    assert report["status"] == "partial"
    assert report["execution"]["requested_count"] == 3
    assert report["execution"]["successful_count"] == 2
    assert report["execution"]["failed_count"] == 1
    assert report["audit"]["slo"]["state"] == "unverified"
    assert report["exit_code"] == 1


def test_no_feasible_candidate_is_rejected_before_requests(monkeypatch):
    from chimeraforge.api import PlanError, benchmark_plan
    from chimeraforge.bench import runner

    saved = plan(PlanRequest(quality_target=1, budget=0, allow_network=False))
    monkeypatch.setattr(
        runner,
        "get_backend",
        lambda *args, **kwargs: pytest.fail("invalid selection must not contact a server"),
    )
    with pytest.raises(PlanError):
        asyncio.run(benchmark_plan(saved))


def test_model_digest_change_during_run_is_not_comparable(monkeypatch):
    saved = saved_plan()
    backend = ObservedBackend(saved)
    original = backend.observe_serving

    async def observe(model):
        data = await original(model)
        if backend.options:
            data["model_digest"] = "b" * 64
        return data

    backend.observe_serving = observe
    report = execute(saved, backend, monkeypatch)
    assert report["binding"]["serving_stability"]["state"] == "mismatch"
    assert report["audit"]["metrics"]["base_decode_tps"]["delta"] is None


def test_known_runtime_context_change_during_run_is_mismatch(monkeypatch):
    saved = saved_plan()
    backend = ObservedBackend(saved)
    original = backend.observe_serving

    async def observe(model):
        data = await original(model)
        if not backend.options:
            data["context_length"] *= 2
        return data

    backend.observe_serving = observe
    report = execute(saved, backend, monkeypatch)
    assert report["binding"]["context_length"]["state"] == "matched"
    assert report["binding"]["serving_stability"]["state"] == "mismatch"
    assert report["audit"]["metrics"]["base_decode_tps"]["delta"] is None


def test_lazy_loading_before_unknown_after_known_is_unverified(monkeypatch):
    saved = saved_plan()
    backend = ObservedBackend(saved, device="gpu")
    original = backend.observe_serving

    async def observe(model):
        data = await original(model)
        if not backend.options:
            data["context_length"] = None
        return data

    backend.observe_serving = observe
    report = execute(saved, backend, monkeypatch)
    assert report["binding"]["serving_stability"]["state"] == "unavailable"
    assert report["exit_code"] == 0


@pytest.mark.parametrize(
    "options",
    [
        {"model": 2},
        {"backend": ""},
        {"runs": True},
        {"runs": 1001},
        {"concurrency": 2},
        {"rate": 1},
        {"prompt": ""},
        {"rate": float("nan")},
    ],
)
def test_invalid_execution_settings_are_rejected_before_contact(monkeypatch, options):
    from chimeraforge.api import PlanError, benchmark_plan
    from chimeraforge.bench import runner

    monkeypatch.setattr(
        runner, "get_backend", lambda *a, **k: pytest.fail("invalid settings contacted server")
    )
    with pytest.raises(PlanError):
        asyncio.run(benchmark_plan(saved_plan(), **options))


def test_endpoint_credentials_in_partial_warning_are_redacted(monkeypatch):
    saved = saved_plan()
    backend = ObservedBackend(saved)
    original = backend.generate

    async def generate(*args, **kwargs):
        if not backend.options:
            backend.options.append({})
            raise RuntimeError(
                "failed https://user:password@serving/generate?token=private-token#secret"
            )
        return await original(*args, **kwargs)

    backend.generate = generate
    report = execute(saved, backend, monkeypatch)
    encoded = json.dumps(report)
    assert report["status"] == "partial" and "https://serving/generate" in encoded
    assert "password" not in encoded and "private-token" not in encoded and "#secret" not in encoded


def test_single_profile_receipt_has_no_applied_arrival_rate(monkeypatch):
    saved = saved_plan()
    report = execute(saved, ObservedBackend(saved), monkeypatch)
    assert report["execution"]["request"]["arrival_rate"] is None


def test_fully_observed_equivalent_base_decode_delta_does_not_qualify_fleet(monkeypatch):
    saved = saved_plan()
    backend = ObservedBackend(saved, device="gpu")
    original = backend.observe_serving
    context = saved.to_dict()["result"]["replay_context"]

    async def observe(model):
        data = await original(model)
        data.update(
            tensor_parallel=1,
            pipeline_parallel=1,
            replicas=saved.candidate().n_agents,
            hardware=context["hardware"]["effective"],
            model_spec=context["model_specs"][model],
            prefix_cache=False,
        )
        return data

    backend.observe_serving = observe
    report = execute(saved, backend, monkeypatch)
    metric = report["audit"]["metrics"]["base_decode_tps"]
    assert metric["state"] == "comparable" and metric["blocking_facts"] == []
    assert metric["delta"] == pytest.approx(40 - saved.candidate().throughput_tps)
    assert report["audit"]["weights"]["state"] == "unverified"
    assert report["audit"]["metrics"]["fleet_tps"]["state"] == "unverified"
    assert report["audit"]["slo"]["state"] == "unverified"


@pytest.mark.parametrize("modifier", ["lora", "offload"])
def test_modified_saved_decode_requires_real_modifier_binding(monkeypatch, modifier):
    from chimeraforge.api import benchmark_plan
    from chimeraforge.bench import runner

    options = (
        {"lora_adapters": 1, "lora_rank": 64}
        if modifier == "lora"
        else {"allow_offload": True, "gpu_overrides": {"vram_gb": 2.0, "bandwidth_gbps": 432.0}}
    )
    saved = plan(
        PlanRequest(
            models=["llama3.2-3b"],
            allow_network=False,
            quality_target=0,
            budget=100000,
            avg_tokens=4,
            prompt_tokens=8,
            overrides={
                "params_b": 3.21,
                "n_layers": 28,
                "n_kv_heads": 8,
                "d_head": 128,
                "hidden_size": 3072,
            },
            **options,
        )
    )
    candidates = saved.to_dict()["result"]["candidates"]
    selected = next(
        i
        for i, row in enumerate(candidates)
        if row["backend"] == "ollama"
        and (row["lora_adapters"] > 0 if modifier == "lora" else row["offload_fraction"] > 0)
    )
    candidate = saved.candidate(selected)
    backend = ObservedBackend(saved, device="gpu", quant=candidate.quant)
    original = backend.observe_serving
    context = saved.to_dict()["result"]["replay_context"]

    async def observe(model):
        data = await original(model)
        data.update(
            tensor_parallel=1,
            pipeline_parallel=1,
            replicas=candidate.n_agents,
            hardware=context["hardware"]["effective"],
            model_spec=context["model_specs"][model],
            prefix_cache=False,
        )
        return data

    backend.observe_serving = observe
    monkeypatch.setattr(runner, "get_backend", lambda *a, **k: backend)
    report = asyncio.run(benchmark_plan(saved, candidate_index=selected, runs=3)).to_dict()
    metric = report["audit"]["metrics"]["base_decode_tps"]
    assert metric["state"] == "unverified" and metric["delta"] is None
    assert any(modifier in reason.lower() for reason in metric["blocking_facts"])
    assert report["binding"]["scenario_modifiers"]["state"] == "unavailable"


def test_known_sglang_weight_version_change_is_mismatch_without_digest_claim(monkeypatch):
    saved = saved_plan()
    backend = ObservedBackend(saved, device="gpu")
    original = backend.observe_serving

    async def observe(model):
        data = await original(model)
        data["weight_version_label"] = "new" if backend.options else "old"
        return data

    backend.observe_serving = observe
    report = execute(saved, backend, monkeypatch)
    stability = report["binding"]["serving_stability"]
    assert stability["state"] == "mismatch"
    assert "weight_version_label" in stability["detail"]["changed_fields"]
    assert report["audit"]["weights"]["state"] == "unverified" and report["exit_code"] == 1


def test_metadata_failure_keeps_real_measurement_and_closes_backend(monkeypatch):
    saved = saved_plan()
    backend = ObservedBackend(saved, device="gpu")

    async def observe(model):
        raise RuntimeError("metadata refused")

    backend.observe_serving = observe
    report = execute(saved, backend, monkeypatch)
    assert report["execution"]["successful_count"] == 3 and backend.closed
    assert report["binding"]["quant"]["state"] == "unavailable"
    assert report["execution"]["serving_after"]["limitations"] == ["RuntimeError"]


def test_cancellation_during_serving_observation_closes_backend(monkeypatch):
    saved = saved_plan()
    backend = ObservedBackend(saved)

    async def observe(model):
        raise asyncio.CancelledError()

    backend.observe_serving = observe
    with pytest.raises(asyncio.CancelledError):
        execute(saved, backend, monkeypatch)
    assert backend.closed and not backend.options


def test_server_and_batch_receipts_describe_applied_profile(monkeypatch):
    from chimeraforge.api import benchmark_plan
    from chimeraforge.bench import runner

    saved = saved_plan()
    monkeypatch.setattr(runner.random, "expovariate", lambda rate: 0)
    for profile in ("server", "batch"):
        backend = ObservedBackend(saved, device="gpu")
        monkeypatch.setattr(runner, "get_backend", lambda *a, **k: backend)
        options = {"rate": 7} if profile == "server" else {}
        report = asyncio.run(
            benchmark_plan(saved, workload=profile, concurrency=2, runs=3, **options)
        ).to_dict()
        request = report["execution"]["request"]
        assert request["concurrency"] == 2 and request["workload"] == profile
        assert request["arrival_rate"] == (7 if profile == "server" else None)
        assert report["execution"]["successful_count"] == 3 and backend.closed
        assert "single-stream workload" in " ".join(
            report["audit"]["metrics"]["base_decode_tps"]["blocking_facts"]
        )


def test_saved_plan_benchmark_cli_missing_artifact_is_json_error(tmp_path):
    from typer.testing import CliRunner
    from chimeraforge.cli import app

    result = CliRunner().invoke(app, ["bench", "--plan", str(tmp_path / "missing.json"), "--json"])
    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"]
