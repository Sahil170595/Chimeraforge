# TR117 Harness (Cross-Backend Frontier Benchmark)

This directory preserves the historical TR117 harness and its environment declarations.
The instructions below describe that research snapshot; they are not a currently
qualified installation or benchmark reproduction path.

## Historical dependency snapshot

[`requirements_frozen.txt`](https://github.com/Sahil170595/Chimeraforge/blob/b74a41569d17950182999ee8217994b3248eeabf/experiments/research/tr117/requirements_frozen.txt)
was archived in commit `b74a41569d17950182999ee8217994b3248eeabf`. Keep its exact
pins as evidence of the declared research environment. Updating individual pins
would change that evidence without establishing compatibility or reproducing
the original results. The accompanying Dockerfile installs this historical
manifest and is also unqualified for current use.

As reviewed on 2026-10-04, the pinned NLTK 3.9.1 and sentence-transformers 3.3.1
have known security advisories, including
[NLTK unsafe model deserialization](https://github.com/advisories/GHSA-rhp5-r9x4-f5g2)
and a [sentence-transformers local model loading trust bypass](https://github.com/advisories/GHSA-jhr6-gm9c-rqjv).
Even NLTK 3.10.3 retains an
[unpatched model-artifact sandbox bypass](https://github.com/nltk/nltk/security/advisories/GHSA-8mgp-746c-j5xp).
Do not install this archived environment for new work or use it to process
untrusted models, corpus resources, or model paths. Preserving these pins does
not dismiss the advisories or establish that the rest of the stack is secure.

A future rerun needs a separately qualified environment, recorded dependency
and model revisions, and new output artifacts. Label those outputs as a new
run rather than treating a dependency update as reproduction of the historical
measurements. No such maintained environment is supplied by this archive.

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
