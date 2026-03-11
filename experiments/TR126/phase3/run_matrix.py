#!/usr/bin/env python3
"""TR126 Phase 3: Backend matrix rerun under Linux.

Runs a focused subset of TR117's Tier-3 matrix using direct model loading
(transformers-gpu, transformers-gpu-compile) and Ollama HTTP API.

Uses the same measurement functions as Phase 2 (from TR120 patterns)
to ensure consistent timing methodology across phases.

Outputs:
  research/tr126/results/phase3/<run_id>/<mode>/
    - metrics.csv
    - manifest.json
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
from pathlib import Path
import sys
import time
import traceback
from typing import Any, Literal

import requests
import yaml

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[2]
sys.path.insert(0, str(_REPO))

from research.tr126.shared.env_fingerprint import capture_environment

Mode = Literal["prefill", "kv_decode", "e2e_kv"]


def _now_run_id() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, obj: Any) -> None:
    _ensure_dir(path.parent)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Transformers runner (reuses TR120/Phase2 patterns)
# ---------------------------------------------------------------------------


def _run_transformers(
    model,
    tokenizer,
    device,
    prompts: list[str],
    mode: Mode,
    max_new_tokens: int,
    repetitions: int,
    warmup_reps: int,
) -> list[dict[str, Any]]:
    """Run transformers backend (eager or compiled) on prompts."""
    import torch

    # Tokenize
    tokenized = []
    for prompt in prompts:
        enc = tokenizer(prompt, return_tensors="pt", add_special_tokens=True)
        tokenized.append(
            {
                "input_ids": enc["input_ids"].to(device),
                "attention_mask": enc.get(
                    "attention_mask", torch.ones_like(enc["input_ids"])
                ).to(device),
                "prompt": prompt,
            }
        )

    # Warmup
    for _ in range(warmup_reps):
        for enc in tokenized:
            with torch.no_grad():
                if device.type == "cuda":
                    torch.cuda.synchronize()
                out = model(
                    input_ids=enc["input_ids"],
                    attention_mask=enc["attention_mask"],
                    use_cache=True,
                )
                if mode in ("kv_decode", "e2e_kv"):
                    logits = out.logits[:, -1, :]
                    past = out.past_key_values
                    next_tok = torch.argmax(logits, dim=-1, keepdim=True)
                    for _ in range(min(max_new_tokens, 4)):
                        out2 = model(
                            input_ids=next_tok, use_cache=True, past_key_values=past
                        )
                        past = out2.past_key_values
                        next_tok = torch.argmax(
                            out2.logits[:, -1, :], dim=-1, keepdim=True
                        )
                if device.type == "cuda":
                    torch.cuda.synchronize()

    # Measure
    rows: list[dict[str, Any]] = []
    for _ in range(repetitions):
        for enc in tokenized:
            input_ids = enc["input_ids"]
            attn_mask = enc["attention_mask"]

            if device.type == "cuda":
                torch.cuda.synchronize()
            start = time.perf_counter()

            with torch.no_grad():
                if mode == "prefill":
                    out = model(
                        input_ids=input_ids, attention_mask=attn_mask, use_cache=True
                    )
                    if device.type == "cuda":
                        torch.cuda.synchronize()
                    wall_ms = (time.perf_counter() - start) * 1000.0
                    n_tokens = int(attn_mask.sum().item())
                elif mode == "kv_decode":
                    out = model(
                        input_ids=input_ids, attention_mask=attn_mask, use_cache=True
                    )
                    logits = out.logits[:, -1, :]
                    past = out.past_key_values
                    next_tok = torch.argmax(logits, dim=-1, keepdim=True)

                    if device.type == "cuda":
                        torch.cuda.synchronize()
                    dec_start = time.perf_counter()
                    generated = 0
                    for _ in range(max_new_tokens):
                        out2 = model(
                            input_ids=next_tok, use_cache=True, past_key_values=past
                        )
                        logits = out2.logits[:, -1, :]
                        past = out2.past_key_values
                        next_tok = torch.argmax(logits, dim=-1, keepdim=True)
                        generated += 1
                    if device.type == "cuda":
                        torch.cuda.synchronize()
                    wall_ms = (time.perf_counter() - dec_start) * 1000.0
                    n_tokens = generated
                elif mode == "e2e_kv":
                    out = model(
                        input_ids=input_ids, attention_mask=attn_mask, use_cache=True
                    )
                    logits = out.logits[:, -1, :]
                    past = out.past_key_values
                    next_tok = torch.argmax(logits, dim=-1, keepdim=True)
                    generated = 0
                    for _ in range(max_new_tokens):
                        out2 = model(
                            input_ids=next_tok, use_cache=True, past_key_values=past
                        )
                        logits = out2.logits[:, -1, :]
                        past = out2.past_key_values
                        next_tok = torch.argmax(logits, dim=-1, keepdim=True)
                        generated += 1
                    if device.type == "cuda":
                        torch.cuda.synchronize()
                    wall_ms = (time.perf_counter() - start) * 1000.0
                    n_tokens = int(attn_mask.sum().item()) + generated
                else:
                    raise ValueError(f"Unknown mode: {mode}")

            tps = (n_tokens / (wall_ms / 1000.0)) if wall_ms > 0 else 0.0
            rows.append(
                {
                    "latency_ms": wall_ms,
                    "tokens": n_tokens,
                    "tokens_per_s": tps,
                    "status": "ok",
                }
            )

    return rows


# ---------------------------------------------------------------------------
# Ollama runner
# ---------------------------------------------------------------------------


def _run_ollama(
    ollama_tag: str,
    prompts: list[str],
    mode: Mode,
    max_new_tokens: int,
    repetitions: int,
    ollama_url: str,
    timeout_s: int,
) -> list[dict[str, Any]]:
    """Run Ollama backend via HTTP API."""
    rows: list[dict[str, Any]] = []

    for _ in range(repetitions):
        for prompt in prompts:
            try:
                start = time.perf_counter()
                resp = requests.post(
                    f"{ollama_url}/api/generate",
                    json={
                        "model": ollama_tag,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "num_predict": max_new_tokens,
                            "temperature": 0.0,
                            "seed": 42,
                        },
                    },
                    timeout=timeout_s,
                )
                wall_ms = (time.perf_counter() - start) * 1000.0
                resp.raise_for_status()
                data = resp.json()

                # Extract Ollama native timing
                eval_duration_ns = data.get("eval_duration", 0)
                prompt_eval_duration_ns = data.get("prompt_eval_duration", 0)
                eval_count = data.get("eval_count", 0)
                prompt_eval_count = data.get("prompt_eval_count", 0)

                if mode == "prefill":
                    latency_ms = (
                        prompt_eval_duration_ns / 1e6
                        if prompt_eval_duration_ns
                        else wall_ms
                    )
                    n_tokens = prompt_eval_count
                elif mode == "kv_decode":
                    latency_ms = eval_duration_ns / 1e6 if eval_duration_ns else wall_ms
                    n_tokens = eval_count
                elif mode == "e2e_kv":
                    latency_ms = wall_ms
                    n_tokens = prompt_eval_count + eval_count
                else:
                    latency_ms = wall_ms
                    n_tokens = eval_count

                tps = (n_tokens / (latency_ms / 1000.0)) if latency_ms > 0 else 0.0
                rows.append(
                    {
                        "latency_ms": latency_ms,
                        "tokens": n_tokens,
                        "tokens_per_s": tps,
                        "status": "ok",
                        "wall_ms": wall_ms,
                        "ollama_eval_ms": (
                            eval_duration_ns / 1e6 if eval_duration_ns else None
                        ),
                        "ollama_prompt_eval_ms": (
                            prompt_eval_duration_ns / 1e6
                            if prompt_eval_duration_ns
                            else None
                        ),
                    }
                )
            except Exception as e:
                rows.append(
                    {
                        "latency_ms": 0.0,
                        "tokens": 0,
                        "tokens_per_s": 0.0,
                        "status": "error",
                        "error": str(e),
                    }
                )

    return rows


# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------


def _write_metrics_csv(rows: list[dict[str, Any]], out_path: Path) -> None:
    _ensure_dir(out_path.parent)
    if not rows:
        return
    # Collect all keys across all rows (Ollama rows have extra fields vs HF rows)
    all_keys: list[str] = []
    seen: set[str] = set()
    for r in rows:
        for k in r:
            if k not in seen:
                all_keys.append(k)
                seen.add(k)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="TR126 Phase 3: backend matrix rerun")
    parser.add_argument("--config", type=Path, default=_DIR / "config.yaml")
    parser.add_argument("--out-root", type=Path, default=None)
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output.")
    args = parser.parse_args()

    cfg = _load_yaml(args.config)
    tier3 = _load_yaml(_REPO / cfg["tier3_config"])

    run_id = _now_run_id()
    out_root = args.out_root or (
        _REPO / cfg.get("output_dir", "research/tr126/results/phase3")
    )
    out_root = out_root / run_id
    _ensure_dir(out_root)

    device_str = cfg.get("device", "cuda")
    dtype_str = cfg.get("dtype", "fp32")
    repetitions = int(cfg.get("repetitions", 7))
    warmup_reps = int(cfg.get("warmup_repetitions", 2))
    max_new_tokens = int(cfg.get("max_new_tokens", 128))
    backends = cfg.get("backends", [])
    models = cfg.get("models", [])
    scenarios_allow = set(cfg.get("scenarios", []))
    modes: list[Mode] = [
        m
        for m in cfg.get("modes", ["e2e_kv"])
        if m in ("prefill", "kv_decode", "e2e_kv")
    ]
    compile_cfg = dict(cfg.get("torch_compile", {}) or {})
    ollama_url = cfg.get("ollama_url", "http://localhost:11434")
    ollama_timeout = int(cfg.get("ollama_timeout_s", 120))

    # Resolve scenarios from tier3 config
    tier3_scenarios = tier3.get("scenarios", [])
    scenarios = [s for s in tier3_scenarios if s.get("name") in scenarios_allow]
    prompt_sets = tier3.get("prompt_sets", {})

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    device = torch.device(device_str if torch.cuda.is_available() else "cpu")

    # Manifest
    manifest = {
        "run_id": run_id,
        "platform": "linux-docker",
        "backends": backends,
        "models": [m["name"] for m in models],
        "scenarios": [s["name"] for s in scenarios],
        "modes": modes,
        "repetitions": repetitions,
        "max_new_tokens": max_new_tokens,
        "environment": capture_environment(),
    }
    _write_json(out_root / "manifest.json", manifest)

    # Determine which models have local HF paths
    hf_local: dict[str, bool] = {}
    for model_cfg in models:
        mname = model_cfg["name"]
        local_path = Path(mname) if Path(mname).is_absolute() else (_REPO / mname)
        hf_local[mname] = local_path.exists()
        if not hf_local[mname]:
            print(f"  No local HF path for {mname} (Ollama-only)")

    # Accumulate rows per mode across all models
    mode_rows: dict[str, list[dict[str, Any]]] = {m: [] for m in modes}

    # Outer loop: model (load once, run all modes, then free)
    for model_idx, model_cfg in enumerate(models, 1):
        mname = model_cfg["name"]
        ollama_tag = model_cfg.get("ollama_tag")
        model_dtype_str = model_cfg.get("dtype", dtype_str)
        model_torch_dtype = (
            torch.float16 if model_dtype_str == "fp16" else torch.float32
        )
        model_quant = "fp16" if model_dtype_str == "fp16" else "fp32"

        print(f"\n{'='*60}")
        print(f"Model {model_idx}/{len(models)}: {mname} (dtype={model_dtype_str})")
        print(f"{'='*60}")

        # Load HF model (if applicable)
        eager_model = None
        compiled_model = None
        tok = None

        if hf_local[mname]:
            print(f"  Loading HF model: {mname}")
            tok = AutoTokenizer.from_pretrained(mname, local_files_only=True)
            if tok.pad_token_id is None and tok.eos_token_id is not None:
                tok.pad_token_id = tok.eos_token_id
            eager_model = AutoModelForCausalLM.from_pretrained(
                mname, local_files_only=True, dtype=model_torch_dtype
            )
            eager_model.eval().to(device)

            # Compile with Triton
            torch._dynamo.reset()
            compiled_model = torch.compile(
                eager_model,
                backend=compile_cfg.get("backend", "inductor"),
                mode=compile_cfg.get("mode", "reduce-overhead"),
            )
            dummy = torch.ones((1, 8), dtype=torch.long, device=device)
            with torch.no_grad():
                _ = compiled_model(input_ids=dummy, use_cache=True)
            if device.type == "cuda":
                torch.cuda.synchronize()
            print(f"  Compiled with {compile_cfg.get('backend', 'inductor')}")

        # Run all modes × scenarios × backends for this model
        for mode in modes:
            for scenario in scenarios:
                scenario_name = scenario["name"]
                prompt_set_name = scenario.get("prompt_set", "short")
                prompts = [str(p) for p in prompt_sets.get(prompt_set_name, ["Hello"])]

                for backend in backends:
                    # Skip incompatible combos
                    if backend == "ollama" and not ollama_tag:
                        continue
                    if backend.startswith("transformers") and not hf_local[mname]:
                        continue

                    print(
                        f"  [{mode}] {scenario_name} / {mname} / {backend}...",
                        end=" ",
                        flush=True,
                    )

                    try:
                        if backend == "ollama":
                            rows = _run_ollama(
                                ollama_tag,
                                prompts,
                                mode,
                                max_new_tokens,
                                repetitions,
                                ollama_url,
                                ollama_timeout,
                            )
                        elif backend == "transformers-gpu-compile":
                            rows = _run_transformers(
                                compiled_model,
                                tok,
                                device,
                                prompts,
                                mode,
                                max_new_tokens,
                                repetitions,
                                warmup_reps,
                            )
                        elif backend == "transformers-gpu":
                            rows = _run_transformers(
                                eager_model,
                                tok,
                                device,
                                prompts,
                                mode,
                                max_new_tokens,
                                repetitions,
                                warmup_reps,
                            )
                        else:
                            print("skipped (unsupported)")
                            continue
                    except Exception as e:
                        # Catch CUDA OOM and other unexpected errors gracefully
                        print(f"ERROR: {e}")
                        traceback.print_exc()
                        rows = [
                            {
                                "latency_ms": 0.0,
                                "tokens": 0,
                                "tokens_per_s": 0.0,
                                "status": "error",
                                "error": str(e),
                            }
                        ]
                        # Try to recover GPU memory after OOM
                        if "out of memory" in str(e).lower():
                            gc.collect()
                            torch.cuda.empty_cache()

                    # Tag rows
                    for r in rows:
                        r["scenario"] = scenario_name
                        r["prompt_set"] = prompt_set_name
                        r["backend"] = backend
                        r["model"] = mname
                        r["quantization"] = model_quant

                    ok = sum(1 for r in rows if r.get("status") == "ok")
                    print(f"{ok}/{len(rows)} ok")
                    mode_rows[mode].extend(rows)

        # Free GPU memory before next model
        if eager_model is not None:
            print(f"  Freeing {mname}...")
            del eager_model, compiled_model, tok
            gc.collect()
            torch.cuda.empty_cache()

    # Write per-mode CSVs
    for mode in modes:
        rows = mode_rows[mode]
        out_path = out_root / mode / "metrics.csv"
        _write_metrics_csv(rows, out_path)
        print(f"  {mode}: {len(rows)} total rows")

    print(f"\nPhase 3 matrix written to: {out_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
