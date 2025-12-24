#!/usr/bin/env python3
"""
TR118: Build TensorRT engines from ONNX models with multiple precision modes.

Usage:
    python build_trt_engines.py --onnx artifacts/onnx/gpt2.onnx --output artifacts/tensorrt/ --precisions fp32 fp16 int8
"""

from __future__ import annotations

import argparse
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

from scripts.tr118.artifact_utils import file_sha256, inspect_trt_engine, resolve_repo_path
from scripts.tr118.onnx_sanitize import sanitize_onnx_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _build_int8_calibration_batches(
    tokenizer_name_or_path: str,
    dataset_name: str = "wikitext",
    dataset_config: str = "wikitext-2-raw-v1",
    split: str = "test",
    text_field: str = "text",
    samples: int = 256,
    batch_size: int = 8,
    seq_len: int = 128,
    seed: int = 42,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Create calibration batches for TensorRT INT8 calibrator.
    Falls back to random token IDs when datasets/transformers are unavailable.
    """
    try:
        import numpy as np  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("numpy is required for calibration") from exc

    tokenizer_available = True
    try:
        from transformers import AutoTokenizer  # type: ignore

        tokenizer = AutoTokenizer.from_pretrained(tokenizer_name_or_path)
        if getattr(tokenizer, "pad_token", None) is None:
            tokenizer.pad_token = tokenizer.eos_token
    except Exception as exc:  # pragma: no cover - optional
        logger.warning("Tokenizer unavailable for calibration; using random tokens: %s", exc)
        tokenizer = None
        tokenizer_available = False

    texts: list[str] = []
    datasets_available = True
    if tokenizer is not None:
        try:
            from datasets import load_dataset  # type: ignore

            ds = load_dataset(dataset_name, dataset_config, split=split)
            for row in ds:
                txt = str(row.get(text_field, "")).strip()
                if not txt:
                    continue
                texts.append(txt)
                if len(texts) >= samples:
                    break
        except Exception as exc:
            logger.warning("datasets unavailable for calibration; using random tokens: %s", exc)
            texts = []
            datasets_available = False
    else:
        datasets_available = False

    rng = np.random.default_rng(seed)
    batches: list[dict[str, Any]] = []
    cur_ids: list[Any] = []
    cur_mask: list[Any] = []

    def _flush():
        if not cur_ids:
            return
        batch_ids = np.stack(cur_ids).astype(np.int32)
        batch_mask = np.stack(cur_mask).astype(np.int32)
        batches.append({"input_ids": batch_ids, "attention_mask": batch_mask})
        cur_ids.clear()
        cur_mask.clear()

    if texts and tokenizer is not None:
        for txt in texts:
            enc = tokenizer(
                txt,
                truncation=True,
                padding="max_length",
                max_length=seq_len,
                return_tensors="np",
            )
            cur_ids.append(enc["input_ids"][0])
            cur_mask.append(enc["attention_mask"][0])
            if len(cur_ids) >= batch_size:
                _flush()
        _flush()
    else:
        vocab = int(getattr(tokenizer, "vocab_size", 50257) or 50257) if tokenizer is not None else 50257
        total = max(samples, batch_size)
        for _ in range(total):
            ids = rng.integers(low=0, high=vocab, size=(seq_len,), dtype=np.int32)
            mask = np.ones((seq_len,), dtype=np.int32)
            cur_ids.append(ids)
            cur_mask.append(mask)
            if len(cur_ids) >= batch_size:
                _flush()
        _flush()

    source = "dataset" if (texts and tokenizer is not None) else "random"
    meta = {
        "source": source,
        "tokenizer_available": bool(tokenizer_available),
        "datasets_available": bool(datasets_available),
        "dataset_name": str(dataset_name),
        "dataset_config": str(dataset_config),
        "split": str(split),
        "text_field": str(text_field),
        "samples": int(samples),
        "texts_loaded": len(texts),
        "batch_size": int(batch_size),
        "seq_len": int(seq_len),
        "seed": int(seed),
        "num_batches": len(batches),
        "random_vocab_size": int(vocab) if source != "dataset" else None,
    }
    return batches, meta


def _maybe_sha256(path: Path, max_mb: float = 512.0) -> str | None:
    try:
        if not path.exists():
            return None
        if float(path.stat().st_size) > float(max_mb) * 1024 * 1024:
            return None
        return file_sha256(path)
    except Exception:
        return None


def build_tensorrt_engine(
    onnx_path: Path,
    output_path: Path,
    precision: str = "fp16",
    workspace_gb: int = 4,
    dynamic_shapes: dict[str, tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]]
    | None = None,
    profiles: list[
        dict[str, tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]]
    ]
    | None = None,
    int8_calibration: dict[str, Any] | None = None,
    tokenizer_name_or_path: str | None = None,
    builder_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a TensorRT engine from ONNX model.

    Args:
        onnx_path: Path to .onnx file
        output_path: Where to save .plan file
        precision: "fp32", "fp16", or "int8"
        workspace_gb: Max workspace size in GB
        dynamic_shapes: Dict of {input_name: (min_shape, opt_shape, max_shape)}

    Returns:
        Metadata dict with build stats
    """
    try:
        sanitize_onnx_file(onnx_path)
    except Exception as exc:
        logger.warning("ONNX sanitization skipped (non-fatal): %s", exc)

    cuda = None
    if precision == "int8" and int8_calibration is not None:
        if tokenizer_name_or_path is None:
            raise RuntimeError("tokenizer_name_or_path required for INT8 calibration")
        try:
            from scripts.tr118.trt_inference import ensure_cuda_dll_search_path

            ensure_cuda_dll_search_path()
            import pycuda.autoinit  # type: ignore  # noqa: F401
            import pycuda.driver as cuda  # type: ignore
        except ImportError as exc:
            error_msg = (
                "pycuda required for INT8 calibration. Install with: pip install pycuda\n"
                "Note: On Windows, ensure CUDA DLLs are accessible (use ensure_cuda_dll_search_path)."
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg) from exc
        except Exception as exc:
            error_msg = f"CUDA initialization failed for INT8 calibration: {exc}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from exc

    try:
        import tensorrt as trt
    except ImportError as exc:
        error_msg = (
            "TensorRT not installed. Install with: pip install tensorrt\n"
            "Note: TensorRT requires NVIDIA GPU and CUDA. On Windows, ensure CUDA DLLs are in PATH."
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg) from exc

    start_time = time.perf_counter()

    logger.info(f"Building TensorRT engine: {precision}, workspace={workspace_gb}GB")

    TRT_LOGGER = trt.Logger(trt.Logger.INFO)
    builder = trt.Builder(TRT_LOGGER)
    network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
    parser = trt.OnnxParser(network, TRT_LOGGER)

    # Parse ONNX
    logger.info(f"Parsing ONNX from {onnx_path}...")
    with onnx_path.open("rb") as f:
        if not parser.parse(f.read()):
            errors = []
            for i in range(parser.num_errors):
                errors.append(str(parser.get_error(i)))
            error_msg = "\n".join(errors)
            logger.error(f"ONNX parse errors:\n{error_msg}")
            raise RuntimeError(f"Failed to parse ONNX: {error_msg}")

    # Configure builder
    config = builder.create_builder_config()
    config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, workspace_gb * (1 << 30))
    calibration_shape: tuple[int, int] | None = None
    int8_meta: dict[str, Any] | None = None

    # Optional builder strategy tweaks (TR118 sweeps).
    if isinstance(builder_settings, dict) and builder_settings:
        try:
            if "builder_optimization_level" in builder_settings and hasattr(config, "builder_optimization_level"):
                config.builder_optimization_level = int(builder_settings["builder_optimization_level"])
            if "max_num_tactics" in builder_settings and hasattr(config, "max_num_tactics"):
                config.max_num_tactics = int(builder_settings["max_num_tactics"])
            if "tiling_optimization_level" in builder_settings and hasattr(config, "tiling_optimization_level"):
                config.tiling_optimization_level = int(builder_settings["tiling_optimization_level"])
            if "profiling_verbosity" in builder_settings and hasattr(config, "profiling_verbosity"):
                pv = str(builder_settings["profiling_verbosity"]).upper()
                if hasattr(trt.ProfilingVerbosity, pv):
                    config.profiling_verbosity = getattr(trt.ProfilingVerbosity, pv)
            if "tactic_sources" in builder_settings and hasattr(config, "set_tactic_sources"):
                sources = builder_settings.get("tactic_sources")
                if isinstance(sources, list) and sources:
                    mask = 0
                    for s in sources:
                        name = str(s).upper()
                        if not hasattr(trt.TacticSource, name):
                            continue
                        mask |= 1 << int(getattr(trt.TacticSource, name))
                    if mask:
                        config.set_tactic_sources(int(mask))
        except Exception as exc:  # pragma: no cover - TRT API/version dependent
            logger.warning("Ignoring builder_settings due to error: %s", exc)

    # Default to DETAILED profiling so EngineInspector can report dtype coverage.
    if hasattr(config, "profiling_verbosity") and not (
        isinstance(builder_settings, dict) and "profiling_verbosity" in builder_settings
    ):
        try:
            if hasattr(trt, "ProfilingVerbosity"):
                config.profiling_verbosity = trt.ProfilingVerbosity.DETAILED
        except Exception:  # pragma: no cover - TRT API/version dependent
            pass

    # Set precision
    if precision == "fp16":
        if not builder.platform_has_fast_fp16:
            logger.warning("FP16 not supported on this platform, falling back to FP32")
        else:
            config.set_flag(trt.BuilderFlag.FP16)
            logger.info("FP16 enabled")
    elif precision == "int8":
        if not builder.platform_has_fast_int8:
            logger.warning("INT8 not supported on this platform, falling back to FP32")
        else:
            config.set_flag(trt.BuilderFlag.INT8)
            allow_no_cal = os.getenv("BANTER_TRT_ALLOW_NO_CALIBRATOR", "0") == "1"
            if int8_calibration is None and not allow_no_cal:
                raise RuntimeError("INT8 requested but no calibration config provided")
            if int8_calibration is not None:
                if cuda is None:
                    raise RuntimeError("pycuda required for INT8 calibration")

                batches, calib_meta = _build_int8_calibration_batches(
                    tokenizer_name_or_path=tokenizer_name_or_path,
                    dataset_name=str(int8_calibration.get("dataset_name", "wikitext")),
                    dataset_config=str(
                        int8_calibration.get("dataset_config", "wikitext-2-raw-v1")
                    ),
                    split=str(int8_calibration.get("split", "test")),
                    text_field=str(int8_calibration.get("text_field", "text")),
                    samples=int(int8_calibration.get("samples", 256)),
                    batch_size=int(int8_calibration.get("batch_size", 8)),
                    seq_len=int(int8_calibration.get("seq_len", 128)),
                    seed=int(int8_calibration.get("seed", 42)),
                )
                cache_path = resolve_repo_path(
                    _REPO_ROOT,
                    str(int8_calibration.get("cache_path", str(output_path) + ".calib")),
                )
                cache_hit_before = bool(cache_path.exists())
                cache_size_before = int(cache_path.stat().st_size) if cache_path.exists() else None
                cache_sha_before = _maybe_sha256(cache_path)
                int8_meta = {
                    **calib_meta,
                    "cache_path": str(cache_path),
                    "cache_hit_before": cache_hit_before,
                    "cache_size_bytes_before": cache_size_before,
                    "cache_sha256_before": cache_sha_before,
                }

                input_names = [network.get_input(i).name for i in range(network.num_inputs)]
                max_batch = batches[0]["input_ids"].shape[0]
                max_seq = batches[0]["input_ids"].shape[1]
                calibration_shape = (int(max_batch), int(max_seq))

                class _EntropyCalibrator(trt.IInt8EntropyCalibrator2):  # type: ignore[misc]
                    def __init__(self):
                        super().__init__()
                        self._batches = batches
                        self._i = 0
                        self._cache_path = cache_path
                        self._input_names = input_names
                        self._d_inputs = {
                            "input_ids": cuda.mem_alloc(max_batch * max_seq * 4),
                            "attention_mask": cuda.mem_alloc(max_batch * max_seq * 4),
                        }

                    def get_batch_size(self) -> int:  # type: ignore[override]
                        return max_batch

                    def get_batch(self, names):  # type: ignore[override]
                        if self._i >= len(self._batches):
                            return None
                        batch = self._batches[self._i]
                        self._i += 1
                        cuda.memcpy_htod(self._d_inputs["input_ids"], batch["input_ids"])
                        cuda.memcpy_htod(
                            self._d_inputs["attention_mask"], batch["attention_mask"]
                        )
                        return [int(self._d_inputs[n]) for n in names]

                    def read_calibration_cache(self):  # type: ignore[override]
                        if self._cache_path.exists():
                            return self._cache_path.read_bytes()
                        return None

                    def write_calibration_cache(self, cache):  # type: ignore[override]
                        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
                        self._cache_path.write_bytes(cache)

                config.int8_calibrator = _EntropyCalibrator()
                logger.info("INT8 calibrator configured (cache=%s)", cache_path)
            else:
                logger.warning("INT8 enabled but no calibrator set (allow_no_calibrator=1)")
    elif precision != "fp32":
        raise ValueError(f"Unknown precision: {precision}")

    # Set optimization profiles (required for dynamic shapes)
    added_profiles: list[Any] = []
    if profiles:
        for idx, profile_shapes in enumerate(profiles):
            profile = builder.create_optimization_profile()
            for input_name, (min_shape, opt_shape, max_shape) in profile_shapes.items():
                profile.set_shape(input_name, min_shape, opt_shape, max_shape)
            config.add_optimization_profile(profile)
            added_profiles.append(profile)
            logger.info("Added optimization profile %d with %d inputs", idx, len(profile_shapes))
    elif dynamic_shapes:
        profile = builder.create_optimization_profile()
        for input_name, (min_shape, opt_shape, max_shape) in dynamic_shapes.items():
            profile.set_shape(input_name, min_shape, opt_shape, max_shape)
            logger.info(
                "Dynamic shape for %s: min=%s opt=%s max=%s",
                input_name,
                min_shape,
                opt_shape,
                max_shape,
            )
        config.add_optimization_profile(profile)
        added_profiles.append(profile)

    # When calibrating INT8 with dynamic shapes, TensorRT requires an explicit
    # calibration profile that supports the calibrator's (batch, seq) shape.
    if precision == "int8" and int8_calibration is not None and calibration_shape is not None and added_profiles:
        calib_batch, calib_seq = calibration_shape
        selected: int | None = None
        if profiles:
            for idx, profile_shapes in enumerate(profiles):
                ids = profile_shapes.get("input_ids")
                mask = profile_shapes.get("attention_mask")
                if not ids or not mask:
                    continue
                min_ids, _opt_ids, max_ids = ids
                min_mask, _opt_mask, max_mask = mask
                if (
                    min_ids[0] <= calib_batch <= max_ids[0]
                    and min_ids[1] <= calib_seq <= max_ids[1]
                    and min_mask[0] <= calib_batch <= max_mask[0]
                    and min_mask[1] <= calib_seq <= max_mask[1]
                ):
                    selected = idx
                    break
        elif dynamic_shapes:
            ids = dynamic_shapes.get("input_ids")
            mask = dynamic_shapes.get("attention_mask")
            if ids and mask:
                min_ids, _opt_ids, max_ids = ids
                min_mask, _opt_mask, max_mask = mask
                if (
                    min_ids[0] <= calib_batch <= max_ids[0]
                    and min_ids[1] <= calib_seq <= max_ids[1]
                    and min_mask[0] <= calib_batch <= max_mask[0]
                    and min_mask[1] <= calib_seq <= max_mask[1]
                ):
                    selected = 0

        if selected is not None and 0 <= selected < len(added_profiles):
            config.set_calibration_profile(added_profiles[selected])
            logger.info("Set INT8 calibration profile to %d (%dx%d)", selected, calib_batch, calib_seq)
        else:
            calib_profile = builder.create_optimization_profile()
            for name in [network.get_input(i).name for i in range(network.num_inputs)]:
                calib_profile.set_shape(name, (calib_batch, calib_seq), (calib_batch, calib_seq), (calib_batch, calib_seq))
            config.add_optimization_profile(calib_profile)
            config.set_calibration_profile(calib_profile)
            logger.info("Added INT8 calibration profile (%dx%d)", calib_batch, calib_seq)

    # Build engine
    logger.info("Building engine (this may take several minutes)...")
    try:
        serialized_engine = builder.build_serialized_network(network, config)
        if serialized_engine is None:
            raise RuntimeError("Engine build failed (returned None)")
    except Exception as exc:
        logger.error(f"Engine build failed: {exc}")
        raise

    build_time = time.perf_counter() - start_time

    # Save engine
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as f:
        f.write(serialized_engine)

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(f"Engine saved: {output_path} ({file_size_mb:.2f} MB) in {build_time:.2f}s")

    if int8_meta is not None:
        cache_path = Path(int8_meta.get("cache_path", ""))
        if cache_path.exists():
            int8_meta["cache_size_bytes_after"] = int(cache_path.stat().st_size)
            int8_meta["cache_sha256_after"] = _maybe_sha256(cache_path)
        else:
            int8_meta["cache_size_bytes_after"] = None
            int8_meta["cache_sha256_after"] = None

    engine_inspect = inspect_trt_engine(output_path)

    applied_builder_settings: dict[str, Any] = {}
    for key in ("builder_optimization_level", "max_num_tactics", "tiling_optimization_level", "profiling_verbosity"):
        if hasattr(config, key):
            try:
                val = getattr(config, key)
                applied_builder_settings[key] = int(val) if isinstance(val, (int,)) else str(val)
            except Exception:
                applied_builder_settings[key] = None

    metadata = {
        "onnx_path": str(onnx_path),
        "output_path": str(output_path),
        "precision": precision,
        "workspace_gb": workspace_gb,
        "builder_settings": builder_settings or {},
        "applied_builder_settings": applied_builder_settings,
        "tensorrt_version": str(getattr(trt, "__version__", None) or "unknown"),
        "build_time_s": build_time,
        "file_size_mb": file_size_mb,
        "engine_sha256": _maybe_sha256(output_path),
        "engine_inspect": engine_inspect,
        "int8_calibration": int8_meta,
        "dynamic_shapes": bool(dynamic_shapes or profiles),
        "profiles": len(profiles) if profiles else (1 if dynamic_shapes else 0),
        "timestamp": time.time(),
    }

    return metadata


