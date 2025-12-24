#!/usr/bin/env python3
"""
TR121: Model scaling study runner.

Measures prefill and KV-cached decode separately (TR120-style) for:
  - Local Hugging Face models (via torch eager)
  - Ollama models (via /api/generate; uses prompt_eval_duration / eval_duration)

Outputs (under --out-dir):
  - manifest.json
  - metrics.csv
  - runs.jsonl (one record per measurement)

This runner is intentionally minimal and artifact-first (TR118/TR120 style).
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import math
import os
from pathlib import Path
import platform
import random
import hashlib
import sys
import time
from typing import Any
import urllib.request

import yaml


def _now_run_id() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _git_head() -> str | None:
    import subprocess

    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=_repo_root())
        return out.decode("utf-8").strip()
    except Exception:
        return None


def _safe_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True)


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _relpath_safe(p: Path, base: Path) -> str:
    try:
        return str(p.relative_to(base))
    except Exception:
        return str(p)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for k in row.keys():
            if k not in fieldnames:
                fieldnames.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def _cuda_available() -> bool:
    try:
        import torch  # type: ignore

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _torch_versions() -> dict[str, str | None]:
    out: dict[str, str | None] = {"torch": None, "transformers": None}
    try:
        import torch  # type: ignore

        out["torch"] = getattr(torch, "__version__", None)
        out["cuda"] = getattr(torch.version, "cuda", None)
    except Exception:
        pass
    try:
        import transformers  # type: ignore

        out["transformers"] = getattr(transformers, "__version__", None)
    except Exception:
        pass
    return out


def _nvml_info() -> dict[str, Any] | None:
    try:
        import pynvml  # type: ignore

        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        name = pynvml.nvmlDeviceGetName(h)
        mem = pynvml.nvmlDeviceGetMemoryInfo(h)
        return {
            "name": name.decode("utf-8") if isinstance(name, (bytes, bytearray)) else str(name),
            "memory_total_mb": float(mem.total) / (1024**2),
        }
    except Exception:
        return None
    finally:
        try:
            import pynvml  # type: ignore

            pynvml.nvmlShutdown()
        except Exception:
            pass


def _dtype_from_str(s: str):
    import torch  # type: ignore

    v = (s or "fp32").strip().lower()
    if v in ("fp16", "float16", "half"):
        return torch.float16
    if v in ("bf16", "bfloat16"):
        return torch.bfloat16
    return torch.float32


def _cuda_event_timer(device: str):
    if device != "cuda":
        return None
    try:
        import torch  # type: ignore

        if not torch.cuda.is_available():
            return None
        start = torch.cuda.Event(enable_timing=True)
        end = torch.cuda.Event(enable_timing=True)

        def time_fn(fn):
            torch.cuda.synchronize()
            start.record()
            out = fn()
            end.record()
            torch.cuda.synchronize()
            return float(start.elapsed_time(end)), out

        return time_fn
    except Exception:
        return None


def _load_hf(model_path: str, device: str, dtype: str):
    import torch  # type: ignore
    from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore

    tok = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    if getattr(tok, "pad_token", None) is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(model_path, local_files_only=True, dtype=_dtype_from_str(dtype))
    model.eval()
    dev = torch.device("cuda" if device == "cuda" else "cpu")
    model.to(dev)
    return tok, model, dev


def _measure_hf(
    *,
    tok,
    model,
    device,
    prompt: str,
    gen_tokens: int,
    batch_size: int,
) -> dict[str, Any]:
    """
    Measures both prefill and KV decode (TR120-style) and returns component timings.

    Projection into per-mode "latency_ms" is done by the caller.
    """
    import torch  # type: ignore

    bs = int(batch_size) if int(batch_size) > 0 else 1
    prompts = [prompt] * bs
    enc = tok(prompts, return_tensors="pt", add_special_tokens=True, padding=True)
    input_ids = enc["input_ids"].to(device)
    attention_mask = enc.get("attention_mask")
    if attention_mask is not None:
        attention_mask = attention_mask.to(device)
    seq_len = int(input_ids.shape[1])
    prompt_tokens_total = int(attention_mask.sum().item()) if attention_mask is not None else int(bs * seq_len)
    timer = _cuda_event_timer("cuda" if device.type == "cuda" else "cpu")

    # Memory snapshot (best-effort)
    gpu_peak_mb = None
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats()

    def prefill_call():
        with torch.no_grad():
            return model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                use_cache=True,
            )

    started = time.perf_counter()
    if timer is not None:
        cuda_ms, out = timer(prefill_call)
    else:
        out = prefill_call()
        cuda_ms = None
    prefill_ms = (time.perf_counter() - started) * 1000.0

    past = getattr(out, "past_key_values", None)
    if past is None:
        # Fallback: treat as degraded.
        return {
            "status": "error",
            "error": "missing_past_key_values",
            "batch_size": bs,
            "seq_len": seq_len,
            "prompt_tokens_raw": prompt_tokens_total,
            "gen_tokens_raw": int(gen_tokens) * bs,
        }

    def decode_loop():
        # Start from the last prompt token and greedily step.
        next_token = input_ids[:, -1:]
        kv = past
        with torch.no_grad():
            for _ in range(gen_tokens):
                r = model(
                    input_ids=next_token,
                    attention_mask=None,
                    past_key_values=kv,
                    use_cache=True,
                )
                logits = r.logits
                kv = r.past_key_values
                next_token = torch.argmax(logits[:, -1, :], dim=-1, keepdim=True)

    started = time.perf_counter()
    if timer is not None:
        decode_cuda_ms, _ = timer(lambda: decode_loop())
    else:
        decode_loop()
        decode_cuda_ms = None
    decode_ms = (time.perf_counter() - started) * 1000.0

    if device.type == "cuda":
        gpu_peak_mb = float(torch.cuda.max_memory_allocated()) / (1024**2)

    return {
        "status": "ok",
        "error": "",
        "batch_size": bs,
        "seq_len": seq_len,
        "prompt_tokens_raw": prompt_tokens_total,
        "gen_tokens_raw": int(gen_tokens) * bs,
        "prefill_ms": prefill_ms,
        "prefill_cuda_event_ms": cuda_ms,
        "kv_decode_ms": decode_ms,
        "kv_decode_cuda_event_ms": decode_cuda_ms,
        "gpu_peak_mb": gpu_peak_mb,
    }


def _ollama_generate(url: str, model: str, prompt: str, options: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": options,
    }
    req = urllib.request.Request(
        f"{url}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # type: ignore[attr-defined]
        body = resp.read().decode("utf-8")
    return json.loads(body)


def _ollama_tags(url: str, timeout_s: float) -> dict[str, Any]:
    req = urllib.request.Request(f"{url}/api/tags", method="GET")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # type: ignore[attr-defined]
        body = resp.read().decode("utf-8")
    return json.loads(body)


def _parse_ollama_parameter_size(s: str | None) -> float | None:
    if not s:
        return None
    v = str(s).strip().upper().replace(",", "")
    try:
        if v.endswith("B"):
            return float(v[:-1]) * 1000.0
        if v.endswith("M"):
            return float(v[:-1])
    except Exception:
        return None
    return None


def _measure_ollama(
    *,
    url: str,
    model: str,
    prompt: str,
    gen_tokens: int,
    options: dict[str, Any],
    timeout_s: float,
) -> dict[str, Any]:
    # Ensure fixed decode budget
    opts = dict(options or {})
    opts.setdefault("num_predict", int(gen_tokens))
    started = time.perf_counter()
    data = _ollama_generate(url, model, prompt, opts, timeout_s=timeout_s)
    wall_ms = (time.perf_counter() - started) * 1000.0

    prompt_tokens = int(data.get("prompt_eval_count") or 0)
    eval_tokens = int(data.get("eval_count") or 0)
    prompt_eval_ms = float(data.get("prompt_eval_duration") or 0) / 1e6
    eval_ms = float(data.get("eval_duration") or 0) / 1e6
    load_ms = float(data.get("load_duration") or 0) / 1e6
    total_duration_ms = float(data.get("total_duration") or 0) / 1e6

    kv_ms_per_token = (eval_ms / eval_tokens) if eval_tokens > 0 else float("nan")
    kv_decode_ms_equiv = (kv_ms_per_token * float(gen_tokens)) if eval_tokens > 0 else eval_ms

    return {
        "status": "ok" if data.get("done") else "error",
        "error": "",
        "batch_size": 1,
        "seq_len": None,
        "prompt_tokens_raw": prompt_tokens,
        "prefill_ms": prompt_eval_ms,
        "prefill_cuda_event_ms": None,
        "kv_decode_ms": eval_ms,
        "kv_decode_ms_equiv": kv_decode_ms_equiv,
        "kv_decode_ms_per_token": kv_ms_per_token,
        "kv_decode_cuda_event_ms": None,
        "gen_tokens_raw": eval_tokens,
        "gen_tokens_equiv": int(gen_tokens),
        "ollama_wall_ms": wall_ms,
        "ollama_total_duration_ms": total_duration_ms,
        "ollama_load_ms": load_ms,
        "ollama_done_reason": data.get("done_reason"),
    }


@dataclasses.dataclass
class ModelSpec:
    name: str
    kind: str
    params_millions: float


@dataclasses.dataclass
class BackendSpec:
    name: str
    kind: str
    device: str | None = None
    dtype: str | None = None
    batch_size: int | None = None
    url: str | None = None
    options: dict[str, Any] | None = None


def main() -> int:
    ap = argparse.ArgumentParser(description="TR121 scaling runner")
    ap.add_argument("--config", default="scripts/tr121/configs/scaling.yaml")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--repetitions", type=int, default=None)
    ap.add_argument("--warmup-repetitions", type=int, default=None)
    ap.add_argument("--gen-tokens", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--ollama-timeout-s", type=float, default=300.0)
    ap.add_argument(
        "--models",
        default=None,
        help="Optional comma-separated allowlist of model names from config.",
    )
    ap.add_argument(
        "--backends",
        default=None,
        help="Optional comma-separated allowlist of backend names from config.",
    )
    ap.add_argument(
        "--scenarios",
        default=None,
        help="Optional comma-separated allowlist of scenario names from config.",
    )
    args = ap.parse_args()

    cfg_path = Path(args.config)
    cfg_bytes = cfg_path.read_bytes()
    cfg = yaml.safe_load(cfg_bytes.decode("utf-8"))
    run_id = _now_run_id()
    out_dir = Path(args.out_dir) if args.out_dir else Path("scripts/tr121/results") / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    repetitions = int(args.repetitions) if args.repetitions is not None else int(cfg.get("repetitions") or 1)
    warmups = int(args.warmup_repetitions) if args.warmup_repetitions is not None else int(cfg.get("warmup_repetitions") or 0)
    gen_tokens = int(args.gen_tokens) if args.gen_tokens is not None else int(cfg.get("gen_tokens") or 64)
    seed = int(args.seed) if args.seed is not None else int(cfg.get("seed") or 0)

    scenarios = cfg.get("scenarios") or []
    models = [ModelSpec(**m) for m in (cfg.get("models") or [])]
    backends = [BackendSpec(**b) for b in (cfg.get("backends") or [])]

    allow_models = {s.strip() for s in str(args.models).split(",")} if args.models else None
    allow_backends = {s.strip() for s in str(args.backends).split(",")} if args.backends else None
    allow_scenarios = {s.strip() for s in str(args.scenarios).split(",")} if args.scenarios else None

    if allow_models is not None:
        models = [m for m in models if m.name in allow_models]
    if allow_backends is not None:
        backends = [b for b in backends if b.name in allow_backends]
    if allow_scenarios is not None:
        scenarios = [s for s in scenarios if str(s.get("name")) in allow_scenarios]

    resolved = {
        "scenarios": [{"name": str(s.get("name")), "prompt": str(s.get("prompt"))} for s in scenarios],
        "models": [dataclasses.asdict(m) for m in models],
        "backends": [dataclasses.asdict(b) for b in backends],
        "filters": {
            "models_allowlist": sorted(list(allow_models)) if allow_models is not None else None,
            "backends_allowlist": sorted(list(allow_backends)) if allow_backends is not None else None,
            "scenarios_allowlist": sorted(list(allow_scenarios)) if allow_scenarios is not None else None,
        },
    }

    manifest: dict[str, Any] = {
        "run_id": run_id,
        "run_name": cfg.get("run_name"),
        "argv": list(sys.argv),
        "config_path": str(cfg_path),
        "config_sha256": _sha256_bytes(cfg_bytes),
        "git_head": _git_head(),
        "platform": {
            "python": platform.python_version(),
            "os": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
        "torch": _torch_versions(),
        "nvml": _nvml_info(),
        "cuda_available": _cuda_available(),
        "repetitions": repetitions,
        "warmup_repetitions": warmups,
        "gen_tokens": gen_tokens,
        "seed": seed,
        "ollama_timeout_s": float(args.ollama_timeout_s),
        "resolved": resolved,
    }

    runs_jsonl = out_dir / "runs.jsonl"
    metrics_rows: list[dict[str, Any]] = []

    # HF cache: {model_path, device, dtype} -> (tok, model, device)
    hf_cache: dict[tuple[str, str, str], tuple[Any, Any, Any]] = {}
    hf_load_ms: dict[tuple[str, str, str], float] = {}
    hf_params_millions: dict[tuple[str, str, str], float] = {}

    runs_jsonl.write_text("", encoding="utf-8")

    def write_record(f, rec: dict[str, Any]) -> None:
        f.write(json.dumps(rec) + "\n")

    def project_mode(meas: dict[str, Any], mode: str) -> dict[str, Any]:
        batch_size = int(meas.get("batch_size") or 1)
        prompt_tokens_total = int(meas.get("prompt_tokens_raw") or 0)
        gen_tokens_raw = int(meas.get("gen_tokens_raw") or 0)
        gen_tokens_equiv = int(meas.get("gen_tokens_equiv") or gen_tokens_raw)
        prefill_ms = float(meas.get("prefill_ms") or 0.0)
        decode_ms = float(meas.get("kv_decode_ms") or 0.0)
        decode_ms_equiv = float(meas.get("kv_decode_ms_equiv") or decode_ms)
        prefill_cuda = meas.get("prefill_cuda_event_ms")
        decode_cuda = meas.get("kv_decode_cuda_event_ms")

        if mode == "prefill":
            latency_ms = prefill_ms
            cuda_ms = prefill_cuda
            tokens_total = prompt_tokens_total
            gen_tokens_mode = 0
        elif mode == "kv_decode":
            latency_ms = decode_ms_equiv
            cuda_ms = decode_cuda
            tokens_total = gen_tokens_equiv
            gen_tokens_mode = gen_tokens_equiv
        else:
            latency_ms = prefill_ms + decode_ms_equiv
            cuda_ms = (
                float(prefill_cuda) + float(decode_cuda)
                if (prefill_cuda is not None and decode_cuda is not None)
                else None
            )
            tokens_total = prompt_tokens_total + gen_tokens_equiv
            gen_tokens_mode = gen_tokens_equiv

        tok_s = (tokens_total / (latency_ms / 1000.0)) if latency_ms > 0 else float("nan")
        return {
            "mode": mode,
            "latency_ms": latency_ms,
            "cuda_event_ms": cuda_ms,
            "tokens_total": tokens_total,
            "tokens_per_s": tok_s,
            "gen_tokens": gen_tokens_mode,
            "batch_size": batch_size,
        }

    rng = random.Random(seed)

    tasks: list[tuple[dict[str, Any], ModelSpec, BackendSpec]] = []
    for scenario in scenarios:
        for model in models:
            for backend in backends:
                if backend.kind != model.kind:
                    continue
                if backend.kind == "hf" and backend.device == "cuda" and not _cuda_available():
                    continue
                tasks.append((scenario, model, backend))
    rng.shuffle(tasks)

    manifest["task_count"] = int(len(tasks))
    manifest["modes"] = ["prefill", "kv_decode", "e2e_kv"]
    manifest["records_expected"] = int(len(tasks) * (warmups + repetitions) * 3)
    (out_dir / "manifest.json").write_text(_safe_json(manifest), encoding="utf-8")

    # Resolve Ollama model sizes (best-effort; used for scaling-law x-axis when available).
    ollama_params_millions: dict[str, float] = {}
    ollama_details: dict[str, dict[str, Any]] = {}
    for backend in backends:
        if backend.kind != "ollama":
            continue
        try:
            tags = _ollama_tags(str(backend.url), timeout_s=float(args.ollama_timeout_s))
            for m in tags.get("models") or []:
                name = str(m.get("name") or m.get("model") or "")
                details = m.get("details") or {}
                pm = _parse_ollama_parameter_size(details.get("parameter_size"))
                if name and isinstance(details, dict):
                    ollama_details[name] = {
                        "parameter_size_raw": details.get("parameter_size"),
                        "quantization_level": details.get("quantization_level"),
                        "family": details.get("family"),
                    }
                if name and pm is not None:
                    ollama_params_millions[name] = float(pm)
        except Exception:
            # Keep best-effort; config still supplies params_millions for every model.
            pass

    def _get_or_load_hf(model_name: str, device: str, dtype: str) -> tuple[Any, Any, Any, float | None, float | None]:
        key = (model_name, device, dtype)
        if key in hf_cache:
            return (*hf_cache[key], None, hf_params_millions.get(key))
        t0 = time.perf_counter()
        tok, hf_model, dev = _load_hf(model_name, device, dtype)
        load_ms = (time.perf_counter() - t0) * 1000.0
        hf_cache[key] = (tok, hf_model, dev)
        hf_load_ms[key] = load_ms
        try:
            import torch  # type: ignore

            hf_params_millions[key] = float(sum(p.numel() for p in hf_model.parameters())) / 1e6
        except Exception:
            hf_params_millions[key] = float("nan")
        return tok, hf_model, dev, load_ms, hf_params_millions.get(key)

    def _measure_one(
        *,
        scenario_name: str,
        prompt: str,
        model: ModelSpec,
        backend: BackendSpec,
    ) -> dict[str, Any]:
        if backend.kind == "hf":
            tok, hf_model, dev, load_ms, params_m = _get_or_load_hf(
                model.name, str(backend.device or "cpu"), str(backend.dtype or "fp32")
            )
            meas = _measure_hf(
                tok=tok,
                model=hf_model,
                device=dev,
                prompt=prompt,
                gen_tokens=gen_tokens,
                batch_size=int(backend.batch_size or 1),
            )
            if load_ms is not None:
                meas["hf_load_ms"] = load_ms
            if params_m is not None and math.isfinite(float(params_m)):
                meas["params_millions_measured"] = float(params_m)
            return meas

        # ollama
        opts = dict(backend.options or {})
        # If supported, set deterministic seed unless the user overrides it.
        opts.setdefault("seed", seed)
        meas = _measure_ollama(
            url=str(backend.url),
            model=model.name,
            prompt=prompt,
            gen_tokens=gen_tokens,
            options=opts,
            timeout_s=float(args.ollama_timeout_s),
        )
        pm = ollama_params_millions.get(model.name)
        if pm is not None and math.isfinite(float(pm)):
            meas["params_millions_measured"] = float(pm)
        return meas

    call_idx = 0
    sample_idx = 0
    with runs_jsonl.open("a", encoding="utf-8") as runs_f:
        for task_idx, (scenario, model, backend) in enumerate(tasks):
            scenario_name = str(scenario["name"])
            prompt = str(scenario["prompt"])

            base_meta = {
                "task_idx": task_idx,
                "scenario": scenario_name,
                "backend": backend.name,
                "backend_kind": backend.kind,
                "model": model.name,
                "model_kind": model.kind,
                "params_millions": float(model.params_millions),
                "params_millions_config": float(model.params_millions),
                "prompt": prompt,
                "prompt_chars": int(len(prompt)),
                "gen_tokens_target": gen_tokens,
                "batch_size_config": int(backend.batch_size or 1),
            }

            for warmup_idx in range(warmups):
                started = time.time()
                try:
                    meas = _measure_one(
                        scenario_name=scenario_name,
                        prompt=prompt,
                        model=model,
                        backend=backend,
                    )
                except Exception as exc:
                    meas = {"status": "error", "error": str(exc)}
                this_call_idx = call_idx
                call_idx += 1

                for mode in ("prefill", "kv_decode", "e2e_kv"):
                    projected = project_mode(meas, mode) if meas.get("status") == "ok" else {}
                    rec = {
                        **base_meta,
                        "call_idx": this_call_idx,
                        "sample_idx": sample_idx,
                        "is_warmup": True,
                        "warmup_idx": warmup_idx,
                        "rep": None,
                        "mode": mode,
                        "status": meas.get("status"),
                        "error": meas.get("error", ""),
                        "started_at_unix": started,
                        **{k: v for k, v in meas.items() if k not in ("status", "error")},
                        **projected,
                    }
                    write_record(runs_f, rec)
                    metrics_rows.append(rec)
                    sample_idx += 1

            for rep in range(repetitions):
                started = time.time()
                try:
                    meas = _measure_one(
                        scenario_name=scenario_name,
                        prompt=prompt,
                        model=model,
                        backend=backend,
                    )
                except Exception as exc:
                    meas = {"status": "error", "error": str(exc)}
                this_call_idx = call_idx
                call_idx += 1

                for mode in ("prefill", "kv_decode", "e2e_kv"):
                    projected = project_mode(meas, mode) if meas.get("status") == "ok" else {}
                    rec = {
                        **base_meta,
                        "call_idx": this_call_idx,
                        "sample_idx": sample_idx,
                        "is_warmup": False,
                        "warmup_idx": None,
                        "rep": rep,
                        "mode": mode,
                        "status": meas.get("status"),
                        "error": meas.get("error", ""),
                        "started_at_unix": started,
                        **{k: v for k, v in meas.items() if k not in ("status", "error")},
                        **projected,
                    }
                    write_record(runs_f, rec)
                    metrics_rows.append(rec)
                    sample_idx += 1

    _write_csv(out_dir / "metrics.csv", metrics_rows)
    _write_csv(out_dir / "hf_load_ms.csv", [{"model": k[0], "device": k[1], "dtype": k[2], "hf_load_ms": v} for k, v in hf_load_ms.items()])
    _write_csv(
        out_dir / "resolved_model_params.csv",
        [
            {
                "model": m.name,
                "kind": m.kind,
                "params_millions_config": float(m.params_millions),
                "params_millions_measured": ollama_params_millions.get(m.name),
                **(ollama_details.get(m.name) or {}),
            }
            for m in models
            if m.kind == "ollama"
        ]
        + [
            {"model": k[0], "kind": "hf", "device": k[1], "dtype": k[2], "params_millions_measured": v}
            for k, v in hf_params_millions.items()
        ],
    )

    # Rewrite manifest with end-of-run measurements (exact HF params, Ollama tag-derived params).
    manifest["results"] = {
        "metrics_csv": _relpath_safe(out_dir / "metrics.csv", _repo_root()),
        "runs_jsonl": _relpath_safe(out_dir / "runs.jsonl", _repo_root()),
        "hf_load_ms_csv": _relpath_safe(out_dir / "hf_load_ms.csv", _repo_root()),
        "resolved_model_params_csv": _relpath_safe(out_dir / "resolved_model_params.csv", _repo_root()),
    }
    manifest["measured_params"] = {
        "hf_params_millions": [
            {"model": k[0], "device": k[1], "dtype": k[2], "params_millions_measured": v}
            for k, v in sorted(hf_params_millions.items())
        ],
        "ollama_params_millions": [
            {
                "model": m.name,
                "params_millions_measured": ollama_params_millions.get(m.name),
                **(ollama_details.get(m.name) or {}),
            }
            for m in models
            if m.kind == "ollama"
        ],
    }
    (out_dir / "manifest.json").write_text(_safe_json(manifest), encoding="utf-8")
    print(f"TR121 run written to: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
