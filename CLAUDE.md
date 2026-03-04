# CLAUDE.md — ChimeraForge

## Project Overview

ChimeraForge is an LLM inference benchmarking and deployment planning platform, broken out from the Banterhearts program. It provides quantified, reproducible answers to LLM deployment decisions, backed by 70,000+ real measurements on consumer GPUs. Ships both research artifacts (26+ technical reports, TR108-TR133) and production CLI tools (`chimeraforge plan` and `chimeraforge bench`).

**Version:** 0.2.0 | **License:** MIT | **Python:** >=3.10 | **Rust:** >=1.70

## Quick Reference

```bash
# Install (editable, all deps)
pip install -e ".[all]"

# Run capacity planner
chimeraforge plan --model-size 3b --request-rate 1.0 --hardware "RTX 4080 12GB"

# Run benchmarks (requires live Ollama)
chimeraforge bench --model llama3.2-3b --runs 5

# Run tests (158 total: 80 planner + 73 bench + 5 monitoring)
pytest tests/ -v

# Lint
ruff check src/
ruff format src/

# Rust agents
cd src/rust/demo_agent && cargo build --release
cd src/rust/demo_multiagent && cargo build --release
```

## Repository Layout

```
src/
  chimeraforge/                       # CLI tool + capacity planner (pip-installable)
    __init__.py                       # Exports __version__ = "0.2.0"
    cli.py                            # Typer entry point, `plan` command (lazy imports)
    planner/
      __init__.py                     # Re-exports Candidate, all models, load_models
      engine.py                       # 4-gate search: Candidate dataclass, enumerate_candidates()
      models.py                       # 6 predict-only dataclass models + PlannerModels container
      hardware.py                     # GPUSpec dataclass, GPU_DB (15 GPUs), bandwidth_ratio()
      constants.py                    # QUANT_LEVELS, QUANT_BPW, BACKENDS, MODEL_PARAMS_B, MODEL_ARCH
      formatter.py                    # Rich panels/tables output + JSON serialization
      data/fitted_models.json         # Pre-fitted coefficients from TR133 (loaded via importlib.resources)

  python/banterhearts/                # Python agent benchmarking package
    demo_agent/                       # Single-agent comparison (Baseline vs Chimera)
      agents/
        base_agent.py                 # ABC: BenchmarkData, AnalysisResult, BaseAgent
        baseline_agent.py             # BaselineAgent — standard Ollama config
        chimera_agent.py              # ChimeraAgent — TR108-optimized config
      config/
        baseline_config.py            # BaselineConfig dataclass (num_gpu=80, num_ctx=1024)
        chimera_config.py             # ChimeraConfig dataclass (num_ctx=512), get_chimera_config_for_model()
      metrics/
        collector.py                  # AggregateMetrics dataclass, MetricsCollector
      run_demo.py                     # ChimeraDemoOrchestrator (subprocess isolation, model unload)
      analyze_report_quality.py       # ReportQualityAnalyzer (compares vs actual TR108)
    demo_multiagent/                  # Multi-agent concurrent execution
      agents/
        data_collector.py             # Placeholder (prompts defined in orchestrator)
        insight_agent.py              # Placeholder (prompts defined in orchestrator)
      coordinator.py                  # ResourceCoordinator — asyncio.Semaphore(permits=2)
      orchestrator.py                 # build_prompts(), aggregate_runs()
      run_multiagent_demo.py          # argparse CLI, call_ollama(), run_pair() via asyncio.gather()
    benchmarking/
      benchmark_manager.py            # BenchmarkManager — simulated metrics for anomaly detection
    monitoring/                       # 16-module observability subsystem
      analysis.py                     # MetricPoint, SLO dataclasses, summarize_metric(), analyze_metrics()
      performance_monitor.py          # PerformanceMonitor — daemon thread, psutil + pynvml snapshots
      baseline_harness.py             # BaselineHarness — SLO + 20% regression threshold
      nvidia_tools.py                 # get_gpu_snapshots() — optional pynvml (graceful degradation)
      ml_performance.py               # MLPerformanceTracker — record_inference() with throughput calc
      torch_profiler.py               # profile_inference() — thin wrapper, Chrome trace export
      logging.py                      # structlog-based configure_logging(), get_logger()
      benchmarking.py                 # build_latency_sli(), slice_by_tag()
      agents/
        aggregator.py                 # MetricAggregator — thread-safe (Lock) point collector
        perf_digest_agent.py          # PerfDigestAgent — markdown digest with p50/p95/max
        suggestions.py                # SuggestionsAgent — SLO breach + model recommendations
        model_recommender.py          # ModelRecommender — heuristic flags (GPU>90%, CPU>85%, etc.)
        parsers.py                    # parse_log_lines() — regex + JSON line parsing
        storage_adapter.py            # StorageAdapter — JSONL append + file rotation
    profiling/
      profiler_agent.py               # TR117: LoopLagMonitor, ChunkProfiler, instrumented streaming

  rust/
    demo_agent/                       # Rust single-agent (Tokio, reqwest streaming, ~1500 lines)
      src/main.rs                     # Args, OllamaOptions, call_ollama_streaming(), workflow, reports
    demo_multiagent/                  # Rust multi-agent (5 runtime features, ~2000 lines)
      src/main.rs                     # Scenario enum, AgentConfig, ResourceCoordinator, try_join!

experiments/                          # TR108-TR133 experiment folders
data/                                 # baselines/, csv/, research/
outputs/publish_ready/                # Final reports and notebooks
scripts/                              # Mostly scaffolded (empty); setup_ollama_model.ps1 is live
tests/                                # test_planner.py (63 tests), test_monitoring.py (5 tests)
docs/                                 # 18 guides (~12,400 lines total)
resources/prompts/                    # Legacy banter_prompts.txt (not used in benchmarking)
```

