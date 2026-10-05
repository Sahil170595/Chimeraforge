"""Deployment config fidelity and format-specific argument safety."""

import json
import hashlib
import plistlib
from dataclasses import asdict, replace

import pytest
import yaml
from typer.testing import CliRunner

from chimeraforge.api import PlanRequest, snapshot
from chimeraforge.cli import app
from chimeraforge.planner.engine import Candidate
from chimeraforge.planner.models import load_effective_models
from chimeraforge.planner.resolver import ModelSpec, SOURCE_HF, SOURCE_OLLAMA
from chimeraforge.planner.service import PlanResult


def artifact(
    *,
    backend="vllm",
    quant="FP16",
    source=SOURCE_HF,
    native_quant=None,
    model="Qwen/Qwen2.5-7B-Instruct",
    platform="linux",
    inputs=None,
    candidate_changes=None,
    spec_changes=None,
):
    candidate = Candidate(
        model=model,
        quant=quant,
        backend=backend,
        n_agents=1,
        vram_gb=15.0,
        quality=0.8,
        quality_tier="negligible",
        throughput_tps=100.0,
        total_throughput_tps=100.0,
        eta=1.0,
        p95_latency_ms=500.0,
        utilisation=0.5,
        monthly_cost=25.0,
        cost_per_1m_tok=0.1,
        safety_refusal=None,
        rtsi_risk="UNKNOWN",
        warnings=["Predictions are estimates, not measured deployment acceptance."],
        effective_batch=4,
        gpus_total=1,
        platform="macos" if platform == "macos" else "linux-cuda",
    )
    candidate = replace(candidate, **(candidate_changes or {}))
    spec = (
        None
        if source is None
        else ModelSpec(
            name=model,
            params_b=7.0,
            n_layers=28,
            n_kv_heads=4,
            d_head=128,
            source=source,
            native_quant=native_quant,
            **(spec_changes or {}),
        )
    )
    request = PlanRequest(platform=platform, allow_network=False, **(inputs or {}))
    corpus_hash = hashlib.sha256(
        json.dumps(
            asdict(load_effective_models()), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    return snapshot(
        request,
        PlanResult(
            [candidate],
            [model],
            {model: spec} if spec else {},
            platform=platform,
            corpus_sha256=corpus_hash,
        ),
    )


def export(artifact, **options):
    from chimeraforge.deploy import export_deployment

    return export_deployment(artifact, **options)


def test_compose_parses_and_preserves_context_batch_dtype_and_gpu_count():
    saved = artifact(
        candidate_changes={"tensor_parallel": 2, "gpus_total": 2},
        inputs={"context_length": 4096, "max_num_batched_tokens": 512},
    )
    result = export(saved, format="compose", image="vllm/vllm-openai:v0.30.0")
    data = yaml.safe_load(result.content)
    service = data["services"]["inference"]
    assert service["image"] == "vllm/vllm-openai:v0.30.0"
    assert service["entrypoint"] == ["vllm", "serve"]
    args = service["command"]
    assert args[0] == "Qwen/Qwen2.5-7B-Instruct"
    for flag, value in [
        ("--max-model-len", "4096"),
        ("--max-num-seqs", "4"),
        ("--dtype", "float16"),
        ("--tensor-parallel-size", "2"),
        ("--max-num-batched-tokens", "512"),
    ]:
        assert args[args.index(flag) + 1] == value
    assert service["deploy"]["resources"]["reservations"]["devices"] == [
        {"driver": "nvidia", "count": 2, "capabilities": ["gpu"]}
    ]
    assert service["ports"] == ["127.0.0.1:8000:8000"]
    assert saved.to_dict()["fingerprint"] in result.content
    assert any("GPU" in note for note in result.notes)


@pytest.mark.parametrize(
    "backend, entrypoint, model_flag, context_flag",
    [
        ("sglang", ["python3", "-m", "sglang.launch_server"], "--model-path", "--context-length"),
        ("tgi", ["text-generation-launcher"], "--model-id", "--max-total-tokens"),
    ],
)
def test_other_hf_compose_templates(backend, entrypoint, model_flag, context_flag):
    result = export(artifact(backend=backend), format="compose", image="example/engine:1.2.3")
    service = yaml.safe_load(result.content)["services"]["inference"]
    assert service["entrypoint"] == entrypoint
    assert (
        service["command"][service["command"].index(model_flag) + 1] == "Qwen/Qwen2.5-7B-Instruct"
    )
    assert service["command"][service["command"].index(context_flag) + 1] == "2048"


def test_ollama_daemon_with_companion_modelfile_and_provisioning():
    saved = artifact(
        backend="ollama",
        model="ollama:qwen2.5:7b-instruct-q4_K_M",
        source=SOURCE_OLLAMA,
        quant="Q4_K_M",
        native_quant="Q4_K_M",
        inputs={"kv_quant": "q8", "context_length": 8192},
    )
    result = export(saved, format="compose", image="ollama/ollama:0.6.8")
    service = yaml.safe_load(result.content)["services"]["inference"]
    assert service["entrypoint"] == ["ollama", "serve"]
    assert not service.get("command")
    assert service["environment"]["OLLAMA_NUM_PARALLEL"] == "4"
    assert service["environment"]["OLLAMA_KV_CACHE_TYPE"] == "q8_0"
    assert service["environment"]["OLLAMA_FLASH_ATTENTION"] == "1"
    assert service["environment"]["OLLAMA_CONTEXT_LENGTH"] == "8192"
    assert "FROM qwen2.5:7b-instruct-q4_K_M\nPARAMETER num_ctx 8192" in result.files["Modelfile"]
    assert any("ollama create" in step for step in result.provisioning)
    assert any("ollama pull" in step for step in result.provisioning)
    assert any("Use model" in step for step in result.provisioning)


def test_modelfile_carries_daemon_requirements_without_pretending_it_starts_server():
    saved = artifact(
        backend="ollama",
        model="ollama:qwen2.5:7b-instruct-q4_K_M",
        source=SOURCE_OLLAMA,
        quant="Q4_K_M",
        native_quant="Q4_K_M",
    )
    result = export(saved, format="modelfile")
    assert "PARAMETER num_ctx 2048" in result.content
    assert "OLLAMA_NUM_PARALLEL=4" in "\n".join(result.provisioning)
    assert any("ollama serve" in step for step in result.provisioning)


def test_launchd_is_real_plist_with_argv_and_environment():
    saved = artifact(
        backend="ollama",
        model="ollama:qwen2.5:7b-instruct-q4_K_M",
        source=SOURCE_OLLAMA,
        quant="Q4_K_M",
        native_quant="Q4_K_M",
        platform="macos",
    )
    result = export(
        saved, format="launchd", executable="/Applications/Ollama.app/Contents/Resources/ollama"
    )
    data = plistlib.loads(result.content.encode())
    assert data["ProgramArguments"] == [
        "/Applications/Ollama.app/Contents/Resources/ollama",
        "serve",
    ]
    assert data["EnvironmentVariables"]["OLLAMA_HOST"] == "127.0.0.1:11434"
    assert data["EnvironmentVariables"]["OLLAMA_NUM_PARALLEL"] == "4"
    assert data["RunAtLoad"] is True
    assert "Modelfile" in result.files


def test_systemd_argv_escapes_dollars_percents_quotes_and_backslashes():
    name = 'org/model$ENV%u;"\\quoted'
    result = export(artifact(model=name), format="systemd", executable="/opt/engine/bin/vllm")
    assert '"org/model$$ENV%%u;\\"\\\\quoted"' in result.content
    assert 'ExecStart="/opt/engine/bin/vllm" "serve"' in result.content
    assert '--host" "127.0.0.1' in result.content
    assert "bash" not in result.content and "sh -c" not in result.content


def test_compose_escapes_interpolation_and_uses_argument_list():
    name = "org/model${SECRET};$(id)%u"
    result = export(artifact(model=name), format="compose", image="example/engine:1.2.3")
    service = yaml.safe_load(result.content)["services"]["inference"]
    assert service["command"][0] == "org/model$${SECRET};$$(id)%u"
    assert "SECRET" not in service.get("environment", {})


@pytest.mark.parametrize(
    "image",
    [
        None,
        "example/engine",
        "example/engine:latest",
        "example/engine:",
        "example/engine:1.2\ncommand: bad",
        "example/${TAG}:1.2",
    ],
)
def test_compose_requires_explicit_image_identity(image):
    from chimeraforge.deploy import DeploymentError

    with pytest.raises(DeploymentError, match="image"):
        export(artifact(), format="compose", image=image)


def test_digest_image_and_bf16_plan_are_supported():
    result = export(
        artifact(quant="BF16"), format="compose", image="example/engine@sha256:" + "a" * 64
    )
    command = yaml.safe_load(result.content)["services"]["inference"]["command"]
    assert command[command.index("--dtype") + 1] == "bfloat16"


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"n_agents": 2, "gpus_total": 2}, "replica"),
        ({"offload_fraction": 0.2}, "offload"),
        ({"lora_adapters": 2}, "adapter"),
        ({"tensor_parallel": 2, "gpus_total": 1}, "GPU count"),
        ({"effective_batch": 0}, "batch"),
    ],
)
def test_refuses_unexpressed_candidate_requirements(changes, message):
    from chimeraforge.deploy import DeploymentError

    with pytest.raises(DeploymentError, match=message):
        export(artifact(candidate_changes=changes), format="compose", image="example/engine:1.2.3")


