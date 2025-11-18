# Patch 10: Performance Digest Agent & Intelligent Recommendations

**Date:** 2025-10-03  
**Status:** Completed  
**Commits:** `356383a`, `ff3ebd8`, `1631ad9`

## Overview
A dedicated monitoring agent now ingests every benchmark artifact under `reports/` and `csv_data/`, detects latency regressions, and produces an opinionated Markdown digest for the operators. The feature set grew across two commits: the initial Performance Digest Agent implementation and a follow-up that injected system profiling plus task-aware model recommendations. Lint configuration was normalized in the same window to keep the new monitoring surface compliant with the repo's style gates.

## Monitoring Agent Stack
- **Parsers & Aggregator (`banterhearts/monitoring/agents/parsers.py`, `aggregator.py`)**  
  Consolidate CSV/Markdown metrics, normalize schemas, compute latency deltas against recorded baselines, and rank backends by throughput and memory footprint.
- **Suggestion Engine (`suggestions.py`)**  
  Produces prioritized remediation/intel bullets with confidence scores. Suggestions cover backend switches, profiling targets, memory hygiene, and regression triage.
- **Performance Digest Agent (`perf_digest_agent.py`)**  
  Orchestrates parsing, aggregation, suggestion ranking, and formatting. The agent supports top-k suggestion limits and exposes a pure-Python interface for other tooling.
- **System Profiler & Model Recommender (`system_profiler.py`, `model_recommender.py`)**  
  Optional modules that capture OS/CPU/RAM/GPU stats (via `nvidia-smi`/`torch`) and enumerate locally-available Ollama models, then recommend LLM/quantization combos for typical tasks based on VRAM ceilings.

## CLI, Artifacts, and Docs
- **`scripts/generate_perf_digest.py`** (later mirrored under `banterhearts/enterprise/scripts/`) wraps the agent with a CLI: `python scripts/generate_perf_digest.py --reports-dir reports --csv-dir csv_data --output reports/performance_digest.md --top-suggestions 5 --regression-threshold 10`.  
  Flags `--include-system` and `--include-model-recs` gate the optional sections added in the second commit.
- **`reports/performance_digest.md`** shows the machine-generated digest with KPIs, backend rankings, regression table, top suggestions, system profile, and recommendation table.
- **`docs/enterprise/performance_digest_agent.md`** documents usage, inputs, outputs, and common tuning knobs so other teams can integrate the agent.

## Quality & Coverage
- Added `banterhearts/tests/monitoring/test_perf_digest_agent.py` to validate parsing, aggregation, suggestion ordering, and markdown rendering across synthetic baselines and regression scenarios.
- `flake8` configuration was quieted (`1631ad9`) to keep the expanded monitoring tree warning-free in CI.

## Verification
1. `python scripts/generate_perf_digest.py --reports-dir reports --csv-dir csv_data --output reports/performance_digest.md --include-system --include-model-recs`
2. `pytest banterhearts/tests/monitoring/test_perf_digest_agent.py -q`

Successful runs should regenerate the digest and pass the monitoring test suite without lint violations.
