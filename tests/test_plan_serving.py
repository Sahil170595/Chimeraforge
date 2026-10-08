"""Serving observations use documented protocol facts, not benchmark labels."""

import asyncio
import copy
import json

import httpx
import pytest

from chimeraforge.bench.serving import (
    MAX_METADATA_BYTES,
    metadata,
    observe_ollama,
    observe_vllm,
    observe_tgi,
    observe_sglang,
)


SHOW = {
    "details": {"family": "llama", "parameter_size": "3.2B", "quantization_level": "Q4_K_M"},
    "model_info": {
        "general.architecture": "llama",
        "llama.block_count": 28,
        "llama.attention.head_count": 24,
        "llama.attention.head_count_kv": 8,
        "llama.embedding_length": 3072,
        "llama.context_length": 131072,
    },
    "parameters": "private-parameter-token",
    "template": "private-template",
    "modelfile": "private-auth-modelfile",
}


def observe(observer, payloads, model="model"):
    async def run():
        def reply(request):
            payload = payloads.get(request.url.path)
            return httpx.Response(200, json=payload) if payload is not None else httpx.Response(404)

        async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as client:
            return await observer(client, "http://serving", model)

    return asyncio.run(run())


def test_ollama_show_architecture_context_is_not_loaded_runtime_context():
    show = copy.deepcopy(SHOW)
    result = observe(
        observe_ollama,
        {
            "/api/show": show,
            "/api/version": {"version": "0.35.1"},
            "/api/tags": {"models": [{"name": "model:latest", "digest": "a" * 64}]},
            "/api/ps": {
                "models": [
                    {
                        "name": "model:latest",
                        "digest": "a" * 64,
                        "size": 1000,
                        "size_vram": 0,
                        "context_length": 2048,
                    }
                ]
            },
        },
    )
    assert result["backend"] == "ollama" and result["quant"] == "Q4_K_M"
    assert result["context_length"] == 2048 and result["device"] == "cpu"
    assert result["model_spec"]["n_layers"] == 28
    assert result["hardware"] is None and result["tensor_parallel"] is None
    encoded = json.dumps(result)
    assert "private-" not in encoded and "modelfile" not in encoded


def test_ollama_unloaded_model_leaves_active_context_and_device_unknown():
    result = observe(observe_ollama, {"/api/show": SHOW, "/api/version": {"version": "0.35.1"}})
    assert result["model_spec"]["d_head"] == 128
    assert result["context_length"] is None and result["device"] is None
    assert result["limitations"]


@pytest.mark.parametrize(
    "payload", [{"details": "bad", "model_info": []}, {"details": {}, "model_info": {}}, {}]
)
def test_malformed_optional_ollama_metadata_is_unavailable(payload):
    result = observe(observe_ollama, {"/api/show": payload, "/api/ps": {"models": "bad"}})
    assert result["model_spec"] is None and result["quant"] is None


def test_vllm_observed_parallel_and_context_use_structured_config_only():
    result = observe(
        observe_vllm,
        {
            "/version": {"version": "0.30.0"},
            "/v1/models": {"data": [{"id": "model"}]},
            "/server_info": {
                "vllm_config": {
                    "model_config": {
                        "dtype": "torch.float16",
                        "max_model_len": 4096,
                        "token": "private-auth-token",
                    },
                    "parallel_config": {
                        "tensor_parallel_size": 2,
                        "pipeline_parallel_size": 1,
                        "data_parallel_size": 3,
                    },
                    "cache_config": {"enable_prefix_caching": False},
                    "device_config": {"device": "cuda"},
                },
                "vllm_env": {"HF_TOKEN": "private-hf-secret"},
                "system_env": {"gpu_models": "RTX 4080"},
            },
        },
    )
    assert result["model"] == "model" and result["quant"] == "FP16"
    assert result["tensor_parallel"] == 2 and result["pipeline_parallel"] == 1
    assert result["replicas"] == 3 and result["context_length"] == 4096
    assert result["prefix_cache"] is False and result["device"] == "gpu"
    assert result["hardware"] is None and result["model_digest"] is None
    assert "private-" not in json.dumps(result) and "RTX 4080" not in json.dumps(result)


def test_vllm_text_repr_is_never_evaluated_or_treated_as_verified_config():
    result = observe(
        observe_vllm, {"/server_info": {"vllm_config": "VllmConfig(token='private-secret')"}}
    )
    assert result["quant"] is None and result["tensor_parallel"] is None
    assert "private-secret" not in json.dumps(result)


def test_plugin_observation_whitelist_and_url_redaction():
    from chimeraforge.bench.serving import safe_observation, sanitize_message

    result = safe_observation(
        {
            "backend": "plugin",
            "source": "https://user:password@host/info?token=secret",
            "api_key": "private-key",
            "model_spec": {"n_layers": 10, "token": "private-token"},
            "hardware": {"name": "GPU", "auth": "private-auth"},
        }
    )
    assert result["model_spec"] == {"n_layers": 10} and result["hardware"] == {"name": "GPU"}
    assert result["source"] == "https://host/info" and "private-" not in json.dumps(result)
    assert (
        sanitize_message("https://user:pw@[::1]:8000/info?token=secret")
        == "https://[::1]:8000/info"
    )
    assert sanitize_message("https://bad:port/info?token=secret") == "[redacted-endpoint]"


