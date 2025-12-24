"""
TR118: TensorRT inference utilities (optional).

This module is intentionally dependency-light and only imports TensorRT/pycuda
inside functions/classes that need them.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys
from typing import Any


@dataclass(frozen=True)
class TensorRTEngineMetadata:
    engine_path: str
    api: str  # "bindings" (TRT<=9) or "tensors" (TRT>=10)
    num_io_tensors: int
    num_profiles: int
    input_names: list[str]
    output_names: list[str]
    output_dtype: str


def ensure_cuda_dll_search_path() -> list[str]:
    """
    On Windows, Python uses a restricted DLL search path for extension modules.
    PyCUDA's `_driver` extension depends on CUDA DLLs (e.g. `curand64_10.dll`)
    that typically live under `%CUDA_PATH%\\bin`.

    This helper makes PyCUDA/TensorRT usable without requiring global PATH tweaks.
    """
    if os.name != "nt":
        return []
    add_dir = getattr(os, "add_dll_directory", None)
    if add_dir is None:
        return []

    candidates: list[Path] = []

    # CUDA_PATH, CUDA_PATH_V12_8, CUDA_PATH_V13_0, ...
    for key, value in os.environ.items():
        if not key.upper().startswith("CUDA_PATH"):
            continue
        if not value:
            continue
        candidates.append(Path(value) / "bin")

    # PyTorch wheels ship CUDA DLLs under torch\lib (e.g. curand64_10.dll),
    # which PyCUDA may need at import time.
    try:  # pragma: no cover - environment dependent
        import torch  # type: ignore

        candidates.append(Path(torch.__file__).resolve().parent / "lib")
    except Exception:
        pass

    # TensorRT pip packages ship DLLs under tensorrt_libs (e.g. nvinfer_10.dll).
    try:  # pragma: no cover - environment dependent
        import tensorrt_libs  # type: ignore

        candidates.append(Path(tensorrt_libs.__file__).resolve().parent)
    except Exception:
        pass

    # NVIDIA pip CUDA runtime packages may ship DLLs under nvidia\cu*\bin\x86_64.
    for sp in list(dict.fromkeys(sys.path)):  # stable order, de-duped
        try:
            base = Path(sp)
        except Exception:
            continue
        if not base.exists():
            continue
        try:
            for p in base.glob("nvidia/cu*/bin/x86_64"):
                candidates.append(p)
        except Exception:
            continue

    added: list[str] = []
    seen: set[str] = set()
    for p in candidates:
        try:
            p_str = str(p)
            if p_str in seen:
                continue
            if not p.exists():
                continue
            add_dir(p_str)
            added.append(p_str)
            seen.add(p_str)
        except Exception:
            continue
    return added


class TensorRTInferenceEngine:
    def __init__(self, engine_path: Path):
        self.engine_path = engine_path

        try:
            ensure_cuda_dll_search_path()
            import pycuda.autoinit  # type: ignore  # noqa: F401
            import pycuda.driver as cuda  # type: ignore
            import tensorrt as trt  # type: ignore
        except Exception as exc:
            raise RuntimeError(f"tensorrt_or_pycuda_missing:{exc}") from exc

        self._trt = trt
        self._cuda = cuda

        runtime = trt.Runtime(trt.Logger(trt.Logger.ERROR))
        engine = runtime.deserialize_cuda_engine(engine_path.read_bytes())
        if engine is None:
            raise RuntimeError("engine_deserialize_failed")
        context = engine.create_execution_context()
        if context is None:
            raise RuntimeError("context_create_failed")

        self._runtime = runtime
        self._engine = engine
        self._context = context
        self._stream = cuda.Stream()

        self._api = "tensors" if hasattr(engine, "num_io_tensors") else "bindings"
        self._num_profiles = int(getattr(engine, "num_optimization_profiles", 1) or 1)

        if self._api == "bindings":
            base_ids, base_mask, base_out = self._binding_indices_base()

            bindings_per_profile = int(engine.num_bindings // self._num_profiles) if self._num_profiles > 0 else engine.num_bindings
            if self._num_profiles > 0 and bindings_per_profile * self._num_profiles != engine.num_bindings:
                self._num_profiles = 1
                bindings_per_profile = int(engine.num_bindings)

            input_names = []
            for i in range(bindings_per_profile):
                if engine.binding_is_input(i):
                    input_names.append(str(engine.get_binding_name(i)))
            output_name = str(engine.get_binding_name(base_out))

            out_dtype = self._trt.nptype(engine.get_binding_dtype(base_out))
            output_dtype_name = str(getattr(out_dtype, "__name__", out_dtype))

            self._base_binding_ids = base_ids
            self._base_binding_mask = base_mask
            self._base_binding_out = base_out
            self._bindings_per_profile = bindings_per_profile
            self._input_names = input_names
            self._output_names = [output_name]

            self.metadata = TensorRTEngineMetadata(
                engine_path=str(engine_path),
                api=self._api,
                num_io_tensors=int(engine.num_bindings),
                num_profiles=self._num_profiles,
                input_names=input_names,
                output_names=[output_name],
                output_dtype=output_dtype_name,
            )
        else:
            io_names = [str(engine.get_tensor_name(i)) for i in range(int(engine.num_io_tensors))]
            input_names = [n for n in io_names if engine.get_tensor_mode(n) == trt.TensorIOMode.INPUT]
            output_names = [n for n in io_names if engine.get_tensor_mode(n) == trt.TensorIOMode.OUTPUT]
            if not output_names:
                raise RuntimeError("no_output_tensors_found")
            # Prefer common HF export name.
            output_name = "logits" if "logits" in output_names else output_names[0]

            out_dtype = self._trt.nptype(engine.get_tensor_dtype(output_name))
            output_dtype_name = str(getattr(out_dtype, "__name__", out_dtype))

            self._input_names = input_names
            self._output_names = output_names
            self._output_name = output_name

            self.metadata = TensorRTEngineMetadata(
                engine_path=str(engine_path),
                api=self._api,
                num_io_tensors=int(engine.num_io_tensors),
                num_profiles=self._num_profiles,
                input_names=input_names,
                output_names=output_names,
                output_dtype=output_dtype_name,
            )

    def _binding_indices_base(self) -> tuple[int, int, int]:
        engine = self._engine

        def first_index(name: str) -> int:
            for i in range(engine.num_bindings):
                if engine.get_binding_name(i) == name:
                    return int(i)
            return -1

        idx_ids = first_index("input_ids")
        idx_mask = first_index("attention_mask")
        idx_out = next((i for i in range(engine.num_bindings) if not engine.binding_is_input(i)), -1)
        if idx_ids < 0 or idx_mask < 0 or idx_out < 0:
            raise RuntimeError("binding_names_not_found")
        return idx_ids, idx_mask, int(idx_out)

    def _profile_shapes(self, profile_idx: int, binding_name: str) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]] | None:
        engine = self._engine
        try:
            if hasattr(engine, "get_tensor_profile_shape"):
                shapes = engine.get_tensor_profile_shape(binding_name, profile_idx)
                if shapes and len(shapes) == 3:
                    min_shape, opt_shape, max_shape = shapes
                    return (
                        tuple(int(x) for x in min_shape),
                        tuple(int(x) for x in opt_shape),
                        tuple(int(x) for x in max_shape),
                    )
            min_shape, opt_shape, max_shape = engine.get_profile_shape(profile_idx, binding_name)
            return (
                tuple(int(x) for x in min_shape),
                tuple(int(x) for x in opt_shape),
                tuple(int(x) for x in max_shape),
            )
        except Exception:
            return None

    def select_profile(self, batch: int, seq: int, input_binding_name: str = "input_ids") -> int:
        if self._num_profiles <= 1:
            return 0
        for p in range(self._num_profiles):
            shapes = self._profile_shapes(p, input_binding_name)
            if shapes is None:
                continue
            min_s, _opt_s, max_s = shapes
            if len(min_s) < 2 or len(max_s) < 2:
                continue
            if min_s[0] <= batch <= max_s[0] and min_s[1] <= seq <= max_s[1]:
                return p
        return 0

    def _binding_index_for_profile(self, base_index: int, profile_idx: int) -> int:
        if self._api != "bindings":
            return base_index
        if self._num_profiles <= 1:
            return base_index
        return int(base_index + profile_idx * self._bindings_per_profile)

    def _activate_profile(self, profile_idx: int) -> None:
        ctx = self._context
        stream = self._stream
        try:
            ctx.set_optimization_profile_async(profile_idx, stream.handle)
            return
        except Exception:
            pass
        try:
            ctx.active_optimization_profile = profile_idx
        except Exception:
            pass

    def prepare(self, batch: int, seq: int, vocab_size: int) -> dict[str, Any]:
        import numpy as np  # type: ignore

        engine = self._engine
        ctx = self._context
        cuda = self._cuda

        profile_idx = self.select_profile(batch=batch, seq=seq)
        self._activate_profile(profile_idx)

        if self._api == "tensors":
            input_ids_name = "input_ids"
            attention_mask_name = "attention_mask"
            output_name = getattr(self, "_output_name", "logits")

            if not bool(ctx.set_input_shape(input_ids_name, (batch, seq))):
                raise RuntimeError(f"set_input_shape_failed:{input_ids_name}:{batch}x{seq}")
            if not bool(ctx.set_input_shape(attention_mask_name, (batch, seq))):
                raise RuntimeError(f"set_input_shape_failed:{attention_mask_name}:{batch}x{seq}")

            out_shape = tuple(int(x) for x in ctx.get_tensor_shape(output_name))
            if not out_shape or any(int(x) < 0 for x in out_shape):
                out_shape = (batch, seq, int(vocab_size))

            out_dtype = self._trt.nptype(engine.get_tensor_dtype(output_name))
            host_out = np.empty(out_shape, dtype=out_dtype)

            d_ids = cuda.mem_alloc(batch * seq * 4)
            d_mask = cuda.mem_alloc(batch * seq * 4)
            d_out = cuda.mem_alloc(int(host_out.nbytes))

            ctx.set_tensor_address(input_ids_name, int(d_ids))
            ctx.set_tensor_address(attention_mask_name, int(d_mask))
            ctx.set_tensor_address(output_name, int(d_out))

            return {
                "profile_idx": profile_idx,
                "input_ids_name": input_ids_name,
                "attention_mask_name": attention_mask_name,
                "output_name": output_name,
                "d_ids": d_ids,
                "d_mask": d_mask,
                "d_out": d_out,
                "host_out": host_out,
            }

        idx_ids = self._binding_index_for_profile(self._base_binding_ids, profile_idx)
        idx_mask = self._binding_index_for_profile(self._base_binding_mask, profile_idx)
        idx_out = self._binding_index_for_profile(self._base_binding_out, profile_idx)

        ctx.set_binding_shape(idx_ids, (batch, seq))
        ctx.set_binding_shape(idx_mask, (batch, seq))

        out_shape = tuple(int(x) for x in ctx.get_binding_shape(idx_out))
        if not out_shape or any(int(x) < 0 for x in out_shape):
            out_shape = (batch, seq, int(vocab_size))

        out_dtype = self._trt.nptype(engine.get_binding_dtype(idx_out))
        host_out = np.empty(out_shape, dtype=out_dtype)

        d_ids = cuda.mem_alloc(batch * seq * 4)
        d_mask = cuda.mem_alloc(batch * seq * 4)
        d_out = cuda.mem_alloc(int(host_out.nbytes))

        bindings = [0] * int(engine.num_bindings)
        bindings[idx_ids] = int(d_ids)
        bindings[idx_mask] = int(d_mask)
        bindings[idx_out] = int(d_out)

        return {
            "profile_idx": profile_idx,
            "idx_ids": idx_ids,
            "idx_mask": idx_mask,
            "idx_out": idx_out,
            "d_ids": d_ids,
            "d_mask": d_mask,
            "d_out": d_out,
            "bindings": bindings,
            "host_out": host_out,
        }

    def infer(self, prepared: dict[str, Any], input_ids, attention_mask) -> tuple[float, Any]:
        cuda = self._cuda
        ctx = self._context
        stream = self._stream

        cuda.memcpy_htod_async(prepared["d_ids"], input_ids, stream)
        cuda.memcpy_htod_async(prepared["d_mask"], attention_mask, stream)

        start = __import__("time").perf_counter()
        if self._api == "tensors":
            ok = bool(ctx.execute_async_v3(stream_handle=stream.handle))
            if not ok:
                raise RuntimeError("execute_async_v3_failed")
        else:
            ctx.execute_async_v2(bindings=prepared["bindings"], stream_handle=stream.handle)
        cuda.memcpy_dtoh_async(prepared["host_out"], prepared["d_out"], stream)
        stream.synchronize()
        latency_ms = (__import__("time").perf_counter() - start) * 1000
        return latency_ms, prepared["host_out"]