@pytest.mark.parametrize("backend", ["vllm", "tgi", "sglang"])
def test_q4_kv_cannot_silently_become_fp8(backend):
    from chimeraforge.deploy import DeploymentError

    with pytest.raises(DeploymentError, match="q4 KV"):
        export(
            artifact(backend=backend, inputs={"kv_quant": "q4"}),
            format="compose",
            image="example/engine:1.2.3",
        )


@pytest.mark.parametrize(
    "quant,native", [("Q4_K_M", None), ("AWQ", None), ("GPTQ", "AWQ"), ("FP16", "AWQ")]
)
def test_checkpoint_quantization_must_match_plan(quant, native):
    from chimeraforge.deploy import DeploymentError

    with pytest.raises(DeploymentError, match="quant"):
        export(
            artifact(quant=quant, native_quant=native),
            format="compose",
            image="example/engine:1.2.3",
        )


def test_verified_awq_checkpoint_flag():
    result = export(
        artifact(quant="AWQ", native_quant="AWQ"), format="compose", image="example/engine:1.2.3"
    )
    command = yaml.safe_load(result.content)["services"]["inference"]["command"]
    assert command[command.index("--quantization") + 1] == "awq"


def test_registry_placeholder_requires_explicit_model_and_preserves_identity_note():
    from chimeraforge.deploy import DeploymentError

    saved = artifact(source=None, model="llama3.2-3b")
    with pytest.raises(DeploymentError, match="model"):
        export(saved, format="compose", image="example/engine:1.2.3")
    result = export(
        saved, format="compose", image="example/engine:1.2.3", model="org/concrete-model"
    )
    assert (
        yaml.safe_load(result.content)["services"]["inference"]["command"][0]
        == "org/concrete-model"
    )
    assert any("registry" in note and "override" in note for note in result.notes)


