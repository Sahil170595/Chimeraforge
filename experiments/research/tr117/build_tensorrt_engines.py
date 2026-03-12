"""TensorRT engine builder for TR117 benchmark models."""

from __future__ import annotations

from pathlib import Path
import time
from typing import Any


def build_tensorrt_engine_from_onnx(
    onnx_path: Path,
    engine_path: Path,
    max_workspace_size: int = 1 << 30,  # 1GB
    fp16_mode: bool = False,
    int8_mode: bool = False,
    dynamic_shapes: (
        dict[str, tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]] | None
    ) = None,
) -> dict[str, Any]:
    """
    Build TensorRT engine from ONNX model.

    Args:
        onnx_path: Path to ONNX model
        engine_path: Output path for engine
        max_workspace_size: Max memory for TRT workspace
        fp16_mode: Enable FP16 precision
        int8_mode: Enable INT8 precision
        dynamic_shapes: Dict of {input_name: (min_shape, opt_shape, max_shape)}

    Returns:
        Build metadata dict
    """
    try:
        import tensorrt as trt  # type: ignore
    except ImportError:
        return {
            "success": False,
            "error": "tensorrt not available",
            "engine_path": None,
        }

    if not onnx_path.exists():
        return {
            "success": False,
            "error": f"ONNX model not found: {onnx_path}",
            "engine_path": None,
        }

    logger = trt.Logger(trt.Logger.WARNING)
    builder = trt.Builder(logger)
    network = builder.create_network(
        1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
    )
    parser = trt.OnnxParser(network, logger)

    start_time = time.time()

    # Parse ONNX
    with open(onnx_path, "rb") as f:
        if not parser.parse(f.read()):
            errors = [parser.get_error(i) for i in range(parser.num_errors)]
            return {
                "success": False,
                "error": f"ONNX parse failed: {errors}",
                "engine_path": None,
            }

    # Configure builder
    config = builder.create_builder_config()
    config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, max_workspace_size)

    if fp16_mode and builder.platform_has_fast_fp16:
        config.set_flag(trt.BuilderFlag.FP16)

    if int8_mode and builder.platform_has_fast_int8:
        config.set_flag(trt.BuilderFlag.INT8)
        # Note: INT8 calibration would be needed for real use

    # Set dynamic shapes if provided
    if dynamic_shapes:
        profile = builder.create_optimization_profile()
        for input_name, shapes in dynamic_shapes.items():
            min_shape, opt_shape, max_shape = shapes
            profile.set_shape(input_name, min_shape, opt_shape, max_shape)
        config.add_optimization_profile(profile)

    # Build engine
    try:
        serialized_engine = builder.build_serialized_network(network, config)
        if serialized_engine is None:
            return {
                "success": False,
                "error": "Engine build failed",
                "engine_path": None,
            }
    except Exception as exc:
        return {
            "success": False,
            "error": f"Engine build exception: {exc}",
            "engine_path": None,
        }

    # Save engine
    engine_path.parent.mkdir(parents=True, exist_ok=True)
    with open(engine_path, "wb") as f:
        f.write(serialized_engine)

    build_time = time.time() - start_time
    engine_size_mb = len(serialized_engine) / (1024 * 1024)

    return {
        "success": True,
        "error": None,
        "engine_path": str(engine_path),
        "build_time_s": build_time,
        "engine_size_mb": engine_size_mb,
        "fp16_enabled": fp16_mode,
        "int8_enabled": int8_mode,
        "dynamic_shapes": dynamic_shapes is not None,
    }


