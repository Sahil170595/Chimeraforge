"""TR127 — Core context-length sweep runner.

For each (model x backend x context_length), measures prefill, decode, and
end-to-end latency plus VRAM usage.  OOM is recorded as a data point, not a
crash.

Usage:
    python research/tr127/run_context_sweep.py --config research/tr127/config.yaml -v
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import logging
from pathlib import Path
import sys
import time
import traceback
from typing import Any

import requests
import yaml

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[1]
sys.path.insert(0, str(_REPO))

from research.tr126.shared.env_fingerprint import capture_environment
from research.tr127.shared.utils import generate_ollama_prompt, generate_prompt

log = logging.getLogger("tr127.sweep")

# ── dtype mapping ─────────────────────────────────────────────────────
_DTYPE_MAP: dict[str, str] = {
    "fp16": "float16",
    "fp32": "float32",
    "bf16": "bfloat16",
}


# ── pre-flight validation ─────────────────────────────────────────────


def _validate_environment(device: str) -> dict[str, Any]:
    """Pre-flight check: verify GPU state before measurement.

    Returns validation dict (also written to manifest). Logs warnings
    for anything suspicious but does NOT abort — the environment data
    is recorded for post-hoc auditing.
    """
    validation: dict[str, Any] = {"passed": True, "checks": {}}

    if device != "cuda":
        validation["checks"]["cuda_requested"] = False
        log.info("Pre-flight: CPU mode — skipping GPU checks")
        return validation

    try:
        import torch

        # 1. CUDA available
        cuda_ok = torch.cuda.is_available()
        validation["checks"]["cuda_available"] = cuda_ok
        if not cuda_ok:
            validation["passed"] = False
            log.error("Pre-flight FAIL: CUDA not available")
            return validation

        # 2. GPU memory — check no large allocations from other processes
        free_mem, total_mem = torch.cuda.mem_get_info(0)
        free_gb = free_mem / (1024**3)
        total_gb = total_mem / (1024**3)
        used_gb = total_gb - free_gb
        validation["checks"]["gpu_free_gb"] = round(free_gb, 2)
        validation["checks"]["gpu_total_gb"] = round(total_gb, 2)
        validation["checks"]["gpu_used_gb"] = round(used_gb, 2)

        if used_gb > 1.0:
            log.warning(
                "Pre-flight WARNING: %.1f GB GPU memory already in use "
                "(%.1f GB free of %.1f GB). Other CUDA processes may "
                "affect measurements.",
                used_gb,
                free_gb,
                total_gb,
            )
            validation["checks"]["gpu_clean"] = False
        else:
            validation["checks"]["gpu_clean"] = True
            log.info("Pre-flight: GPU clean (%.1f GB free)", free_gb)

        # 3. Device name
        validation["checks"]["gpu_name"] = torch.cuda.get_device_name(0)

        # 4. No pending CUDA errors
        try:
            torch.cuda.synchronize()
            validation["checks"]["cuda_sync_ok"] = True
        except RuntimeError as e:
            validation["checks"]["cuda_sync_ok"] = False
            validation["passed"] = False
            log.error("Pre-flight FAIL: CUDA sync error: %s", e)

    except ImportError:
        validation["passed"] = False
        validation["checks"]["torch_import"] = False
        log.error("Pre-flight FAIL: torch not importable")

    return validation


# ── helpers ───────────────────────────────────────────────────────────


def _load_yaml(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _resolve_dtype(model_cfg: dict[str, Any], device: str) -> str:
    """Resolve torch dtype string from config, with device-aware fallback."""
    dtype_str = model_cfg.get("dtype", "fp16" if device == "cuda" else "fp32")
    return _DTYPE_MAP.get(dtype_str, "float16")


def _write_metrics_csv(rows: list[dict[str, Any]], out_path: Path) -> None:
    """Write CSV with union-of-keys schema (HF and Ollama rows coexist)."""
    all_keys: list[str] = []
    seen: set[str] = set()
    for r in rows:
        for k in r:
            if k not in seen:
                all_keys.append(k)
                seen.add(k)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    log.info("Wrote %d rows → %s", len(rows), out_path)


# ── HF transformers runner ───────────────────────────────────────────


def _run_hf_sweep(
    model_cfg: dict[str, Any],
    context_lengths: list[int],
    max_new_tokens: int,
    repetitions: int,
    warmup_reps: int,
    device: str,
    seed: int,
) -> list[dict[str, Any]]:
    """Run context-length sweep for one HF model.  Returns list of metric rows."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    mname = model_cfg["name"]
    mpath = str(_REPO / model_cfg["path"])
    max_ctx = model_cfg["max_context"]
    rows: list[dict[str, Any]] = []

    # Per-model dtype override (TR126 pattern)
    dtype_name = _resolve_dtype(model_cfg, device)
    model_torch_dtype = getattr(torch, dtype_name)
    log.info("Loading HF model %s from %s (dtype=%s)", mname, mpath, dtype_name)

    tokenizer = AutoTokenizer.from_pretrained(mpath, local_files_only=True)

    # Pad token fallback — models like LLaMA lack pad_token_id
    if tokenizer.pad_token_id is None and tokenizer.eos_token_id is not None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    model = AutoModelForCausalLM.from_pretrained(
        mpath,
        local_files_only=True,
        torch_dtype=model_torch_dtype,
    )
    model.eval().to(device)

    try:
        for ctx_len in context_lengths:
            if ctx_len > max_ctx:
                log.warning(
                    "%s: context_length %d exceeds max_context %d — skip",
                    mname,
                    ctx_len,
                    max_ctx,
                )
                rows.append(
                    _oom_row(mname, "transformers-gpu", ctx_len, "exceeds_max_context")
                )
                continue

            log.info("  %s @ %d tokens", mname, ctx_len)
            prompt = generate_prompt(tokenizer, ctx_len)
            enc = tokenizer(prompt, return_tensors="pt").to(device)
            prompt_tokens = int(enc["attention_mask"].sum().item())

            # ── warmup ────────────────────────────────────────────
            for _ in range(warmup_reps):
                try:
                    _hf_measure_once(model, enc, max_new_tokens, device)
                except torch.cuda.OutOfMemoryError:
                    break  # skip remaining warmup, but try measurement
                finally:
                    if device == "cuda":
                        torch.cuda.empty_cache()

            # ── measurement reps ──────────────────────────────────
            for rep in range(repetitions):
                try:
                    if device == "cuda":
                        torch.cuda.reset_peak_memory_stats()

                    metrics = _hf_measure_once(model, enc, max_new_tokens, device)

                    vram_peak_mb = 0.0
                    if device == "cuda":
                        vram_peak_mb = torch.cuda.max_memory_allocated() / (1024**2)

                    # prefill row
                    rows.append(
                        {
                            "model": mname,
                            "backend": "transformers-gpu",
                            "context_length": ctx_len,
                            "prompt_tokens": prompt_tokens,
                            "mode": "prefill",
                            "rep": rep,
                            "latency_ms": metrics["prefill_ms"],
                            "tokens": prompt_tokens,
                            "tokens_per_s": (
                                prompt_tokens / (metrics["prefill_ms"] / 1000)
                                if metrics["prefill_ms"] > 0
                                else 0.0
                            ),
                            "vram_peak_mb": vram_peak_mb,
                            "status": "ok",
                        }
                    )
                    # decode row
                    decode_tps = (
                        metrics["decode_tokens"] / (metrics["decode_ms"] / 1000)
                        if metrics["decode_ms"] > 0
                        else 0.0
                    )
                    rows.append(
                        {
                            "model": mname,
                            "backend": "transformers-gpu",
                            "context_length": ctx_len,
                            "prompt_tokens": prompt_tokens,
                            "mode": "decode",
                            "rep": rep,
                            "latency_ms": metrics["decode_ms"],
                            "tokens": metrics["decode_tokens"],
                            "tokens_per_s": decode_tps,
                            "vram_peak_mb": vram_peak_mb,
                            "status": "ok",
                        }
                    )
                    # e2e row
                    e2e_ms = metrics["prefill_ms"] + metrics["decode_ms"]
                    e2e_tokens = prompt_tokens + metrics["decode_tokens"]
                    rows.append(
                        {
                            "model": mname,
                            "backend": "transformers-gpu",
                            "context_length": ctx_len,
                            "prompt_tokens": prompt_tokens,
                            "mode": "e2e",
                            "rep": rep,
                            "latency_ms": e2e_ms,
                            "tokens": e2e_tokens,
                            "tokens_per_s": (
                                e2e_tokens / (e2e_ms / 1000) if e2e_ms > 0 else 0.0
                            ),
                            "vram_peak_mb": vram_peak_mb,
                            "status": "ok",
                        }
                    )

                except torch.cuda.OutOfMemoryError:
                    log.warning("  OOM: %s @ %d tokens, rep %d", mname, ctx_len, rep)
                    rows.append(
                        _oom_row(
                            mname,
                            "transformers-gpu",
                            ctx_len,
                            "oom",
                            rep=rep,
                            prompt_tokens=prompt_tokens,
                        )
                    )
                    if device == "cuda":
                        torch.cuda.empty_cache()
                    break  # remaining reps at this ctx_len will also OOM

                except Exception:
                    log.error(
                        "  Error: %s @ %d tokens, rep %d\n%s",
                        mname,
                        ctx_len,
                        rep,
                        traceback.format_exc(),
                    )
                    rows.append(
                        _oom_row(
                            mname,
                            "transformers-gpu",
                            ctx_len,
                            "error",
                            rep=rep,
                            prompt_tokens=prompt_tokens,
                        )
                    )
                finally:
                    if device == "cuda":
                        torch.cuda.empty_cache()

    finally:
        # Free GPU memory before next model
        del model, tokenizer
        gc.collect()
        if device == "cuda":
            import torch as _torch

            _torch.cuda.empty_cache()

    return rows


