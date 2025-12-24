from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any


def resolve_repo_path(repo_root: Path, path_value: str | Path) -> Path:
    p = Path(path_value)
    if p.is_absolute():
        return p
    return (repo_root / p).resolve()


def file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def _onnx_dtype_bytes(data_type: int) -> int | None:
    # Minimal mapping (covers typical weight types).
    # ONNX TensorProto.DataType values: https://github.com/onnx/onnx/blob/main/onnx/onnx.proto
    if data_type in (1,):  # FLOAT
        return 4
    if data_type in (10,):  # FLOAT16
        return 2
    if data_type in (11,):  # DOUBLE
        return 8
    if data_type in (2,):  # UINT8
        return 1
    if data_type in (3,):  # INT8
        return 1
    if data_type in (4,):  # UINT16
        return 2
    if data_type in (5,):  # INT16
        return 2
    if data_type in (6,):  # INT32
        return 4
    if data_type in (7,):  # INT64
        return 8
    if data_type in (9,):  # BOOL
        return 1
    if data_type in (12,):  # UINT32
        return 4
    if data_type in (13,):  # UINT64
        return 8
    if data_type in (14,):  # COMPLEX64
        return 8
    if data_type in (15,):  # COMPLEX128
        return 16
    if data_type in (16,):  # BFLOAT16
        return 2
    if data_type in (17,):  # FLOAT8E4M3FN (treat as 1 byte)
        return 1
    if data_type in (18,):  # FLOAT8E4M3FNUZ
        return 1
    if data_type in (19,):  # FLOAT8E5M2
        return 1
    if data_type in (20,):  # FLOAT8E5M2FNUZ
        return 1
    return None