def export_model_to_onnx(
    model_name: str,
    output_path: Path,
    opset_version: int = 14,
) -> dict[str, Any]:
    """
    Export HuggingFace model to ONNX format.

    Args:
        model_name: HuggingFace model name or local path
        output_path: Output ONNX file path
        opset_version: ONNX opset version

    Returns:
        Export metadata dict
    """
    try:
        import torch  # type: ignore
        from transformers import AutoModel, AutoTokenizer  # type: ignore
    except ImportError:
        return {
            "success": False,
            "error": "torch or transformers not available",
            "onnx_path": None,
        }

    try:
        # Load model and tokenizer
        model = AutoModel.from_pretrained(model_name)
        tokenizer = AutoTokenizer.from_pretrained(model_name)

        # Prepare dummy input
        dummy_text = "This is a sample input for ONNX export."
        inputs = tokenizer(dummy_text, return_tensors="pt")

        # Export to ONNX
        output_path.parent.mkdir(parents=True, exist_ok=True)

        torch.onnx.export(
            model,
            (inputs["input_ids"],),
            str(output_path),
            input_names=["input_ids"],
            output_names=["last_hidden_state"],
            dynamic_axes={
                "input_ids": {0: "batch", 1: "sequence"},
                "last_hidden_state": {0: "batch", 1: "sequence"},
            },
            opset_version=opset_version,
            do_constant_folding=True,
        )

        onnx_size_mb = output_path.stat().st_size / (1024 * 1024)

        return {
            "success": True,
            "error": None,
            "onnx_path": str(output_path),
            "onnx_size_mb": onnx_size_mb,
            "opset_version": opset_version,
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "onnx_path": None,
        }


def build_all_engines(
    models_dir: Path = Path("models"),
    output_dir: Path = Path("artifacts/tensorrt_engines"),
    precision_modes: list[str] | None = None,
) -> dict[str, Any]:
    """Build TensorRT engines for all available models."""
    if precision_modes is None:
        precision_modes = ["fp32", "fp16"]
    results = {}

    # Find all HuggingFace models
    model_dirs = [d for d in models_dir.iterdir() if d.is_dir()]

    for model_dir in model_dirs:
        model_name = model_dir.name

        # First, export to ONNX
        onnx_path = output_dir / model_name / f"{model_name}.onnx"
        onnx_result = export_model_to_onnx(str(model_dir), onnx_path)

        if not onnx_result["success"]:
            results[model_name] = {"onnx_export": onnx_result, "engines": {}}
            continue

        # Build engines for each precision
        engines = {}
        for precision in precision_modes:
            engine_path = output_dir / model_name / f"{model_name}_{precision}.plan"

            engine_result = build_tensorrt_engine_from_onnx(
                onnx_path,
                engine_path,
                fp16_mode=(precision == "fp16"),
                int8_mode=(precision == "int8"),
            )

            engines[precision] = engine_result

        results[model_name] = {
            "onnx_export": onnx_result,
            "engines": engines,
        }

    return results


def main() -> None:
    """Build TensorRT engines for TR117 models."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Build TensorRT engines for TR117")
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=Path("models"),
        help="Directory containing HuggingFace models",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/tensorrt_engines"),
        help="Output directory for engines",
    )
    parser.add_argument(
        "--precision",
        nargs="+",
        default=["fp32", "fp16"],
        help="Precision modes to build",
    )

    args = parser.parse_args()

    print("Building TensorRT engines...")
    print(f"Models dir: {args.models_dir}")
    print(f"Output dir: {args.output_dir}")
    print(f"Precision modes: {args.precision}")

    results = build_all_engines(
        models_dir=args.models_dir,
        output_dir=args.output_dir,
        precision_modes=args.precision,
    )

    # Save results
    results_path = args.output_dir / "build_results.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {results_path}")

    # Print summary
    for model_name, result in results.items():
        print(f"\n{model_name}:")
        print(f"  ONNX export: {result['onnx_export']['success']}")
        for precision, engine_result in result.get("engines", {}).items():
            if engine_result["success"]:
                print(
                    f"  {precision} engine: ✓ ({engine_result['build_time_s']:.1f}s, {engine_result['engine_size_mb']:.1f}MB)"
                )
            else:
                print(f"  {precision} engine: ✗ ({engine_result['error']})")


if __name__ == "__main__":
    main()
