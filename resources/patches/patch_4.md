# Patch 4: Ollama benchmarking automation, reporting, and publication hook

Date: 2025-09-30
Status: Completed

## Highlights
- Collected a fresh baseline against the live Ollama stack and exported system/ML telemetry.
- Ran a full quantization sweep (q4_0, q5_K_M, q8_0) plus runtime parameter tuning to identify optimal throughput/latency trade-offs.
- Published both a concise summary (`reports/ollama_benchmark_summary.md`) and an in-depth report (`docs/Ollama_Benchmark_Report.md`) with plots and reproduction steps.
- Added a GitHub Actions workflow that copies the deep-dive report into the personal profile repo (`Sahil170595/Sahil170595`) under a dated folder, ready for manual README updates.

## Changes

### 1) Baseline + benchmark data collection
- Executed `python test_baseline_performance.py`, capturing:
  - System metrics (`baseline_system_metrics.json` ? 6 samples, CPU 13.9?% avg, GPU util 33?% avg, peaks captured for temperature/power).
  - Summary reports (`baseline_system_report.txt`, `baseline_ml_report.txt`) noting the emoji encoding warning.
- Created `prompts/banter_prompts.txt` with five representative gameplay prompts used across experiments.

### 2) Quantization sweep (q4_0/q5_K_M/q8_0)
- Pulled missing Ollama models (`ollama pull …-q5_K_M`, `…-q8_0`).
- Automated REST sweep; stored metrics in `csv_data/ollama_quant_bench.csv` with per-call TTFT, throughput, counts, and error tracking.
- Derived summary stats (mean, median, p95) and prompt-level throughput comparisons.

### 3) Runtime parameter tuning (q4_0 focus)
- Swept `num_gpu` ? {999, 80, 60, 40}, `num_ctx` ? {1024, 2048, 4096}, `temperature` ? {0.2, 0.4, 0.8}.
- Persisted raw results to `csv_data/ollama_param_tuning.csv` and aggregated means to `csv_data/ollama_param_tuning_summary.csv`.
- Identified best combo (`num_gpu=40`, `num_ctx=1024`, `temperature=0.4`) delivering ~78.4 tokens/s @ 0.088?s TTFT.

### 4) Visualization + reporting
- Generated plots under `artifacts/ollama/`:
  - `quant_tokens_per_sec.png`, `quant_ttft.png` (bar charts).
  - `param_ttft_vs_tokens.png` (scatter) and `param_heatmap_temp_{0.2,0.4,0.8}.png`.
- Authored:
  - `reports/ollama_benchmark_summary.md`: concise digest for quick sharing.
  - `docs/Ollama_Benchmark_Report.md`: comprehensive deep dive covering methodology, tables, observations, and reproduction commands.
- Updated `README.md` documentation list with a direct link to the deep-dive report.

### 5) Publication workflow
- Added `.github/workflows/publish-reports.yml`:
  - Triggers on changes to the deep-dive report or via `workflow_dispatch`.
  - Copies the report into `Sahil170595/Sahil170595` under `reports/ollama/<YYYY-MM-DD>/ollama_benchmark_<YYYY-MM-DD>.md`.
  - Requires a secret `REPORTS_PUSH_TOKEN` (PAT with `repo` scope) to push to the target repo.

## Impact
- Team now has up-to-date, reproducible benchmarking data with clear winners for quantization and runtime settings.
- Visual assets and markdown reports are ready for inclusion in documentation, blog posts, or presentations.
- Automated publication closes the loop, ensuring the personal profile repo always hosts the freshest report without manual file juggling.

## Next
- Integrate the recommended runtime parameters into deployment configs and surround with automated warm-up to stabilize TTFT.
- Extend the workflow to optionally publish summary CSVs/plots once downstream consumers confirm storage layout.
- Address the Windows console encoding warning (e.g., enforce UTF-8) so ML metric exports persist without manual intervention.
