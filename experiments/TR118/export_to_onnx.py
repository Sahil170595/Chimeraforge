#!/usr/bin/env python3
"""
TR118: Export Transformer models to ONNX format with validation.

Usage:
    python export_to_onnx.py --model gpt2 --output artifacts/onnx/gpt2.onnx
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any

import torch
import torch.onnx
from transformers import AutoModelForCausalLM, AutoTokenizer

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.tr118.artifact_utils import (
    file_sha256,
    inspect_model_weight_files,
    inspect_onnx_artifact,
    resolve_repo_path,
)
from scripts.tr118.onnx_sanitize import sanitize_onnx_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@contextlib.contextmanager
def _patch_transformers_masking_no_vmap():
    """
    Work around Transformer masking implementations that rely on `torch.vmap`, which
    can break TorchScript-based ONNX export on some torch/transformers combos.

    We temporarily replace the SDPA mask interface with a simple, broadcast-based
    causal+padding mask that does not use `vmap`.
    """
    try:
        import transformers.masking_utils as mu  # type: ignore
    except Exception:
        yield
        return

    orig_sdpa_mask = getattr(mu, "sdpa_mask", None)
    orig_mapping = dict(getattr(mu.AttentionMaskInterface, "_global_mapping", {}) or {})

    def _sdpa_mask_without_vmap(
        batch_size: int,
        cache_position,  # torch.Tensor
        kv_length: int,
        kv_offset: int = 0,
        mask_function=None,  # noqa: ARG001 - ignored; used by vmap-based implementation
        attention_mask=None,  # torch.Tensor | None
        local_size: int | None = None,
        allow_is_causal_skip: bool = True,
        allow_torch_fix: bool = True,
        **kwargs,
    ):
        import torch  # type: ignore

        padding_mask = attention_mask
        if padding_mask is not None:
            try:
                padding_mask = mu.prepare_padding_mask(padding_mask, kv_length, kv_offset)
            except Exception:
                pass
            padding_mask = padding_mask.to(dtype=torch.bool)

        # Prefer deriving dynamic sizes from the (exported) attention_mask.
        if padding_mask is not None:
            batch = padding_mask.size(0)
            seq = padding_mask.size(-1)
            device = padding_mask.device
        else:
            batch = int(batch_size)
            seq = cache_position.size(0)
            device = cache_position.device

        try:
            if allow_is_causal_skip and hasattr(mu, "_ignore_causal_mask_sdpa"):
                if mu._ignore_causal_mask_sdpa(padding_mask, seq, seq, kv_offset, local_size):  # type: ignore[attr-defined]
                    return None
        except Exception:
            pass

        cfg = kwargs.get("config")
        max_pos = int(
            getattr(cfg, "n_positions", None)
            or getattr(cfg, "max_position_embeddings", None)
            or 2048
        )
        base = torch.arange(max_pos, device=device)
        kv_arange = base[:seq] + int(kv_offset)
        reshaped_cache_position = cache_position.view(-1, 1)

        causal_mask = kv_arange <= reshaped_cache_position

        sliding_window = getattr(kwargs.get("config"), "sliding_window", None)
        chunk_size = getattr(kwargs.get("config"), "attention_chunk_size", None)
        if sliding_window is not None and chunk_size is not None:
            raise ValueError("Cannot use both `sliding_window` and `attention_chunk_size`")
        if sliding_window is not None:
            sliding_mask_overlay = kv_arange > (reshaped_cache_position - int(sliding_window))
            causal_mask = causal_mask & sliding_mask_overlay
        elif chunk_size is not None:
            chunk = int(chunk_size)
            chunked_mask_overlay = (kv_arange // chunk) == (reshaped_cache_position // chunk)
            causal_mask = causal_mask & chunked_mask_overlay

        causal_mask = causal_mask[None, None, :, :].expand(batch, -1, -1, -1)
        if padding_mask is not None:
            causal_mask = causal_mask & padding_mask[:, None, None, :]

        try:
            if not getattr(mu, "_is_torch_greater_or_equal_than_2_5", True) and allow_torch_fix:
                causal_mask = causal_mask | torch.all(~causal_mask, dim=-1, keepdim=True)
        except Exception:
            pass

        return causal_mask

    try:
        mu.sdpa_mask = _sdpa_mask_without_vmap  # type: ignore[attr-defined]
        mu.AttentionMaskInterface.register("sdpa", _sdpa_mask_without_vmap)
        yield
    finally:
        try:
            if orig_sdpa_mask is not None:
                mu.sdpa_mask = orig_sdpa_mask  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            mu.AttentionMaskInterface._global_mapping = orig_mapping  # type: ignore[attr-defined]
        except Exception:
            pass


class CausalLMOnnxWrapper(torch.nn.Module):
    """
    Stable ONNX export wrapper for HF causal LMs.

    - Uses keyword args for attention_mask (avoids positional mismatch).
    - Optionally casts int32 inputs to int64 for PyTorch embedding layers.
    - Forces use_cache=False for export simplicity.
    """

    def __init__(self, model: torch.nn.Module, cast_int32_inputs: bool):
        super().__init__()
        self.model = model
        self.cast_int32_inputs = cast_int32_inputs

    def forward(
        self, input_ids: torch.Tensor, attention_mask: torch.Tensor
    ) -> torch.Tensor:
        if self.cast_int32_inputs:
            input_ids = input_ids.to(dtype=torch.int64)
            attention_mask = attention_mask.to(dtype=torch.int64)
        outputs = self.model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            use_cache=False,
        )
        return outputs.logits  # type: ignore[return-value]


def export_model_to_onnx(
    model_name_or_path: str,
    output_path: Path,
    opset_version: int = 17,
    dynamic_axes: bool = True,
    sample_inputs: dict[str, torch.Tensor] | None = None,
    trt_friendly_inputs: bool = False,
    max_retries: int = 3,
    retry_delay_s: float = 1.0,
    save_metadata_on_failure: bool = True,
) -> dict[str, Any]:
    """
    Export a HuggingFace transformer model to ONNX with retry logic and error recovery.

    Args:
        model_name_or_path: Path to model or HF model ID
        output_path: Where to save .onnx file
        opset_version: ONNX opset version (17 for best compatibility)
        dynamic_axes: Use dynamic batch/sequence axes
        sample_inputs: Optional custom inputs (otherwise uses dummy)
        max_retries: Maximum number of retry attempts for transient failures
        retry_delay_s: Delay between retries in seconds
        save_metadata_on_failure: Save metadata even if export fails

    Returns:
        Metadata dict with export stats (includes error info on failure)
    """
    output_path = resolve_repo_path(_REPO_ROOT, output_path)
    start_time = time.perf_counter()
    export_error: Exception | None = None
    model = None
    tokenizer = None

    try:
        logger.info(f"Loading model from {model_name_or_path}...")
        model = AutoModelForCausalLM.from_pretrained(model_name_or_path, torch_dtype=torch.float32)
        tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)
        model.eval()

        if sample_inputs is None:
            # Create dummy inputs
            dummy_text = "Hello, this is a test prompt for ONNX export validation."
            sample_inputs = tokenizer(dummy_text, return_tensors="pt")

        # Move to CPU for export (ONNX export is CPU-based)
        model = model.cpu()
        sample_inputs = {k: v.cpu() for k, v in sample_inputs.items()}
        if trt_friendly_inputs:
            sample_inputs = {k: v.to(dtype=torch.int32) for k, v in sample_inputs.items()}

        # Define dynamic axes if requested
        if dynamic_axes:
            dynamic_axes_config = {
                "input_ids": {0: "batch", 1: "sequence"},
                "attention_mask": {0: "batch", 1: "sequence"},
                "logits": {0: "batch", 1: "sequence"},
            }
        else:
            dynamic_axes_config = None

        logger.info(f"Exporting to ONNX (opset={opset_version}, dynamic={dynamic_axes})...")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        wrapper = CausalLMOnnxWrapper(model, cast_int32_inputs=trt_friendly_inputs)
        
        # Retry logic for transient failures
        last_exception = None
        for attempt in range(max_retries):
            try:
                with _patch_transformers_masking_no_vmap():
                    torch.onnx.export(
                        wrapper,
                        (sample_inputs["input_ids"], sample_inputs["attention_mask"]),
                        str(output_path),
                        input_names=["input_ids", "attention_mask"],
                        output_names=["logits"],
                        dynamic_axes=dynamic_axes_config,
                        opset_version=opset_version,
                        do_constant_folding=True,
                        verbose=False,
                    )
                # Success - break out of retry loop
                break
            except Exception as exc:
                last_exception = exc
                export_error = exc
                if attempt < max_retries - 1:
                    logger.warning(
                        f"ONNX export attempt {attempt + 1}/{max_retries} failed: {exc}. "
                        f"Retrying in {retry_delay_s}s..."
                    )
                    time.sleep(retry_delay_s)
                    # Clean up partial output if it exists
                    if output_path.exists():
                        try:
                            output_path.unlink()
                        except Exception:
                            pass
                else:
                    logger.error(f"ONNX export failed after {max_retries} attempts: {exc}")
                    raise
        
        if last_exception is not None:
            raise last_exception

    except Exception as exc:
        export_error = exc
        logger.error(f"ONNX export failed: {exc}")
        if not save_metadata_on_failure:
            raise
        
        # Build failure metadata
        export_time = time.perf_counter() - start_time
        metadata = {
            "model": model_name_or_path,
            "output_path": str(output_path),
            "export_time_s": export_time,
            "success": False,
            "error": str(exc),
            "error_type": type(exc).__name__,
            "opset_version": opset_version,
            "dynamic_axes": dynamic_axes,
            "trt_friendly_inputs": trt_friendly_inputs,
            "retries_attempted": max_retries,
            "timestamp": time.time(),
        }
        
        # Try to get model info even on failure
        try:
            if model is not None:
                metadata["model_weight_files"] = inspect_model_weight_files(model_name_or_path)
        except Exception:
            pass
        
        return metadata

    # Success path
    export_time = time.perf_counter() - start_time
    file_size_mb = output_path.stat().st_size / (1024 * 1024)

    logger.info(f"Export complete: {output_path} ({file_size_mb:.2f} MB) in {export_time:.2f}s")

    # TensorRT compatibility: apply minimal, safe ONNX rewrites.
    sanitize_info: dict[str, Any] = {}
    try:
        sanitize_info = sanitize_onnx_file(output_path)
        if sanitize_info.get("changed"):
            logger.info("Applied ONNX sanitization: %s", sanitize_info)
    except Exception as exc:
        logger.warning("ONNX sanitization skipped (non-fatal): %s", exc)

    # Validate ONNX graph
    logger.info("Validating ONNX model...")
    valid = False
    validation_error: str | None = None
    try:
        import onnx

        onnx_model = onnx.load(str(output_path))
        onnx.checker.check_model(onnx_model)
        logger.info("ONNX model validation: PASSED")
        valid = True
    except Exception as exc:
        validation_error = str(exc)
        logger.warning(f"ONNX validation failed: {exc}")
        valid = False

    metadata = {
        "model": model_name_or_path,
        "output_path": str(output_path),
        "export_time_s": export_time,
        "file_size_mb": file_size_mb,
        "opset_version": opset_version,
        "dynamic_axes": dynamic_axes,
        "trt_friendly_inputs": trt_friendly_inputs,
        "onnx_sanitization": sanitize_info,
        "valid": valid,
        "validation_error": validation_error,
        "success": True,
        "onnx_sha256": file_sha256(output_path) if output_path.exists() and output_path.stat().st_size <= 512 * 1024 * 1024 else None,
        "onnx_inspect": inspect_onnx_artifact(output_path) if output_path.exists() else None,
        "model_weight_files": inspect_model_weight_files(model_name_or_path),
        "timestamp": time.time(),
    }

    return metadata


def validate_onnx_inference(
    onnx_path: Path,
    model_name_or_path: str,
    test_prompt: str = "The quick brown fox",
) -> dict[str, Any]:
    """
    Run a test inference with ONNX Runtime to validate the export.

    Returns:
        Validation results including latency and output shape
    """
    import onnxruntime as ort

    logger.info(f"Loading ONNX model from {onnx_path}...")
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])

    tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)
    inputs = tokenizer(test_prompt, return_tensors="np")
    try:
        import numpy as np  # type: ignore

        input_type = str(session.get_inputs()[0].type)
        if "int32" in input_type:
            inputs["input_ids"] = inputs["input_ids"].astype(np.int32)
            inputs["attention_mask"] = inputs["attention_mask"].astype(np.int32)
        elif "int64" in input_type:
            inputs["input_ids"] = inputs["input_ids"].astype(np.int64)
            inputs["attention_mask"] = inputs["attention_mask"].astype(np.int64)
    except Exception:
        pass

    start_time = time.perf_counter()
    outputs = session.run(
        None,
        {
            "input_ids": inputs["input_ids"],
            "attention_mask": inputs["attention_mask"],
        },
    )
    inference_time = time.perf_counter() - start_time

    logits = outputs[0]
    predicted_token_id = logits[0, -1, :].argmax()
    predicted_token = tokenizer.decode([predicted_token_id])

    logger.info(
        f"ONNX inference: {inference_time*1000:.2f}ms, predicted token: '{predicted_token}'"
    )

    return {
        "inference_time_ms": inference_time * 1000,
        "output_shape": logits.shape,
        "predicted_token": predicted_token,
        "success": True,
    }


def main():
    parser = argparse.ArgumentParser(description="Export transformer model to ONNX")
    parser.add_argument("--model", required=True, help="Model path or HF ID")
    parser.add_argument("--output", required=True, help="Output ONNX file path")
    parser.add_argument("--opset", type=int, default=17, help="ONNX opset version")
    parser.add_argument(
        "--static-shapes", action="store_true", help="Use static shapes (no dynamic axes)"
    )
    parser.add_argument(
        "--trt-friendly",
        action="store_true",
        help="Export with int32 inputs (TensorRT-friendly).",
    )
    parser.add_argument("--validate", action="store_true", help="Run validation inference")
    parser.add_argument("--metadata", help="Save metadata JSON to this path")
    parser.add_argument("--max-retries", type=int, default=3, help="Maximum retry attempts for export")
    parser.add_argument("--retry-delay", type=float, default=1.0, help="Delay between retries (seconds)")

    args = parser.parse_args()

    try:
        out_path = resolve_repo_path(_REPO_ROOT, str(args.output))
        metadata = export_model_to_onnx(
            args.model,
            out_path,
            opset_version=args.opset,
            dynamic_axes=not args.static_shapes,
            trt_friendly_inputs=args.trt_friendly,
            max_retries=args.max_retries,
            retry_delay_s=args.retry_delay,
        )

        # Always save metadata (even on failure)
        if args.metadata:
            metadata_path = resolve_repo_path(_REPO_ROOT, str(args.metadata))
            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            with metadata_path.open("w") as f:
                json.dump(metadata, f, indent=2)
            logger.info(f"Metadata saved to {metadata_path}")

        if not metadata.get("success", True):
            logger.error(f"Export failed: {metadata.get('error', 'Unknown error')}")
            return 1

        if args.validate:
            validation = validate_onnx_inference(out_path, args.model)
            metadata["validation"] = validation
            # Update metadata file if it was saved
            if args.metadata:
                metadata_path = resolve_repo_path(_REPO_ROOT, str(args.metadata))
                with metadata_path.open("w") as f:
                    json.dump(metadata, f, indent=2)

        logger.info("Export successful!")
        return 0

    except Exception as exc:
        logger.error(f"Export failed: {exc}", exc_info=True)
        # Try to save error metadata if metadata path was provided
        if args.metadata:
            try:
                metadata_path = resolve_repo_path(_REPO_ROOT, str(args.metadata))
                metadata_path.parent.mkdir(parents=True, exist_ok=True)
                error_metadata = {
                    "model": args.model,
                    "output_path": str(out_path) if 'out_path' in locals() else str(args.output),
                    "success": False,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "timestamp": time.time(),
                }
                with metadata_path.open("w") as f:
                    json.dump(error_metadata, f, indent=2)
                logger.info(f"Error metadata saved to {metadata_path}")
            except Exception:
                pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
