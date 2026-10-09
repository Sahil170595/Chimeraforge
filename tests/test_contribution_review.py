"""Unsigned contribution decisions and actual runner replay preserve evidence limits."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
from typing import get_type_hints

import pytest
from typer.testing import CliRunner

from chimeraforge.bench.backends.base import Backend
from chimeraforge.bench.metrics import (
    BenchmarkResult,
    EnvironmentInfo,
    RunMetrics,
    aggregate_runs,
    result_to_dict,
)
from chimeraforge.cli import app
from chimeraforge.contrib import (
    ContribError,
    build_contribution,
    import_contribution,
    load_quarantine,
)


@pytest.fixture
def legacy(tmp_path, monkeypatch):
    monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path / "cache"))
    samples = [RunMetrics(4, 100.0, 4.0, 44.0, 4.0, 40.0) for _ in range(3)]
    result = BenchmarkResult(
        "llama3.2-3b",
        "ollama",
        "Q4_K_M",
        "single",
        3,
        2048,
        samples,
        aggregate_runs(samples),
        EnvironmentInfo(
            "Linux",
            "Linux-test",
            "3.12",
            "0.46.0",
            "NVIDIA GeForce RTX 4090",
            "570",
            "12.8",
            "ollama",
            "0.35.1",
            24,
        ),
        "2026-10-01T12:00:00+00:00",
    )
    contribution = build_contribution(result_to_dict(result))
    path = tmp_path / "unsigned-legacy.contribution.json"
    path.write_text(json.dumps(contribution), encoding="utf-8")
    return contribution, path


class ReplayBackend(Backend):
    name = "ollama"

    def __init__(self, *, fail=0, quant="Q4_K_M", model="llama3.2-3b", device="cpu"):
        self.calls = []
        self.closed = False
        self.fail = fail
        self.quant, self.model, self.device = quant, model, device

    async def health_check(self):
        return True, ""

    async def check_model(self, model):
        return True, ""

    async def get_version(self):
        return "0.35.1"

    async def observe_serving(self, model):
        return {
            "backend": self.name,
            "version": "0.35.1",
            "model": self.model,
            "quant": self.quant,
            "context_length": 2048,
            "device": self.device,
            "model_digest": "a" * 64,
            "source": "serving metadata",
            "loaded_gpu_bytes": 0 if self.device == "cpu" else None,
        }

    async def generate(self, model, prompt, options=None):
        self.calls.append((model, prompt, copy.deepcopy(options)))
        if len(self.calls) <= self.fail:
            raise RuntimeError("request failed at http://user:secret@localhost:9999/?token=private")
        return RunMetrics(
            4, 40.0, 2.0, 102.0, 2.0, 100.0, prompt_tokens=8, ttft_basis="server-prefill-duration"
        )

    async def close(self):
        self.closed = True


def execute(source, backend, monkeypatch, **options):
    from chimeraforge.api import replay_contribution
    from chimeraforge.bench import runner

    monkeypatch.setattr(runner, "get_backend", lambda *args, **kwargs: backend)
    return asyncio.run(
        replay_contribution(source, prompt="Replay prompt", output_tokens=4, runs=3, **options)
    )


def test_review_keeps_original_id_quarantine_and_unsigned_disposition(legacy):
    from chimeraforge.api import review_contribution

    contribution, path = legacy
    original = path.read_bytes()
    import_contribution(path)
    before = load_quarantine()
    report = review_contribution(path, decision="retain", reason="Keep for a controlled replay")
    data = report.to_dict()
    assert data["contribution"]["id"] == contribution["id"]
    assert data["contribution"]["quarantine_state"] == "present"
    assert data["contribution"]["attestation"]["signed"] is False
    assert (
        data["decision"]["disposition"] == "retain"
        and data["decision"]["changes_quarantine"] is False
    )
    assert data["replay_equivalence"]["state"] == "unverified"
    assert {"original_prompt", "serving_configuration", "remote_hardware"} <= set(
        data["replay_equivalence"]["missing"]
    )
    assert report.exit_code == 0
    assert path.read_bytes() == original and load_quarantine() == before
    data["contribution"]["fingerprint"]["model"] = "mutated"
    assert (
        report.to_dict()["contribution"]["fingerprint"]["model"]
        == contribution["fingerprint"]["model"]
    )


def test_review_quarantine_id_and_saved_receipt_are_useful_without_trust_change(legacy, tmp_path):
    from chimeraforge.api import review_contribution

    contribution, path = legacy
    import_contribution(path)
    report = review_contribution(
        contribution["id"], decision="reject", reason="Original prompt unavailable"
    )
    out = tmp_path / "review.json"
    report.save(out)
    assert json.loads(out.read_text()) == report.to_dict()
    assert load_quarantine()[0]["id"] == contribution["id"]
    with pytest.raises(ContribError, match="overwrite|quarantine"):
        report.save(path)


@pytest.mark.parametrize(
    "options", [{"decision": "trusted"}, {"decision": "retain"}, {"reason": 5}]
)
def test_invalid_review_dispositions_cannot_claim_trust(legacy, options):
    from chimeraforge.api import review_contribution

    with pytest.raises(ContribError):
        review_contribution(legacy[0], **options)


def test_live_replay_uses_runner_receipts_native_deltas_and_cpu_ineligibility(legacy, monkeypatch):
    contribution, path = legacy
    original = path.read_bytes()
    backend = ReplayBackend()
    report = execute(path, backend, monkeypatch)
    data = report.to_dict()
    assert data["contribution"]["id"] == contribution["id"] and backend.closed
    assert (
        data["execution"]["request"]["prompt_sha256"]
        == hashlib.sha256(b"Replay prompt").hexdigest()
    )
    assert all(
        options["num_predict"] == 4 and options["num_ctx"] == 2048
        for _, _, options in backend.calls
    )
    assert data["execution"]["successful_count"] == 3 and data["execution"]["failed_count"] == 0
    assert data["gpu_eligibility"]["state"] == "ineligible"
    metric = data["comparison"]["decode_tps"]
    assert (
        metric["unit"] == "tokens/second" and metric["original"] == 100 and metric["replayed"] == 40
    )
    assert (
        metric["raw_delta"] == -60 and metric["state"] == "unverified" and metric["delta"] is None
    )
    assert data["comparison"]["ttft_ms"]["state"] == "unverified"  # old TTFT basis absent
    assert data["contribution"]["attestation"]["signed"] is False and report.exit_code == 1
    assert path.read_bytes() == original and load_quarantine() == []


@pytest.mark.parametrize("field,value", [("quant", "FP16"), ("model", "other-model")])
def test_known_remote_disagreement_survives_legacy_gaps(legacy, monkeypatch, field, value):
    backend = ReplayBackend(device="unknown", **{field: value})
    data = execute(legacy[0], backend, monkeypatch).to_dict()
    assert data["binding"][field]["state"] == "mismatch"
    assert data["exit_code"] == 1 and data["comparison"]["decode_tps"]["state"] == "unverified"


def test_matching_claimed_labels_do_not_verify_original_remote_hardware(legacy, monkeypatch):
    data = execute(legacy[0], ReplayBackend(device="cuda"), monkeypatch).to_dict()
    assert data["binding"]["model"]["state"] == "matched"
    assert data["gpu_eligibility"]["state"] == "unverified"
    assert data["replay_equivalence"]["state"] == "unverified" and data["exit_code"] == 0


@pytest.mark.parametrize("fail", [1, 3])
def test_failed_requests_and_no_survivors_are_preserved_not_passed(legacy, monkeypatch, fail):
    backend = ReplayBackend(fail=fail)
    data = execute(legacy[0], backend, monkeypatch).to_dict()
    assert backend.closed and data["exit_code"] == 1
    assert data["execution"]["requested_count"] == 3
    assert (
        data["execution"]["failed_count"] == fail
        and data["execution"]["successful_count"] == 3 - fail
    )
    assert data["comparison"]["decode_tps"]["replayed_count"] == 3 - fail
    assert "secret" not in json.dumps(data) and "private" not in json.dumps(data)


@pytest.mark.parametrize(
    "options",
    [
        {"prompt": ""},
        {"output_tokens": 0},
        {"output_tokens": True},
        {"runs": 0},
        {"runs": 1001},
        {"workload": "server"},
        {"concurrency": 0},
    ],
)
def test_invalid_replay_refused_before_contact(legacy, monkeypatch, options):
    from chimeraforge.api import replay_contribution
    from chimeraforge.bench import runner

    contacted = []
    monkeypatch.setattr(runner, "get_backend", lambda *a, **k: contacted.append(True))
    kwargs = {"prompt": "explicit", "output_tokens": 4, "runs": 3, **options}
    with pytest.raises(ContribError):
        asyncio.run(replay_contribution(legacy[0], **kwargs))
    assert contacted == []


def test_malformed_contribution_replay_cannot_contact_backend(legacy, monkeypatch):
    broken = copy.deepcopy(legacy[0])
    broken["measurements"]["decode_tps_mean"] = 123
    with pytest.raises(ContribError, match="hash"):
        execute(broken, ReplayBackend(), monkeypatch)


def test_public_types_and_actual_review_cli_json(legacy):
    from chimeraforge.api import review_contribution, replay_contribution

    assert get_type_hints(review_contribution)["return"]
    assert get_type_hints(replay_contribution)["return"]
    result = CliRunner().invoke(app, ["contribute", "review", str(legacy[1]), "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert (
        data["contribution"]["id"] == legacy[0]["id"]
        and data["decision"]["disposition"] == "pending"
    )


def test_actual_replay_cli_json_equals_atomic_receipt_and_refuses_input_collision(
    legacy, tmp_path, monkeypatch
):
    from chimeraforge.bench import runner

    backend = ReplayBackend()
    monkeypatch.setattr(runner, "get_backend", lambda *a, **k: backend)
    out = tmp_path / "replay.json"
    args = [
        "contribute",
        "replay",
        str(legacy[1]),
        "--prompt",
        "Replay prompt",
        "--output-tokens",
        "4",
        "--runs",
        "3",
        "--json",
    ]
    result = CliRunner().invoke(app, [*args, "--out", str(out)])
    assert result.exit_code == 1, result.output
    assert json.loads(result.stdout) == json.loads(out.read_text()) and backend.closed
    before = legacy[1].read_bytes()
    collision = CliRunner().invoke(app, [*args, "--out", str(legacy[1])])
    assert collision.exit_code == 2 and legacy[1].read_bytes() == before


@pytest.mark.parametrize("options", [{"model": ""}, {"backend": ""}, {"workload": ""}])
def test_empty_explicit_overrides_do_not_silently_reuse_legacy_labels(legacy, monkeypatch, options):
    from chimeraforge.api import replay_contribution
    from chimeraforge.bench import runner

    contacted = []
    monkeypatch.setattr(runner, "get_backend", lambda *a, **k: contacted.append(True))
    with pytest.raises(ContribError):
        asyncio.run(replay_contribution(legacy[0], prompt="explicit", output_tokens=4, **options))
    assert contacted == []


def test_original_unknown_engine_version_is_not_a_known_contradiction(legacy, monkeypatch):
    from chimeraforge.contrib import _content_id

    contribution = legacy[0]
    contribution["fingerprint"]["backend_version"] = None
    contribution["id"] = _content_id(contribution["fingerprint"], contribution["measurements"])
    data = execute(contribution, ReplayBackend(device="cuda"), monkeypatch).to_dict()
    assert data["binding"]["backend_version"]["state"] == "unavailable" and data["exit_code"] == 0


def test_preflight_failure_receipt_preserves_intent_without_claiming_attempted_generations(
    legacy, monkeypatch
):
    backend = ReplayBackend()

    async def refuse():
        return False, "http://user:secret@localhost:9999/?token=private unavailable"

    backend.health_check = refuse
    data = execute(legacy[0], backend, monkeypatch).to_dict()
    assert backend.closed and backend.calls == []
    assert data["status"] == "failed" and data["exit_code"] == 1
    assert data["execution"]["attempted_count"] == 0 and data["execution"]["not_started_count"] == 3
    assert (
        data["requested_execution"]["prompt_sha256"] == hashlib.sha256(b"Replay prompt").hexdigest()
    )
    assert data["measurement"] is None and data["error"]["type"] == "RuntimeError"
    assert "secret" not in json.dumps(data) and "private" not in json.dumps(data)


def test_typed_metadata_unknown_and_known_mid_run_changes_stay_distinct(legacy, monkeypatch):
    backend = ReplayBackend(device="cuda")
    observe = backend.observe_serving

    async def changed(model):
        data = await observe(model)
        data["version"] = {"api_key": "private"}
        if backend.calls:
            data["quant"] = "FP16"
        return data

    backend.observe_serving = changed
    data = execute(legacy[0], backend, monkeypatch).to_dict()
    assert data["binding"]["backend_version"]["state"] == "unavailable"
    assert data["binding"]["quant"]["state"] == "mismatch"
    assert data["binding"]["serving_stability"]["state"] == "mismatch"
    assert "private" not in json.dumps(data)


@pytest.mark.parametrize(
    "name,vram,wanted",
    [
        ("NVIDIA GeForce RTX 4090", 24, "unverified"),
        ("RTX 4090", 24, "unverified"),
        ("unknown future GPU", 24, "unverified"),
        ("RTX 4080 12GB", 12, "ineligible"),
        ("NVIDIA GeForce RTX 4090", 1, "ineligible"),
    ],
)
def test_gpu_alias_unknown_names_and_known_geometry_contradictions(
    legacy, monkeypatch, name, vram, wanted
):
    backend = ReplayBackend(device="cuda")
    observe = backend.observe_serving

    async def with_hardware(model):
        result = await observe(model)
        result["hardware"] = {"name": name, "vram_gb": vram}
        return result

    backend.observe_serving = with_hardware
    data = execute(legacy[0], backend, monkeypatch).to_dict()
    assert data["gpu_eligibility"]["state"] == wanted


def test_replay_real_ollama_adapter_observes_cpu_and_actual_tokens_not_output_cap(
    legacy, monkeypatch
):
    import httpx
    from chimeraforge.bench.backends.ollama import OllamaBackend

    requests = []

    def handle(request):
        requests.append((request.method, request.url.path))
        if request.url.path == "/":
            return httpx.Response(200, text="Ollama is running")
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.35.1"})
        if request.url.path == "/api/show":
            return httpx.Response(
                200, json={"details": {"quantization_level": "Q4_K_M"}, "model_info": {}}
            )
        if request.url.path in {"/api/tags", "/api/ps"}:
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "llama3.2-3b:latest",
                            "digest": "a" * 64,
                            "context_length": 2048,
                            "size_vram": 0,
                            "details": {"quantization_level": "Q4_K_M"},
                        }
                    ]
                },
            )
        assert request.url.path == "/api/generate"
        data = json.loads(request.content)
        assert data["prompt"] == "Replay prompt" and data["options"]["num_predict"] == 4
        return httpx.Response(
            200,
            json={
                "eval_count": 2,
                "eval_duration": 100000000,
                "prompt_eval_count": 8,
                "prompt_eval_duration": 2000000,
                "total_duration": 102000000,
            },
        )

    backend = OllamaBackend(base_url="http://localhost:9999")
    backend._client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    data = execute(legacy[0], backend, monkeypatch, base_url="http://localhost:9999").to_dict()
    assert backend._client.is_closed
    assert data["gpu_eligibility"]["state"] == "ineligible"
    assert data["binding"]["model"]["state"] == "matched"
    assert data["execution"]["serving_after"]["loaded_gpu_bytes"] == 0
    assert data["requested_execution"]["output_token_cap"] == 4
    assert [row["tokens_generated"] for row in data["measurement"]["individual_runs"]] == [2, 2, 2]
    assert requests.count(("POST", "/api/generate")) == 3
    assert data["comparison"]["decode_tps"]["state"] == "unverified"


def test_replay_artifact_redacts_endpoint_credentials_and_cannot_write_quarantine(
    legacy, monkeypatch
):
    from chimeraforge.contrib import quarantine_dir

    data = execute(
        legacy[0],
        ReplayBackend(),
        monkeypatch,
        base_url="http://user:secret@localhost:9999/?token=private",
    ).to_dict()
    assert data["execution"]["endpoint"] == "http://localhost:9999/"
    assert "secret" not in json.dumps(data) and "private" not in json.dumps(data)
    report = execute(legacy[0], ReplayBackend(), monkeypatch)
    with pytest.raises(ContribError, match="quarantine"):
        report.save(quarantine_dir() / "review.json")


@pytest.mark.parametrize(
    "name,vram",
    [
        (7, 24),
        (True, 24),
        ("", 24),
        ("RTX 4060 Ti", "8"),
        ("NVIDIA GeForce RTX 4090", "not-numeric"),
        ("NVIDIA GeForce RTX 4090", float("nan")),
        ("NVIDIA GeForce RTX 4090", -1),
        ("NVIDIA GeForce RTX 4090", True),
    ],
)
def test_malformed_hardware_metadata_is_unavailable_without_crashing(
    legacy, monkeypatch, name, vram
):
    backend = ReplayBackend(device="cuda")
    observer = backend.observe_serving

    async def wrong_type(model):
        result = await observer(model)
        result["hardware"] = {"name": name, "vram_gb": vram}
        return result

    backend.observe_serving = wrong_type
    data = execute(legacy[0], backend, monkeypatch).to_dict()
    assert data["gpu_eligibility"]["state"] == "unverified"


@pytest.mark.parametrize(
    "recorded,observed,wanted",
    [(23.6, 23.6, "unverified"), (None, 23.6, "unverified"), (23.6, 24, "ineligible")],
)
def test_gpu_capacity_compares_recorded_observation_not_marketed_nominal(
    legacy, monkeypatch, recorded, observed, wanted
):
    from chimeraforge.contrib import _content_id

    contribution = legacy[0]
    contribution["fingerprint"]["gpu_memory_gb"] = recorded
    contribution["id"] = _content_id(contribution["fingerprint"], contribution["measurements"])
    backend = ReplayBackend(device="cuda")
    observer = backend.observe_serving

    async def hardware(model):
        result = await observer(model)
        result["hardware"] = {"name": "NVIDIA GeForce RTX 4090", "vram_gb": observed}
        return result

    backend.observe_serving = hardware
    data = execute(contribution, backend, monkeypatch).to_dict()
    assert data["gpu_eligibility"]["state"] == wanted


@pytest.mark.parametrize(
    "url",
    ["file:///invalid", "", "localhost:11434", "http:///missing", "http://localhost:not-a-port", 7],
)
def test_invalid_endpoint_is_refused_before_actual_adapter_contact(legacy, monkeypatch, url):
    from chimeraforge.api import replay_contribution
    from chimeraforge.bench import runner

    contacted = []
    monkeypatch.setattr(runner, "get_backend", lambda *a, **k: contacted.append(True))
    with pytest.raises(ContribError, match="HTTP"):
        asyncio.run(
            replay_contribution(legacy[0], prompt="explicit", output_tokens=4, base_url=url)
        )
    assert contacted == []


def test_actual_adapter_operational_protocol_failure_keeps_failed_receipt(legacy, monkeypatch):
    import httpx
    from chimeraforge.bench.backends.ollama import OllamaBackend

    def fail(request):
        raise httpx.RemoteProtocolError(
            "ERROR_SECRET_SENTINEL at http://user:USERINFO_SECRET_SENTINEL@localhost/?token=QUERY_SECRET_SENTINEL",
            request=request,
        )

    backend = OllamaBackend(base_url="http://localhost:9999")
    backend._client = httpx.AsyncClient(transport=httpx.MockTransport(fail))
    data = execute(legacy[0], backend, monkeypatch, base_url="http://localhost:9999").to_dict()
    assert backend._client.is_closed
    assert data["status"] == "failed" and data["exit_code"] == 1
    assert data["error"]["type"] == "RemoteProtocolError"
    assert data["execution"]["attempted_count"] == 0 and data["execution"]["not_started_count"] == 3
    assert data["measurement"] is None and data["requested_execution"]["output_token_cap"] == 4
    leaked = [
        value
        for value in ("ERROR_SECRET_SENTINEL", "USERINFO_SECRET_SENTINEL", "QUERY_SECRET_SENTINEL")
        if value in json.dumps(data)
    ]
    assert leaked == []


@pytest.mark.parametrize("adapter", ["vllm", "sglang", "tgi"])
@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {"data": "private"},
        {"data": [{"id": 7}], "model_id": 7},
        {"data": [{}], "model_id": []},
    ],
)
def test_actual_adapter_malformed_model_response_is_failed_receipt(
    legacy, monkeypatch, adapter, payload
):
    import httpx
    from chimeraforge.api import replay_contribution
    from chimeraforge.bench import runner
    from chimeraforge.bench.backends import get_backend

    info_reads = 0

    def handle(request):
        nonlocal info_reads
        if request.url.path == "/health":
            return httpx.Response(200)
        if request.url.path in {"/version", "/server_info", "/get_server_info"}:
            return httpx.Response(200, json={"version": "0.30.0"})
        if request.url.path == "/info":
            info_reads += 1
            if info_reads == 1:
                return httpx.Response(200, json={"version": "3.3.7"})
        assert request.url.path in {"/v1/models", "/info"}
        return httpx.Response(
            200, text="not JSON private secret" if payload is None else json.dumps(payload)
        )

    backend = get_backend(
        adapter, base_url="http://localhost:9999", transport=httpx.MockTransport(handle)
    )
    monkeypatch.setattr(runner, "get_backend", lambda *a, **k: backend)
    data = asyncio.run(
        replay_contribution(legacy[0], prompt="explicit", output_tokens=4, runs=3, backend=adapter)
    ).to_dict()
    assert backend._client.is_closed
    assert data["status"] == "failed" and data["error"]["type"] == "RuntimeError"
    assert data["execution"]["attempted_count"] == 0 and data["execution"]["not_started_count"] == 3
    assert "private" not in json.dumps(data) and "secret" not in json.dumps(data)


def test_actual_invalid_endpoint_cli_has_input_exit_without_traceback(legacy):
    result = CliRunner().invoke(
        app,
        [
            "contribute",
            "replay",
            str(legacy[1]),
            "--prompt",
            "explicit",
            "--output-tokens",
            "4",
            "--base-url",
            "file:///invalid",
        ],
    )
    assert result.exit_code == 2 and isinstance(result.exception, SystemExit)
    assert "HTTP" in result.output


def test_receipt_output_failure_is_domain_error_and_cli_input_exit(legacy, tmp_path):
    from chimeraforge.api import review_contribution

    target = tmp_path / "nonexistent-parent" / "receipt.json"
    with pytest.raises(ContribError, match="save|write"):
        review_contribution(legacy[0]).save(target)
    result = CliRunner().invoke(app, ["contribute", "review", str(legacy[1]), "--out", str(target)])
    assert result.exit_code == 2 and isinstance(result.exception, SystemExit)
    assert not target.exists()


def test_hosted_replay_guard_rejects_trust_or_equivalence_promotion(legacy, monkeypatch):
    from test_ci_acceptance import load_script

    script = load_script("ci_cpu_serving")
    report = execute(legacy[0], ReplayBackend(), monkeypatch).to_dict()
    script.validate_contribution_replay(report, legacy[0], 3)
    changed = copy.deepcopy(report)
    changed["trust"]["changes_corpus"] = True
    with pytest.raises(AssertionError):
        script.validate_contribution_replay(changed, legacy[0], 3)
    changed = copy.deepcopy(report)
    changed["comparison"]["decode_tps"]["state"] = "comparable"
    with pytest.raises(AssertionError):
        script.validate_contribution_replay(changed, legacy[0], 3)


def test_unavailable_ttft_sentinel_is_preserved_without_a_latency_delta(legacy, monkeypatch):
    backend = ReplayBackend(device="cuda")
    generate = backend.generate

    async def unknown_ttft(model, prompt, options=None):
        result = await generate(model, prompt, options)
        result.ttft_ms, result.ttft_basis = -1, "unknown"
        return result

    backend.generate = unknown_ttft
    data = execute(legacy[0], backend, monkeypatch).to_dict()
    metric = data["comparison"]["ttft_ms"]
    assert metric["replayed_samples"] == [-1, -1, -1]
    assert metric["replayed"] is None and metric["raw_delta"] is None


def test_unknown_original_version_does_not_hide_known_mid_run_version_change(legacy, monkeypatch):
    from chimeraforge.contrib import _content_id

    contribution = legacy[0]
    contribution["fingerprint"]["backend_version"] = None
    contribution["id"] = _content_id(contribution["fingerprint"], contribution["measurements"])
    backend = ReplayBackend(device="cuda")
    observe = backend.observe_serving

    async def changing(model):
        result = await observe(model)
        result["version"] = "0.35.2" if backend.calls else "0.35.1"
        return result

    backend.observe_serving = changing
    data = execute(contribution, backend, monkeypatch).to_dict()
    assert data["binding"]["backend_version"]["state"] == "unavailable"
    assert data["binding"]["serving_stability"]["state"] == "mismatch" and data["exit_code"] == 1


def test_known_remote_backend_disagreement_is_actionable(legacy, monkeypatch):
    backend = ReplayBackend(device="cuda")
    backend.name = "vllm"
    data = execute(legacy[0], backend, monkeypatch).to_dict()
    assert data["binding"]["backend"]["state"] == "mismatch" and data["exit_code"] == 1
