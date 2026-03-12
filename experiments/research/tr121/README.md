# TR121: Model Scaling Study

**Status:** Pipeline implemented + publish-ready report (TR121 v1)  
**Target:** Week of 2025-12-30  
**Depends On:** TR117, TR118, TR120

## Research Question

How do inference latency/throughput and cold-start risk change as model size increases, and how does that differ for:

- prefill vs KV-cached decode, and
- small local HF models vs larger served (Ollama) models?

## Scope

- Phase-split measurements (TR120-style): `prefill`, `kv_decode`, `e2e_kv`
- Scaling-law fits: latency vs `params_millions` (log-log power law)
- Warmup/cold-start effect analysis
- Optional decode-length sweep (`gen_tokens` 8/32/64/128)

## Key Gaps from TR117

- Model skew (54.8% on tiny-gpt2)
- No same-model cross-backend comparison yet (planned follow-up)
- Missing scaling law analysis

## Expected Deliverables

1. 4+ models tested on 5+ backends (20+ combinations)
2. Scaling-law fits with confidence intervals
3. Regime characterization (overhead-dominated vs decode-dominated)
4. Cold-start/warmup policy implications
5. Technical report with decision framing

## Repository layout

- `scripts/tr121/configs/scaling.yaml` - default scaling matrix (HF + Ollama)
- `scripts/tr121/configs/decode_sweep.yaml` - decode-length sweep definition
- `scripts/tr121/configs/gemma_family.yaml` - within-family Gemma3 scaling check (reduces family confound)
- `scripts/tr121/configs/boundary_shift_batch8.yaml` - batch-size ablation (HF GPU bs=1 vs bs=8)
- `scripts/tr121/configs/boundary_shift_gen512.yaml` - decode-length ablation (HF GPU gen_tokens=512)
- `scripts/tr121/run_scaling.py` - runner (prefill + KV decode; artifact-backed)
- `scripts/tr121/run_decode_sweep.py` - runs multiple `gen_tokens` sweeps + aggregates fits
- `scripts/tr121/analyze_scaling.py` - aggregates + scaling fits + plots
- `scripts/tr121/generate_report.py` - generates a draft Markdown summary
- `scripts/tr121/results/<RUN_ID>/` - run artifacts
- `PublishReady/reports/Technical_Report_121v1.md` - TR121 publish-ready report (definitive v1)

## Quick start

Run the full scaling matrix (can take time due to 7B/8B/20B Ollama models):

```bash
python scripts/tr121/run_scaling.py --config scripts/tr121/configs/scaling.yaml
python scripts/tr121/analyze_scaling.py --run-dir scripts/tr121/results/<RUN_ID>
python scripts/tr121/generate_report.py --run-dir scripts/tr121/results/<RUN_ID>
```

Smoke run (fast; validates pipeline):

```bash
python scripts/tr121/run_scaling.py --config scripts/tr121/configs/scaling.yaml --out-dir scripts/tr121/results/tr121_smoke \
  --repetitions 1 --warmup-repetitions 0 --gen-tokens 16 \
  --models models/gpt2-5m,gemma3:270m --backends hf_cpu_fp32,hf_gpu_fp16,ollama --scenarios micro
python scripts/tr121/analyze_scaling.py --run-dir scripts/tr121/results/tr121_smoke
python scripts/tr121/generate_report.py --run-dir scripts/tr121/results/tr121_smoke
```

Decode-length sweep:

```bash
python scripts/tr121/run_decode_sweep.py --config scripts/tr121/configs/decode_sweep.yaml
```

Within-family Gemma3 check (reduces model-family confound for Ollama scaling):

```bash
python scripts/tr121/run_scaling.py --config scripts/tr121/configs/gemma_family.yaml
python scripts/tr121/analyze_scaling.py --run-dir scripts/tr121/results/<RUN_ID>
```

Boundary shift (HF GPU batching):

```bash
python scripts/tr121/run_scaling.py --config scripts/tr121/configs/boundary_shift_batch8.yaml
python scripts/tr121/analyze_scaling.py --run-dir scripts/tr121/results/<RUN_ID>
```

## Timeline

- Week 1: Multi-model setup
- Week 2-3: Benchmark sweep (20+ combinations)
- Week 4: Scaling law analysis + report

**Start Date:** TBD

