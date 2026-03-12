# TR118: ONNX Runtime + TensorRT Deep Dive (Local-First, Publishable)

TR118 closes the TR117 gap where ONNX/TensorRT runs were 100% degraded by building a publishable, reproducible pipeline for fully local inference:

- Correct ONNX export for HuggingFace causal LMs (keyword-arg wrapper)
- TensorRT engine builds (FP32/FP16/INT8) including real INT8 calibration when deps are available
- TR115_v2-style run-level benchmark outputs (JSONL) suitable for statistical analysis
- Perplexity accuracy gates (PyTorch baseline vs ORT/TRT)
- Report generator that writes `reports/generated/Technical_Report_118.md` from artifacts

---

## What TR118 Measures (Important)

TR118 supports two benchmark modes:

- **`prefill`**: one forward call over padded `(batch, seq_len)` inputs
- **`generate`**: an uncached greedy generation loop (repeated full forward passes, `use_cache=False`)

The generation mode is intentionally uncached to keep ORT/TRT/PyTorch comparable without exporting/handling past-KV I/O.

---

## Quickstart (End-to-End)

```bash
pip install -r scripts/tr118/requirements.txt
python scripts/tr118/run_experiment.py --config scripts/tr118/configs/matrix_postdoc.yaml --device cuda
```

## Smoke Test (Fast)

```bash
python scripts/tr118/run_experiment.py --config scripts/tr118/configs/smoke.yaml --skip-accuracy --no-report --no-plots --device cuda
```

## Sweeps (Roadmap: Shapes / Workspace / Builder Strategy)

Run the base sweep config plus per-variant overrides (static shapes, workspace sizes, builder settings). This writes a sweep manifest so reports can be generated later from artifacts.

```bash
python scripts/tr118/run_sweeps.py --base-config scripts/tr118/configs/sweep_base.yaml
```

Variants live under `scripts/tr118/configs/variants/*.yaml`. Each variant uses isolated results + ONNX/TRT artifact directories by default.

## Measuring Build Overhead (Optional)

To rebuild TensorRT engines and refresh build-time metadata (useful when changing TRT config):

```bash
python scripts/tr118/run_experiment.py --config scripts/tr118/configs/matrix_postdoc.yaml --device cuda --force-trt-rebuild
```

ONNX export can be forced via `--force-export`, but on some Windows + torch/onnx combinations the exporter may be flaky; TR118 will restore the previous ONNX artifact if a forced export fails.

Outputs land under:

- `scripts/tr118/results/raw/bench_*.jsonl` (run-level records)
- `scripts/tr118/results/processed/` (summaries, statistical comparisons, perplexity, manifests)
- `scripts/tr118/results/plots/` (plots when matplotlib is installed)

---

## Main Config

- `scripts/tr118/configs/matrix_postdoc.yaml`
  - 6 backends x 6 scenarios x 5 reps = 180 run-level samples
  - Dynamic TRT profiles for batch=1 and batch=4
  - INT8 calibration config + cache path

---

## Key Scripts

- `scripts/tr118/export_to_onnx.py`
- `scripts/tr118/onnx_sanitize.py`
- `scripts/tr118/build_trt_engines.py`
- `scripts/tr118/trt_inference.py`
- `scripts/tr118/fix_pycuda_windows.py`
- `scripts/tr118/run_benchmark.py`
- `scripts/tr118/analyze_results.py`
- `scripts/tr118/validate_accuracy.py`
- `scripts/tr118/visualize.py`
- `scripts/tr118/run_experiment.py`
- `scripts/tr118/generate_report.py`

---

## Local-First Notes

- `onnxruntime-gpu` requires `CUDAExecutionProvider`. If unavailable, `onnxruntime-gpu` is treated as degraded (no silent CPU fallback).
- Windows + TensorRT is supported via pip, but CUDA DLL loading must work; validate with `python scripts/tr118/fix_pycuda_windows.py`.
- ORT CUDA vs TRT (Windows): keep `onnxruntime-*` before `tensorrt-*` backends; `run_benchmark.py` lazily initializes TRT runners to avoid batched `execute_async_v3` failures after ORT CUDA has run.
- On Windows, Inductor+Triton wheels are often unavailable; TR118 defaults `transformers-*-compile` to `torch.compile(..., backend=\"cudagraphs\", dynamic=False)` for stability. Override via `BANTER_TR118_TORCH_COMPILE_BACKEND`.
- ONNX export: recent `transformers` builds may construct SDPA masks via `torch.vmap` (not export-friendly); TR118 temporarily patches mask creation during export (see `scripts/tr118/export_to_onnx.py`).
- Publishable INT8 requires a real-text calibration set (`datasets` + WikiText-2); otherwise calibration falls back to random tokens (flagged in build metadata).
- ONNX sanitization: TR118 automatically rewrites a small set of TRT-hostile ONNX patterns (see `scripts/tr118/onnx_sanitize.py`) before TRT builds.