def test_tgi_router_limit_is_not_active_model_context_or_quant():
    result = observe(
        observe_tgi,
        {
            "/info": {
                "version": "3.3.7",
                "model_id": "org/model",
                "model_sha": "a" * 40,
                "max_total_tokens": 4096,
                "max_input_tokens": 2048,
            }
        },
    )
    assert result["model"] == "org/model" and result["backend"] == "tgi"
    assert result["router_max_total_tokens"] == 4096
    assert result["context_length"] is None and result["quant"] is None


def test_sglang_current_identity_and_resolved_parallel_config_exclude_secrets():
    result = observe(
        observe_sglang,
        {
            "/server_info": {
                "version": "0.5.20",
                "served_model_name": "old-model",
                "tp_size": 2,
                "pp_size": 1,
                "dp_size": 1,
                "context_length": 4096,
                "disable_radix_cache": True,
                "device": "cuda",
                "quantization": "awq",
                "dtype": "float16",
                "api_key": "private-api-key",
                "launch_command": "private-token",
            },
            "/model_info": {
                "served_model_name": "current-model",
                "weight_version": "operator-label",
            },
        },
    )
    assert result["model"] == "current-model" and result["tensor_parallel"] == 2
    assert result["prefix_cache"] is False
    assert result["quant"] == "AWQ", (
        "Preserve the observed quant method without relabeling it as a GGUF quant."
    )
    assert result["model_digest"] is None and "private-" not in json.dumps(result)


@pytest.mark.parametrize(
    "payload",
    [b"[]", b"not json", b"x" * (MAX_METADATA_BYTES + 1)],
    ids=["array", "malformed", "oversize"],
)
def test_metadata_bounds_and_object_shape(payload):
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, content=payload))
        ) as client:
            with pytest.raises(ValueError):
                await metadata(client, "GET", "http://serving/info")

    asyncio.run(run())


def test_real_ollama_adapter_produces_useful_native_audit_without_gpu_accuracy(
    monkeypatch, tmp_path
):
    from chimeraforge.api import PlanRequest, plan
    from chimeraforge.bench.backends.ollama import OllamaBackend
    from chimeraforge.bench import runner
    from chimeraforge.cli import app
    from typer.testing import CliRunner

    saved = plan(
        PlanRequest(
            models=["llama3.2-3b"],
            allow_network=False,
            quality_target=0,
            budget=100000,
            avg_tokens=4,
            prompt_tokens=8,
        )
    )
    selected = next(
        i
        for i, row in enumerate(saved.to_dict()["result"]["candidates"])
        if row["backend"] == "ollama" and row["quant"] == "Q4_K_M"
    )
    model = saved.candidate(selected).model
    calls = []

    def reply(request):
        calls.append(request)
        path = request.url.path
        if path == "/":
            return httpx.Response(200, text="Ollama is running")
        bodies = {
            "/api/version": {"version": "0.35.1"},
            "/api/show": SHOW,
            "/api/tags": {"models": [{"name": model, "digest": "a" * 64}]},
            "/api/ps": {
                "models": [
                    {
                        "name": model,
                        "digest": "a" * 64,
                        "size": 1000,
                        "size_vram": 0,
                        "context_length": 2048,
                    }
                ]
            },
        }
        if path == "/api/generate":
            sent = json.loads(request.content)
            assert sent["options"]["num_predict"] == 4 and sent["options"]["num_ctx"] == 2048
            return httpx.Response(
                200,
                json={
                    "eval_count": 4,
                    "eval_duration": 100000000,
                    "prompt_eval_count": 8,
                    "prompt_eval_cached_count": 0,
                    "prompt_eval_duration": 2000000,
                    "total_duration": 102000000,
                },
            )
        return httpx.Response(200, json=bodies[path])

    actual = OllamaBackend("http://serving")
    actual._client = httpx.AsyncClient(transport=httpx.MockTransport(reply))
    monkeypatch.setattr(runner, "get_backend", lambda *args, **kwargs: actual)
    source = tmp_path / "plan.json"
    saved.save(source)
    original = source.read_bytes()
    outcome = CliRunner().invoke(
        app,
        [
            "bench",
            "--plan",
            str(source),
            "--runs",
            "3",
            "--candidate-index",
            str(selected),
            "--prompt",
            "actual prompt",
            "--output-dir",
            str(tmp_path / "results"),
            "--json",
        ],
    )
    assert outcome.exit_code == 1, outcome.output
    report = json.loads(outcome.stdout)
    assert "binding" in report, report
    assert source.read_bytes() == original and actual._client.is_closed
    assert report["binding"]["quant"]["state"] == "matched"
    assert report["binding"]["context_length"]["state"] == "matched"
    assert report["binding"]["prompt_tokens"]["state"] == "matched"
    metric = report["audit"]["metrics"]["base_decode_tps"]
    assert metric["measured"] == 40 and metric["modeled"] > 0
    assert metric["raw_delta"] == pytest.approx(40 - metric["modeled"])
    assert metric["delta"] is None and "hardware: mismatch" in metric["blocking_facts"]
    (receipt,) = (tmp_path / "results").glob("plan-bench_*.json")
    assert json.loads(receipt.read_text()) == report
    assert "private-" not in json.dumps(report)
    assert sum(request.url.path == "/api/generate" for request in calls) == 3