## Code Conventions

### Python
- **Style:** PEP 8 via ruff (line-length: 100, target: py310)
- **Type hints:** Required on function signatures; use `from __future__ import annotations`
- **Docstrings:** Google-style with Args, Returns, Raises
- **Data containers:** `@dataclass` everywhere (configs, metrics, results, SLOs, GPU specs)
- **Naming:** snake_case functions/variables, PascalCase classes
- **Async:** `asyncio` + `httpx.AsyncClient` for agent execution; `asyncio.gather()` for multi-agent
- **CLI:** Typer + Rich (chimeraforge CLI); argparse (multiagent runner)
- **Formatting:** ruff format (NOT black — pyproject.toml configures ruff only)
- **Logging:** structlog for monitoring; standard logging elsewhere

### Rust
- **Edition:** 2021
- **Async:** Tokio (default), async-std, smol as feature-gated alternatives in multiagent
- **HTTP:** reqwest with streaming (`bytes_stream()` + newline-delimited JSON parsing)
- **Error handling:** `anyhow::Result<T>` throughout
- **CLI:** clap derive macros
- **Serialization:** serde + serde_json; `#[serde(skip_serializing_if = "Option::is_none")]`
- **Logging:** tracing + tracing-subscriber (INFO default)
- **Formatting:** rustfmt | **Linting:** clippy

### General
- ASCII-only in all files for universal compatibility
- Never commit model binaries (*.gguf, *.safetensors, *.pth, etc.)
- Never commit secrets (.env, credentials, API keys)

## Planner Architecture (src/chimeraforge/planner/)

The `chimeraforge plan` CLI runs a 4-gate exhaustive search over (model x quant x backend x N_agents):

**Gate 1 — VRAM:** `weight_gb + kv_cache_gb + activations_gb <= hw_vram`
- Weight: `params_B * bits_per_weight / 8 * overhead_factor`
- KV-cache: `2 * n_layers * batch * context * n_kv_heads * d_head * 2 bytes`

**Gate 2 — Quality:** `quality_score >= quality_target`
- Lookup table (model|quant), fallback: fp16_baseline + quant_delta, default: 0.5
- Tiers: negligible (>-3pp), acceptable (>-10pp), concerning (>-15pp), unacceptable

**Gate 3 — Latency:** `p95_latency_ms <= latency_slo`
- Throughput: lookup table -> FP16 * quant_multiplier -> power law fallback (`a * params^-b`)
- Quant multipliers increase throughput (Q2_K = 2.3x FP16 — lower precision = faster)
- Scaling: Amdahl's Law `eta(N) = 1/(s + (1-s)*N)`, serial fractions per model|backend
- N search: 1..16 agents until `N * tps_per_agent * eta(N) >= request_rate * avg_tokens`
- Latency: M/D/1 queueing, p95 ~ service_ms + 3 * mean_wait, 70% utilisation safety cap

**Gate 4 — Cost:** `monthly_cost <= budget`
- Monthly = `hw_cost_per_hour * 720 * N_agents`

Results sorted by (cost asc, quality desc). Output: Rich panels + alternatives table, or JSON.

### Key Gotchas in Planner
- Quantization is a throughput *multiplier* (faster at lower precision), not a penalty
- vLLM/TGI fitted serial fractions (0.81-0.92) are much worse than defaults (0.15/0.20)
- N search hard-capped at 16; p95 uses 3x-mean-wait rule of thumb
- GPU lookup uses case-insensitive substring match — "4080" matches "RTX 4080 12GB"
- `fitted_models.json` loaded via `importlib.resources` (bundled with pip package)
- Cost model hw_cost_per_hour ($0.035) is baked into JSON, not configurable via CLI

