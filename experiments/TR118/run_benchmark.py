#!/usr/bin/env python3
"""
TR118: ONNX Runtime + TensorRT deep-dive benchmark runner.

Design goal: TR115_v2-level statistical rigor (run-level samples, repeatable matrix).

Output:
- Run-level JSONL under `scripts/tr118/results/raw/bench_<mode>_<ts>.jsonl`
  Each line corresponds to one (backend, scenario, repetition) run and contains
  per-prompt latencies plus run-level summaries and optional resource metrics.

This runner is local-first and degrades gracefully when optional deps are missing:
- onnxruntime / onnxruntime-gpu
- tensorrt + pycuda
- pynvml/psutil for resource monitoring
"""

from __future__ import annotations

import argparse
import contextlib
from dataclasses import asdict, dataclass, field
import json
import logging
import os
from pathlib import Path
import platform
import sys
import time
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.tr118.artifact_utils import (
    file_sha256,
    inspect_model_weight_files,
    inspect_onnx_artifact,
    inspect_trt_engine,
    resolve_repo_path,
)
from scripts.tr118.build_trt_engines import build_tensorrt_engine
from scripts.tr118.export_to_onnx import export_model_to_onnx
from scripts.tr118.onnx_sanitize import sanitize_onnx_file
from scripts.tr118.trt_inference import TensorRTInferenceEngine

try:
    from scripts.tr117.instrumentation import ResourceMonitor  # type: ignore
except Exception:  # pragma: no cover - optional
    ResourceMonitor = None  # type: ignore

logger = logging.getLogger("tr118")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def _maybe_sha256(path: Path, max_mb: float = 512.0) -> str | None:
    try:
        if not path.exists():
            return None
        if float(path.stat().st_size) > float(max_mb) * 1024 * 1024:
            return None
        return file_sha256(path)
    except Exception:
        return None


@dataclass(frozen=True)
class RunSpec:
    backend: str
    scenario: str
    prompt_set: str
    model: str
    repetition: int
    batch_size: int
    seq_len: int
    mode: str


@dataclass
class RunResult:
    spec: RunSpec
    status: str
    error: str | None
    latencies_ms: list[float]
    tokens_processed: list[int]
    throughput_tok_s: list[float]
    ttft_ms: list[float] = field(default_factory=list)
    predicted_tokens: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    degraded_count: int = 0
    degraded_reasons: list[str] = field(default_factory=list)
    warmup_latencies_ms: list[float] = field(default_factory=list)
    resource_metrics: dict[str, Any] | None = None
    export_metadata: dict[str, Any] | None = None
    trt_build_metadata: list[dict[str, Any]] | None = None
    backend_metadata: dict[str, Any] | None = None
    started_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": asdict(self.spec),
            "status": self.status,
            "error": self.error,
            "latencies_ms": self.latencies_ms,
            "ttft_ms": self.ttft_ms,
            "tokens_processed": self.tokens_processed,
            "throughput_tok_s": self.throughput_tok_s,
            "predicted_tokens": self.predicted_tokens,
            "outputs": self.outputs,
            "degraded_count": self.degraded_count,
            "degraded_reasons": self.degraded_reasons,
            "warmup_latencies_ms": self.warmup_latencies_ms,
            "resource_metrics": self.resource_metrics,
            "export_metadata": self.export_metadata,
            "trt_build_metadata": self.trt_build_metadata,
            "backend_metadata": self.backend_metadata,
            "started_at": self.started_at,
        }


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_prompt_config(path: Path) -> tuple[dict[str, list[str]], dict[str, dict[str, Any]]]:
    cfg = _load_yaml(path)
    prompt_sets = {k: [str(p) for p in v] for k, v in cfg.get("prompt_sets", {}).items()}
    scenarios = {}
    for s in cfg.get("scenarios", []):
        if isinstance(s, dict) and s.get("name"):
            scenarios[str(s["name"])] = s
    return prompt_sets, scenarios


def _resolve_scenario(
    scenario_name: str,
    prompt_sets: dict[str, list[str]],
    scenario_defs: dict[str, dict[str, Any]],
) -> tuple[str, list[str], int]:
    """
    Returns (prompt_set_name, prompts, batch_size).
    Supports:
    - scenario_name directly referencing a prompt_set key (e.g., "short")
    - scenario_name referencing a named scenario in TR117 configs (e.g., "single_short", "batch_short")
    """
    if scenario_name in prompt_sets:
        return scenario_name, prompt_sets[scenario_name], 1
    if scenario_name in scenario_defs:
        sdef = scenario_defs[scenario_name]
        prompt_set = str(sdef.get("prompt_set", scenario_name))
        prompts = prompt_sets.get(prompt_set, [])
        batch_size = int(sdef.get("batch_size", 1) or 1)
        return prompt_set, prompts, batch_size
    return scenario_name, [], 1