def _hf_measure_once(
    model: Any,
    enc: dict[str, Any],
    max_new_tokens: int,
    device: str,
) -> dict[str, float]:
    """Single prefill + decode measurement.  Returns timing dict."""
    import torch

    input_ids = enc["input_ids"]
    attn_mask = enc["attention_mask"]

    # ── prefill ───────────────────────────────────────────────
    if device == "cuda":
        torch.cuda.synchronize()
    t0 = time.perf_counter()

    with torch.no_grad():
        out = model(input_ids=input_ids, attention_mask=attn_mask, use_cache=True)

    if device == "cuda":
        torch.cuda.synchronize()
    prefill_ms = (time.perf_counter() - t0) * 1000.0

    # ── decode ────────────────────────────────────────────────
    logits = out.logits[:, -1, :]
    past = out.past_key_values
    next_tok = torch.argmax(logits, dim=-1, keepdim=True)

    if device == "cuda":
        torch.cuda.synchronize()
    t1 = time.perf_counter()

    generated = 0
    with torch.no_grad():
        for _ in range(max_new_tokens):
            out2 = model(input_ids=next_tok, use_cache=True, past_key_values=past)
            logits = out2.logits[:, -1, :]
            past = out2.past_key_values
            next_tok = torch.argmax(logits, dim=-1, keepdim=True)
            generated += 1

    if device == "cuda":
        torch.cuda.synchronize()
    decode_ms = (time.perf_counter() - t1) * 1000.0

    return {
        "prefill_ms": prefill_ms,
        "decode_ms": decode_ms,
        "decode_tokens": generated,
    }


