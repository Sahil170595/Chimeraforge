# TR117 Harness (Cross-Backend Frontier Benchmark)

This directory contains the runnable harness for TR117. It is designed to run locally with graceful degradation
(CPU-only is fine) and to capture artifacts under `results/tr117/`.

## What it does

- Sweeps the matrix defined in `configs/matrix.yaml` across backends (torch CPU/compile, ONNX Runtime, Ollama)
  and quant modes (fp32/fp16/int8 labels).
- Uses the Banterhearts inference service with `BANTER_FORCE_BACKEND` per run and records latencies, tokens,
  and outputs.
- Detects capabilities and skips unavailable backends without failing the run.
- Persists per-run JSON and aggregates to a CSV via the analyzer.
- Optional `--prepare-quant` runs a tiny PTQ/QAT compile per model/quant mode to generate manifests for metadata.

## Quickstart

```bash
python scripts/tr117/run_matrix.py \
  --config scripts/tr117/configs/matrix.yaml \
  --output-root results/tr117/runs \
  --ensure-optional-deps \
  --prepare-quant

python scripts/tr117/analyze_tr117.py \
  --runs-root results/tr117/runs \
  --output results/tr117/metrics.csv
```

Capture env/capabilities:

```bash
python scripts/tr117/env_capture.py
```

## Notes

- For Ollama tests, set `BANTER_OLLAMA_MODEL` or rely on the `model` field in the matrix.
- For Transformers tests, set `BANTER_TRANSFORMER_MODEL` to a locally available model or expect echo-style fallback.
- TensorRT/ORT backends are capability-gated; unavailable backends are marked as skipped.
- Accuracy is compared to the baseline backend (`baseline_backend`) and fails the run if below `accuracy_threshold`.
- For HF models, set `BANTER_TRANSFORMER_MODEL` to a local tiny model path (e.g., the bundled
  `models/tiny-gpt2`) and export `HF_HUB_OFFLINE=1` to avoid network pulls during runs.