def _maybe_export_onnx(cfg: dict[str, Any], meta_path: Path) -> tuple[Path, dict[str, Any] | None]:
    model_name = cfg["model"]["name"]
    out_dir = resolve_repo_path(_REPO_ROOT, str(cfg["output"]["onnx_dir"]))
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(model_name).name
    onnx_path = out_dir / f"{stem}.onnx"

    force_export = bool(cfg.get("onnx", {}).get("force_export", False)) or os.getenv("BANTER_TR118_FORCE_EXPORT", "0") == "1"
    skip_export = os.getenv("BANTER_TR118_SKIP_EXPORT", "0") == "1"

    if meta_path.exists() and onnx_path.exists() and not force_export:
        try:
            existing = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                if "onnx_inspect" not in existing:
                    existing["onnx_inspect"] = inspect_onnx_artifact(onnx_path)
                if "onnx_sha256" not in existing:
                    existing["onnx_sha256"] = _maybe_sha256(onnx_path)
                if "model_weight_files" not in existing:
                    existing["model_weight_files"] = inspect_model_weight_files(model_name)
                meta_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
                return onnx_path, existing
        except Exception:
            pass

    if onnx_path.exists() and not force_export:
        try:
            backends = [str(b) for b in cfg.get("benchmark", {}).get("backends", [])]
            if any(b.startswith("tensorrt") for b in backends):
                sanitize_onnx_file(onnx_path)
        except Exception as exc:
            logger.warning("ONNX sanitization skipped (non-fatal): %s", exc)
        meta = {
            "model": model_name,
            "output_path": str(onnx_path),
            "export_time_s": None,
            "file_size_mb": float(onnx_path.stat().st_size / (1024 * 1024)) if onnx_path.exists() else None,
            "opset_version": int(cfg["onnx"]["opset_version"]),
            "dynamic_axes": bool(cfg["onnx"].get("dynamic_axes", True)),
            "trt_friendly_inputs": bool(cfg["onnx"].get("trt_friendly_inputs", True)),
            "valid": None,
            "reused": True,
            "onnx_sha256": _maybe_sha256(onnx_path),
            "onnx_inspect": inspect_onnx_artifact(onnx_path),
            "model_weight_files": inspect_model_weight_files(model_name),
            "timestamp": time.time(),
        }
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return onnx_path, meta

    if skip_export and not force_export:
        if onnx_path.exists():
            meta = {
                "model": model_name,
                "output_path": str(onnx_path),
                "export_time_s": None,
                "file_size_mb": float(onnx_path.stat().st_size / (1024 * 1024)),
                "opset_version": int(cfg["onnx"]["opset_version"]),
                "dynamic_axes": bool(cfg["onnx"].get("dynamic_axes", True)),
                "trt_friendly_inputs": bool(cfg["onnx"].get("trt_friendly_inputs", True)),
                "valid": None,
                "reused": True,
                "skipped": True,
                "onnx_sha256": _maybe_sha256(onnx_path),
                "onnx_inspect": inspect_onnx_artifact(onnx_path),
                "model_weight_files": inspect_model_weight_files(model_name),
                "timestamp": time.time(),
            }
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            return onnx_path, meta
        logger.warning("ONNX export skipped but ONNX file not found at %s", onnx_path)
        return onnx_path, None

    try:
        backup_path: Path | None = None
        if force_export and onnx_path.exists():
            backup_path = onnx_path.with_suffix(onnx_path.suffix + ".bak")
            try:
                backup_path.unlink(missing_ok=True)  # type: ignore[arg-type]
            except Exception:
                pass
            try:
                onnx_path.replace(backup_path)
            except Exception:
                backup_path = None
        dynamic_axes = bool(cfg["onnx"].get("dynamic_axes", True))
        sample_inputs = None
        if not dynamic_axes:
            try:
                from transformers import AutoTokenizer  # type: ignore

                static_seq_len = int(
                    cfg.get("onnx", {}).get("static_seq_len", cfg.get("benchmark", {}).get("max_seq_len", 512))
                    or 512
                )
                static_batch = int(cfg.get("onnx", {}).get("static_batch", 1) or 1)
                dummy_text = str(
                    cfg.get("onnx", {}).get(
                        "static_dummy_text",
                        "Hello, this is a test prompt for ONNX export validation.",
                    )
                )
                tok = AutoTokenizer.from_pretrained(model_name)
                if getattr(tok, "pad_token", None) is None:
                    tok.pad_token = tok.eos_token
                enc = tok(
                    dummy_text,
                    truncation=True,
                    padding="max_length",
                    max_length=static_seq_len,
                    return_tensors="pt",
                )
                if static_batch > 1:
                    enc["input_ids"] = enc["input_ids"].repeat(static_batch, 1)
                    enc["attention_mask"] = enc["attention_mask"].repeat(static_batch, 1)
                sample_inputs = {"input_ids": enc["input_ids"], "attention_mask": enc["attention_mask"]}
            except Exception as exc:
                logger.warning("Failed to build static sample_inputs; falling back to exporter defaults: %s", exc)
                sample_inputs = None

        meta = export_model_to_onnx(
            model_name_or_path=model_name,
            output_path=onnx_path,
            opset_version=int(cfg["onnx"]["opset_version"]),
            dynamic_axes=dynamic_axes,
            sample_inputs=sample_inputs,
            trt_friendly_inputs=bool(cfg["onnx"].get("trt_friendly_inputs", True)),
        )
        meta["reused"] = False
        meta["onnx_sha256"] = _maybe_sha256(onnx_path)
        meta["onnx_inspect"] = inspect_onnx_artifact(onnx_path)
        meta["model_weight_files"] = inspect_model_weight_files(model_name)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        if backup_path is not None and backup_path.exists():
            try:
                backup_path.unlink()
            except Exception:
                pass
        return onnx_path, meta
    except Exception as exc:
        # Restore backup ONNX if present.
        try:
            backup_path = onnx_path.with_suffix(onnx_path.suffix + ".bak")
            if backup_path.exists() and not onnx_path.exists():
                backup_path.replace(onnx_path)
        except Exception:
            pass
        logger.warning("ONNX export failed; continuing with existing artifacts: %s", exc)
        return onnx_path, None