def inspect_onnx_artifact(onnx_path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {
        "onnx_path": str(onnx_path),
        "exists": bool(onnx_path.exists()),
        "onnx_file_size_bytes": int(onnx_path.stat().st_size) if onnx_path.exists() else None,
        "onnx_file_size_mb": float(onnx_path.stat().st_size / (1024 * 1024)) if onnx_path.exists() else None,
        "external_data": None,
        "external_files": [],
        "external_total_size_bytes": 0,
        "external_total_size_mb": 0.0,
        "total_artifact_size_bytes": int(onnx_path.stat().st_size) if onnx_path.exists() else None,
        "total_artifact_size_mb": float(onnx_path.stat().st_size / (1024 * 1024)) if onnx_path.exists() else None,
        "initializer_count": None,
        "initializer_numel": None,
        "initializer_bytes_est": None,
        "initializer_bytes_est_mb": None,
        "initializer_dtype_counts": {},
        "opset_import": None,
        "ir_version": None,
        "parse_error": None,
    }
    if not onnx_path.exists():
        return info

    try:
        import onnx  # type: ignore

        model = onnx.load_model(str(onnx_path), load_external_data=False)
        info["ir_version"] = int(getattr(model, "ir_version", 0) or 0)

        try:
            opset = {}
            for op in getattr(model, "opset_import", []) or []:
                domain = str(getattr(op, "domain", "") or "")
                ver = int(getattr(op, "version", 0) or 0)
                opset[domain or "ai.onnx"] = ver
            info["opset_import"] = opset
        except Exception:
            info["opset_import"] = None

        tensor_proto = onnx.TensorProto
        external_locations: set[str] = set()
        external = False
        dtype_counts: dict[str, int] = {}
        total_numel = 0
        total_bytes_est = 0
        initializers = list(getattr(getattr(model, "graph", None), "initializer", []) or [])
        for init in initializers:
            dims = list(getattr(init, "dims", []) or [])
            numel = 1
            for d in dims:
                numel *= int(d)
            total_numel += int(numel)

            dt = int(getattr(init, "data_type", 0) or 0)
            try:
                name = str(tensor_proto.DataType.Name(dt))
            except Exception:
                name = str(dt)
            dtype_counts[name] = int(dtype_counts.get(name, 0) + 1)

            bpe = _onnx_dtype_bytes(dt)
            if bpe is not None:
                total_bytes_est += int(numel) * int(bpe)

            try:
                if int(getattr(init, "data_location", 0) or 0) == int(tensor_proto.EXTERNAL):
                    external = True
                if getattr(init, "external_data", None):
                    for kv in init.external_data:
                        if getattr(kv, "key", "") == "location" and getattr(kv, "value", ""):
                            external_locations.add(str(kv.value))
            except Exception:
                pass

        info["initializer_count"] = len(initializers)
        info["initializer_numel"] = int(total_numel)
        info["initializer_bytes_est"] = int(total_bytes_est)
        info["initializer_bytes_est_mb"] = float(total_bytes_est / (1024 * 1024))
        info["initializer_dtype_counts"] = dtype_counts
        info["external_data"] = bool(external or external_locations)

        external_total = 0
        external_files: list[dict[str, Any]] = []
        for loc in sorted(external_locations):
            p = (onnx_path.parent / loc).resolve()
            size = int(p.stat().st_size) if p.exists() else None
            if size is not None:
                external_total += size
            external_files.append({"location": loc, "path": str(p), "size_bytes": size})

        info["external_files"] = external_files
        info["external_total_size_bytes"] = int(external_total)
        info["external_total_size_mb"] = float(external_total / (1024 * 1024))

        total_artifact = int(onnx_path.stat().st_size) + int(external_total)
        info["total_artifact_size_bytes"] = total_artifact
        info["total_artifact_size_mb"] = float(total_artifact / (1024 * 1024))
        return info
    except Exception as exc:
        info["parse_error"] = f"{type(exc).__name__}: {exc}"
        return info


def inspect_model_weight_files(model_name_or_path: str) -> dict[str, Any]:
    """
    Best-effort local weight-file size inspection. Only works for local paths.
    """
    p = Path(model_name_or_path)
    if not p.exists() or not p.is_dir():
        return {"model_path": model_name_or_path, "is_local_dir": False, "weight_files": [], "total_size_bytes": 0}

    candidates = []
    for pat in [
        "pytorch_model*.bin",
        "*.safetensors",
        "model.safetensors",
        "tf_model.h5",
        "flax_model.msgpack",
    ]:
        candidates.extend(p.glob(pat))

    files: list[dict[str, Any]] = []
    total = 0
    for f in sorted({c.resolve() for c in candidates}):
        try:
            size = int(f.stat().st_size)
        except Exception:
            continue
        total += size
        files.append({"path": str(f), "name": f.name, "size_bytes": size, "size_mb": float(size / (1024 * 1024))})

    return {
        "model_path": str(p),
        "is_local_dir": True,
        "weight_files": files,
        "total_size_bytes": int(total),
        "total_size_mb": float(total / (1024 * 1024)),
    }


def _trt_engine_layer_dtype_counts(engine_info: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    layers = engine_info.get("Layers")
    if not isinstance(layers, list):
        return counts
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        outs = layer.get("Outputs") or []
        if not isinstance(outs, list):
            continue
        for out in outs:
            if not isinstance(out, dict):
                continue
            dt = str(out.get("Format/Datatype", "")).strip() or "unknown"
            counts[dt] = int(counts.get(dt, 0) + 1)
    return counts


def inspect_trt_engine(engine_path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {
        "engine_path": str(engine_path),
        "exists": bool(engine_path.exists()),
        "file_size_bytes": int(engine_path.stat().st_size) if engine_path.exists() else None,
        "file_size_mb": float(engine_path.stat().st_size / (1024 * 1024)) if engine_path.exists() else None,
        "deserialize_error": None,
        "num_layers": None,
        "num_profiles": None,
        "io_names": None,
        "engine_inspector": None,
        "layer_output_dtype_counts": {},
        "has_int8_tensors": None,
    }
    if not engine_path.exists():
        return info

    try:
        import tensorrt as trt  # type: ignore

        logger = trt.Logger(trt.Logger.ERROR)
        runtime = trt.Runtime(logger)
        engine = runtime.deserialize_cuda_engine(engine_path.read_bytes())
        if engine is None:
            raise RuntimeError("engine_deserialize_failed")

        info["num_layers"] = int(getattr(engine, "num_layers", 0) or 0)
        info["num_profiles"] = int(getattr(engine, "num_optimization_profiles", 1) or 1)
        try:
            if hasattr(engine, "num_io_tensors"):
                names = [str(engine.get_tensor_name(i)) for i in range(int(engine.num_io_tensors))]
            else:
                names = [str(engine.get_binding_name(i)) for i in range(int(engine.num_bindings))]
            info["io_names"] = names
        except Exception:
            info["io_names"] = None

        inspector = engine.create_engine_inspector() if hasattr(engine, "create_engine_inspector") else None
        if inspector is not None:
            import json

            raw = inspector.get_engine_information(trt.LayerInformationFormat.JSON)
            parsed = json.loads(raw)
            info["engine_inspector"] = {
                "layer_entry_type": type((parsed.get("Layers") or [None])[0]).__name__
                if isinstance(parsed.get("Layers"), list) and parsed.get("Layers")
                else None,
                "has_int8_in_json": "INT8" in str(raw).upper(),
            }
            dtype_counts = _trt_engine_layer_dtype_counts(parsed)
            info["layer_output_dtype_counts"] = dtype_counts
            info["has_int8_tensors"] = any("INT8" in k.upper() or "INT8" in str(k).upper() or "Int8" in str(k) for k in dtype_counts.keys())

        try:
            del inspector
        except Exception:
            pass
        try:
            del engine
        except Exception:
            pass
        try:
            runtime.__del__()  # type: ignore[attr-defined]
        except Exception:
            pass

        return info
    except Exception as exc:
        info["deserialize_error"] = f"{type(exc).__name__}: {exc}"
        return info


def human_bytes(n: int | float | None) -> str:
    if n is None:
        return "N/A"
    n = float(n)
    if n < 0:
        return "N/A"
    units = ["B", "KB", "MB", "GB", "TB"]
    idx = 0
    while n >= 1024 and idx < len(units) - 1:
        n /= 1024.0
        idx += 1
    if idx == 0:
        return f"{int(n)} {units[idx]}"
    return f"{n:.2f} {units[idx]}"


def safe_div(a: float, b: float) -> float | None:
    if b == 0:
        return None
    if not math.isfinite(a) or not math.isfinite(b):
        return None
    return float(a / b)
