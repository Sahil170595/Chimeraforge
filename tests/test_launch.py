"""Tests for launch-command export (planner/launch.py).

Locks the two things that matter: the *derived* flags are correct (context, TP/PP,
batch, KV dtype), and everything the emitter cannot stand behind (backend/id-source
mismatch, GGUF-quant-on-vLLM, gpu-mem-util) surfaces as a note rather than a
confident-but-wrong flag.
"""

from __future__ import annotations

import pytest

from chimeraforge.planner.engine import Candidate
from chimeraforge.planner.launch import LaunchCommand, build_launch_command
from chimeraforge.planner.resolver import SOURCE_HF, SOURCE_OLLAMA, ModelSpec


def _cand(**over) -> Candidate:
    base = dict(
        model="Qwen/Qwen2.5-7B-Instruct",
        quant="FP16",
        backend="vllm",
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
        warnings=[],
    )
    base.update(over)
    return Candidate(**base)


def _spec(source: str, name: str) -> ModelSpec:
    return ModelSpec(name=name, params_b=7.0, n_layers=28, n_kv_heads=4, d_head=128, source=source)


class TestVllm:
    def test_hf_repo_no_placeholder(self):
        lc = build_launch_command(
            _cand(backend="vllm"),
            _spec(SOURCE_HF, "Qwen/Qwen2.5-7B-Instruct"),
            context_length=2048,
        )
        assert lc.backend == "vllm"
        assert lc.command.startswith("vllm serve Qwen/Qwen2.5-7B-Instruct")
        assert "--max-model-len 2048" in lc.command
        assert "--gpu-memory-utilization 0.9" in lc.command
        assert "<hf-repo>" not in lc.command

    def test_tensor_parallel_flag(self):
        lc = build_launch_command(
            _cand(backend="vllm", tensor_parallel=4, gpus_total=4),
            _spec(SOURCE_HF, "x/y"),
            context_length=4096,
        )
        assert "--tensor-parallel-size 4" in lc.command

    def test_pipeline_parallel_flag(self):
        lc = build_launch_command(
            _cand(backend="vllm", pipeline_parallel=2, gpus_total=2),
            _spec(SOURCE_HF, "x/y"),
            context_length=4096,
        )
        assert "--pipeline-parallel-size 2" in lc.command

    def test_batch_flag(self):
        lc = build_launch_command(
            _cand(backend="vllm", effective_batch=8),
            _spec(SOURCE_HF, "x/y"),
            context_length=2048,
        )
        assert "--max-num-seqs 8" in lc.command

    def test_kv_quant_maps_to_fp8_with_q4_note(self):
        lc = build_launch_command(
            _cand(backend="vllm"),
            _spec(SOURCE_HF, "x/y"),
            context_length=2048,
            kv_quant="q4",
        )
        assert "--kv-cache-dtype fp8" in lc.command
        assert any("q4" in n and "fp8" in n for n in lc.notes)

    def test_gguf_quant_is_a_note_not_a_flag(self):
        lc = build_launch_command(
            _cand(backend="vllm", quant="Q4_K_M"),
            _spec(SOURCE_HF, "x/y"),
            context_length=2048,
        )
        assert "--quantization Q4_K_M" not in lc.command
        assert "Q4_K_M" not in lc.command
        assert any("Q4_K_M" in n and "GGUF" in n for n in lc.notes)

    def test_ollama_source_on_vllm_backend_is_placeholder(self):
        # A model resolved from Ollama can't be handed to `vllm serve` -- placeholder + note.
        lc = build_launch_command(
            _cand(backend="vllm", model="qwen3:14b"),
            _spec(SOURCE_OLLAMA, "qwen3:14b"),
            context_length=2048,
        )
        assert "<hf-repo>" in lc.command
        assert any("Hugging Face repo" in n for n in lc.notes)

    def test_fp16_has_no_quant_note(self):
        lc = build_launch_command(
            _cand(backend="vllm", quant="FP16"),
            _spec(SOURCE_HF, "x/y"),
            context_length=2048,
        )
        assert not any("GGUF" in n for n in lc.notes)


class TestOllama:
    def test_strips_ollama_prefix(self):
        lc = build_launch_command(
            _cand(backend="ollama", model="ollama:qwen3:14b"),
            _spec(SOURCE_OLLAMA, "ollama:qwen3:14b"),
            context_length=8192,
        )
        assert lc.command == "ollama run qwen3:14b"
        assert any("num_ctx 8192" in n for n in lc.notes)

    def test_batch_and_kv_env(self):
        lc = build_launch_command(
            _cand(backend="ollama", model="qwen3:14b", effective_batch=4),
            _spec(SOURCE_OLLAMA, "qwen3:14b"),
            context_length=2048,
            kv_quant="q8",
        )
        assert "OLLAMA_NUM_PARALLEL=4" in lc.env
        assert "OLLAMA_KV_CACHE_TYPE=q8_0" in lc.env
        assert "OLLAMA_FLASH_ATTENTION=1" in lc.env

    def test_hf_source_on_ollama_backend_is_placeholder(self):
        lc = build_launch_command(
            _cand(backend="ollama", model="Qwen/Qwen2.5-7B-Instruct"),
            _spec(SOURCE_HF, "Qwen/Qwen2.5-7B-Instruct"),
            context_length=2048,
        )
        assert "<ollama-tag>" in lc.command

    def test_multi_gpu_note(self):
        lc = build_launch_command(
            _cand(backend="ollama", model="qwen3:14b", gpus_total=4, tensor_parallel=4),
            _spec(SOURCE_OLLAMA, "qwen3:14b"),
            context_length=2048,
        )
        assert any("CUDA_VISIBLE_DEVICES" in n for n in lc.notes)