def _maybe_build_trt(
    cfg: dict[str, Any],
    onnx_path: Path,
    meta_path: Path,
) -> tuple[dict[str, Path], list[dict[str, Any]]]:
    out_dir = resolve_repo_path(_REPO_ROOT, str(cfg["output"]["tensorrt_dir"]))
    out_dir.mkdir(parents=True, exist_ok=True)
    precisions = [str(p) for p in cfg["tensorrt"]["precisions"]]

    dyn_cfg = cfg["tensorrt"].get("dynamic_shapes", {}) or {}
    enable_profiles = bool(dyn_cfg.get("enabled", False))
    profiles: list[dict[str, tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]]] = []
    if enable_profiles:
        for profile in dyn_cfg.get("profiles", []) or []:
            min_shape = tuple(int(x) for x in profile["min_shape"])
            opt_shape = tuple(int(x) for x in profile["opt_shape"])
            max_shape = tuple(int(x) for x in profile["max_shape"])
            profiles.append(
                {
                    "input_ids": (min_shape, opt_shape, max_shape),
                    "attention_mask": (min_shape, opt_shape, max_shape),
                }
            )

    int8_cal = cfg["tensorrt"].get("int8_calibration")
    if isinstance(int8_cal, dict) and int8_cal.get("cache_path"):
        int8_cal = dict(int8_cal)
        int8_cal["cache_path"] = str(resolve_repo_path(_REPO_ROOT, str(int8_cal["cache_path"])))
    tokenizer_name = cfg["model"]["name"]
    builder_settings = cfg.get("tensorrt", {}).get("builder")

    engines: dict[str, Path] = {}
    build_meta: list[dict[str, Any]] = []
    skip_build = os.getenv("BANTER_TR118_SKIP_TRT_BUILD", "0") == "1"
    force_rebuild = bool(cfg.get("tensorrt", {}).get("force_rebuild", False)) or os.getenv("BANTER_TR118_FORCE_TRT_REBUILD", "0") == "1"

    for precision in precisions:
        engines[precision] = out_dir / f"{onnx_path.stem}_{precision}.plan"

    if meta_path.exists() and not force_rebuild:
        try:
            existing = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(existing, list) and existing:
                have = {str(r.get("precision")) for r in existing if isinstance(r, dict) and r.get("precision")}
                if all(p in have for p in precisions) and all(engines[p].exists() for p in precisions):
                    changed = False
                    for r in existing:
                        if not isinstance(r, dict):
                            continue
                        prec = str(r.get("precision", "")).strip()
                        plan = engines.get(prec)
                        if plan and plan.exists() and "engine_inspect" not in r:
                            r["engine_inspect"] = inspect_trt_engine(plan)
                            changed = True
                        if plan and plan.exists() and "engine_sha256" not in r:
                            r["engine_sha256"] = _maybe_sha256(plan)
                            changed = True
                    if changed:
                        meta_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
                    return engines, existing
        except Exception:
            pass

    for precision in precisions:
        plan_path = engines[precision]
        base_meta = {
            "onnx_path": str(onnx_path),
            "output_path": str(plan_path),
            "precision": precision,
            "workspace_gb": int(cfg["tensorrt"]["workspace_gb"]),
            "builder_settings": builder_settings if isinstance(builder_settings, dict) else {},
            "int8_calibration_config": int8_cal if (precision == "int8" and isinstance(int8_cal, dict)) else None,
            "dynamic_shapes": bool(profiles),
            "profiles": len(profiles) if profiles else 0,
            "timestamp": time.time(),
        }
        if skip_build:
            if plan_path.exists():
                size_mb = float(plan_path.stat().st_size / (1024 * 1024))
                build_meta.append(
                    {
                        **base_meta,
                        "build_time_s": None,
                        "file_size_mb": size_mb,
                        "built": False,
                        "reused": True,
                        "error": None,
                        "engine_sha256": _maybe_sha256(plan_path),
                        "engine_inspect": inspect_trt_engine(plan_path),
                    }
                )
            else:
                build_meta.append(
                    {
                        **base_meta,
                        "build_time_s": None,
                        "file_size_mb": None,
                        "built": False,
                        "reused": False,
                        "error": "missing_engine",
                    }
                )
            continue
        if plan_path.exists() and not force_rebuild:
            size_mb = float(plan_path.stat().st_size / (1024 * 1024))
            build_meta.append(
                {
                    **base_meta,
                    "build_time_s": None,
                    "file_size_mb": size_mb,
                    "built": False,
                    "reused": True,
                    "error": None,
                    "engine_sha256": _maybe_sha256(plan_path),
                    "engine_inspect": inspect_trt_engine(plan_path),
                }
            )
            continue
        backup_plan: Path | None = None
        if force_rebuild and plan_path.exists():
            backup_plan = plan_path.with_suffix(plan_path.suffix + ".bak")
            try:
                backup_plan.unlink(missing_ok=True)  # type: ignore[arg-type]
            except Exception:
                pass
            try:
                plan_path.replace(backup_plan)
            except Exception:
                backup_plan = None
        try:
            meta = build_tensorrt_engine(
                onnx_path=onnx_path,
                output_path=plan_path,
                precision=precision,
                workspace_gb=int(cfg["tensorrt"]["workspace_gb"]),
                profiles=profiles or None,
                int8_calibration=int8_cal if precision == "int8" else None,
                tokenizer_name_or_path=tokenizer_name,
                builder_settings=builder_settings if isinstance(builder_settings, dict) else None,
            )
            meta["built"] = True
            meta["reused"] = False
            meta.setdefault("engine_sha256", _maybe_sha256(plan_path))
            meta.setdefault("engine_inspect", inspect_trt_engine(plan_path))
            build_meta.append(meta)
            if backup_plan is not None and backup_plan.exists():
                try:
                    backup_plan.unlink()
                except Exception:
                    pass
        except Exception as exc:
            logger.warning("TensorRT build failed for %s: %s", precision, exc)
            if backup_plan is not None and backup_plan.exists() and not plan_path.exists():
                try:
                    backup_plan.replace(plan_path)
                except Exception:
                    pass
            if plan_path.exists():
                size_mb = float(plan_path.stat().st_size / (1024 * 1024))
                build_meta.append(
                    {
                        **base_meta,
                        "build_time_s": None,
                        "file_size_mb": size_mb,
                        "built": False,
                        "reused": True,
                        "error": f"rebuild_failed:{exc}",
                    }
                )
                continue
            build_meta.append(
                {
                    **base_meta,
                    "build_time_s": None,
                    "file_size_mb": None,
                    "built": False,
                    "reused": False,
                    "error": str(exc),
                }
            )

    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(build_meta, indent=2), encoding="utf-8")
    return engines, build_meta


def _init_tokenizer(model_name: str):
    try:
        from transformers import AutoTokenizer  # type: ignore

        tok = AutoTokenizer.from_pretrained(model_name)
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        return tok
    except Exception as exc:
        logger.warning("Tokenizer unavailable: %s", exc)
        return None