def test_quantized_registry_override_does_not_fabricate_checkpoint_identity():
    from chimeraforge.deploy import DeploymentError

    with pytest.raises(DeploymentError, match="quant"):
        export(
            artifact(source=None, model="llama3.2-3b", quant="AWQ"),
            format="compose",
            image="example/engine:1.2.3",
            model="org/arbitrary-AWQ",
        )


def test_explicit_resolved_model_cannot_be_replaced_with_another_model():
    from chimeraforge.deploy import DeploymentError

    with pytest.raises(DeploymentError, match="replan"):
        export(
            artifact(), format="compose", image="example/engine:1.2.3", model="org/different-model"
        )


@pytest.mark.parametrize(
    "format,platform,backend,executable",
    [
        ("launchd", "linux", "ollama", "/usr/bin/ollama"),
        ("systemd", "macos", "ollama", "/usr/bin/ollama"),
        ("compose", "macos", "ollama", None),
        ("systemd", "linux", "tgi", "/usr/bin/launcher"),
        ("modelfile", "linux", "vllm", None),
    ],
)
def test_platform_and_format_compatibility(format, platform, backend, executable):
    from chimeraforge.deploy import DeploymentError

    with pytest.raises(DeploymentError):
        export(
            artifact(backend=backend, platform=platform),
            format=format,
            image="example/engine:1.2.3",
            executable=executable,
        )