## Agent Architecture

### Single-Agent (demo_agent)
- **Pattern:** BaseAgent ABC -> BaselineAgent / ChimeraAgent
- **Workflow:** `ingest_benchmarks() -> analyze_data() -> generate_report() -> get_metrics()`
- **LLM call:** HTTP POST to `{base_url}/api/generate`, stream=False, 120s timeout
- **Isolation:** `ChimeraDemoOrchestrator` runs each agent in a **separate subprocess** to prevent warm-cache bias; forces `ollama stop all` + 30s cooling between agents
- **Chimera config:** num_ctx=512 (vs baseline 1024), derived from TR108 findings

### Multi-Agent (demo_multiagent)
- **Agents:** DataCollector-9000 (systems analyst) + InsightAgent (operations specialist)
- **Concurrency:** `asyncio.gather()` with `ResourceCoordinator(permits=2)` semaphore
- **Scenarios:** baseline_vs_chimera, chimera_homo, chimera_hetero
- **Metrics:** concurrency_speedup = sequential_estimate / concurrent_wall_time; efficiency = (speedup / 2) * 100
- **Dual Ollama:** `--collector-ollama-url` and `--insight-ollama-url` for separate endpoints

### Rust Agents
- **Single-agent:** Tokio-only, reqwest streaming, TTFT measured at first non-empty response chunk
- **Multi-agent:** 5 runtime features (tokio-default, tokio-localset, async-std, smol, smol-1kb)
- **HTTP bridge:** Non-Tokio runtimes use a dedicated 2-worker Tokio runtime for reqwest calls
- **Concurrency:** `futures_util::try_join!` with runtime-specific `ResourceCoordinator` (Tokio Semaphore / async-std Mutex / smol Semaphore)
- **Metrics:** Same structure as Python — SingleRunMetrics, AggregateMetrics, ComparisonMetrics with stddev

### Ollama API Integration
- **Endpoint:** POST `{base_url}/api/generate`
- **Payload:** `{model, prompt, stream, options: {num_gpu, num_ctx, temperature, top_p, top_k, repeat_penalty}}`
- **Key response fields:** `eval_count` (tokens), `eval_duration` (ns), `prompt_eval_duration` (ns)
- **Throughput:** `eval_count / (eval_duration / 1e9)` tok/s
- **TTFT:** `prompt_eval_duration / 1e6` ms (Python) or first-chunk timing (Rust streaming)

## Monitoring Subsystem (src/python/banterhearts/monitoring/)

16 modules providing real-time observability:
- **Metrics:** MetricPoint dataclass, percentile computation (p50/p90/p95/p99)
- **SLOs:** Dataclass with `evaluate(stats)` -> pass/fail against target using p95
- **PerformanceMonitor:** Daemon thread, 2s interval, psutil (CPU/mem/disk/net) + pynvml (GPU)
- **ModelRecommender:** Heuristic flags — GPU>90%, CPU>85%, TTFT>800ms, low throughput + low GPU
- **BaselineHarness:** SLO evaluation + 20% regression detection
- **Storage:** JSONL append with optional file rotation
- **Logging:** structlog with optional JSON output

## Testing

```bash
pytest tests/ -v                    # 158 total tests
pytest tests/ --cov=src             # With coverage
```

**test_planner.py** (80 tests, 17 test classes):
- TestConstants (4) — quant ordering, BPW coverage, model registry consistency
- TestHardwareDB (8) — GPU lookup, bandwidth ratio, case-insensitive matching
- TestVRAMModel (6) — quant/size/context scaling, defaults for unknown models
- TestThroughputModel (5) — lookup, quant multipliers, bandwidth scaling, 0.1 floor
- TestScalingModel (3) — Amdahl's law, eta monotonically decreasing
- TestQualityModel (4) — FP16 best, quality in [0,1], tier classification
- TestCostModel (5) — formula validation, zero-throughput -> inf
- TestLatencyModel (3) — M/D/1 queueing, saturation flag at 70%
- TestSerialization (3) — round-trip JSON, all 6 models, fitted=True
- TestPlanner (8) — 4-gate filtering, candidate fields, find_models_for_size
- TestSpotChecks (10) — real TR133 data validation
- TestFindModelsEdgeCases (6) — 0b, negative, empty, non-numeric, large, decimal
- TestQualityTiers (4) — FP16 negligible, Q2 tier, bounded values, 8b FP16
- TestScalingEdgeCases (2) — n=0, n=-1
- TestVRAMBatchSize (1) — batch_size=4 > batch_size=1
- TestLatencyEdgeCases (2) — saturated returns inf, zero service time
- TestSerializationExtended (2) — all 6 models round-trip, empty JSON defaults
- TestPlannerExtended (2) — empty target_models, N-search latency retry
- TestCLIPlan (5) — help, negative rate, zero tokens, invalid quality, JSON output
- TestFormatter (2) — format_json all fields, empty list

