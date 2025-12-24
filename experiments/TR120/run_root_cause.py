#!/usr/bin/env python3
"""
TR120.A (root-cause execution): reproduce compile-vs-eager behavior under a controlled harness.

Why this exists:
  - The TR117 Tier-3 artifacts label backends as transformers-gpu(-compile), but the
    then-and-now inference path does not actually invoke torch.compile for the "-compile"
    backend label. TR120.A needs a controlled, explicit compile vs eager harness.

What this script does:
  - Loads a local HF model once (no per-call model load).
  - Runs prefill and KV-cached decode loops with deterministic greedy decoding.
  - Compares eager vs torch.compile() on the same workload shapes (prompt sets from TR117 tier3 config).
  - Writes TR117-shaped artifacts:
      - run_*.json per (mode, scenario, backend)
      - metrics.csv per mode for downstream analysis

Outputs:
  scripts/tr120/results/tr120_root_cause/<run_id>/<mode>/
    - runs/.../run_*.json
    - metrics.csv
    - manifest.json
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
import time
from typing import Any, Literal

import yaml


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
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _dynamo_counters_clear() -> None:
    try:
        import torch._dynamo.utils as dynamo_utils  # type: ignore

        dynamo_utils.counters.clear()  # type: ignore[attr-defined]
    except Exception:
        return


def _dynamo_counters_snapshot() -> dict[str, Any]:
    """
    Best-effort snapshot of torch._dynamo counters for artifact-backed recompilation evidence.
    """
    try:
        import copy
        import json as _json
        import torch._dynamo.utils as dynamo_utils  # type: ignore

        counters = getattr(dynamo_utils, "counters", None)
        if counters is None:
            return {}
        # counters is a nested defaultdict-like structure; deep-copy can fail in some
        # torch builds, so fall back to a shallow view if needed.
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
            # Last resort: ensure JSON-serializable (don't fail the whole snapshot).
            try:
                _json.dumps(obj)
                return obj
            except Exception:
                return str(obj)
            return obj

        try:
            snap_dict = dict(snap)
        except Exception:
            # Last resort: attempt to stringify whatever structure we got.
            return {"raw": str(snap)}

        return to_plain(snap_dict)
    except Exception:
        return {}

def _resolve_device(device_pref: str):
    import torch  # type: ignore

    pref = (device_pref or "cpu").strip().lower()
    if pref == "cuda" and torch.cuda.is_available():
        return torch.device("cuda")
    if pref == "cpu":
        return torch.device("cpu")
    # fallback: attempt user string
    try:
        dev = torch.device(pref)
        if dev.type == "cuda" and not torch.cuda.is_available():
            return torch.device("cpu")
        return dev
    except Exception:
        return torch.device("cpu")


def _resolve_dtype(dtype_pref: str):
    import torch  # type: ignore

    pref = (dtype_pref or "fp32").strip().lower()
    if pref in ("fp16", "float16"):
        return torch.float16, "fp16"
    return torch.float32, "fp32"


def _load_model(model_path: str, device, torch_dtype):
    import torch  # type: ignore
    from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore

    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    if tokenizer.pad_token_id is None and tokenizer.eos_token_id is not None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        local_files_only=True,
        torch_dtype=torch_dtype,
    )
    model.eval()
    model.to(device)
    # Determinism knobs (best effort; CUDA kernels still may vary)
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
    import torch  # type: ignore

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
                pad_to_multiple_of=int(pad_to_multiple_of) if pad_to_multiple_of else None,
            )
        else:
            enc = tokenizer(prompt, return_tensors="pt", add_special_tokens=True)
        batch.append(
            {
                "input_ids": enc["input_ids"].to(device),
                "attention_mask": enc.get("attention_mask", torch.ones_like(enc["input_ids"])).to(device),
            }
        )
    return batch


def _maybe_compile(model, enabled: bool, backend_label: str, cfg: dict[str, Any]):
    if not enabled or not backend_label.endswith("-compile"):
        return model, None
    import torch  # type: ignore

    mode = str(cfg.get("mode", "reduce-overhead"))
    backend = cfg.get("backend")
    fallback_backend = cfg.get("fallback_backend")
    dynamic = bool(cfg.get("dynamic", False))
    fullgraph = bool(cfg.get("fullgraph", False))
    disable_cudagraphs = bool(cfg.get("disable_cudagraphs", False))
    # Clear counters so compile-stage evidence is attributable to this compilation attempt.
    _dynamo_counters_clear()
    started = time.perf_counter()
    try:
        if disable_cudagraphs:
            try:
                import torch._inductor.config as inductor_config  # type: ignore

                # Best-effort: different torch versions use different config layouts.
                if hasattr(inductor_config, "use_cudagraphs"):
                    setattr(inductor_config, "use_cudagraphs", False)
                triton_cfg = getattr(inductor_config, "triton", None)
                if triton_cfg is not None:
                    # In recent torch builds, cudagraph behavior is primarily controlled by
                    # config.triton.cudagraph_trees (not just config.triton.cudagraphs).
                    # We disable both to make KV-cache decode loops safe by default.
                    if hasattr(triton_cfg, "cudagraphs"):
                        setattr(triton_cfg, "cudagraphs", False)
                    if hasattr(triton_cfg, "cudagraph_trees"):
                        setattr(triton_cfg, "cudagraph_trees", False)
            except Exception:
                pass

        compile_kwargs: dict[str, Any] = {"mode": mode, "dynamic": dynamic, "fullgraph": fullgraph}
        if backend:
            compile_kwargs["backend"] = backend
        compiled = torch.compile(model, **compile_kwargs)  # type: ignore[attr-defined]
        # Force a first execution to surface backend/toolchain issues early (e.g., TritonMissing).
        try:
            device = next(compiled.parameters()).device  # type: ignore[call-arg]
            dummy = torch.ones((1, 8), dtype=torch.long, device=device)
            with torch.no_grad():
                _ = compiled(input_ids=dummy, use_cache=True)
            if device.type == "cuda":
                torch.cuda.synchronize()
        except Exception as exc_run:
            raise RuntimeError(f"compile_smoke_failed: {exc_run!s}") from exc_run
        compile_ms = (time.perf_counter() - started) * 1000.0
        return compiled, {
            "enabled": True,
            "backend": backend or "inductor",
            "mode": mode,
            "dynamic": dynamic,
            "fullgraph": fullgraph,
            "disable_cudagraphs": disable_cudagraphs,
            "compile_time_ms": compile_ms,
            "compile_wrapper_ms": compile_ms,
            "dynamo_counters_after_compile": _dynamo_counters_snapshot(),
        }
    except Exception as exc:
        # Common Windows/Python 3.13 failure mode: inductor GPU path requires Triton wheels.
        if fallback_backend and backend != fallback_backend:
            try:
                _dynamo_counters_clear()
                started_fb = time.perf_counter()
                compiled = torch.compile(
                    model,
                    backend=str(fallback_backend),
                    mode=mode,
                    dynamic=dynamic,
                    fullgraph=fullgraph,
                )  # type: ignore[attr-defined]
                compile_ms = (time.perf_counter() - started_fb) * 1000.0
                return compiled, {
                    "enabled": True,
                    "backend": str(fallback_backend),
                    "mode": mode,
                    "dynamic": dynamic,
                    "fullgraph": fullgraph,
                    "disable_cudagraphs": disable_cudagraphs,
                    "compile_time_ms": compile_ms,
                    "compile_wrapper_ms": compile_ms,
                    "fallback_from": backend or "inductor",
                    "fallback_error": str(exc),
                    "dynamo_counters_after_compile": _dynamo_counters_snapshot(),
                }
            except Exception as exc2:
                compile_ms = (time.perf_counter() - started) * 1000.0
                return model, {
                    "enabled": True,
                    "failed": True,
                    "backend": backend or "inductor",
                    "fallback_backend": str(fallback_backend),
                    "mode": mode,
                    "dynamic": dynamic,
                    "fullgraph": fullgraph,
                    "disable_cudagraphs": disable_cudagraphs,
                    "compile_time_ms": compile_ms,
                    "compile_wrapper_ms": compile_ms,
                    "error": str(exc),
                    "fallback_error": str(exc2),
                    "dynamo_counters_after_compile": _dynamo_counters_snapshot(),
                }
        compile_ms = (time.perf_counter() - started) * 1000.0
        return model, {
            "enabled": True,
            "failed": True,
            "backend": backend or "inductor",
            "mode": mode,
            "dynamic": dynamic,
            "fullgraph": fullgraph,
            "disable_cudagraphs": disable_cudagraphs,
            "compile_time_ms": compile_ms,
            "compile_wrapper_ms": compile_ms,
            "error": str(exc),
            "dynamo_counters_after_compile": _dynamo_counters_snapshot(),
        }


def _cuda_sync(device) -> None:
    if device.type != "cuda":
        return
    import torch  # type: ignore

    torch.cuda.synchronize()


def _cuda_event_timer(device):
    """
    Best-effort CUDA event timer.

    Returns a tuple (start_event, end_event, elapsed_ms_fn) or (None, None, fn) on CPU.
    """
    if getattr(device, "type", None) != "cuda":
        return None, None, lambda: None
    try:
        import torch  # type: ignore

        start = torch.cuda.Event(enable_timing=True)
        end = torch.cuda.Event(enable_timing=True)

        def elapsed_ms() -> float | None:
            try:
                # Ensure end is recorded and visible to the host.
                end.synchronize()
                return float(start.elapsed_time(end))
            except Exception:
                return None

        return start, end, elapsed_ms
    except Exception:
        return None, None, lambda: None


def _cudagraph_mark_step_begin() -> None:
    """
    Best-effort mitigation for Inductor+cudagraph_trees reuse hazards when
    running compiled models in tight loops (common in decode).
    """
    try:
        import torch  # type: ignore

        mark = getattr(getattr(torch, "compiler", None), "cudagraph_mark_step_begin", None)
        if callable(mark):
            mark()
    except Exception:
        return


def _prefill(model, input_ids, device) -> tuple[float, float | None, Any, Any]:
    import torch  # type: ignore

    _cuda_sync(device)
    _cudagraph_mark_step_begin()
    start_ev, end_ev, elapsed_ms = _cuda_event_timer(device)
    start = time.perf_counter()
    with torch.no_grad():
        if start_ev is not None:
            start_ev.record()
        out = model(input_ids=input_ids, use_cache=True)
        if end_ev is not None:
            end_ev.record()
        logits = out.logits[:, -1, :]
        past = out.past_key_values
    _cuda_sync(device)
    wall_ms = (time.perf_counter() - start) * 1000.0
    return wall_ms, elapsed_ms(), logits, past


def _prefill_with_mask(model, input_ids, attention_mask, device) -> tuple[float, float | None, Any, Any]:
    import torch  # type: ignore

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


def _kv_decode(model, logits, past, device, max_new_tokens: int) -> tuple[float, float | None, int]:
    import torch  # type: ignore

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


def _dynamo_explain_summary(model, *, call_kwargs: dict[str, Any]) -> dict[str, Any]:
    """
    Best-effort compiler evidence: graph count, break reasons, and guard volume.

    Note: `torch._dynamo.explain(f, *args, **kwargs)` is deprecated in newer torch;
    we use `torch._dynamo.explain(f)(*args, **kwargs)` when available.
    """
    try:
        import torch._dynamo as dynamo  # type: ignore

        explain = getattr(dynamo, "explain", None)
        if not callable(explain):
            return {"available": False}
        out = explain(model)(**call_kwargs)
        ops = getattr(out, "ops_per_graph", None)
        if isinstance(ops, list):
            ops_summary: Any = []
            for g in ops:
                try:
                    ops_summary.append(int(len(g)))  # type: ignore[arg-type]
                except Exception:
                    ops_summary.append(None)
        else:
            ops_summary = None
        summary: dict[str, Any] = {
            "available": True,
            "graph_count": getattr(out, "graph_count", None),
            "graph_break_count": getattr(out, "graph_break_count", None),
            "break_reasons_count": len(getattr(out, "break_reasons", []) or []),
            "break_reasons_sample": [str(x) for x in (getattr(out, "break_reasons", []) or [])[:10]],
            "out_guards_count": len(getattr(out, "out_guards", []) or []),
            "ops_per_graph_len": ops_summary,
        }
        return summary
    except Exception as exc:
        return {"available": False, "error": str(exc)}


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
    import torch  # type: ignore

    pad_to_max_length = bool(tokenization_cfg.get("pad_to_max_length", False))
    pad_scope = str(tokenization_cfg.get("pad_scope", "per_scenario"))
    pad_to_multiple_of = tokenization_cfg.get("pad_to_multiple_of")
    pad_to_multiple_of = int(pad_to_multiple_of) if pad_to_multiple_of else None

    # Determine pad length (token count) for stable shapes, if enabled.
    max_len: int | None = None
    if pad_to_max_length:
        if pad_scope not in ("per_scenario", "global"):
            raise ValueError(f"tokenization.pad_scope must be per_scenario|global, got: {pad_scope}")
        # per_scenario: max length among prompts in this spec.
        # global: caller should pass in a max_length; we compute per_scenario here unless provided.
        max_len = int(tokenization_cfg.get("max_length") or 0) or None
        if max_len is None:
            lens = [len(tokenizer(p, add_special_tokens=True).get("input_ids", [])) for p in spec.prompts]
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

    # Warmup: run the full path for each prompt a few times to stabilize caches/compilation.
    for _ in range(int(warmup_repetitions)):
        for enc in tokenized:
            input_ids = enc["input_ids"]
            attention_mask = enc["attention_mask"]
            pre_ms, _pre_cuda_ms, logits, past = _prefill_with_mask(model, input_ids, attention_mask, device)
            if mode in ("kv_decode", "e2e_kv"):
                _kv_decode(model, logits, past, device, max_new_tokens=max_new_tokens)
            else:
                _ = pre_ms  # keep structure parallel

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

    ttft_ms = list(latencies_ms)  # TR117 compatibility placeholder
    tokens_per_s = [
        (t / (ms / 1000.0)) if ms > 0 else 0.0 for t, ms in zip(tokens, latencies_ms, strict=False)
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


def main() -> int:
    parser = argparse.ArgumentParser(description="TR120 root-cause runner (explicit eager vs torch.compile).")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("scripts/tr120/configs/root_cause.yaml"),
        help="Runner config yaml.",
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        default=Path("scripts/tr120/results/tr120_root_cause"),
        help="Root output directory (run_id folder is created under this).",
    )
    args = parser.parse_args()

    cfg = _load_yaml(args.config)
    run_id = _now_run_id()
    out_root = args.out_root / run_id
    _ensure_dir(out_root)

    model_path = str(cfg["model_path"])
    tier3_path = Path(str(cfg["tier3_config"]))
    tier3 = _load_yaml(tier3_path)

    scenarios_allow = set(str(s) for s in cfg.get("scenarios", []))
    scenarios_cfg = tier3.get("scenarios", [])
    scenarios = [s for s in scenarios_cfg if str(s.get("name")) in scenarios_allow]
    if not scenarios:
        raise SystemExit("No scenarios selected; check config.scenarios against tier3_config.scenarios[].name")

    device = _resolve_device(str(cfg.get("device", "cpu")))
    torch_dtype, quant_label = _resolve_dtype(str(cfg.get("dtype", "fp32")))
    repetitions = int(cfg.get("repetitions", 10))
    warmup_reps = int(cfg.get("warmup_repetitions", 2))
    max_new_tokens = int(cfg.get("max_new_tokens", 64))
    modes: list[Mode] = [m for m in cfg.get("modes", ["prefill"]) if m in ("prefill", "kv_decode", "e2e_kv")]
    compile_cfg = dict(cfg.get("torch_compile", {}) or {})
    compile_enabled = bool(compile_cfg.get("enabled", True))
    tokenization_cfg = dict(cfg.get("tokenization", {}) or {})

    backends = ["transformers-gpu", "transformers-gpu-compile"]

    model, tokenizer = _load_model(model_path, device=device, torch_dtype=torch_dtype)
    model_eager = model
    model_compiled, compile_meta_once = _maybe_compile(
        model, compile_enabled, "transformers-gpu-compile", compile_cfg
    )

    # Compiler evidence (best-effort): capture a single explain snapshot on representative inputs.
    compiler_evidence: dict[str, Any] = {}
    try:
        # Use first prompt of first scenario as a representative shape.
        first_scenario = scenarios[0]
        prompt_set_name = str(first_scenario.get("prompt_set"))
        prompts = [str(p) for p in tier3.get("prompt_sets", {}).get(prompt_set_name, [])]
        if prompts:
            tokenization_cfg = dict(cfg.get("tokenization", {}) or {})
            tokenized = _tokenize_prompts(
                tokenizer,
                [prompts[0]],
                device,
                pad_to_max_length=bool(tokenization_cfg.get("pad_to_max_length", False)),
                pad_to_multiple_of=int(tokenization_cfg["pad_to_multiple_of"])
                if tokenization_cfg.get("pad_to_multiple_of")
                else None,
                max_length=int(tokenization_cfg["max_length"])
                if tokenization_cfg.get("pad_to_max_length") and tokenization_cfg.get("max_length")
                else None,
            )
            if tokenized:
                enc = tokenized[0]
                input_ids = enc["input_ids"]
                attention_mask = enc["attention_mask"]
                compiler_evidence["prefill_explain"] = _dynamo_explain_summary(
                    model_eager,
                    call_kwargs={
                        "input_ids": input_ids,
                        "attention_mask": attention_mask,
                        "use_cache": True,
                    },
                )
                # One-step decode explain (KV-cached).
                import torch  # type: ignore

                with torch.no_grad():
                    _cuda_sync(device)
                    out = model_eager(
                        input_ids=input_ids, attention_mask=attention_mask, use_cache=True
                    )
                    logits = out.logits[:, -1, :]
                    past = out.past_key_values
                    next_token = torch.argmax(logits, dim=-1, keepdim=True)
                compiler_evidence["kv_decode_step_explain"] = _dynamo_explain_summary(
                    model_eager,
                    call_kwargs={"input_ids": next_token, "use_cache": True, "past_key_values": past},
                )
    except Exception as exc:
        compiler_evidence["error"] = str(exc)

    manifest = {
        "run_id": run_id,
        "model_path": model_path,
        "tier3_config": str(tier3_path.as_posix()),
        "scenarios": [str(s.get("name")) for s in scenarios],
        "device": str(device),
        "dtype": quant_label,
        "repetitions": repetitions,
        "warmup_repetitions": warmup_reps,
        "max_new_tokens": max_new_tokens,
        "modes": modes,
        "torch_compile_config": compile_cfg,
        "tokenization": tokenization_cfg,
        "env": {
            "CUDA_VISIBLE_DEVICES": os.getenv("CUDA_VISIBLE_DEVICES"),
            "HF_HUB_OFFLINE": os.getenv("HF_HUB_OFFLINE"),
        },
    }
    try:
        import torch  # type: ignore

        manifest["torch"] = {
            "version": getattr(torch, "__version__", None),
            "cuda_available": bool(torch.cuda.is_available()),
            "cuda_version": getattr(torch.version, "cuda", None),
            "cudnn_version": getattr(torch.backends.cudnn, "version", lambda: None)(),
        }
        if device.type == "cuda":
            manifest["torch"]["gpu_name"] = torch.cuda.get_device_name(0)
            manifest["torch"]["gpu_cc"] = torch.cuda.get_device_capability(0)
    except Exception:
        pass
    _write_json(out_root / "manifest.json", manifest)
    if compiler_evidence:
        _write_json(out_root / "compiler_evidence.json", compiler_evidence)

    for mode in modes:
        mode_root = out_root / mode
        runs_root = mode_root / "runs"
        _ensure_dir(runs_root)
        metrics_rows: list[dict[str, Any]] = []

        # Reset dynamo counters per-mode so we can attribute recompiles/graphs to a mode.
        # Note: this tracks *new* compilation/recompilation activity during the mode; the
        # initial compile-stage counters are stored in compile_meta_once.
        _dynamo_counters_clear()

        for scenario in scenarios:
            scenario_name = str(scenario.get("name"))
            prompt_set_name = str(scenario.get("prompt_set"))
            prompts = [str(p) for p in tier3.get("prompt_sets", {}).get(prompt_set_name, [])]
            if not prompts:
                raise SystemExit(f"prompt_set '{prompt_set_name}' missing/empty in {tier3_path}")

            for backend in backends:
                if backend.endswith("-compile"):
                    effective_model = model_compiled
                    compile_meta = compile_meta_once
                else:
                    effective_model = model_eager
                    compile_meta = None
                spec = RunSpec(
                    mode=mode,
                    scenario=scenario_name,
                    prompt_set=prompt_set_name,
                    prompts=prompts,
                    backend=backend,
                    model=model_path,
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

                run_path = runs_root / scenario_name / backend / quant_label / f"run_{int(time.time()*1000)}.json"
                _ensure_dir(run_path.parent)
                run_with_path = {"path": str(run_path.as_posix()), **run}
                _write_json(run_path, run_with_path)

                # Rowify into TR117-like metrics.csv
                for latency_ms, cuda_ms, ttft_ms, tok, tps in zip(
                    run["latencies_ms"],
                    run.get("cuda_event_ms", []),
                    run["ttft_ms"],
                    run["tokens"],
                    run["tokens_per_s"],
                    strict=False,
                ):
                    metrics_rows.append(
                        {
                            "scenario": scenario_name,
                            "prompt_set": prompt_set_name,
                            "backend": backend,
                            "model": model_path,
                            "quantization": quant_label,
                            "latency_ms": float(latency_ms),
                            "cuda_event_ms": float(cuda_ms) if cuda_ms is not None else "",
                            "ttft_ms": float(ttft_ms),
                            "tokens": int(tok),
                            "tokens_per_s": float(tps),
                            "status": "ok",
                            "error": "",
                            "accuracy": "",
                            "degraded_count": 0,
                            "degraded_reasons": "",
                            "path": str(run_path.as_posix()),
                        }
                    )

        _write_metrics_csv(metrics_rows, mode_root / "metrics.csv")
        _write_json(
            mode_root / "dynamo_counters.json",
            {
                "mode": mode,
                "backend_labels": backends,
                "compile_meta": compile_meta_once,
                "dynamo_counters": _dynamo_counters_snapshot(),
            },
        )

    print(f"TR120 root-cause run written to: {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