@pytest.mark.parametrize(
    "executable", [None, "vllm", "/opt/bin/vllm\nExecStart=bad", "C:\\vllm.exe"]
)
def test_native_units_require_explicit_absolute_posix_executable(executable):
    from chimeraforge.deploy import DeploymentError

    with pytest.raises(DeploymentError, match="executable"):
        export(artifact(), format="systemd", executable=executable)


@pytest.mark.parametrize("model", ["org/x\nExecStart=bad", "<hf-repo>", "--malicious", "org/x\x00"])
def test_control_characters_placeholders_and_option_injection_are_refused(model):
    from chimeraforge.deploy import DeploymentError

    with pytest.raises(DeploymentError, match="model"):
        export(artifact(model=model), format="compose", image="example/engine:1.2.3")


def test_cli_writes_config_and_reports_notes(tmp_path):
    path = tmp_path / "plan.json"
    artifact().save(path)
    output = tmp_path / "compose.yaml"
    result = CliRunner().invoke(
        app,
        [
            "deploy",
            "--plan",
            str(path),
            "--format",
            "compose",
            "--image",
            "example/engine:1.2.3",
            "--out",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    assert yaml.safe_load(output.read_text())["services"]["inference"]
    assert "Config only" in result.output


def test_cli_failure_does_not_write_or_traceback(tmp_path):
    path = tmp_path / "plan.json"
    artifact(candidate_changes={"n_agents": 3}).save(path)
    output = tmp_path / "compose.yaml"
    result = CliRunner().invoke(
        app,
        [
            "deploy",
            "--plan",
            str(path),
            "--format",
            "compose",
            "--image",
            "example/engine:1.2.3",
            "--out",
            str(output),
        ],
    )
    assert result.exit_code == 1
    assert "replica" in result.output
    assert not output.exists()
    assert "Traceback" not in result.output


def test_cli_does_not_overwrite_unrelated_file(tmp_path):
    path = tmp_path / "plan.json"
    artifact().save(path)
    output = tmp_path / "compose.yaml"
    output.write_text("keep me")
    result = CliRunner().invoke(
        app,
        [
            "deploy",
            "--plan",
            str(path),
            "--format",
            "compose",
            "--image",
            "example/engine:1.2.3",
            "--out",
            str(output),
        ],
    )
    assert result.exit_code == 1
    assert output.read_text() == "keep me"


def test_cli_writes_ollama_companion_and_refuses_companion_collision(tmp_path):
    path = tmp_path / "plan.json"
    saved = artifact(
        backend="ollama",
        model="ollama:qwen2.5:7b-instruct-q4_K_M",
        source=SOURCE_OLLAMA,
        quant="Q4_K_M",
        native_quant="Q4_K_M",
    )
    saved.save(path)
    output = tmp_path / "compose.yaml"
    companion = tmp_path / "Modelfile"
    companion.write_text("unrelated")
    args = [
        "deploy",
        "--plan",
        str(path),
        "--format",
        "compose",
        "--image",
        "ollama/ollama:0.6.8",
        "--out",
        str(output),
    ]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 1
    assert not output.exists()
    assert companion.read_text() == "unrelated"
    companion.unlink()
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    assert "PARAMETER num_ctx" in companion.read_text()


def test_unknown_format_and_candidate_index_have_typed_errors():
    from chimeraforge.deploy import DeploymentError

    with pytest.raises(DeploymentError, match="format"):
        export(artifact(), format="kubernetes")
    with pytest.raises(DeploymentError, match="index"):
        export(artifact(), format="compose", image="example/engine:1.2.3", candidate_index=2)


def test_deployment_result_metadata_is_json_serializable():
    result = export(artifact(), format="compose", image="example/engine:1.2.3")
    assert json.loads(json.dumps(result.to_dict()))["format"] == "compose"


@pytest.mark.parametrize(
    "format,options",
    [("systemd", {"image": "example/engine:1.2.3"}), ("compose", {"executable": "/usr/bin/vllm"})],
)
def test_unused_overrides_are_rejected(format, options):
    from chimeraforge.deploy import DeploymentError

    with pytest.raises(DeploymentError, match="override"):
        export(artifact(), format=format, **options)


def test_tgi_context_one_is_not_exported_with_zero_input_limit():
    from chimeraforge.deploy import DeploymentError

    with pytest.raises(DeploymentError, match="context_length"):
        export(
            artifact(backend="tgi", inputs={"context_length": 1}),
            format="compose",
            image="example/engine:1.2.3",
        )


def test_quantized_size_class_metadata_does_not_establish_override_checkpoint():
    from chimeraforge.deploy import DeploymentError
    from chimeraforge.planner.resolver import SOURCE_REGISTRY

    with pytest.raises(DeploymentError, match="quant"):
        export(
            artifact(source=SOURCE_REGISTRY, model="llama-7b", quant="AWQ", native_quant="AWQ"),
            model="org/other-AWQ",
            format="compose",
            image="example/engine:1.2.3",
        )


@pytest.mark.parametrize("backend", ["sglang", "tgi"])
def test_bf16_native_kv_cannot_silently_become_planned_fp16(backend):
    from chimeraforge.deploy import DeploymentError

    with pytest.raises(DeploymentError, match="KV dtype"):
        export(
            artifact(backend=backend, quant="BF16"), format="compose", image="example/engine:1.2.3"
        )


def test_unmodeled_chunked_prefill_is_explicitly_disabled():
    for backend, flag, value in [
        ("vllm", "--no-enable-chunked-prefill", None),
        ("sglang", "--chunked-prefill-size", "-1"),
    ]:
        result = export(artifact(backend=backend), format="compose", image="example/engine:1.2.3")
        command = yaml.safe_load(result.content)["services"]["inference"]["command"]
        assert flag in command
        if value is not None:
            assert command[command.index(flag) + 1] == value


def test_real_planner_saved_candidate_exports_without_replanning(tmp_path, monkeypatch):
    from chimeraforge.api import load_plan, plan
    from chimeraforge import api

    saved = plan(PlanRequest(allow_network=False, hardware="RTX 4090 24GB"))
    index = next(
        i
        for i, row in enumerate(saved.to_dict()["result"]["candidates"])
        if row["backend"] == "vllm" and row["quant"] == "FP16" and row["n_agents"] == 1
    )
    path = tmp_path / "plan.json"
    saved.save(path)

    def unexpected_search(**kwargs):
        pytest.fail("deployment export must not replan")

    monkeypatch.setattr(api, "run_plan", unexpected_search)
    result = export(
        load_plan(path),
        format="compose",
        candidate_index=index,
        model="meta-llama/Llama-3.2-3B-Instruct",
        image="vllm/vllm-openai:v0.30.0",
    )
    data = yaml.safe_load(result.content)
    args = data["services"]["inference"]["command"]
    assert args[args.index("--max-num-seqs") + 1] == str(saved.candidate(index).effective_batch)
    assert saved.to_dict()["fingerprint"] in result.content


@pytest.mark.parametrize("dtype_declared", [True, False])
@pytest.mark.parametrize("quant", ["FP16", "BF16"])
def test_recurrent_state_exports_refuse_missing_exact_dtype(dtype_declared, quant):
    from chimeraforge.deploy import DeploymentError

    saved = artifact(
        quant=quant,
        spec_changes={
            "recurrent_state_bytes_per_seq": 8192.0,
            "recurrent_state_dtype_declared": dtype_declared,
        },
    )
    with pytest.raises(DeploymentError, match="recurrent-state.*dtype"):
        export(saved, format="compose", image="vllm/vllm-openai:v0.30.0")
