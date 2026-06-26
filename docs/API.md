# API Documentation

## Overview

This document covers the public Python API for the `chimeraforge` package (v0.6.0).
For CLI usage, see the [README](../README.md).

Install: `pip install chimeraforge[all]`

---

## chimeraforge.planner

Capacity planning engine. Searches (model x quant x backend x N-instances) space
through 5 gates: VRAM, quality, latency, budget, and an opt-in safety gate.

```python
from chimeraforge.planner import (
    Candidate,
    PlannerModels,
    enumerate_candidates,
    find_models_for_size,
    load_bundled_models,
)

models = load_bundled_models()
candidates = enumerate_candidates(
    models=models,
    model_size="3b",
    request_rate=1.0,
    latency_slo=5000.0,
    quality_target=0.5,
    budget=100.0,
    hw_name="RTX 4080 12GB",
    context_length=2048,
    avg_tokens=128,
)
for c in candidates:
    print(f"{c.model}|{c.quant}|{c.backend} N={c.n_agents} ${c.monthly_cost:.0f}/mo")
```

### Key types

- **`Candidate`** — dataclass: model, quant, backend, n_agents, vram_gb, quality, throughput_tps, p95_latency_ms, monthly_cost, cost_per_1m_tok, safety_refusal, rtsi_risk, warnings, plus model-agnostic fields `params_b`, `model_source`, and `provenance` (per-prediction `measured`/`estimated`/`unknown`)
- **`PlannerModels`** — container for 7 model objects (VRAM, Throughput, Scaling, Quality, Cost, Latency, Safety)
- **`GPUSpec`** — frozen dataclass: name, vram_gb, bandwidth_gbps, cost_per_hour

### Hardware DB

```python
from chimeraforge.planner.hardware import GPU_DB, get_gpu, bandwidth_ratio

gpu = get_gpu("4080")  # Case-insensitive substring match
print(gpu.name, gpu.vram_gb, gpu.bandwidth_gbps)
```

15 GPUs: RTX 3080/3090/4060/4060Ti/4070/4070Ti/4080/4090, A100 (40/80GB), H100, L4, T4.

---

## chimeraforge.planner.resolver — model-agnostic specs

Resolve any identifier (registry name, Ollama tag, HF repo, or manual overrides)
to a concrete `ModelSpec` (params + attention geometry). Network resolution needs
the `resolve` extra (`httpx`).

```python
from chimeraforge.planner.resolver import resolve_spec, ModelSpec

spec = resolve_spec("Qwen/Qwen2.5-1.5B-Instruct")          # HF config.json + safetensors
spec = resolve_spec("qwen3:14b", ollama_url="http://localhost:11434")  # Ollama /api/show
spec = resolve_spec("my/model", overrides={"params_b": 7, "n_layers": 32,
                                           "n_kv_heads": 8, "d_head": 128})  # air-gapped
print(spec.params_b, spec.n_layers, spec.n_kv_heads, spec.source)
```

- Source priority: overrides > registry > on-disk cache > Ollama > HF > offline family approximation
- Raises `ResolverError` (never fabricates a spec); pass `allow_network=False` for registry/cache only
- Spec cache: `~/.cache/chimeraforge/specs` (override `$CHIMERAFORGE_CACHE`)
- Pass `specs={name: spec}` to `enumerate_candidates` to plan off-registry models

## chimeraforge.planner.discovery — discover & catalog

```python
from chimeraforge.planner.discovery import suggest, build_catalog, load_catalog
from chimeraforge.planner.models import load_effective_models

build_catalog(include_seed=True)                 # resolve a curated seed -> persisted catalog
specs = load_catalog()                            # offline
ranked = suggest(load_effective_models(), specs, hardware="RTX 4080 12GB",
                 request_rate=1.0, latency_slo=5000.0, quality_target=0.5,
                 budget=100.0, avg_tokens=128, context_length=2048)
```

`load_effective_models()` prefers a measured corpus (see below) over bundled data.

## chimeraforge.measure — measure-on-demand

Benchmark a live model and fold real throughput + scaling into a local corpus, so
`plan`/`suggest` run on measured numbers (provenance `measured`).

```python
import asyncio
from chimeraforge.measure import measure_model

res = asyncio.run(measure_model("qwen3:14b", backend="ollama",
                                ollama_url="http://localhost:11434"))
print(res.tps_n1, res.eta_at_n, res.serial_fraction, res.corpus_path)
```

