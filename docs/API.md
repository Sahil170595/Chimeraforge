# API Documentation

## Overview

This document covers the public Python API for the `chimeraforge` package.
This document covers released Chimeraforge 0.76.0 and the explicitly marked unreleased 0.81.0 source candidate (including the 0.77.0-0.80.0 candidate features below).

Unreleased 0.81.0 adds typed `api.KubernetesOptions(namespace="default", name_prefix=None, node_selector={})` and lazy sync `api.verify_deployment(saved, config_path, *, image, format="compose", kubernetes=None, model=None, candidate_index=0, gpu_devices=None, host_port=None, replica_gpu_devices=None, replica_host_ports=None)`. The direct `chimeraforge.deploy.export_deployment(..., format="kubernetes", kubernetes=options)` preserves every original supported online Linux CUDA vLLM/SGLang member in bounded JSON; export remains a direct module API. Explicit Kubernetes verification uses independently supplied namespace/prefix/selectors/image/selection and preserves native match0/drift5/invalid1. Default Compose report shape stays unchanged. See [complete signatures, examples, fidelity and API-admission proof limits](kubernetes-deployment.md).

Unreleased 0.80.0 adds closed `api.FleetTraceGatePolicy`, sync `api.gate_fleet_traces(baseline, candidate, *, policy)` and `api.write_fleet_trace_gate(decision, *, out=None, junit=None)`. One whole fleet per arm retains every member/row, strict source and ordered-population commitments, native global arithmetic and separate evidence blockers. Bounded JSON/JUnit output protects held inputs and both destinations. See [full original-fleet regression policy and output contract](fleet-trace-gate.md).

Unreleased 0.79.0 adds frozen `api.TraceRoute`, defensive `api.FleetTraceReplay`, async `api.replay_fleet_trace(saved, requests, endpoints, routes, *, candidate_index=0, model=None, concurrency=1, request_timeout=300, trace_timeout=600, cleanup_timeout=2, stop_event=None, connections=None)` and sync strict `api.load_fleet_trace(source)`. Every original member and routed request stays in one native population with separate execution, SLO, configuration and cooperative cleanup facts. See [complete original-fleet examples, receiving schema and limits](fleet-trace.md).

Unreleased 0.78.0 adds opaque runtime `api.MonitorConnection` / `MonitorConnectionError`, `run_monitor(..., connection=None)`, `api.monitor_plan(..., connection=None)` and async `api.monitor_fleet(..., connections=None)`. Explicit fleet mappings, including `{}`, opt every original endpoint into verified HTTPS; omitted IDs receive secure anonymous trust, without credential broadcast. The same origin-bound bearer/privateCA/mTLS policy covers metrics and all metadata. These settings stay outside persisted requests/reports. See [constructor, CLI/API examples, trust and lifecycle limits](secure-monitoring.md).