def _compute_seq_len(tokenizer, prompts: list[str], max_len: int, min_len: int = 1) -> int:
    min_len = max(1, int(min_len) or 1)
    min_len = min(min_len, int(max_len) or min_len)
    lengths = []
    for prompt in prompts:
        enc = tokenizer(prompt, add_special_tokens=True)
        lengths.append(len(enc.get("input_ids", [])))
    if not lengths:
        return max(min(32, max_len), min_len)
    return max(min(max(lengths), max_len), min_len)


def _onnxruntime_session(onnx_path: Path, providers: list[str]):
    import onnxruntime as ort  # type: ignore

    available = ort.get_available_providers()
    use = [p for p in providers if p in available]
    if not use:
        use = ["CPUExecutionProvider"]
    session = ort.InferenceSession(str(onnx_path), providers=use)
    input_type = str(session.get_inputs()[0].type)
    return session, input_type, use


def _to_numpy_inputs(tokenizer, prompt: str, seq_len: int, batch_size: int, dtype: str):
    import numpy as np  # type: ignore

    enc = tokenizer(
        prompt,
        truncation=True,
        padding="max_length",
        max_length=seq_len,
        return_tensors="np",
    )
    input_ids = enc["input_ids"]
    attention_mask = enc["attention_mask"]
    if dtype == "int32":
        input_ids = input_ids.astype(np.int32)
        attention_mask = attention_mask.astype(np.int32)
    else:
        input_ids = input_ids.astype(np.int64)
        attention_mask = attention_mask.astype(np.int64)
    if batch_size > 1:
        input_ids = np.repeat(input_ids, batch_size, axis=0)
        attention_mask = np.repeat(attention_mask, batch_size, axis=0)
    return input_ids, attention_mask


def _infer_ort(session, input_type: str, tokenizer, prompt: str, seq_len: int, batch_size: int) -> tuple[float, str]:
    dtype = "int32" if "int32" in input_type else "int64"
    input_ids, attention_mask = _to_numpy_inputs(tokenizer, prompt, seq_len, batch_size, dtype=dtype)
    start = time.perf_counter()
    outputs = session.run(None, {"input_ids": input_ids, "attention_mask": attention_mask})
    latency_ms = (time.perf_counter() - start) * 1000
    logits = outputs[0]
    token_id = int(logits[0, -1, :].argmax())
    token = tokenizer.decode([token_id])
    return latency_ms, token


def _infer_ort_logits(session, input_type: str, input_ids, attention_mask) -> tuple[float, Any]:
    import numpy as np  # type: ignore

    dtype = np.int32 if "int32" in str(input_type) else np.int64
    if getattr(input_ids, "dtype", None) != dtype:
        input_ids = input_ids.astype(dtype, copy=False)
    if getattr(attention_mask, "dtype", None) != dtype:
        attention_mask = attention_mask.astype(dtype, copy=False)
    start = time.perf_counter()
    outputs = session.run(None, {"input_ids": input_ids, "attention_mask": attention_mask})
    latency_ms = (time.perf_counter() - start) * 1000
    return latency_ms, outputs[0]


def _infer_torch(
    model,
    tokenizer,
    prompt: str,
    seq_len: int,
    batch_size: int,
    device: str,
) -> tuple[float, str, bool, str | None]:
    try:
        import torch  # type: ignore
    except Exception as exc:
        return 0.0, "", True, f"torch_missing:{exc}"

    enc = tokenizer(
        prompt,
        truncation=True,
        padding="max_length",
        max_length=seq_len,
        return_tensors="pt",
    )
    input_ids = enc["input_ids"]
    attention_mask = enc["attention_mask"]
    if batch_size > 1:
        input_ids = input_ids.repeat(batch_size, 1)
        attention_mask = attention_mask.repeat(batch_size, 1)

    try:
        input_ids = input_ids.to(device)
        attention_mask = attention_mask.to(device)
        if device.startswith("cuda") and torch.cuda.is_available():
            torch.cuda.synchronize()
        with torch.inference_mode():
            start = time.perf_counter()
            out = model(input_ids=input_ids, attention_mask=attention_mask, use_cache=False)
            logits = out.logits
            # include device->host transfer to align with ORT/TRT returning host arrays
            logits_np = logits.detach().cpu().numpy()
            if device.startswith("cuda") and torch.cuda.is_available():
                torch.cuda.synchronize()
            latency_ms = (time.perf_counter() - start) * 1000
        token_id = int(logits_np[0, -1, :].argmax())
        token = tokenizer.decode([token_id])
        return latency_ms, token, False, None
    except Exception as exc:
        return 0.0, "", True, str(exc)


def _infer_tensorrt(
    runner: TensorRTInferenceEngine,
    prepared: dict[str, Any],
    tokenizer,
    prompt: str,
    seq_len: int,
    batch_size: int,
) -> tuple[float, str, bool, str | None]:
    try:
        input_ids, attention_mask = _to_numpy_inputs(
            tokenizer, prompt, seq_len, batch_size, dtype="int32"
        )
        latency_ms, logits = runner.infer(prepared, input_ids, attention_mask)
        token_id = int(logits[0, -1, :].argmax())
        token = tokenizer.decode([token_id])
        return latency_ms, token, False, None
    except Exception as exc:
        return 0.0, "", True, str(exc)


def _infer_torch_logits(model, input_ids, attention_mask, device: str) -> tuple[float, Any, bool, str | None]:
    try:
        import torch  # type: ignore
    except Exception as exc:
        return 0.0, None, True, f"torch_missing:{exc}"

    try:
        input_ids_t = torch.as_tensor(input_ids, dtype=torch.long).to(device)
        attention_mask_t = torch.as_tensor(attention_mask, dtype=torch.long).to(device)
        if device.startswith("cuda") and torch.cuda.is_available():
            torch.cuda.synchronize()
        with torch.inference_mode():
            start = time.perf_counter()
            out = model(input_ids=input_ids_t, attention_mask=attention_mask_t, use_cache=False)
            logits = out.logits
            logits_np = logits.detach().cpu().numpy()
            if device.startswith("cuda") and torch.cuda.is_available():
                torch.cuda.synchronize()
            latency_ms = (time.perf_counter() - start) * 1000
        return latency_ms, logits_np, False, None
    except Exception as exc:
        return 0.0, None, True, str(exc)