# ── Ollama runner ─────────────────────────────────────────────────────


def _run_ollama_sweep(
    model_cfg: dict[str, Any],
    context_lengths: list[int],
    max_new_tokens: int,
    repetitions: int,
    seed: int,
    ollama_url: str,
    timeout_s: int,
) -> list[dict[str, Any]]:
    """Run context-length sweep for one Ollama model."""
    mname = model_cfg["name"]
    tag = model_cfg["ollama_tag"]
    max_ctx = model_cfg["max_context"]
    rows: list[dict[str, Any]] = []

    log.info("Running Ollama model %s (tag=%s)", mname, tag)

    for ctx_len in context_lengths:
        if ctx_len > max_ctx:
            log.warning(
                "%s: context_length %d exceeds max_context %d — skip",
                mname,
                ctx_len,
                max_ctx,
            )
            rows.append(_oom_row(mname, "ollama", ctx_len, "exceeds_max_context"))
            continue

        log.info("  %s @ %d tokens (Ollama)", mname, ctx_len)

        # Use shared prompt generator (single source of truth)
        prompt = generate_ollama_prompt(ctx_len)

        for rep in range(repetitions):
            try:
                start = time.perf_counter()
                resp = requests.post(
                    f"{ollama_url}/api/generate",
                    json={
                        "model": tag,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "num_predict": max_new_tokens,
                            "temperature": 0.0,
                            "seed": seed,
                            "num_ctx": ctx_len + max_new_tokens,
                        },
                    },
                    timeout=timeout_s,
                )
                wall_ms = (time.perf_counter() - start) * 1000.0
                resp.raise_for_status()
                data = resp.json()

                # Extract native Ollama timing
                prompt_eval_ns = data.get("prompt_eval_duration", 0)
                eval_ns = data.get("eval_duration", 0)
                prompt_eval_count = data.get("prompt_eval_count", 0)
                eval_count = data.get("eval_count", 0)

                prefill_ms = prompt_eval_ns / 1e6 if prompt_eval_ns else wall_ms
                decode_ms = eval_ns / 1e6 if eval_ns else wall_ms

                prefill_tps = (
                    prompt_eval_count / (prefill_ms / 1000)
                    if prefill_ms > 0 and prompt_eval_count > 0
                    else 0.0
                )
                decode_tps = (
                    eval_count / (decode_ms / 1000)
                    if decode_ms > 0 and eval_count > 0
                    else 0.0
                )
                e2e_ms = prefill_ms + decode_ms
                e2e_tokens = prompt_eval_count + eval_count
                e2e_tps = e2e_tokens / (e2e_ms / 1000) if e2e_ms > 0 else 0.0

                base = {
                    "model": mname,
                    "backend": "ollama",
                    "context_length": ctx_len,
                    "prompt_tokens": prompt_eval_count,
                    "rep": rep,
                    "vram_peak_mb": None,
                    "status": "ok",
                    "wall_ms": wall_ms,
                    "ollama_prompt_eval_ms": (
                        prompt_eval_ns / 1e6 if prompt_eval_ns else None
                    ),
                    "ollama_eval_ms": (eval_ns / 1e6 if eval_ns else None),
                }

                # prefill row
                rows.append(
                    {
                        **base,
                        "mode": "prefill",
                        "latency_ms": prefill_ms,
                        "tokens": prompt_eval_count,
                        "tokens_per_s": prefill_tps,
                    }
                )
                # decode row
                rows.append(
                    {
                        **base,
                        "mode": "decode",
                        "latency_ms": decode_ms,
                        "tokens": eval_count,
                        "tokens_per_s": decode_tps,
                    }
                )
                # e2e row
                rows.append(
                    {
                        **base,
                        "mode": "e2e",
                        "latency_ms": e2e_ms,
                        "tokens": e2e_tokens,
                        "tokens_per_s": e2e_tps,
                    }
                )

            except requests.exceptions.Timeout:
                log.warning("  Timeout: %s @ %d tokens, rep %d", mname, ctx_len, rep)
                rows.append(_oom_row(mname, "ollama", ctx_len, "timeout", rep=rep))

            except Exception:
                log.error(
                    "  Error: %s @ %d tokens, rep %d\n%s",
                    mname,
                    ctx_len,
                    rep,
                    traceback.format_exc(),
                )
                rows.append(_oom_row(mname, "ollama", ctx_len, "error", rep=rep))

    return rows