**test_bench.py** (73 tests, 18 test classes):
- TestStatSummary (5) — summarize, single value, empty, percentiles, two values
- TestAggregateRuns (4) — count, tokens, throughput stats, single run
- TestPrompts (4) — non-empty, default, short vs long, medium between
- TestProfiles (8) — exist, single, server rate, get, overrides, unknown, concurrency
- TestEnvironment (3) — fields, no version, ISO format
- TestResultSerialization (4) — to_dict, JSON round-trip, warnings, all fields
- TestBackendRegistry (4) — all backends, get ollama, with URL, unknown raises
- TestOllamaBackend (8) — name, health check, model check, generate, version
- TestRunner (7) — single, batch, health fail, model fail, aggregation, progress, fields
- TestSaveResults (3) — creates file, valid JSON, creates directory
- TestCLI (5) — help, requires model, invalid context, negative runs, negative rate
- TestRunnerSweeps (2) — quant sweep, context sweep
- TestServerMode (1) — server workload
- TestErrorResilience (2) — partial failures, all failures
- TestCVWarning (2) — high variance, stable
- TestVLLMBackend (3) — name, default URL, custom URL
- TestTGIBackend (4) — name, URL, exact match, rejects substring
- TestOllamaEdgeCases (1) — missing eval_duration returns 0 throughput

**test_monitoring.py** (5 tests):
- SLO evaluation, log parsing (text+JSON), thread-safe aggregation, model recommender, monitor lifecycle

**Pattern:** No mocks for planner (uses real fitted_models.json); monkeypatch for monitoring (avoids psutil). Session-scoped `bundled_models` fixture. Async tests use pytest-asyncio strict mode.

## Dependencies

**Python core:** typer >=0.9, rich >=13.0
**Optional groups:**
- bench: psutil, pyyaml, httpx, platformdirs, structlog
- eval: evaluate
- refit: numpy, scipy
- dev: pytest, pytest-cov, pytest-asyncio, ruff

**Rust (demo_agent):** anyhow, serde/serde_json, clap, reqwest (json+stream), tokio (full), tracing, bytes, futures-util, chrono, csv, walkdir, criterion (dev)
**Rust (demo_multiagent):** Above + async-std, smol, hyper/hyper-util (feature-gated), once_cell

**External:** Ollama 0.6.x+, NVIDIA CUDA 11.8+ (optional pynvml for monitoring)

## Key Architecture Decisions

- **Dual Ollama for multi-agent:** Single Ollama caps at 82.2% efficiency; dual (11434/11435) enables 95-99% (TR113-114)
- **Subprocess isolation in demo_agent:** Prevents warm-cache bias; `ollama stop all` + 30s cooling between agents
- **Tokio as default Rust runtime:** Best consistency (98.72% mean, 1.21pp sigma) per TR115
- **Q4_K_M as default quantization:** Universal sweet spot across models (TR125)
- **Lookup tables over ML:** Planner uses empirical lookups + first-principles interpolation, no ML (TR133)
- **Feature-gated Rust runtimes:** 5 async runtimes compile-time selectable for benchmarking (TR115)
- **Lazy imports in CLI:** Heavy modules imported inside `plan()` to keep `chimeraforge --version` fast

## Experiments & Technical Reports

TR{number} (108-133+). Each experiment: `experiments/TR###/` with README, scripts, artifacts. Published: `outputs/publish_ready/reports/`.

**Phase 1 (TR108-TR116):** Single/multi-agent baselines, Rust vs Python, runtime selection, cross-model
**Phase 2 (TR117-TR133):** Backend benchmarking, cost, compile paradox, quantization matrix, capacity planner

**Methodology:** 3-5 runs per config, cold starts, process isolation, CV<5% target, IQR outlier detection

## Commit Message Style

```
type: short description

# Types: feat, fix, docs, chore
```

## Hardware Context

Primary test rig: RTX 4080 12GB, i9-13900HX, 64GB RAM, Windows 11.
GPU database (hardware.py): 15 GPUs — RTX 3080/3090/4060/4060Ti/4070/4070Ti/4080/4090, A100 (40/80GB), H100, L4, T4. Reference GPU: RTX 4080 12GB (bandwidth ratio baseline).