def _generate_uncached(
    infer_logits,
    tokenizer,
    prompt: str,
    seq_len: int,
    batch_size: int,
    max_new_tokens: int,
    stop_on_eos: bool,
    timeout_s: float,
) -> tuple[float, float, int, str, bool, str | None]:
    """
    Uncached greedy generation loop using repeated full forward passes.

    Returns:
      total_latency_ms, ttft_ms, tokens_generated, output_text, degraded, reason
    """
    import numpy as np  # type: ignore

    if max_new_tokens <= 0:
        return 0.0, 0.0, 0, prompt, False, None

    enc = tokenizer(
        prompt,
        truncation=True,
        padding="max_length",
        max_length=seq_len,
        return_tensors="np",
    )
    input_ids = enc["input_ids"]
    attention_mask = enc["attention_mask"]
    if batch_size > 1:
        input_ids = np.repeat(input_ids, batch_size, axis=0)
        attention_mask = np.repeat(attention_mask, batch_size, axis=0)

    eos_token_id = getattr(tokenizer, "eos_token_id", None)
    cur_len = int(attention_mask[0].sum())
    if cur_len >= seq_len:
        return 0.0, 0.0, 0, prompt, True, "no_room_for_generation"

    start_total = time.perf_counter()
    ttft_ms = 0.0
    steps_done = 0

    for step in range(max_new_tokens):
        if timeout_s > 0 and (time.perf_counter() - start_total) > timeout_s:
            total_ms = (time.perf_counter() - start_total) * 1000
            out_text = tokenizer.decode(input_ids[0, :cur_len].tolist())
            return total_ms, ttft_ms, steps_done * batch_size, out_text, True, "timeout"
        if cur_len >= seq_len:
            break

        step_ms, logits = infer_logits(input_ids, attention_mask)
        if step == 0:
            ttft_ms = float(step_ms)

        last_idx = max(cur_len - 1, 0)
        token_id = int(np.asarray(logits)[0, last_idx, :].argmax())
        input_ids[:, cur_len] = token_id
        attention_mask[:, cur_len] = 1
        cur_len += 1
        steps_done += 1

        if stop_on_eos and eos_token_id is not None and token_id == int(eos_token_id):
            break

    total_ms = (time.perf_counter() - start_total) * 1000
    out_text = tokenizer.decode(input_ids[0, :cur_len].tolist())
    return total_ms, ttft_ms, steps_done * batch_size, out_text, False, None