Unreleased 0.77.0 adds async `api.check_inventory(saved, *, candidate_index=0, gpu_devices=None, replica_gpu_devices=None, timeout=10)` and frozen `InventoryCheck`, `InventoryBaseline`, `InventoryDevice`, `InventoryObservation`, `InventorySlot` types. It compares the full original ordered selector population and reported free memory with the saved per-GPU modeled batch-one baseline. Invalid input raises `InventoryCheckError`; unknown observations remain explicit. See [exact CLI/API examples, outcomes and limits](inventory-check.md). Every result has `deployment_ready: null`.
Chimeraforge 0.72.0 extends `PlanScenario` / `study_plan` with exact hardware
alternatives under held model/input facts; see
[the complete study contract](planning-api.md#frozen-context-sensitivity).
Chimeraforge 0.73.0 adds keyword-only `gpu_devices: list[str] | None`
and `host_port: int | None` to the direct `chimeraforge.deploy.export_deployment`
API. This is a module API, not an additional `chimeraforge.api` re-export. See
[the exact placement contract and complete example](deployment.md#explicit-device-selection-and-host-ports).

Chimeraforge 0.74.0 adds keyword-only
`replica_gpu_devices: list[list[str]] | None` and `replica_host_ports: list[int] | None`
to the same direct deployment API. They require a complete explicit layout for
an original online vLLM/SGLang multi-replica Compose candidate. See the
[full API/CLI contract](deployment.md#homogeneous-compose-replicas).

Chimeraforge 0.75.0 adds the separate typed direct module API
`chimeraforge.deployment_verify.verify_deployment` and `deploy-verify` CLI. It
checks generated JSON Compose/required companion bytes against independent saved
plan and render intent. See [full signatures, examples and outcomes](deployment-verification.md).
In released 0.75.0/0.76.0 it is not a `chimeraforge.api` re-export. The unreleased 0.81.0 candidate adds that lazy public entry point; neither version is a runtime/source-authentication check.

Chimeraforge 0.76.0 adds typed `FleetEndpoint`,
`FleetMonitorRequest`, `FleetMonitorReport` and async
`api.monitor_fleet(saved, request, *, candidate_index=0, stop_event=None)`.
It observes every explicitly declared original replica under shared budgets,
retaining partial native windows/metadata and separate closure/coverage facts.
See [complete examples, outcomes and limits](fleet-monitoring.md).

For CLI usage, see the [README](../README.md).
Chimeraforge 0.63.0's `TraceGatePolicy` / `gate_traces` API is
documented in [queue-inclusive trace regression gates](trace-regression-gate.md).
Chimeraforge 0.64.0 adds async `replay_trace_campaign` / `TraceCampaign`;
see [the serial campaign contract](trace-campaign.md).
Chimeraforge 0.65.0 adds `sign_contribution`, `verify_signed_contribution` and
async `replay_signed_contribution`, with defensive `SignedContribution` and
`SignedContributionReceipt` results. Install the optional `sign` extra and see
[signed contributions and private replay](signed-contribution-v2.md) for exact
interfaces, receiver trust, private-input bindings and unavailable outcomes.
Chimeraforge 0.66.0 adds `PredictionScorePolicy`, `PredictionScorecard` and
`score_predictions` for offline scoring of frozen candidate throughput against
eligible saved native evidence. See [prediction scorecards](prediction-scorecards.md)
for the explicit population, binding, error-band and unavailable-evidence contract.
Chimeraforge 0.67.0 adds `gate_trace_campaigns` over whole serial
campaigns using `TraceGatePolicy`. Failed and not-started replicas stay in the
declared population. See [whole-campaign gates](trace-campaign-gates.md).
Chimeraforge 0.68.0 adds async `replay_plan_trace` and defensive
`PlanTraceReplay`, retaining a selected frozen candidate beside its unchanged
native trace. See [plan-bound traces](plan-bound-trace.md) for exact cap admission,
before/after bindings, modeled settings and independent SLO outcomes.
Chimeraforge 0.69.0 adds sync `assess_trace_envelope(cases, campaigns,
*, policy)` returning a defensive `RegressionGate`. Cases and policy accept held
JSON objects or paths; campaigns maps declared cell names to `TraceCampaign`,
JSON objects or paths. Missing cells remain declared, and every supplied campaign
must match its cell. See [finite load points](trace-envelope.md) for the closed
schemas, comparability conditions, byte limits and exits.
Chimeraforge 0.70.0 adds `PredictionBundle`,
`create_prediction_bundle`, `verify_prediction_bundle` and `score_prediction_bundle`.
Original policy/receipt bytes remain held alongside the verified original plan
inputs; scoring uses the existing `PredictionScorecard` algorithm. See
[private prediction bundles](prediction-bundles.md) for exact signatures,
inventory, publication behavior and private-content limits.

Chimeraforge 0.71.0 adds sync `gate_signed_contributions(baseline,
candidate, *, trusted_keys, policy)` returning `SignedContributionReceipt`.
Only explicitly trusted, valid signed v2 public native facts are compared;
no private saved-plan bindings are reconstructed. See
[signed native gates](signed-native-gates.md) for exact types, outcomes and limits.

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

- **`Candidate`** — dataclass: model, quant, backend, n_agents, vram_gb, quality, throughput_tps, p95_latency_ms, monthly_cost, cost_per_1m_tok, safety_refusal, rtsi_risk, warnings, plus model-agnostic fields `params_b`, `model_source`, and `provenance` (per-prediction `measured`/`estimated`/`unknown`), the 0.8.0 energy fields `tdp_watts`, `energy_cost_month`, `energy_cost_per_1m_tok`, `perf_per_watt`, and the multi-GPU fields `tensor_parallel` (0.10.0 TP degree), `pipeline_parallel` (0.11.0 PP degree), and `gpus_total` (fleet size = N replicas x TP x PP)
- **`PlannerModels`** — container for 7 model objects (VRAM, Throughput, Scaling, Quality, Cost, Latency, Safety)
- **`GPUSpec`** — frozen dataclass: name, vram_gb, bandwidth_gbps, cost_per_hour, fp16_tflops, tdp_watts (board power, drives the 0.8.0 energy estimate), interconnect_gbps (NVLink/PCIe, drives the 0.10.0 tensor-parallel comms model)

### Hardware DB

```python
from chimeraforge.planner.hardware import GPU_DB, get_gpu, bandwidth_ratio

gpu = get_gpu("4080")  # Case-insensitive substring match
print(gpu.name, gpu.vram_gb, gpu.bandwidth_gbps)
```

50 GPUs: RTX 3080/3090/4060/4060Ti/4070/4070Ti/4080/4090, RTX 5070/5070Ti/5080/5090 (Blackwell), RTX PRO 6000 Blackwell (Workstation/Max-Q/Server), A100 (40/80GB), H100, H200, B200, L4, T4, AMD MI300X/MI325X/MI350X/MI355X/MI455X, RX 9070/9070 XT/9060 XT, Radeon AI PRO R9700, Intel Arc Pro B60/B65, and unified-memory devices (current Apple Silicon by GPU variant, Ryzen AI Max+ 395, DGX Spark), which need `--unified-memory-fraction`. A figure the vendor does not publish is reported as null, never 0.

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
# Tier needs the FP16 baseline composite to measure the drop against:
print(f"Tier: {classify_tier(scores.composite, fp16_composite=0.85)}")
```

### Metrics

- **`compute_exact_match(preds, refs)`** — case-insensitive exact match ratio
- **`compute_rouge_l(preds, refs)`** — ROUGE-L F1 (uses `evaluate` library, falls back to LCS)
- **`compute_bert_score(preds, refs)`** — BERTScore F1 (requires `evaluate` + `bert-score`)
- **`compute_coherence(preds, refs)`** — length-ratio heuristic
- **`compute_composite(scores)`** — weighted: 0.2*EM + 0.3*ROUGE + 0.3*BERT + 0.2*coherence
- **`classify_tier(composite, fp16_composite)`** — negligible (>=-3pp), acceptable (>=-10pp), concerning, unacceptable

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
