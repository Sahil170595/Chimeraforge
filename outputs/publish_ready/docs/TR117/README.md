# Technical Report 117 (Cross-Backend Frontier Benchmark)

Artifacts for TR117 live here. The run harness is in `scripts/tr117/`, and raw outputs default to `results/tr117/runs/`.

## Reproduce

1) Run the matrix (local CPU-only is fine; GPU/TRT/ORT/Ollama are auto-detected and skipped if unavailable).
   Accuracy is gated against the baseline backend.

```bash
python scripts/tr117/run_matrix.py \
  --config scripts/tr117/configs/matrix.yaml \
  --output-root results/tr117/runs \
  --prepare-quant \
  --ensure-optional-deps
```

1) Aggregate to CSV:

```bash
python scripts/tr117/analyze_tr117.py --runs-root results/tr117/runs --output results/tr117/metrics.csv
```

1) Capture env/capabilities:

```bash
python scripts/tr117/env_capture.py
```

1) (Optional) Copy plots/CSV into this folder for the publish-ready report once runs are complete.

## Notes

- Harness sets `BANTER_FORCE_BACKEND` per run; ensure local models exist for the chosen backend (or expect
  echo fallback).
- Backends are capability-gated via `runtime.detect_capabilities`; missing deps write skip markers under
  `results/tr117/runs/.../skipped`.
- Quant modes are labels for now; integrate actual PTQ/QAT flows per model before finalizing the publish-ready
  report.
- For HF models, set `BANTER_TRANSFORMER_MODEL` to a local tiny model path (e.g., `models/tiny-gpt2`) and
  `HF_HUB_OFFLINE=1` to avoid network pulls.
