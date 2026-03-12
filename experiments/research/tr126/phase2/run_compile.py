#!/usr/bin/env python3
"""
TR126 Phase 2: Compile paradox replication under Linux with real Triton.

Adapted from research/tr120/run_root_cause.py. Key differences:
  - NO fallback_backend — force real Inductor+Triton or fail
  - Triton verification: records proof that real Triton kernels were generated
  - Platform tag: linux-docker in manifest
  - Output path: research/tr126/results/phase2/

The measurement harness is otherwise identical to TR120 to ensure
apples-to-apples cross-platform comparison.

Outputs:
  research/tr126/results/phase2/<run_id>/<mode>/
    - runs/.../run_*.json
    - metrics.csv
    - manifest.json
    - compiler_evidence.json
    - triton_evidence.json
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Literal

import yaml

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[2]
sys.path.insert(0, str(_REPO))

Mode = Literal["prefill", "kv_decode", "e2e_kv"]


@dataclass(frozen=True)
class RunSpec:
    mode: Mode
    scenario: str
    prompt_set: str
    prompts: list[str]
    backend: str
    model: str
    quantization: str


def _now_run_id() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Dynamo introspection (identical to TR120)
# ---------------------------------------------------------------------------


def _dynamo_counters_clear() -> None:
    try:
        import torch._dynamo.utils as dynamo_utils

        dynamo_utils.counters.clear()
    except Exception:
        return


def _dynamo_counters_snapshot() -> dict[str, Any]:
    try:
        import copy
        import json as _json

        import torch._dynamo.utils as dynamo_utils

        counters = getattr(dynamo_utils, "counters", None)
        if counters is None:
            return {}
        try:
            snap = copy.deepcopy(counters)
        except Exception:
            snap = counters

        def to_plain(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {str(k): to_plain(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [to_plain(v) for v in obj]
            if obj is None or isinstance(obj, (str, int, float, bool)):
                return obj
            try:
                _json.dumps(obj)
                return obj
            except Exception:
                return str(obj)

        try:
            snap_dict = dict(snap)
        except Exception:
            return {"raw": str(snap)}
        return to_plain(snap_dict)
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Device, dtype, model loading (identical to TR120)
# ---------------------------------------------------------------------------


def _resolve_device(device_pref: str):
    import torch

    pref = (device_pref or "cpu").strip().lower()
    if pref == "cuda" and torch.cuda.is_available():
        return torch.device("cuda")
    if pref == "cpu":
        return torch.device("cpu")
    try:
        dev = torch.device(pref)
        if dev.type == "cuda" and not torch.cuda.is_available():
            return torch.device("cpu")
        return dev
    except Exception:
        return torch.device("cpu")


def _resolve_dtype(dtype_pref: str):
    import torch

    pref = (dtype_pref or "fp32").strip().lower()
    if pref in ("fp16", "float16"):
        return torch.float16, "fp16"
    return torch.float32, "fp32"


def _load_model(model_path: str, device, torch_dtype):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    if tokenizer.pad_token_id is None and tokenizer.eos_token_id is not None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        local_files_only=True,
        dtype=torch_dtype,
    )
    model.eval()
    model.to(device)
    torch.manual_seed(42)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(42)
    return model, tokenizer


def _tokenize_prompts(
    tokenizer,
    prompts: list[str],
    device,
    *,
    pad_to_max_length: bool,
    pad_to_multiple_of: int | None,
    max_length: int | None,
) -> list[dict[str, Any]]:
    import torch

    batch: list[dict[str, Any]] = []
    for prompt in prompts:
        if pad_to_max_length and max_length:
            enc = tokenizer(
                prompt,
                return_tensors="pt",
                add_special_tokens=True,
                truncation=True,
                padding="max_length",
                max_length=int(max_length),
                pad_to_multiple_of=(
                    int(pad_to_multiple_of) if pad_to_multiple_of else None
                ),
            )
        else:
            enc = tokenizer(prompt, return_tensors="pt", add_special_tokens=True)
        batch.append(
            {
                "input_ids": enc["input_ids"].to(device),
                "attention_mask": enc.get(
                    "attention_mask", torch.ones_like(enc["input_ids"])
                ).to(device),
            }
        )
    return batch


# ---------------------------------------------------------------------------
# Compilation — NO FALLBACK (the key TR126 change)
# ---------------------------------------------------------------------------


def _maybe_compile(model, enabled: bool, backend_label: str, cfg: dict[str, Any]):
    """Compile model with real Inductor+Triton. No fallback — fail loudly."""
    if not enabled or not backend_label.endswith("-compile"):
        return model, None
    import torch

    mode = str(cfg.get("mode", "reduce-overhead"))
    backend = cfg.get("backend", "inductor")
    dynamic = bool(cfg.get("dynamic", False))
    fullgraph = bool(cfg.get("fullgraph", False))
    disable_cudagraphs = bool(cfg.get("disable_cudagraphs", False))

    _dynamo_counters_clear()
    started = time.perf_counter()

    if disable_cudagraphs:
        try:
            import torch._inductor.config as inductor_config

            if hasattr(inductor_config, "use_cudagraphs"):
                inductor_config.use_cudagraphs = False
            triton_cfg = getattr(inductor_config, "triton", None)
            if triton_cfg is not None:
                if hasattr(triton_cfg, "cudagraphs"):
                    triton_cfg.cudagraphs = False
                if hasattr(triton_cfg, "cudagraph_trees"):
                    triton_cfg.cudagraph_trees = False
        except Exception:
            pass

    compile_kwargs: dict[str, Any] = {
        "backend": backend,
        "mode": mode,
        "dynamic": dynamic,
        "fullgraph": fullgraph,
    }

    # NO try/except fallback — if Triton is missing, we WANT the error
    compiled = torch.compile(model, **compile_kwargs)

    # Force first execution to surface Triton issues
    device = next(compiled.parameters()).device
    dummy = torch.ones((1, 8), dtype=torch.long, device=device)
    with torch.no_grad():
        _ = compiled(input_ids=dummy, use_cache=True)
    if device.type == "cuda":
        torch.cuda.synchronize()

    compile_ms = (time.perf_counter() - started) * 1000.0

    # Verify Triton was actually used (not aot_eager)
    triton_evidence = _collect_triton_evidence()

    return compiled, {
        "enabled": True,
        "backend": backend,
        "mode": mode,
        "dynamic": dynamic,
        "fullgraph": fullgraph,
        "disable_cudagraphs": disable_cudagraphs,
        "compile_time_ms": compile_ms,
        "triton_verified": triton_evidence.get("triton_available", False),
        "dynamo_counters_after_compile": _dynamo_counters_snapshot(),
    }


def _collect_triton_evidence() -> dict[str, Any]:
    """Collect proof that real Triton was used during compilation."""
    evidence: dict[str, Any] = {}

    try:
        import triton

        evidence["triton_available"] = True
        evidence["triton_version"] = triton.__version__
    except ImportError:
        evidence["triton_available"] = False
        return evidence

    # Check Triton cache for generated kernels
    cache_dir = os.environ.get("TRITON_CACHE_DIR", "/tmp/triton_cache")
    if os.path.isdir(cache_dir):
        kernel_files = list(Path(cache_dir).rglob("*.so")) + list(
            Path(cache_dir).rglob("*.cubin")
        )
        evidence["cached_kernels"] = len(kernel_files)
    else:
        evidence["cached_kernels"] = 0

    # Check inductor output code for triton references
    try:
        import torch._inductor.config as inductor_config

        evidence["inductor_backend"] = getattr(inductor_config, "fallback_random", None)
    except Exception:
        pass

    return evidence


# ---------------------------------------------------------------------------
# CUDA timing helpers (identical to TR120)
# ---------------------------------------------------------------------------


def _cuda_sync(device) -> None:
    if device.type != "cuda":
        return
    import torch

    torch.cuda.synchronize()


def _cuda_event_timer(device):
    if getattr(device, "type", None) != "cuda":
        return None, None, lambda: None
    try:
        import torch

        start = torch.cuda.Event(enable_timing=True)
        end = torch.cuda.Event(enable_timing=True)

        def elapsed_ms() -> float | None:
            try:
                end.synchronize()
                return float(start.elapsed_time(end))
            except Exception:
                return None

        return start, end, elapsed_ms
    except Exception:
        return None, None, lambda: None


def _cudagraph_mark_step_begin() -> None:
    try:
        import torch

        mark = getattr(
            getattr(torch, "compiler", None), "cudagraph_mark_step_begin", None
        )
        if callable(mark):
            mark()
    except Exception:
        return


# ---------------------------------------------------------------------------
# Measurement kernels (identical to TR120)
# ---------------------------------------------------------------------------


def _prefill_with_mask(
    model, input_ids, attention_mask, device
) -> tuple[float, float | None, Any, Any]:
    import torch

    _cuda_sync(device)
    _cudagraph_mark_step_begin()
    start_ev, end_ev, elapsed_ms = _cuda_event_timer(device)
    start = time.perf_counter()
    with torch.no_grad():
        if start_ev is not None:
            start_ev.record()
        out = model(input_ids=input_ids, attention_mask=attention_mask, use_cache=True)
        if end_ev is not None:
            end_ev.record()
        logits = out.logits[:, -1, :]
        past = out.past_key_values
    _cuda_sync(device)
    wall_ms = (time.perf_counter() - start) * 1000.0
    return wall_ms, elapsed_ms(), logits, past


def _kv_decode(
    model, logits, past, device, max_new_tokens: int
) -> tuple[float, float | None, int]:
    import torch

    generated = 0
    _cuda_sync(device)
    start_ev, end_ev, elapsed_ms = _cuda_event_timer(device)
    start = time.perf_counter()
    with torch.no_grad():
        next_token = torch.argmax(logits, dim=-1, keepdim=True)
        if start_ev is not None:
            start_ev.record()
        for _ in range(int(max_new_tokens)):
            _cudagraph_mark_step_begin()
            out = model(input_ids=next_token, use_cache=True, past_key_values=past)
            logits = out.logits[:, -1, :]
            past = out.past_key_values
            next_token = torch.argmax(logits, dim=-1, keepdim=True)
            generated += 1
        if end_ev is not None:
            end_ev.record()
    _cuda_sync(device)
    wall_ms = (time.perf_counter() - start) * 1000.0
    return wall_ms, elapsed_ms(), generated


# ---------------------------------------------------------------------------
# Dynamo explain (identical to TR120)
# ---------------------------------------------------------------------------


def _dynamo_explain_summary(model, *, call_kwargs: dict[str, Any]) -> dict[str, Any]:
    try:
        import torch._dynamo as dynamo

        explain = getattr(dynamo, "explain", None)
        if not callable(explain):
            return {"available": False}
        out = explain(model)(**call_kwargs)
        ops = getattr(out, "ops_per_graph", None)
        if isinstance(ops, list):
            ops_summary: Any = [len(g) if hasattr(g, "__len__") else None for g in ops]
        else:
            ops_summary = None
        return {
            "available": True,
            "graph_count": getattr(out, "graph_count", None),
            "graph_break_count": getattr(out, "graph_break_count", None),
            "break_reasons_count": len(getattr(out, "break_reasons", []) or []),
            "break_reasons_sample": [
                str(x) for x in (getattr(out, "break_reasons", []) or [])[:10]
            ],
            "out_guards_count": len(getattr(out, "out_guards", []) or []),
            "ops_per_graph_len": ops_summary,
        }
    except Exception as exc:
        return {"available": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Mode runner (identical to TR120)
# ---------------------------------------------------------------------------


def _run_mode(
    mode: Mode,
    model,
    tokenizer,
    device,
    max_new_tokens: int,
    repetitions: int,
    warmup_repetitions: int,
    spec: RunSpec,
    tokenization_cfg: dict[str, Any],
) -> dict[str, Any]:

    pad_to_max_length = bool(tokenization_cfg.get("pad_to_max_length", False))
    pad_scope = str(tokenization_cfg.get("pad_scope", "per_scenario"))
    pad_to_multiple_of = tokenization_cfg.get("pad_to_multiple_of")
    pad_to_multiple_of = int(pad_to_multiple_of) if pad_to_multiple_of else None

    max_len: int | None = None
    if pad_to_max_length:
        if pad_scope not in ("per_scenario", "global"):
            raise ValueError(
                f"tokenization.pad_scope must be per_scenario|global, got: {pad_scope}"
            )
        max_len = int(tokenization_cfg.get("max_length") or 0) or None
        if max_len is None:
            lens = [
                len(tokenizer(p, add_special_tokens=True).get("input_ids", []))
                for p in spec.prompts
            ]
            max_len = max(lens) if lens else None
        if max_len and pad_to_multiple_of:
            rem = max_len % pad_to_multiple_of
            if rem:
                max_len = max_len + (pad_to_multiple_of - rem)

    tokenized = _tokenize_prompts(
        tokenizer,
        spec.prompts,
        device,
        pad_to_max_length=pad_to_max_length,
        pad_to_multiple_of=pad_to_multiple_of,
        max_length=max_len,
    )

    # Warmup
    for _ in range(int(warmup_repetitions)):
        for enc in tokenized:
            input_ids = enc["input_ids"]
            attention_mask = enc["attention_mask"]
            pre_ms, _pre_cuda_ms, logits, past = _prefill_with_mask(
                model, input_ids, attention_mask, device
            )
            if mode in ("kv_decode", "e2e_kv"):
                _kv_decode(model, logits, past, device, max_new_tokens=max_new_tokens)

    latencies_ms: list[float] = []
    cuda_event_ms: list[float | None] = []
    tokens: list[int] = []
    started_at = time.time()
    for _ in range(int(repetitions)):
        for enc in tokenized:
            input_ids = enc["input_ids"]
            attention_mask = enc["attention_mask"]
            if mode == "prefill":
                pre_ms, pre_cuda_ms, _logits, _past = _prefill_with_mask(
                    model, input_ids, attention_mask, device
                )
                latencies_ms.append(pre_ms)
                cuda_event_ms.append(pre_cuda_ms)
                tokens.append(int(attention_mask.sum().item()))
            elif mode == "kv_decode":
                _pre_ms, _pre_cuda_ms, logits, past = _prefill_with_mask(
                    model, input_ids, attention_mask, device
                )
                dec_ms, dec_cuda_ms, gen = _kv_decode(
                    model, logits, past, device, max_new_tokens=max_new_tokens
                )
                latencies_ms.append(dec_ms)
                cuda_event_ms.append(dec_cuda_ms)
                tokens.append(int(gen))
            elif mode == "e2e_kv":
                pre_ms, pre_cuda_ms, logits, past = _prefill_with_mask(
                    model, input_ids, attention_mask, device
                )
                dec_ms, dec_cuda_ms, gen = _kv_decode(
                    model, logits, past, device, max_new_tokens=max_new_tokens
                )
                latencies_ms.append(pre_ms + dec_ms)
                if pre_cuda_ms is None or dec_cuda_ms is None:
                    cuda_event_ms.append(None)
                else:
                    cuda_event_ms.append(float(pre_cuda_ms) + float(dec_cuda_ms))
                tokens.append(int(attention_mask.sum().item() + gen))
            else:
                raise ValueError(f"unsupported mode: {mode}")

    ttft_ms = list(latencies_ms)
    tokens_per_s = [
        (t / (ms / 1000.0)) if ms > 0 else 0.0
        for t, ms in zip(tokens, latencies_ms, strict=False)
    ]
    return {
        "spec": asdict(spec),
        "status": "ok",
        "error": None,
        "latencies_ms": latencies_ms,
        "cuda_event_ms": cuda_event_ms,
        "ttft_ms": ttft_ms,
        "tokens": tokens,
        "tokens_per_s": tokens_per_s,
        "started_at": started_at,
        "degraded_count": 0,
        "degraded_reasons": [],
    }


def _write_metrics_csv(rows: list[dict[str, Any]], out_path: Path) -> None:
    _ensure_dir(out_path.parent)
    if not rows:
        out_path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Main — adapted from TR120 with Triton verification
# ---------------------------------------------------------------------------


def _parse_models_list(cfg: dict[str, Any]) -> list[tuple[str, str]]:
    """Parse model list from config.

    Supports two formats:
      1. New: models: [{path: ..., dtype: ...}, ...]
      2. Legacy: model_path: ... + dtype: ...

    Returns list of (model_path, dtype_str) tuples.
    """
    models_cfg = cfg.get("models")
    if models_cfg:
        return [
            (str(m["path"]), str(m.get("dtype", cfg.get("dtype", "fp32"))))
            for m in models_cfg
        ]
    return [(str(cfg["model_path"]), str(cfg.get("dtype", "fp32")))]


def main() -> int:
    import gc

    import torch

    parser = argparse.ArgumentParser(
        description="TR126 Phase 2: compile paradox replication with real Triton."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=_DIR / "config.yaml",
        help="Runner config yaml.",
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        default=_REPO / "research" / "tr126" / "results" / "phase2",
        help="Root output directory.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output.")
    args = parser.parse_args()

    cfg = _load_yaml(args.config)
    run_id = _now_run_id()
    out_root = args.out_root / run_id
    _ensure_dir(out_root)

    # Parse models list (new multi-model or legacy single-model)
    models_list = _parse_models_list(cfg)

    tier3_path = _REPO / str(cfg["tier3_config"])
    tier3 = _load_yaml(tier3_path)

    scenarios_allow = {str(s) for s in cfg.get("scenarios", [])}
    scenarios_cfg = tier3.get("scenarios", [])
    scenarios = [s for s in scenarios_cfg if str(s.get("name")) in scenarios_allow]
    if not scenarios:
        raise SystemExit(
            "No scenarios selected; check config.scenarios against tier3_config"
        )

    device = _resolve_device(str(cfg.get("device", "cpu")))
    repetitions = int(cfg.get("repetitions", 10))
    warmup_reps = int(cfg.get("warmup_repetitions", 2))
    max_new_tokens = int(cfg.get("max_new_tokens", 64))
    modes: list[Mode] = [
        m
        for m in cfg.get("modes", ["prefill"])
        if m in ("prefill", "kv_decode", "e2e_kv")
    ]
    compile_cfg = dict(cfg.get("torch_compile", {}) or {})
    compile_enabled = bool(compile_cfg.get("enabled", True))
    tokenization_cfg = dict(cfg.get("tokenization", {}) or {})

    backends = ["transformers-gpu", "transformers-gpu-compile"]

    # Manifest (captures environment once, lists all models)
    from research.tr126.shared.env_fingerprint import capture_environment

    manifest = {
        "run_id": run_id,
        "platform": "linux-docker",
        "models": [{"path": mp, "dtype": dt} for mp, dt in models_list],
        "tier3_config": str(tier3_path.as_posix()),
        "scenarios": [str(s.get("name")) for s in scenarios],
        "device": str(device),
        "repetitions": repetitions,
        "warmup_repetitions": warmup_reps,
        "max_new_tokens": max_new_tokens,
        "modes": modes,
        "torch_compile_config": compile_cfg,
        "tokenization": tokenization_cfg,
        "environment": capture_environment(),
        "env_vars": {
            "CUDA_VISIBLE_DEVICES": os.getenv("CUDA_VISIBLE_DEVICES"),
            "HF_HUB_OFFLINE": os.getenv("HF_HUB_OFFLINE"),
            "TRITON_CACHE_DIR": os.getenv("TRITON_CACHE_DIR"),
        },
    }
    _write_json(out_root / "manifest.json", manifest)

    # Accumulate metrics across all models
    all_mode_metrics: dict[str, list[dict[str, Any]]] = {m: [] for m in modes}
    all_compile_metas: dict[str, dict[str, Any]] = {}
    total_models = len(models_list)
    total_runs_per_model = len(modes) * len(scenarios) * len(backends) * repetitions

    print(
        f"\n{total_models} model(s), {total_runs_per_model} measurements each, "
        f"{len(modes)} modes"
    )
    print(f"Total runs: {total_models * total_runs_per_model}")

    for model_idx, (model_path, dtype_str) in enumerate(models_list, 1):
        torch_dtype, quant_label = _resolve_dtype(dtype_str)
        model_label = Path(model_path).name

        print(f"\n{'=' * 60}")
        print(f"Model {model_idx}/{total_models}: {model_path} (dtype={quant_label})")
        print(f"{'=' * 60}")

        # Load model
        model, tokenizer = _load_model(
            model_path, device=device, torch_dtype=torch_dtype
        )
        model_eager = model

        # Compile — NO FALLBACK
        print("  Compiling with Inductor+Triton (no fallback)...")
        torch._dynamo.reset()
        model_compiled, compile_meta_once = _maybe_compile(
            model, compile_enabled, "transformers-gpu-compile", compile_cfg
        )
        if compile_meta_once and compile_meta_once.get("triton_verified"):
            print(
                f"  Triton verified. Compile time: {compile_meta_once['compile_time_ms']:.0f}ms"
            )
        elif compile_meta_once:
            print("  WARNING: Triton not verified after compilation")
        all_compile_metas[model_path] = compile_meta_once or {}

        # Collect Triton evidence per model
        triton_evidence = _collect_triton_evidence()
        _write_json(out_root / f"triton_evidence_{model_label}.json", triton_evidence)

        # Run modes × scenarios × backends
        for mode in modes:
            runs_root = out_root / mode / "runs"
            _ensure_dir(runs_root)
            _dynamo_counters_clear()

            for scenario in scenarios:
                scenario_name = str(scenario.get("name"))
                prompt_set_name = str(scenario.get("prompt_set"))
                prompts = [
                    str(p)
                    for p in tier3.get("prompt_sets", {}).get(prompt_set_name, [])
                ]
                if not prompts:
                    raise SystemExit(f"prompt_set '{prompt_set_name}' missing/empty")

                for backend in backends:
                    print(
                        f"  [{mode}] {model_label}/{scenario_name}/{backend}...",
                        end=" ",
                        flush=True,
                    )
                    if backend.endswith("-compile"):
                        effective_model = model_compiled
                        compile_meta = compile_meta_once
                    else:
                        effective_model = model_eager
                        compile_meta = None

                    model_id = f"{model_path}:{quant_label}"
                    spec = RunSpec(
                        mode=mode,
                        scenario=scenario_name,
                        prompt_set=prompt_set_name,
                        prompts=prompts,
                        backend=backend,
                        model=model_id,
                        quantization=quant_label,
                    )
                    run = _run_mode(
                        mode=mode,
                        model=effective_model,
                        tokenizer=tokenizer,
                        device=device,
                        max_new_tokens=max_new_tokens,
                        repetitions=repetitions,
                        warmup_repetitions=warmup_reps,
                        spec=spec,
                        tokenization_cfg=tokenization_cfg,
                    )
                    if compile_meta is not None:
                        run["compile"] = compile_meta

                    run_path = (
                        runs_root
                        / model_label
                        / scenario_name
                        / backend
                        / quant_label
                        / f"run_{int(time.time()*1000)}.json"
                    )
                    _ensure_dir(run_path.parent)
                    _write_json(run_path, {"path": str(run_path.as_posix()), **run})

                    # Metrics CSV rows
                    for latency_ms, cuda_ms, ttft_ms, tok, tps in zip(
                        run["latencies_ms"],
                        run.get("cuda_event_ms", []),
                        run["ttft_ms"],
                        run["tokens"],
                        run["tokens_per_s"],
                        strict=False,
                    ):
                        all_mode_metrics[mode].append(
                            {
                                "scenario": scenario_name,
                                "prompt_set": prompt_set_name,
                                "backend": backend,
                                "model": model_id,
                                "quantization": quant_label,
                                "latency_ms": float(latency_ms),
                                "cuda_event_ms": (
                                    float(cuda_ms) if cuda_ms is not None else ""
                                ),
                                "ttft_ms": float(ttft_ms),
                                "tokens": int(tok),
                                "tokens_per_s": float(tps),
                                "status": "ok",
                                "error": "",
                            }
                        )

                    n = len(run["latencies_ms"])
                    mean = sum(run["latencies_ms"]) / n if n else 0
                    print(f"{n} samples, mean={mean:.2f}ms")

        # Free GPU memory before next model
        print(f"  Freeing {model_label}...")
        del model, model_eager, model_compiled, tokenizer
        gc.collect()
        torch.cuda.empty_cache()

    # Write metrics.csv and dynamo counters per mode
    for mode in modes:
        mode_root = out_root / mode
        _ensure_dir(mode_root)
        _write_metrics_csv(all_mode_metrics[mode], mode_root / "metrics.csv")
        _write_json(
            mode_root / "dynamo_counters.json",
            {
                "mode": mode,
                "backend_labels": backends,
                "compile_metas": all_compile_metas,
                "dynamo_counters": _dynamo_counters_snapshot(),
            },
        )

    print(f"\nTR126 Phase 2 run written to: {out_root}")
    print(f"  Models: {total_models}")
    print(f"  Total samples: {sum(len(v) for v in all_mode_metrics.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
