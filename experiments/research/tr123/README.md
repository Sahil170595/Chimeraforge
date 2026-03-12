# TR123: KV-Cache Production Economics

**Status:** Implementation Complete (awaiting run)
**Phase:** 2
**Depends On:** TR119, TR121
**Sprint:** 1

## Research Question

What is the real production $/tok with KV-cache enabled across diverse model architectures?

## Background

TR119's cost model uses uncached generate (`use_cache=False`), labeled "intentionally pessimistic." Production inference uses KV-cached decode, which is dramatically faster. All cost numbers need updating.

This is grounded in recent literature:
- **TokenPowerBench** (Dec 2025): Phase-aligned energy attribution on H100 clusters
- **Prefill-Decode Disaggregation** (SPAD, Nexus, DuetServe 2025): Separate cost structures per phase
- **KV-Cache Memory Scaling** (Brenndoerfer 2025): `KV_bytes = 2 × L × B × T × H_kv × D_h × precision`

**Gap filled:** No existing work measures phase-split $/tok on consumer hardware across multiple architectures and backends.

## Model Lineup

| Model | Params | Attention | KV Heads | d_head | FP16 VRAM | HF Path |
|-------|--------|-----------|----------|--------|-----------|---------|
| GPT-2 | 124M | MHA | 12 | 64 | 0.3 GB | `gpt2` |
| Llama-3.2-1B | 1.24B | GQA (4:1) | 8 | 64 | 2.5 GB | `meta-llama/Llama-3.2-1B` |
| Qwen2.5-1.5B | 1.54B | GQA (6:1) | 2 | 128 | 3.1 GB | `Qwen/Qwen2.5-1.5B` |
| Phi-2 | 2.7B | MHA | 32 | 80 | 5.4 GB | `microsoft/phi-2` |
| Llama-3.2-3B | 3.21B | GQA (3:1) | 8 | 128 | 6.4 GB | `meta-llama/Llama-3.2-3B` |

**Why these models:**
- Size range: 124M → 3.2B (26x range), all fit in 12GB VRAM in FP16
- MHA vs GQA comparison: demonstrates KV-cache memory scaling differences
- Qwen2.5-1.5B has only 2 KV heads — extreme GQA showing minimal cache overhead
- Llama-3.2 models are gated (requires `huggingface-cli login`)

## Scope

- 5 models × 3 backends × 5 scenarios × 7 reps (with backend_skip for large/CPU combos)
- Two-phase measurement: prefill (prompt processing) + KV-cached decode (token generation)
- Phase-tagged power sampling via PhasePowerSampler (not whole-run average)
- KV-cache memory sweep: 5 models × 6 context lengths
- Phase-split cost tables with 4 pricing tiers, 5 workload blend ratios
- Cross-reference against TR119 uncached results

## Success Criteria

- Production-grade $/tok table (replaces TR119's pessimistic numbers)
- MHA vs GQA comparison: KV-cache memory at same parameter count
- Memory overhead table: KV-cache MB per model per context length
- Break-even analysis: at what request rate does KV-cache memory cost exceed its benefit?
- Cached vs uncached cost improvement ratios

## Contents

```
research/tr123/
  README.md                   # This file
  configs/
    matrix.yaml               # Experiment matrix (5 models, 3 backends, 5 scenarios)
  run_benchmark.py            # Two-phase measurement engine
  analyze_results.py          # JSONL → cost pipeline
  cross_reference_tr119.py    # Cached vs uncached comparison
  kv_cache_analysis.py        # KV-cache memory overhead formulas
  visualize.py                # 8 plot types
  generate_report.py          # Markdown report generator
  validate.py                 # Data quality validation
  smoke_test.py               # Pre-run hardware/model/auth check
  run_experiment.py           # Orchestrator entry point
  results/                    # Benchmark output (gitignored)
```

## Running

```bash
# Prerequisites for gated models:
pip install huggingface_hub
huggingface-cli login  # Accept Llama license at https://huggingface.co/meta-llama

# Full pipeline
python -m research.tr123.run_experiment

# Or step by step:
python -m research.tr123.smoke_test           # Validate hardware + models
python -m research.tr123.run_benchmark        # Run measurements
python -m research.tr123.validate results/... # Check data quality
python -m research.tr123.analyze_results results/...
python -m research.tr123.visualize results/...
python -m research.tr123.generate_report results/...
```

## Published Report

`PublishReady/reports/Technical_Report_123.md`