- Corpus: `~/.cache/chimeraforge/fitted_models.json` (merged via the `refit` loop)
- Quality is not auto-measured (the planner's quality scale is a benchmark composite, not text similarity)

---

## chimeraforge.bench

Live inference benchmarking against Ollama, vLLM, or TGI backends.

```python
import asyncio
from chimeraforge.bench import run_benchmark, get_backend, save_results

backend = get_backend("ollama")
result = asyncio.run(run_benchmark(
    model="llama3.2-3b",
    backend=backend,
    runs=5,
    workload="single",
    context_length=2048,
))
print(f"Throughput: {result.aggregate.throughput_tps.mean:.1f} tok/s")
save_results([result], output_dir="./results")
```

### Key types

- **`BenchmarkResult`** — model, backend, quant, aggregate (AggregateMetrics), individual_runs, environment, warnings
- **`AggregateMetrics`** — throughput_tps, ttft_ms, total_duration_ms (each a StatSummary)
- **`StatSummary`** — mean, p50, p95, p99, min, max, stddev
- **`Backend`** (ABC) — health_check(), check_model(), generate(), get_version()

### Backend registry

```python
from chimeraforge.bench import get_backend

ollama = get_backend("ollama")                          # default localhost:11434
vllm = get_backend("vllm", base_url="http://localhost:8000")
tgi = get_backend("tgi", base_url="http://localhost:8080")
```

---

## chimeraforge.eval

Quality evaluation with text-similarity metrics.

```python
from chimeraforge.eval import evaluate_quality, classify_tier

scores = evaluate_quality(
    predictions=["Paris is the capital of France."],
    references=["The capital of France is Paris."],
)
print(f"Composite: {scores.composite:.3f}")
print(f"Tier: {classify_tier(scores.composite)}")
```

### Metrics

- **`compute_exact_match(preds, refs)`** — case-insensitive exact match ratio
- **`compute_rouge_l(preds, refs)`** — ROUGE-L F1 (uses `evaluate` library, falls back to LCS)
- **`compute_bert_score(preds, refs)`** — BERTScore F1 (requires `evaluate` + `bert-score`)
- **`compute_coherence(preds, refs)`** — length-ratio heuristic
- **`compute_composite(scores)`** — weighted: 0.2*EM + 0.3*ROUGE + 0.3*BERT + 0.2*coherence
- **`classify_tier(score)`** — negligible (>=-3pp), acceptable (>=-10pp), concerning, unacceptable

### Built-in tasks

```python
from chimeraforge.eval import list_tasks, get_task

for name in list_tasks():
    task = get_task(name)
    print(f"{task.name}: {len(task.prompts)} prompts")
```

3 tasks: `general_knowledge` (10 QA), `summarization` (5), `code` (5).

---

## chimeraforge.compare

Diff benchmark results across runs.

```python
from chimeraforge.compare import load_results, compare_results, format_comparison_json

base = load_results("results/run1.json")
cand = load_results("results/run2.json")
rows = compare_results(base, cand)
print(format_comparison_json(rows))
```

### Key types

- **`ComparisonRow`** — key, model, backend, quant, baseline/candidate throughput/ttft/duration, delta percentages

---

## chimeraforge.refit

Update planner coefficients from benchmark data using Bayesian blending.

```python
from pathlib import Path
from chimeraforge.refit import refit_from_bench, save_fitted_models

updated, summary = refit_from_bench(
    bench_paths=[Path("results/run1.json")],
    base_models_path=None,  # uses bundled defaults
)
save_fitted_models(updated, Path("fitted_models.json"))
```

### Validation

```python
from chimeraforge.refit import validate_fitted_models, format_validation_json

result = validate_fitted_models(updated)
print(f"Passed: {result.n_passed}/{result.n_passed + result.n_failed}")
if not result.passed:
    print(format_validation_json(result))
```

10 checks: throughput_positive, quant_multipliers_ordered, service_times_positive,
power_law_reasonable, safety_factor_range, vram_overhead_range, fp16_fastest,
throughput_not_empty, quant_fp16_is_one, latency_has_entries.

---

## chimeraforge.report

Generate Markdown/HTML reports from bench results.

```python
from chimeraforge.report import generate_report, save_report, ReportConfig

config = ReportConfig(title="My Benchmark Report", format="html")
report = generate_report(results, config)
save_report(report, Path("report.html"))
```

### Key types

- **`ReportConfig`** — title, format ("markdown" or "html")
- **`Report`** — content (str), format, title, timestamp
- **`AnalysisStats`** — rmse, mae, mape, r_squared

### Statistical analysis

```python
from chimeraforge.report import compute_rmse, compute_mape, compute_r_squared

rmse = compute_rmse(actual=[100, 95], predicted=[98, 96])
```

---

## Rust Agents

Rust implementations live in `src/rust/` and are built separately with Cargo.

```bash
cd src/rust/demo_agent && cargo run --release -- --model gemma3:latest --runs 5
cd src/rust/demo_multiagent && cargo run --release -- --scenario chimera_homo --runs 5
```

See `src/rust/demo_agent/src/main.rs` and `src/rust/demo_multiagent/src/main.rs`
for the full API (Tokio + reqwest streaming).

---

**Last Updated**: March 2026
