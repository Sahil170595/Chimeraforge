#!/usr/bin/env python3
"""
TR119: Benchmark runner with resource telemetry for cost/energy analysis.

Reuses TR118's inference infrastructure but focuses on cost/energy telemetry.
This ensures parity with TR118's benchmark depth while adding cost/energy measurements.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
from pathlib import Path
import sys
import time
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Reuse TR118's infrastructure
from scripts.tr118.artifact_utils import resolve_repo_path
from scripts.tr118.run_benchmark import (
    _compute_seq_len,
    _init_tokenizer,
    _infer_ort,
    _infer_ort_logits,
    _infer_tensorrt,
    _infer_torch,
    _infer_torch_logits,
    _load_prompt_config,
    _maybe_build_trt,
    _maybe_export_onnx,
    _onnxruntime_session,
    _resolve_scenario,
    _to_numpy_inputs,
    _generate_uncached,
)

try:
    from scripts.tr117.instrumentation import ResourceMonitor  # type: ignore
except Exception:
    ResourceMonitor = None  # type: ignore

logger = logging.getLogger("tr119")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="TR119 benchmark runner with cost/energy telemetry")
    parser.add_argument(
        "--config",
        default="scripts/tr119/configs/baseline.yaml",
        help="TR119 config yaml",
    )
    parser.add_argument(
        "--prompt-config",
        default=None,
        help="Prompt config (TR117 tier3 by default)",
    )
    parser.add_argument(
        "--mode",
        choices=["prefill", "generate"],
        default=None,
        help="Benchmark mode: prefill forward-pass or uncached generation loop",
    )
    parser.add_argument(
        "--device",
        default="cuda",
        help="Device for PyTorch benchmarks (cpu/cuda)",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Optional run id used to name artifacts",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility (defaults to config or None)",
    )
    args = parser.parse_args()

    cfg_path = resolve_repo_path(_REPO_ROOT, str(args.config))
    cfg = _load_yaml(cfg_path)
    prompt_cfg_value = (
        args.prompt_config
        or os.getenv("BANTER_TR119_PROMPT_CONFIG")
        or cfg.get("benchmark", {}).get("prompt_config_path")
        or cfg.get("prompt_config_path")
        or "scripts/tr117/configs/matrix_tier3.yaml"
    )
    prompt_cfg_path = resolve_repo_path(_REPO_ROOT, str(prompt_cfg_value))
    prompt_sets, scenario_defs = _load_prompt_config(prompt_cfg_path)
    
    # Seed control for reproducibility (frontier lab requirement)
    seed = args.seed if args.seed is not None else cfg.get("benchmark", {}).get("seed", None)
    if seed is None:
        seed = cfg.get("seed", None)
    if seed is not None:
        import random
        import numpy as np
        random.seed(seed)
        np.random.seed(seed)
        try:
            import torch
            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)
        except Exception:
            pass
        logger.info("Random seed set to %d for reproducibility", seed)

    mode = str(args.mode or cfg.get("benchmark", {}).get("mode") or "prefill")
    results_root = resolve_repo_path(_REPO_ROOT, str(cfg["output"]["results_dir"]))
    raw_dir = results_root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    run_id = str(args.run_id).strip() if args.run_id is not None else str(int(time.time()))
    out_path = raw_dir / f"bench_tr119_{run_id}.jsonl"
    processed_dir = results_root / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    # TR119 configs may reference TR118-style model/onnx/tensorrt configs
    # For now, we'll use a simple model name and optionally export ONNX/TRT if backends require it
    model_name = cfg.get("model", {}).get("name", "gpt2")
    tokenizer = _init_tokenizer(model_name)
    if tokenizer is None:
        logger.error("Tokenizer required to run TR119 benchmark.")
        return 2

    # Export ONNX / build TRT if needed (reuse TR118's logic)
    # TR119 configs can include onnx/tensorrt sections if needed
    export_path = None
    export_meta = None
    engines = {}
    trt_build_meta = []
    
    # Check if any backends need ONNX/TRT
    backends = [str(b) for b in cfg.get("benchmark", {}).get("backends", [])]
    needs_onnx = any(b.startswith("onnxruntime") or b.startswith("tensorrt") for b in backends)
    needs_trt = any(b.startswith("tensorrt") for b in backends)
    
    if needs_onnx:
        # Create a minimal TR118-style config for ONNX/TRT export
        tr118_cfg = {
            "model": {"name": model_name},
            "onnx": cfg.get("onnx", {
                "opset_version": 17,
                "dynamic_axes": True,
                "trt_friendly_inputs": True,
            }),
            "tensorrt": cfg.get("tensorrt", {
                "precisions": ["fp16"],
                "workspace_gb": 4,
                "dynamic_shapes": {"enabled": False},
            }),
            "output": {
                "onnx_dir": str(results_root / "artifacts" / "onnx"),
                "tensorrt_dir": str(results_root / "artifacts" / "tensorrt"),
            },
        }
        export_meta_path = processed_dir / f"export_metadata_{run_id}.json"
        trt_build_meta_path = processed_dir / f"trt_build_metadata_{run_id}.json"
        export_path, export_meta = _maybe_export_onnx(tr118_cfg, meta_path=export_meta_path)
        if export_path and export_path.exists() and needs_trt:
            engines, trt_build_meta = _maybe_build_trt(tr118_cfg, export_path, meta_path=trt_build_meta_path)

    max_seq_len = int(cfg.get("benchmark", {}).get("max_seq_len", 512) or 512)
    repetitions = int(cfg.get("benchmark", {}).get("repetitions", 1) or 1)
    warmup_runs = int(cfg.get("benchmark", {}).get("warmup_runs", 0) or 0)
    timeout_s = float(cfg.get("benchmark", {}).get("timeout_s", 0) or 0)
    max_new_tokens = int(cfg.get("benchmark", {}).get("max_new_tokens", 8) or 8)
    stop_on_eos = bool(cfg.get("benchmark", {}).get("stop_on_eos", True))
    
    # TR119-specific: telemetry config
    enable_resource = bool(cfg.get("telemetry", {}).get("enable_gpu", True) or cfg.get("telemetry", {}).get("enable_cpu", True))
    sample_interval = float(cfg.get("telemetry", {}).get("sample_interval_s", 0.25) or 0.25)
    resource_monitor_available = enable_resource and ResourceMonitor is not None

    vocab_size = int(getattr(tokenizer, "vocab_size", 50257) or 50257)
    min_seq_len = int(cfg.get("benchmark", {}).get("min_seq_len", 1) or 1)

    # Initialize backends (reuse TR118's logic)
    backend_init_meta: dict[str, dict[str, Any]] = {}
    
    # ORT sessions
    ort_sessions: dict[str, dict[str, Any]] = {}
    if export_path and export_path.exists():
        for backend_name, providers in [
            ("onnxruntime-cpu", ["CPUExecutionProvider"]),
            ("onnxruntime-gpu", ["CUDAExecutionProvider", "CPUExecutionProvider"]),
        ]:
            if backend_name in backends:
                try:
                    start = time.perf_counter()
                    session, input_type, used = _onnxruntime_session(export_path, providers)
                    init_ms = (time.perf_counter() - start) * 1000
                    if backend_name.endswith("-gpu") and "CUDAExecutionProvider" not in used:
                        backend_init_meta[backend_name] = {
                            "backend": backend_name,
                            "init_ms": init_ms,
                            "providers": used,
                            "input_type": input_type,
                            "error": "cuda_provider_unavailable",
                        }
                    else:
                        ort_sessions[backend_name] = {
                            "session": session,
                            "input_type": input_type,
                            "providers": used,
                        }
                        backend_init_meta[backend_name] = {
                            "backend": backend_name,
                            "init_ms": init_ms,
                            "providers": used,
                            "input_type": input_type,
                        }
                except Exception as exc:
                    backend_init_meta[backend_name] = {
                        "backend": backend_name,
                        "error": str(exc),
                    }

    # PyTorch models (lazy-loaded per backend/scenario) - reuse TR118's pattern
    torch_available = False
    torch_mod = None
    torch_model_cls = None
    try:
        import torch  # type: ignore
        from transformers import AutoModelForCausalLM  # type: ignore
        torch_available = True
        torch_mod = torch
        torch_model_cls = AutoModelForCausalLM
    except Exception:
        pass

    import platform
    def _default_torch_compile_backend() -> str | None:
        """Pick a safe torch.compile backend (reuse TR118's logic)."""
        override = os.getenv("BANTER_TR118_TORCH_COMPILE_BACKEND", "").strip()
        if override:
            return override
        if platform.system() == "Windows":
            return "cudagraphs"
        return None

    torch_compile_backend = _default_torch_compile_backend()
    torch_cache: dict[tuple[str, bool, int, int], dict[str, Any]] = {}

    def get_torch_runner(device: str, compile_model: bool, batch_size: int, seq_len: int, model_name: str) -> dict[str, Any] | None:
        """Lazy-load PyTorch models (reuse TR118's pattern)."""
        if not torch_available or torch_mod is None or torch_model_cls is None:
            return None
        key = (device, compile_model, 0, 0)
        if compile_model:
            key = (device, compile_model, int(batch_size), int(seq_len))
        if key in torch_cache:
            return torch_cache[key]
        start = time.perf_counter()
        model = torch_model_cls.from_pretrained(model_name, torch_dtype=torch_mod.float32)
        model.eval()
        model.to(device)
        init_ms = (time.perf_counter() - start) * 1000
        compile_ms = None
        compile_error = None
        compile_backend = None
        if compile_model and hasattr(torch_mod, "compile"):
            try:
                start_compile = time.perf_counter()
                compile_backend = torch_compile_backend
                if compile_backend:
                    model = torch_mod.compile(  # type: ignore[attr-defined]
                        model, backend=compile_backend, dynamic=False
                    )
                else:
                    model = torch_mod.compile(model, dynamic=False)  # type: ignore[attr-defined]
                compile_ms = (time.perf_counter() - start_compile) * 1000
            except Exception as exc:
                compile_error = f"{type(exc).__name__}: {exc}"
                logger.warning("torch.compile failed; continuing without compile: %s", compile_error)
        runner_info = {
            "model": model,
            "device": device,
            "compile": compile_model,
            "compile_backend": compile_backend,
            "init_ms": init_ms,
            "compile_ms": compile_ms,
            "compile_error": compile_error,
        }
        torch_cache[key] = runner_info
        return runner_info

    # TensorRT runners (lazy-loaded) - reuse TR118's pattern
    trt_runners: dict[str, Any] = {}

    def get_trt_runner_for_precision(precision: str):
        """Lazy-load TensorRT runners (reuse TR118's pattern)."""
        if precision in trt_runners:
            return trt_runners[precision]
        if precision not in engines or not engines[precision].exists():
            return None
        try:
            from scripts.tr118.trt_inference import TensorRTInferenceEngine
            runner = TensorRTInferenceEngine(engines[precision])
            trt_runners[precision] = runner
            return runner
        except Exception as exc:
            logger.warning("TensorRT runner init failed for %s: %s", precision, exc)
            return None

    def run_one_backend_scenario(backend: str, scenario: str, rep: int) -> dict[str, Any]:
        prompt_set, prompts, batch_size = _resolve_scenario(scenario, prompt_sets, scenario_defs)
        if not prompts:
            return {
                "spec": {
                    "tr": "TR119",
                    "backend": backend,
                    "scenario": scenario,
                    "repetition": rep,
                    "device": args.device,
                    "mode": mode,
                },
                "status": "skipped",
                "error": "scenario_not_found",
                "latencies_ms": [],
                "throughput_tok_s": [],
                "warmup_latencies_ms": [],
                "degraded_count": 0,
                "resource_metrics": None,
            }

        seq_len = _compute_seq_len(tokenizer, prompts, max_len=max_seq_len, min_len=min_seq_len)
        if mode == "generate":
            prompt_len = _compute_seq_len(tokenizer, prompts, max_len=max_seq_len, min_len=min_seq_len)
            seq_len = min(max(prompt_len + max_new_tokens, min_seq_len), max_seq_len)

        spec = {
            "tr": "TR119",
            "backend": backend,
            "scenario": scenario,
            "repetition": rep,
            "device": args.device,
            "mode": mode,
            "batch_size": batch_size,
            "seq_len": seq_len,
        }

        latencies: list[float] = []
        throughput: list[float] = []
        warmups: list[float] = []
        degraded = 0
        degraded_reasons: list[str] = []
        status = "ok"
        error = None
        resource_metrics = None

        with contextlib.ExitStack() as stack:
            monitor = None
            if enable_resource and ResourceMonitor is not None and resource_monitor_available:
                try:
                    monitor = stack.enter_context(ResourceMonitor(sample_interval_s=sample_interval))
                except Exception as exc:
                    logger.warning("ResourceMonitor unavailable; disabling: %s", exc)
                    monitor = None

            prepared_trt = None
            trt_runner = None
            if backend.startswith("tensorrt"):
                precision = backend.split("-")[-1] if "-" in backend else "fp16"
                trt_runner = get_trt_runner_for_precision(precision)
                if trt_runner is not None:
                    prepared_trt = trt_runner.prepare(batch=batch_size, seq=seq_len, vocab_size=vocab_size)

            # Warmups
            warm_prompt = prompts[0] if prompts else ""
            for _ in range(warmup_runs):
                try:
                    if backend.startswith("onnxruntime"):
                        sess_info = ort_sessions.get(backend)
                        sess = sess_info["session"] if sess_info else None
                        if sess is None:
                            continue
                        ms, _tok = _infer_ort(
                            sess, str(sess_info.get("input_type", "int64")), tokenizer, warm_prompt, seq_len, batch_size
                        )
                        warmups.append(ms)
                    elif backend.startswith("tensorrt"):
                        if trt_runner is None or prepared_trt is None:
                            continue
                        ms, _tok, _d, _r = _infer_tensorrt(
                            trt_runner, prepared_trt, tokenizer, warm_prompt, seq_len, batch_size
                        )
                        warmups.append(ms)
                    elif backend.startswith("transformers"):
                        if not torch_available or torch_mod is None:
                            continue
                        if "gpu" in backend and not torch_mod.cuda.is_available():
                            continue
                        device = "cuda" if "gpu" in backend else "cpu"
                        compile_model = "compile" in backend
                        runner = get_torch_runner(
                            device=device, compile_model=compile_model, batch_size=batch_size, seq_len=seq_len, model_name=model_name
                        )
                        if runner is None:
                            continue
                        ms, _tok, _d, _r = _infer_torch(
                            runner["model"], tokenizer, warm_prompt, seq_len, batch_size, device
                        )
                        warmups.append(ms)
                except Exception:
                    continue

            # Actual benchmark runs
            for prompt in prompts:
                try:
                    if mode == "generate":
                        # Generate mode (uncached loop)
                        if backend.startswith("onnxruntime"):
                            sess_info = ort_sessions.get(backend)
                            sess = sess_info["session"] if sess_info else None
                            if sess is None:
                                degraded += 1
                                degraded_reasons.append("ort_session_missing")
                                continue

                            def _infer_logits(ids, mask):
                                return _infer_ort_logits(
                                    sess,
                                    str(sess_info.get("input_type", "int64")),
                                    ids,
                                    mask,
                                )

                            total_ms, ttft_ms, toks, out_text, is_deg, reason = _generate_uncached(
                                _infer_logits,
                                tokenizer,
                                prompt,
                                seq_len,
                                batch_size,
                                max_new_tokens,
                                stop_on_eos,
                                timeout_s,
                            )
                            if is_deg:
                                degraded += 1
                                degraded_reasons.append(reason or "generate_failed")
                                continue
                            latencies.append(total_ms)
                            throughput.append(toks / (total_ms / 1000.0) if total_ms > 0 else 0.0)
                            continue

                        if backend.startswith("tensorrt"):
                            if trt_runner is None or prepared_trt is None:
                                degraded += 1
                                degraded_reasons.append("trt_engine_missing")
                                continue

                            def _infer_logits(ids, mask):
                                return trt_runner.infer(prepared_trt, ids, mask)

                            total_ms, ttft_ms, toks, out_text, is_deg, reason = _generate_uncached(
                                _infer_logits,
                                tokenizer,
                                prompt,
                                seq_len,
                                batch_size,
                                max_new_tokens,
                                stop_on_eos,
                                timeout_s,
                            )
                            if is_deg:
                                degraded += 1
                                degraded_reasons.append(reason or "generate_failed")
                                continue
                            latencies.append(total_ms)
                            throughput.append(toks / (total_ms / 1000.0) if total_ms > 0 else 0.0)
                            continue

                        if backend.startswith("transformers"):
                            if not torch_available or torch_mod is None:
                                degraded += 1
                                degraded_reasons.append("torch_unavailable")
                                continue
                            if "gpu" in backend and not torch_mod.cuda.is_available():
                                degraded += 1
                                degraded_reasons.append("cuda_unavailable")
                                continue
                            device = "cuda" if "gpu" in backend else "cpu"
                            compile_model = "compile" in backend
                            runner = get_torch_runner(
                                device=device, compile_model=compile_model, batch_size=batch_size, seq_len=seq_len, model_name=model_name
                            )
                            if runner is None:
                                degraded += 1
                                degraded_reasons.append("torch_runner_unavailable")
                                continue

                            def _infer_logits(ids, mask):
                                ms, logits, is_deg, reason = _infer_torch_logits(
                                    runner["model"], ids, mask, device
                                )
                                if is_deg:
                                    raise RuntimeError(reason or "torch_infer_failed")
                                return ms, logits

                            total_ms, ttft_ms, toks, out_text, is_deg, reason = _generate_uncached(
                                _infer_logits,
                                tokenizer,
                                prompt,
                                seq_len,
                                batch_size,
                                max_new_tokens,
                                stop_on_eos,
                                timeout_s,
                            )
                            if is_deg:
                                degraded += 1
                                degraded_reasons.append(reason or "generate_failed")
                                continue
                            latencies.append(total_ms)
                            throughput.append(toks / (total_ms / 1000.0) if total_ms > 0 else 0.0)
                            continue

                        degraded += 1
                        degraded_reasons.append("unsupported_backend_for_generate")
                        continue

                    # Prefill mode
                    if backend.startswith("onnxruntime"):
                        sess_info = ort_sessions.get(backend)
                        sess = sess_info["session"] if sess_info else None
                        if sess is None:
                            degraded += 1
                            degraded_reasons.append("ort_session_missing")
                            continue
                        ms, _tok = _infer_ort(
                            sess, str(sess_info.get("input_type", "int64")), tokenizer, prompt, seq_len, batch_size
                        )
                        if timeout_s > 0 and ms > timeout_s * 1000:
                            degraded += 1
                            degraded_reasons.append("timeout")
                            continue
                        latencies.append(ms)
                        tokens = batch_size * seq_len
                        throughput.append(tokens / (ms / 1000.0) if ms > 0 else 0.0)
                    elif backend.startswith("tensorrt"):
                        if trt_runner is None or prepared_trt is None:
                            degraded += 1
                            degraded_reasons.append("trt_engine_missing")
                            continue
                        ms, _tok, is_deg, reason = _infer_tensorrt(
                            trt_runner, prepared_trt, tokenizer, prompt, seq_len, batch_size
                        )
                        if timeout_s > 0 and ms > timeout_s * 1000:
                            degraded += 1
                            degraded_reasons.append("timeout")
                            continue
                        if is_deg:
                            degraded += 1
                            degraded_reasons.append(reason or "trt_infer_failed")
                            continue
                        latencies.append(ms)
                        tokens = batch_size * seq_len
                        throughput.append(tokens / (ms / 1000.0) if ms > 0 else 0.0)
                    elif backend.startswith("transformers"):
                        if not torch_available or torch_mod is None:
                            degraded += 1
                            degraded_reasons.append("torch_unavailable")
                            continue
                        if "gpu" in backend and not torch_mod.cuda.is_available():
                            degraded += 1
                            degraded_reasons.append("cuda_unavailable")
                            continue
                        device = "cuda" if "gpu" in backend else "cpu"
                        compile_model = "compile" in backend
                        runner = get_torch_runner(
                            device=device, compile_model=compile_model, batch_size=batch_size, seq_len=seq_len, model_name=model_name
                        )
                        if runner is None:
                            degraded += 1
                            degraded_reasons.append("torch_runner_unavailable")
                            continue
                        ms, _tok, is_deg, reason = _infer_torch(
                            runner["model"], tokenizer, prompt, seq_len, batch_size, device
                        )
                        if timeout_s > 0 and ms > timeout_s * 1000:
                            degraded += 1
                            degraded_reasons.append("timeout")
                            continue
                        if is_deg:
                            degraded += 1
                            degraded_reasons.append(reason or "torch_infer_failed")
                            continue
                        latencies.append(ms)
                        tokens = batch_size * seq_len
                        throughput.append(tokens / (ms / 1000.0) if ms > 0 else 0.0)
                    else:
                        degraded += 1
                        degraded_reasons.append("unsupported_backend")
                except Exception as exc:
                    degraded += 1
                    degraded_reasons.append(f"exception:{type(exc).__name__}:{exc}")

        if enable_resource and ResourceMonitor is not None and monitor is not None:
            try:
                resource_metrics = monitor.get_metrics()  # type: ignore[union-attr]
            except Exception:
                resource_metrics = None

        if degraded > 0:
            status = "degraded"
            uniq = ", ".join(sorted(set(degraded_reasons))) if degraded_reasons else "unknown"
            error = f"{degraded} degraded: {uniq}"

        return {
            "spec": spec,
            "status": status,
            "error": error,
            "latencies_ms": latencies,
            "throughput_tok_s": throughput,
            "warmup_latencies_ms": warmups,
            "degraded_count": degraded,
            "degraded_reasons": degraded_reasons,
            "resource_metrics": resource_metrics,
            "backend_metadata": backend_init_meta.get(backend) or {"backend": backend},
        }

    with out_path.open("w", encoding="utf-8") as f:
        for backend in backends:
            backend = str(backend)
            for scenario in cfg.get("benchmark", {}).get("scenarios", []):
                scenario = str(scenario)
                for rep in range(repetitions):
                    try:
                        result = run_one_backend_scenario(backend, scenario, rep)
                    except Exception as exc:
                        result = {
                            "spec": {
                                "tr": "TR119",
                                "backend": backend,
                                "scenario": scenario,
                                "repetition": rep,
                                "device": args.device,
                                "mode": mode,
                            },
                            "status": "error",
                            "error": str(exc),
                            "latencies_ms": [],
                            "throughput_tok_s": [],
                            "warmup_latencies_ms": [],
                            "degraded_count": 1,
                            "degraded_reasons": [f"exception:{type(exc).__name__}:{exc}"],
                        }
                    f.write(json.dumps(result) + "\n")

    logger.info("TR119 raw results written to %s", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