def validate_trt_inference(
    engine_path: Path,
    test_inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Run a test inference with the TensorRT engine.

    Returns:
        Validation results
    """
    import numpy as np

    from scripts.tr118.trt_inference import TensorRTInferenceEngine

    logger.info("Validating TensorRT engine inference via pycuda...")
    runner = TensorRTInferenceEngine(engine_path)

    if test_inputs is None:
        test_inputs = {
            "input_ids": np.array([[1, 2, 3, 4, 5, 6, 7, 8]], dtype=np.int32),
            "attention_mask": np.ones((1, 8), dtype=np.int32),
        }

    batch = int(test_inputs["input_ids"].shape[0])
    seq = int(test_inputs["input_ids"].shape[1])
    vocab_fallback = 50257
    prepared = runner.prepare(batch=batch, seq=seq, vocab_size=vocab_fallback)
    latency_ms, logits = runner.infer(prepared, test_inputs["input_ids"], test_inputs["attention_mask"])
    token_id = int(np.asarray(logits)[0, -1, :].argmax())
    return {
        "success": True,
        "latency_ms": float(latency_ms),
        "output_shape": list(np.asarray(logits).shape),
        "predicted_token_id": int(token_id),
        "engine": runner.metadata.__dict__,
    }


def main():
    parser = argparse.ArgumentParser(description="Build TensorRT engines from ONNX")
    parser.add_argument(
        "--config",
        help="TR118 config yaml (preferred). When set, --onnx/--output are optional and will be inferred.",
    )
    parser.add_argument("--onnx", help="Input ONNX file (override)")
    parser.add_argument("--output", help="Output directory for .plan files (override)")
    parser.add_argument(
        "--precisions",
        nargs="+",
        choices=["fp32", "fp16", "int8"],
        default=None,
        help="Precision modes to build",
    )
    parser.add_argument("--workspace-gb", type=int, default=4, help="Max workspace size in GB")
    parser.add_argument("--validate", action="store_true", help="Run validation inference")
    parser.add_argument("--metadata", help="Save metadata JSON to this path")

    args = parser.parse_args()

    cfg = None
    if args.config:
        cfg_path = resolve_repo_path(_REPO_ROOT, str(args.config))
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))

    if args.onnx:
        onnx_path = resolve_repo_path(_REPO_ROOT, str(args.onnx))
    elif cfg is not None:
        model_name = cfg["model"]["name"]
        onnx_path = resolve_repo_path(_REPO_ROOT, str(cfg["output"]["onnx_dir"])) / f"{Path(model_name).name}.onnx"
    else:
        raise SystemExit("--onnx or --config required")

    if args.output:
        output_dir = resolve_repo_path(_REPO_ROOT, str(args.output))
    elif cfg is not None:
        output_dir = resolve_repo_path(_REPO_ROOT, str(cfg["output"]["tensorrt_dir"]))
    else:
        raise SystemExit("--output or --config required")

    if not onnx_path.exists():
        logger.error("ONNX file not found: %s", onnx_path)
        return 1

    precisions = args.precisions
    if precisions is None:
        precisions = list(cfg.get("tensorrt", {}).get("precisions", ["fp16"])) if cfg else ["fp16"]

    workspace_gb = int(args.workspace_gb)
    profiles = None
    int8_calibration = None
    tokenizer_name_or_path = None
    builder_settings = None
    if cfg is not None:
        trt_cfg = cfg.get("tensorrt", {}) or {}
        workspace_gb = int(trt_cfg.get("workspace_gb", workspace_gb))
        dyn_cfg = trt_cfg.get("dynamic_shapes", {}) or {}
        if bool(dyn_cfg.get("enabled", False)):
            profiles = []
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
        int8_calibration = trt_cfg.get("int8_calibration")
        if isinstance(int8_calibration, dict) and int8_calibration.get("cache_path"):
            int8_calibration = dict(int8_calibration)
            int8_calibration["cache_path"] = str(resolve_repo_path(_REPO_ROOT, str(int8_calibration["cache_path"])))
        tokenizer_name_or_path = cfg.get("model", {}).get("name")
        builder_settings = trt_cfg.get("builder")

    all_metadata = []

    for precision in precisions:
        output_filename = f"{onnx_path.stem}_{precision}.plan"
        output_path = output_dir / output_filename

        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"Building {precision.upper()} engine...")
            logger.info(f"{'='*60}")

            metadata = build_tensorrt_engine(
                onnx_path,
                output_path,
                precision=precision,
                workspace_gb=workspace_gb,
                profiles=profiles,
                int8_calibration=int8_calibration if precision == "int8" else None,
                tokenizer_name_or_path=tokenizer_name_or_path,
                builder_settings=builder_settings if isinstance(builder_settings, dict) else None,
            )

            if args.validate:
                validation = validate_trt_inference(output_path)
                metadata["validation"] = validation

            all_metadata.append(metadata)

        except Exception as exc:
            logger.error(f"Failed to build {precision} engine: {exc}", exc_info=True)
            # Clean up partial build artifacts if they exist
            if output_path.exists():
                try:
                    logger.warning(f"Removing partial build artifact: {output_path}")
                    output_path.unlink()
                except Exception as cleanup_exc:
                    logger.warning(f"Failed to clean up partial artifact: {cleanup_exc}")
            
            all_metadata.append(
                {
                    "precision": precision,
                    "success": False,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "output_path": str(output_path),
                    "timestamp": time.time(),
                }
            )

    # Save combined metadata
    if args.metadata:
        metadata_path = resolve_repo_path(_REPO_ROOT, str(args.metadata))
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with metadata_path.open("w") as f:
            json.dump(all_metadata, f, indent=2)
        logger.info(f"\nMetadata saved to {metadata_path}")

    # Summary
    successful = sum(1 for m in all_metadata if m.get("build_time_s") is not None)
    logger.info(f"\n{'='*60}")
    logger.info(f"BUILD SUMMARY: {successful}/{len(precisions)} engines built successfully")
    logger.info(f"{'='*60}")

    return 0 if successful == len(precisions) else 1


if __name__ == "__main__":
    sys.exit(main())