def main() -> int:
    parser = argparse.ArgumentParser(description="TR118 benchmark runner")
    parser.add_argument(
        "--config",
        default="scripts/tr118/configs/baseline.yaml",
        help="Path to TR118 config yaml",
    )
    parser.add_argument(
        "--prompt-config",
        default=os.getenv(
            "BANTER_TR118_PROMPT_CONFIG",
            "scripts/tr117/configs/matrix_tier3.yaml",
        ),
        help="Prompt config (TR117 tier3 by default)",
    )
    parser.add_argument(
        "--mode",
        choices=["prefill", "generate"],
        default=None,
        help="Benchmark mode: prefill forward-pass or uncached generation loop",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Optional run id used to name artifacts (recommended when orchestrated via run_experiment.py)",
    )
    args = parser.parse_args()

    cfg_path = resolve_repo_path(_REPO_ROOT, str(args.config))
    prompt_cfg_path = resolve_repo_path(_REPO_ROOT, str(args.prompt_config))

    cfg = _load_yaml(cfg_path)
    prompt_sets, scenario_defs = _load_prompt_config(prompt_cfg_path)

    mode = str(args.mode or cfg.get("benchmark", {}).get("mode", "prefill"))
    results_root = resolve_repo_path(_REPO_ROOT, str(cfg["output"]["results_dir"]))
    raw_dir = results_root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    run_id = str(args.run_id).strip() if args.run_id is not None else str(int(time.time()))
    out_path = raw_dir / f"bench_{mode}_{run_id}.jsonl"
    processed_dir = results_root / "processed"
    export_meta_path = processed_dir / f"export_metadata_{run_id}.json"
    trt_build_meta_path = processed_dir / f"trt_build_metadata_{run_id}.json"

    model_name = cfg["model"]["name"]
    tokenizer = _init_tokenizer(model_name)
    if tokenizer is None:
        logger.error("Tokenizer required to run TR118 benchmark.")
        return 2

    export_path, export_meta = _maybe_export_onnx(cfg, meta_path=export_meta_path)
    engines, trt_build_meta = _maybe_build_trt(cfg, export_path, meta_path=trt_build_meta_path)

    max_seq_len = int(cfg.get("benchmark", {}).get("max_seq_len", 512) or 512)
    repetitions = int(cfg["benchmark"]["repetitions"])
    warmup_runs = int(cfg["benchmark"].get("warmup_runs", 0))
    timeout_s = float(cfg["benchmark"].get("timeout_s", 0) or 0)
    max_new_tokens = int(cfg.get("benchmark", {}).get("max_new_tokens", 8) or 8)
    stop_on_eos = bool(cfg.get("benchmark", {}).get("stop_on_eos", True))
    enable_resource = bool(cfg["benchmark"].get("enable_resource_monitoring", False))
    sample_interval = float(cfg.get("resource_sampling_interval_s", 0.1) or 0.1)
    resource_monitor_available = enable_resource and ResourceMonitor is not None

    onnx_dynamic_axes = bool(cfg.get("onnx", {}).get("dynamic_axes", True))
    static_seq_len = int(cfg.get("onnx", {}).get("static_seq_len", max_seq_len) or max_seq_len)
    static_batch = int(cfg.get("onnx", {}).get("static_batch", 1) or 1)

    vocab_size = int(getattr(tokenizer, "vocab_size", 50257) or 50257)
    min_seq_len = int(cfg.get("benchmark", {}).get("min_seq_len", 1) or 1)
    dyn_cfg = cfg.get("tensorrt", {}).get("dynamic_shapes", {}) or {}
    trt_profiles: list[dict[str, tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]]] = []
    try:
        if bool(dyn_cfg.get("enabled", False)):
            prof_min: list[int] = []
            for profile in dyn_cfg.get("profiles", []) or []:
                if not isinstance(profile, dict):
                    continue
                min_shape = profile.get("min_shape")
                opt_shape = profile.get("opt_shape")
                max_shape = profile.get("max_shape")
                if (
                    isinstance(min_shape, list)
                    and isinstance(opt_shape, list)
                    and isinstance(max_shape, list)
                    and len(min_shape) >= 2
                    and len(opt_shape) >= 2
                    and len(max_shape) >= 2
                ):
                    prof_min.append(int(min_shape[1]))
                    trt_profiles.append(
                        {
                            "input_ids": (
                                tuple(int(x) for x in min_shape),
                                tuple(int(x) for x in opt_shape),
                                tuple(int(x) for x in max_shape),
                            ),
                            "attention_mask": (
                                tuple(int(x) for x in min_shape),
                                tuple(int(x) for x in opt_shape),
                                tuple(int(x) for x in max_shape),
                            ),
                        }
                    )
            if prof_min:
                min_seq_len = max(min_seq_len, min(prof_min))
    except Exception:
        trt_profiles = []

    trt_workspace_gb = int(cfg.get("tensorrt", {}).get("workspace_gb", 4) or 4)
    trt_int8_cal = cfg.get("tensorrt", {}).get("int8_calibration")
    trt_builder_settings = cfg.get("tensorrt", {}).get("builder")
    trt_skip_build = os.getenv("BANTER_TR118_SKIP_TRT_BUILD", "0") == "1"
    trt_rebuild_on_init_fail = os.getenv("BANTER_TR118_REBUILD_TRT_ON_INIT_FAIL", "1") != "0"

    backend_init_meta: dict[str, dict[str, Any]] = {}

    # ORT sessions
    ort_sessions: dict[str, dict[str, Any]] = {}
    if export_path.exists():
        for backend_name, providers in [
            ("onnxruntime-cpu", ["CPUExecutionProvider"]),
            ("onnxruntime-gpu", ["CUDAExecutionProvider", "CPUExecutionProvider"]),
        ]:
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
                        "onnx_path": str(export_path),
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
                        "onnx_path": str(export_path),
                    }
            except Exception as exc:
                logger.warning("%s session init failed: %s", backend_name, exc)
                backend_init_meta[backend_name] = {
                    "backend": backend_name,
                    "init_ms": None,
                    "error": str(exc),
                    "onnx_path": str(export_path),
                }

    # TRT engines
    trt_runners: dict[str, TensorRTInferenceEngine | None] = {}
    trt_rebuild_attempted: set[str] = set()

    def get_trt_runner(precision: str) -> TensorRTInferenceEngine | None:
        """
        Lazily instantiate TensorRT runners.

        On Windows, running ORT's CUDAExecutionProvider after a TensorRT runner
        is created can break TensorRT batched execution (Myelin CUDA error 400).

        This keeps TRT runner creation deferred until TRT backends are actually
        executed (typically after ORT backends in the benchmark loop).
        """
        if precision in trt_runners:
            return trt_runners[precision]

        plan = engines.get(precision)
        if not plan or not plan.exists():
            backend_init_meta[f"tensorrt-{precision}"] = {
                "backend": f"tensorrt-{precision}",
                "init_ms": None,
                "error": "trt_engine_missing",
                "engine_path": str(plan) if plan else None,
            }
            return None

        def _init() -> TensorRTInferenceEngine:
            start = time.perf_counter()
            runner = TensorRTInferenceEngine(plan)
            init_ms = (time.perf_counter() - start) * 1000
            backend_init_meta[f"tensorrt-{precision}"] = {
                "backend": f"tensorrt-{precision}",
                "init_ms": init_ms,
                "engine_path": str(plan),
                "engine": runner.metadata.__dict__,
            }
            return runner

        try:
            runner = _init()
            trt_runners[precision] = runner
            return runner
        except Exception as exc:
            logger.warning("TRT engine init failed for %s: %s", precision, exc)

            if (
                trt_rebuild_on_init_fail
                and not trt_skip_build
                and precision not in trt_rebuild_attempted
                and export_path.exists()
            ):
                trt_rebuild_attempted.add(precision)
                logger.warning("Attempting TRT rebuild for %s due to init failure.", precision)
                try:
                    meta = build_tensorrt_engine(
                        onnx_path=export_path,
                        output_path=plan,
                        precision=precision,
                        workspace_gb=trt_workspace_gb,
                        profiles=trt_profiles or None,
                        int8_calibration=trt_int8_cal if precision == "int8" else None,
                        tokenizer_name_or_path=model_name,
                        builder_settings=trt_builder_settings if isinstance(trt_builder_settings, dict) else None,
                    )
                    meta["built"] = True
                    meta["reused"] = False
                    trt_build_meta_path.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        existing = (
                            json.loads(trt_build_meta_path.read_text(encoding="utf-8"))
                            if trt_build_meta_path.exists()
                            else []
                        )
                        if not isinstance(existing, list):
                            existing = []
                    except Exception:
                        existing = []
                    replaced = False
                    for i, r in enumerate(existing):
                        if (
                            isinstance(r, dict)
                            and str(r.get("precision")) == str(meta.get("precision"))
                            and str(r.get("output_path")) == str(meta.get("output_path"))
                        ):
                            existing[i] = meta
                            replaced = True
                            break
                    if not replaced:
                        existing.append(meta)
                    trt_build_meta_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
                    for i, r in enumerate(trt_build_meta):
                        if (
                            isinstance(r, dict)
                            and str(r.get("precision")) == str(meta.get("precision"))
                            and str(r.get("output_path")) == str(meta.get("output_path"))
                        ):
                            trt_build_meta[i] = meta
                            break
                    else:
                        trt_build_meta.append(meta)
                    runner = _init()
                    trt_runners[precision] = runner
                    return runner
                except Exception as rebuild_exc:
                    logger.warning("TRT rebuild failed for %s: %s", precision, rebuild_exc)

            backend_init_meta[f"tensorrt-{precision}"] = {
                "backend": f"tensorrt-{precision}",
                "init_ms": None,
                "error": str(exc),
                "engine_path": str(plan),
            }
            trt_runners[precision] = None
            return None

    # Torch backends (cached by (device, compile))
    torch_available = False
    torch_mod = None
    torch_model_cls = None
    try:
        import torch  # type: ignore
        from transformers import AutoModelForCausalLM  # type: ignore

        torch_available = True
        torch_mod = torch
        torch_model_cls = AutoModelForCausalLM
    except Exception as exc:
        backend_init_meta["transformers"] = {"backend": "transformers", "error": str(exc)}

    def _default_torch_compile_backend() -> str | None:
        """
        Pick a safe torch.compile backend for this platform.

        On Windows, Triton wheels are often unavailable, which makes the default
        Inductor backend fail at runtime. In that case we default to
        `cudagraphs` so the "compile" baseline can still run.
        """
        override = os.getenv("BANTER_TR118_TORCH_COMPILE_BACKEND", "").strip()
        if override:
            return override
        configured = str(cfg.get("benchmark", {}).get("torch_compile_backend", "") or "").strip()
        if configured:
            return configured
        if platform.system() == "Windows":
            return "cudagraphs"
        return None

    torch_compile_backend = _default_torch_compile_backend()

    torch_cache: dict[tuple[str, bool, int, int], dict[str, Any]] = {}

    def get_torch_runner(device: str, compile_model: bool, batch_size: int, seq_len: int) -> dict[str, Any] | None:
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
            except Exception as exc:  # pragma: no cover - depends on platform/torch build
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

    for backend in cfg["benchmark"]["backends"]:
        backend = str(backend)
        if not backend.startswith("transformers"):
            continue
        if not torch_available or torch_mod is None:
            backend_init_meta[backend] = {"backend": backend, "init_ms": None, "error": "torch_unavailable"}
            continue
        if "gpu" in backend and not torch_mod.cuda.is_available():
            backend_init_meta[backend] = {"backend": backend, "init_ms": None, "error": "cuda_unavailable"}
            continue
        device = "cuda" if "gpu" in backend else "cpu"
        compile_model = "compile" in backend
        runner = get_torch_runner(device=device, compile_model=compile_model, batch_size=1, seq_len=min_seq_len)
        if runner is None:
            backend_init_meta[backend] = {"backend": backend, "init_ms": None, "error": "torch_unavailable"}
        else:
            backend_init_meta[backend] = {
                "backend": backend,
                "init_ms": runner.get("init_ms"),
                "compile_ms": runner.get("compile_ms"),
                "compile_error": runner.get("compile_error"),
                "compile_backend": runner.get("compile_backend"),
                "device": runner.get("device"),
                "compile": runner.get("compile"),
            }

    def run_one_backend_scenario(backend: str, scenario: str, rep: int) -> RunResult:
        nonlocal resource_monitor_available
        prompt_set, prompts, batch_size = _resolve_scenario(scenario, prompt_sets, scenario_defs)
        if not prompts:
            return RunResult(
                spec=RunSpec(
                    backend=backend,
                    scenario=scenario,
                    prompt_set=prompt_set,
                    model=model_name,
                    repetition=rep,
                    batch_size=batch_size,
                    seq_len=0,
                    mode=mode,
                ),
                status="skipped",
                error="scenario_not_found",
                latencies_ms=[],
                tokens_processed=[],
                throughput_tok_s=[],
            )
        if not onnx_dynamic_axes:
            if batch_size != static_batch:
                return RunResult(
                    spec=RunSpec(
                        backend=backend,
                        scenario=scenario,
                        prompt_set=prompt_set,
                        model=model_name,
                        repetition=rep,
                        batch_size=batch_size,
                        seq_len=static_seq_len,
                        mode=mode,
                    ),
                    status="skipped",
                    error=f"static_shape_batch_mismatch: scenario_batch={batch_size} expected={static_batch}",
                    latencies_ms=[],
                    tokens_processed=[],
                    throughput_tok_s=[],
                )
            seq_len = static_seq_len
        elif mode == "generate":
            prompt_len = _compute_seq_len(tokenizer, prompts, max_len=max_seq_len, min_len=min_seq_len)
            seq_len = min(max(prompt_len + max_new_tokens, min_seq_len), max_seq_len)
        else:
            seq_len = _compute_seq_len(tokenizer, prompts, max_len=max_seq_len, min_len=min_seq_len)
        spec = RunSpec(
            backend=backend,
            scenario=scenario,
            prompt_set=prompt_set,
            model=model_name,
            repetition=rep,
            batch_size=batch_size,
            seq_len=seq_len,
            mode=mode,
        )

        latencies: list[float] = []
        ttft: list[float] = []
        tokens_processed: list[int] = []
        throughput: list[float] = []
        predicted: list[str] = []
        outputs: list[str] = []
        degraded = 0
        degraded_reasons: list[str] = []
        warmups: list[float] = []
        backend_meta = backend_init_meta.get(backend) or {"backend": backend}

        status = "ok"
        error = None
        resource_metrics = None

        with contextlib.ExitStack() as stack:
            monitor = None
            if enable_resource and ResourceMonitor is not None and resource_monitor_available:
                try:
                    monitor = stack.enter_context(ResourceMonitor(sample_interval_s=sample_interval))
                except Exception as exc:  # pragma: no cover - depends on host NVML/psutil
                    resource_monitor_available = False
                    logger.warning("ResourceMonitor unavailable; disabling: %s", exc)
                    monitor = None

            prepared_trt = None
            trt_runner = None
            if backend.startswith("tensorrt"):
                precision = backend.split("-")[-1]
                trt_runner = get_trt_runner(precision)
                if trt_runner is None:
                    # Graceful degradation: mark as degraded but continue
                    logger.warning(
                        f"TensorRT {precision} runner unavailable for {backend}. "
                        f"Marking scenario as degraded. Check TRT engine build logs."
                    )
                    return RunResult(
                        spec=spec,
                        status="degraded",
                        error=f"tensorrt_{precision}_unavailable",
                        latencies_ms=[],
                        tokens_processed=[],
                        throughput_tok_s=[],
                        degraded_count=1,
                        degraded_reasons=[f"tensorrt_{precision}_runner_missing"],
                        backend_metadata=backend_meta,
                    )
                try:
                    prepared_trt = trt_runner.prepare(batch=batch_size, seq=seq_len, vocab_size=vocab_size)
                except Exception as exc:
                    logger.warning(f"TensorRT prepare failed for {backend}: {exc}. Marking as degraded.")
                    return RunResult(
                        spec=spec,
                        status="degraded",
                        error=f"tensorrt_prepare_failed:{str(exc)}",
                        latencies_ms=[],
                        tokens_processed=[],
                        throughput_tok_s=[],
                        degraded_count=1,
                        degraded_reasons=[f"tensorrt_prepare_error:{type(exc).__name__}"],
                        backend_metadata=backend_meta,
                    )

            # Warmups (single prompt)
            warm_prompt = prompts[0]
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
                            device=device, compile_model=compile_model, batch_size=batch_size, seq_len=seq_len
                        )
                        if runner is None:
                            continue
                        ms, _tok, _d, _r = _infer_torch(
                            runner["model"], tokenizer, warm_prompt, seq_len, batch_size, device
                        )
                        warmups.append(ms)
                except Exception:
                    continue

            for prompt in prompts:
                try:
                    if mode == "generate":
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
                            ttft.append(ttft_ms)
                            tokens_processed.append(int(toks))
                            throughput.append(toks / (total_ms / 1000.0) if total_ms > 0 else 0.0)
                            outputs.append(out_text)
                            predicted.append("")
                            continue

                        if backend.startswith("tensorrt"):
                            if trt_runner is None or prepared_trt is None:
                                degraded += 1
                                degraded_reasons.append("trt_engine_missing_or_unavailable")
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
                            ttft.append(ttft_ms)
                            tokens_processed.append(int(toks))
                            throughput.append(toks / (total_ms / 1000.0) if total_ms > 0 else 0.0)
                            outputs.append(out_text)
                            predicted.append("")
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
                                device=device, compile_model=compile_model, batch_size=batch_size, seq_len=seq_len
                            )
                            if runner is None:
                                degraded += 1
                                degraded_reasons.append("torch_unavailable")
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
                            ttft.append(ttft_ms)
                            tokens_processed.append(int(toks))
                            throughput.append(toks / (total_ms / 1000.0) if total_ms > 0 else 0.0)
                            outputs.append(out_text)
                            predicted.append("")
                            continue

                        degraded += 1
                        degraded_reasons.append("unsupported_backend")
                        continue

                    if backend.startswith("onnxruntime"):
                        sess_info = ort_sessions.get(backend)
                        sess = sess_info["session"] if sess_info else None
                        if sess is None:
                            logger.warning(
                                f"ONNX Runtime session missing for {backend}. "
                                f"Check ONNX export logs. Marking prompt as degraded."
                            )
                            degraded += 1
                            degraded_reasons.append("ort_session_missing")
                            continue
                        ms, tok = _infer_ort(
                            sess, str(sess_info.get("input_type", "int64")), tokenizer, prompt, seq_len, batch_size
                        )
                        if timeout_s > 0 and ms > timeout_s * 1000:
                            degraded += 1
                            degraded_reasons.append("timeout")
                            continue
                        latencies.append(ms)
                        predicted.append(tok)
                        tokens = batch_size * seq_len
                        tokens_processed.append(tokens)
                        throughput.append(tokens / (ms / 1000.0) if ms > 0 else 0.0)
                    elif backend.startswith("tensorrt"):
                        if trt_runner is None or prepared_trt is None:
                            degraded += 1
                            degraded_reasons.append("trt_engine_missing_or_unavailable")
                            continue
                        ms, tok, is_deg, reason = _infer_tensorrt(
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
                        predicted.append(tok)
                        tokens = batch_size * seq_len
                        tokens_processed.append(tokens)
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
                            device=device, compile_model=compile_model, batch_size=batch_size, seq_len=seq_len
                        )
                        if runner is None:
                            degraded += 1
                            degraded_reasons.append("torch_unavailable")
                            continue
                        ms, tok, is_deg, reason = _infer_torch(
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
                        predicted.append(tok)
                        tokens = batch_size * seq_len
                        tokens_processed.append(tokens)
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

        return RunResult(
            spec=spec,
            status=status,
            error=error,
            latencies_ms=latencies,
            ttft_ms=ttft,
            tokens_processed=tokens_processed,
            throughput_tok_s=throughput,
            predicted_tokens=predicted,
            outputs=outputs,
            degraded_count=degraded,
            degraded_reasons=degraded_reasons,
            warmup_latencies_ms=warmups,
            resource_metrics=resource_metrics,
            export_metadata=export_meta,
            trt_build_metadata=trt_build_meta,
            backend_metadata=backend_meta,
        )

    with out_path.open("w", encoding="utf-8") as fh:
        for backend in cfg["benchmark"]["backends"]:
            backend = str(backend)
            for scenario in cfg["benchmark"]["scenarios"]:
                scenario = str(scenario)
                for rep in range(repetitions):
                    try:
                        result = run_one_backend_scenario(backend, scenario, rep)
                    except Exception as exc:
                        result = RunResult(
                            spec=RunSpec(
                                backend=backend,
                                scenario=scenario,
                                prompt_set=scenario,
                                model=model_name,
                                repetition=rep,
                                batch_size=0,
                                seq_len=0,
                                mode=mode,
                            ),
                            status="error",
                            error=str(exc),
                            latencies_ms=[],
                            tokens_processed=[],
                            throughput_tok_s=[],
                            degraded_count=1,
                            degraded_reasons=[f"exception:{type(exc).__name__}:{exc}"],
                            export_metadata=export_meta,
                            trt_build_metadata=trt_build_meta,
                            backend_metadata=backend_init_meta.get(backend) or {"backend": backend},
                        )
                    fh.write(json.dumps(result.to_dict()) + "\n")

    logger.info("TR118 raw results written to %s", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