# ── shared helpers ────────────────────────────────────────────────────


def _oom_row(
    model: str,
    backend: str,
    ctx_len: int,
    status: str,
    rep: int = 0,
    prompt_tokens: int = 0,
) -> dict[str, Any]:
    """Create a row for OOM / error / skip conditions."""
    return {
        "model": model,
        "backend": backend,
        "context_length": ctx_len,
        "prompt_tokens": prompt_tokens,
        "mode": "oom",
        "rep": rep,
        "latency_ms": None,
        "tokens": 0,
        "tokens_per_s": 0.0,
        "vram_peak_mb": None,
        "status": status,
    }


# ── main ──────────────────────────────────────────────────────────────


def run_sweep(config_path: str | Path) -> Path:
    """Execute the full context sweep.  Returns the run output directory."""
    cfg = _load_yaml(config_path)

    context_lengths = cfg["context_lengths"]
    models = cfg["models"]
    repetitions = cfg["repetitions"]
    warmup_reps = cfg["warmup_repetitions"]
    max_new_tokens = cfg["max_new_tokens"]
    device = cfg["device"]
    seed = cfg["seed"]
    ollama_url = cfg["ollama_url"]
    ollama_timeout_s = cfg["ollama_timeout_s"]

    # ── pre-flight validation ─────────────────────────────────
    preflight = _validate_environment(device)
    if not preflight["passed"]:
        log.error("Pre-flight validation FAILED — aborting sweep")
        log.error("Checks: %s", json.dumps(preflight["checks"], indent=2))
        raise RuntimeError(f"Pre-flight validation failed: {preflight['checks']}")
    log.info("Pre-flight validation passed")

    # Output directory
    run_id = time.strftime("%Y%m%d_%H%M%S")
    out_root = _REPO / cfg["output_dir"] / run_id
    out_root.mkdir(parents=True, exist_ok=True)

    # Write manifest
    manifest = {
        "run_id": run_id,
        "experiment": cfg.get("experiment", "tr127"),
        "config": cfg,
        "environment": capture_environment(),
        "preflight_validation": preflight,
        "start_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    all_rows: list[dict[str, Any]] = []

    # ── HF models ─────────────────────────────────────────────
    for model_cfg in models:
        if model_cfg.get("path") is None:
            log.info("Skipping HF for %s (no local path)", model_cfg["name"])
            continue

        hf_path = _REPO / model_cfg["path"]
        if not hf_path.is_dir():
            log.warning("HF path %s not found — skipping", hf_path)
            continue

        rows = _run_hf_sweep(
            model_cfg=model_cfg,
            context_lengths=context_lengths,
            max_new_tokens=max_new_tokens,
            repetitions=repetitions,
            warmup_reps=warmup_reps,
            device=device,
            seed=seed,
        )
        all_rows.extend(rows)

    # ── Ollama models ─────────────────────────────────────────
    for model_cfg in models:
        if model_cfg.get("ollama_tag") is None:
            log.info("Skipping Ollama for %s (no ollama_tag)", model_cfg["name"])
            continue

        rows = _run_ollama_sweep(
            model_cfg=model_cfg,
            context_lengths=context_lengths,
            max_new_tokens=max_new_tokens,
            repetitions=repetitions,
            seed=seed,
            ollama_url=ollama_url,
            timeout_s=ollama_timeout_s,
        )
        all_rows.extend(rows)

    # ── Write results ─────────────────────────────────────────
    _write_metrics_csv(all_rows, out_root / "metrics.csv")

    manifest["end_time"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    manifest["total_rows"] = len(all_rows)
    with (out_root / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)
    log.info("Manifest → %s", out_root / "manifest.json")

    return out_root


# ── CLI ───────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="TR127 context-length sweep")
    parser.add_argument(
        "--config", default=str(_DIR / "config.yaml"), help="Path to config.yaml"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    out = run_sweep(args.config)
    log.info("Done — results in %s", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