class TestTgi:
    def test_docker_shape(self):
        lc = build_launch_command(
            _cand(backend="tgi"),
            _spec(SOURCE_HF, "Qwen/Qwen2.5-7B-Instruct"),
            context_length=2048,
            prompt_tokens=512,
        )
        assert lc.command.startswith("docker run")
        assert "text-generation-inference" in lc.command
        assert "--model-id Qwen/Qwen2.5-7B-Instruct" in lc.command
        assert "--max-total-tokens 2048" in lc.command
        assert "--max-input-tokens 512" in lc.command

    def test_num_shard_for_tp(self):
        lc = build_launch_command(
            _cand(backend="tgi", tensor_parallel=2, gpus_total=2),
            _spec(SOURCE_HF, "x/y"),
            context_length=2048,
        )
        assert "--num-shard 2" in lc.command

    def test_pp_is_a_note(self):
        lc = build_launch_command(
            _cand(backend="tgi", pipeline_parallel=2, gpus_total=2),
            _spec(SOURCE_HF, "x/y"),
            context_length=2048,
        )
        assert any("pipeline-parallel" in n and "PP=2" in n for n in lc.notes)

    def test_kv_quant_fp8(self):
        lc = build_launch_command(
            _cand(backend="tgi"),
            _spec(SOURCE_HF, "x/y"),
            context_length=2048,
            kv_quant="q8",
        )
        assert "--kv-cache-dtype fp8_e5m2" in lc.command

    def test_max_input_capped_below_total(self):
        # prompt longer than the whole context -> clamp to context-1, never exceed total.
        lc = build_launch_command(
            _cand(backend="tgi"),
            _spec(SOURCE_HF, "x/y"),
            context_length=1024,
            prompt_tokens=99999,
        )
        assert "--max-input-tokens 1023" in lc.command


class TestGeneral:
    def test_registry_size_class_no_spec_is_placeholder(self):
        lc = build_launch_command(
            _cand(backend="vllm", model="llama3.1-8b"), None, context_length=2048
        )
        assert "<hf-repo>" in lc.command
        assert any("registry size-class" in n for n in lc.notes)

    def test_unknown_backend_raises(self):
        with pytest.raises(ValueError, match="no launch-command template"):
            build_launch_command(_cand(backend="tensorrt-llm"), context_length=2048)

    def test_to_dict_shape(self):
        lc = build_launch_command(
            _cand(backend="vllm"), _spec(SOURCE_HF, "x/y"), context_length=2048
        )
        d = lc.to_dict()
        assert set(d) == {"backend", "command", "env", "notes"}
        assert isinstance(d["env"], list) and isinstance(d["notes"], list)

    def test_returns_launch_command_type(self):
        lc = build_launch_command(_cand(), _spec(SOURCE_HF, "x/y"), context_length=2048)
        assert isinstance(lc, LaunchCommand)


class TestPlanCliLaunch:
    """`plan --launch` end-to-end, including the --json contract."""

    def _run(self, *args):
        from typer.testing import CliRunner

        from chimeraforge.cli import app

        return CliRunner().invoke(app, ["plan", *args])

    def test_human_output_shows_command(self):
        r = self._run("--model-size", "3b", "--launch")
        assert r.exit_code == 0
        assert "Launch command" in r.output

    def test_no_launch_flag_keeps_output_clean(self):
        r = self._run("--model-size", "3b")
        assert r.exit_code == 0
        assert "Launch command" not in r.output

    def test_json_contract_unchanged_without_flag(self):
        # Default --json must stay a bare array -- existing consumers depend on it.
        import json

        r = self._run("--model-size", "3b", "--json")
        assert r.exit_code == 0
        data = json.loads(r.output[r.output.index("[") : r.output.rindex("]") + 1])
        assert isinstance(data, list)

    def test_json_with_launch_is_one_wrapped_document(self):
        import json

        r = self._run("--model-size", "3b", "--json", "--launch")
        assert r.exit_code == 0
        data = json.loads(r.output[r.output.index("{") : r.output.rindex("}") + 1])
        assert set(data) == {"candidates", "launch"}
        assert isinstance(data["candidates"], list) and data["candidates"]
        assert set(data["launch"]) == {"backend", "command", "env", "notes"}
        assert data["launch"]["command"]

    def test_launch_on_empty_result_does_not_crash(self):
        # Impossible budget -> no candidates; --launch must degrade, not explode.
        r = self._run("--model-size", "3b", "--budget", "0.0001", "--launch")
        assert r.exit_code == 0
        assert "Launch command" not in r.output


class TestMcpLaunch:
    def test_plan_tool_surfaces_launch(self):
        from chimeraforge.mcp_server import plan_deployment

        r = plan_deployment(
            hardware="RTX 4090 24GB", model_size="8b", request_rate=2.0, budget_usd_month=5000
        )
        assert r["ok"]
        assert r["launch"] is not None
        assert set(r["launch"]) == {"backend", "command", "env", "notes"}
        assert r["launch"]["backend"] == r["recommended"]["backend"]
