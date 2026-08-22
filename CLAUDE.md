# CLAUDE.md — ChimeraForge

## Rule 1 -- Assertive by default

**Believe the problem is solvable and move.** The default is to solve it, not to
survey options and hand the decision back. Hesitation that stalls delivery is a
failure mode, the same as a wrong answer.

- **Decide, then report.** If a choice has a defensible best answer, take it,
  state the call and the reasoning, and keep going. Do not present a menu of
  options for something you can determine yourself.
- **Escalate only what is genuinely the user's to decide** -- irreversible or
  outward-facing actions, spending money, publishing under their name, or a
  product-direction call with no technically correct answer. Everything else is
  yours to resolve.
- **A blocker is a task, not a stop.** "That needs data I don't have" is the
  start of the work: go get the data, from the primary source, and record where
  it came from. Missing tooling gets installed; a stale figure gets re-fetched.
- **Finish the whole arc.** Build, verify, document, ship, and confirm live.
  Half-finished work handed back with questions attached is not delivery.

This does **not** license guessing. Assertive means *going and finding out*, not
asserting something unverified -- rigor is how you earn the right to be decisive.
Confidence about the process, honesty about the evidence.

## Research, data, and validation discipline

Any number that reaches a user, a report, or a bundled dataset is a research
artifact and is handled like one.

- **Primary sources only.** Fetch the vendor page, the datasheet, the paper, the
  API. Never transcribe a figure from memory -- model knowledge has a cutoff and
  prices, specs and APIs move.
- **Provenance travels with the value.** Every bundled datum records its source
  (URL or document), the date it was captured, and the method. A dataset without
  a `captured_at` and a source is not shippable.
- **Date-stamp and expire.** Snapshot data declares its age and warns when stale
  rather than presenting an old figure as current.
- **Regenerable, not hand-typed.** Bundled datasets are produced by a script in
  `scripts/` that can be re-run to refresh them, so the pipeline is auditable and
  the data is reproducible.
- **Validate before it lands.** A build script checks ranges, types, required
  fields and internal consistency, and fails loudly rather than writing a
  half-populated file.
- **Derive, then verify against ground truth.** Prefer a first-principles
  derivation over a fitted constant, and pin it to published values in a test
  (as the MoE active-parameter derivation is pinned to Mixtral / DeepSeek-V3 /
  Qwen3). A self-consistent test proves nothing.
- **Label the epistemic status.** measured / estimated / unknown, end to end. If
  a value cannot be stood behind, it is reported as unknown -- never quietly
  filled with a plausible default.
- **Current libraries and tooling.** Use the current, supported version of a
  library, API, or CLI, and check its real interface before writing against it
  rather than coding from recall. Pin what must be reproducible.

## Project Overview

ChimeraForge is an LLM inference benchmarking and deployment planning platform, broken out from the Banterhearts program. It provides quantified, reproducible answers to LLM deployment decisions, backed by ~204,000 real measurements on consumer GPUs. Ships both research artifacts (32 technical reports, TR108-TR137 + TR142/TR146) and production CLI tools (`chimeraforge plan` and `chimeraforge bench`).

**Version:** 0.23.0 | **License:** MIT | **Python:** >=3.10 | **Rust:** >=1.70

## Quick Reference

```bash
# Install (editable, all deps)
pip install -e ".[all]"

# Run capacity planner (registry size-class search)
chimeraforge plan --model-size 3b --request-rate 1.0 --hardware "RTX 4080 12GB"

# Plan ANY model (model-agnostic): Ollama tag, HF repo, or manual overrides
chimeraforge plan --model ollama:qwen2.5:7b --ollama-url http://localhost:11434
chimeraforge plan --model Qwen/Qwen2.5-1.5B-Instruct --hardware "RTX 4090 24GB"
chimeraforge plan --model my/unreleased-7b --params-b 7 --n-layers 32 --n-kv-heads 8 --d-head 128 --no-network

# Tensor parallelism: size a model too big for one GPU across several (or --tp auto)
chimeraforge plan --model meta-llama/Llama-3.3-70B-Instruct --hardware "H100 80GB" --tp 4

# Discover + rank deployable models for your hardware (Ollama install / HF Hub)
chimeraforge suggest --source ollama --hardware "RTX 4090 24GB" --budget 500
chimeraforge suggest --source hf --hf-limit 8 --hardware "RTX 4080 12GB"

# Build a local catalog of curated models, then rank it OFFLINE
chimeraforge catalog --build              # resolves seed (+ --with-ollama) to specs, caches them
chimeraforge catalog                      # list cached catalog
chimeraforge suggest --source catalog --hardware "RTX 4080 12GB"   # no network needed

# Measure-on-demand: benchmark a live model for REAL throughput+scaling, then plan on it
chimeraforge measure --model qwen3:14b --ollama-url http://localhost:11434
chimeraforge plan --model qwen3:14b --measure   # bench live first, then plan (provenance: measured)

# Export the serve command for the winning config (vllm/ollama/tgi)
chimeraforge plan --model-size 8b --hardware "RTX 4090 24GB" --launch

# Run benchmarks (requires live Ollama)
chimeraforge bench --model llama3.2-3b --runs 5

# MCP server: let Claude/GPT/Cursor call the planner (needs the `mcp` extra)
pip install -e ".[mcp]" && chimeraforge mcp   # stdio server: plan/resolve/list-hardware tools

# Run tests (1027 total; 0.6.0 adds KV-batch/prefill-decode/continuous-batching/variance/pareto/accuracy + blind-audit regressions)
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
    __init__.py                       # Exports __version__ = "0.12.0"
    cli.py                            # Typer entry point, registers plan/suggest/safety/mcp/... (lazy imports)
    commands/                         # One module per CLI command (plan.py, suggest.py, mcp.py, ...)
    mcp_server.py                     # MCP server (FastMCP): plan/resolve/list-hardware tools for Claude/GPT/Cursor
    planner/
      __init__.py                     # Re-exports Candidate, all models, load_models
      service.py                      # run_plan(): shared presentation-free planning core (CLI + MCP)
      engine.py                       # 5-gate search (4 + opt-in safety): Candidate (w/ params_b, model_source, provenance), enumerate_candidates(specs=...)
      models.py                       # 7 predict-only dataclass models; ThroughputModel.roofline_tps(), QualityModel.estimate() (provenance)
      resolver.py                     # ModelSpec + resolve_spec(): any id -> params/arch (registry/Ollama /api/show/HF config.json/manual). Model-agnostic core.
      discovery.py                    # suggest(): enumerate models from Ollama /api/tags + HF Hub, resolve, rank
      identity.py                     # parse_identity()/resolve_model(): family+param matching; _FAMILIES derived from registry
      hardware.py                     # GPUSpec dataclass (+ tdp_watts, interconnect_gbps), GPU_DB (22 GPUs), bandwidth_ratio()
      constants.py                    # QUANT_LEVELS, QUANT_BPW, BACKENDS, MODEL_PARAMS_B, MODEL_ARCH, MBU_DEFAULT
      formatter.py                    # Rich panels/tables output + JSON serialization (plan + suggest)
      launch.py                       # build_launch_command(): Candidate -> vllm/ollama/tgi serve command (0.13.0)
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
tests/                                # 34 files, 1027 tests (planner/bench split per-concern; test_accuracy falsifiability gates)
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

### Serving model (0.6.0)
The planner models LLM serving as the literature describes it, not replicas-of-single-stream:
- **Prefill vs decode:** TTFT = prefill (compute-bound, `2*params*prompt_tokens / (fp16_tflops*MFU)`); TPOT = decode (bandwidth-bound). End-to-end p95 = TTFT + decode + queueing. `GPUSpec.fp16_tflops` drives prefill; `--prompt-tokens` sets input length.
- **Continuous batching:** vLLM/TGI serve B concurrent sequences per GPU; `ThroughputModel.batched_decode_tps()` = `B*bw*MBU / (weight_eff + B*kv_per_seq)`, `weight_eff = bw*MBU/n1_tps` (anchored to measured/roofline single-stream, quant-correct), capped by `max_concurrent_seqs` (KV-bound) and the decode compute ceiling. Ollama = B=1. The engine searches **(N replicas x B batch/GPU)** for the cheapest SLO-feasible config. `BACKEND_CONTINUOUS_BATCHING`, `Candidate.effective_batch`.
- **Replicas scale linearly** (eta=1); the old Amdahl serial-fraction model was wrong for replica fan-out (capped throughput at ~1.8x; rejected >=7B) and is no longer applied.
- **Tensor parallelism (0.10.0):** `plan --tensor-parallel {N|auto}` (alias `--tp`) splits ONE model across N GPUs — weights /N, KV across heads (`VRAMModel...tp=`), so a model too big for one GPU fits (70B FP16 on 4x H100). `ThroughputModel.tp_decode_tps` gives ~Nx aggregate bandwidth minus Megatron all-reduce comms (2/layer, scaled by `GPUSpec.interconnect_gbps`): near-ideal on NVLink, erodes on PCIe/high batch. TP throughput is an **estimate** (comms modelled, not measured — warns; `INTERCONNECT_EFFICIENCY` calibratable). Fleet = N replicas x TP GPUs (cost/energy scale with `gpus_total`); `auto` = smallest TP that fits. `tp=1` reproduces pre-0.10.0 exactly.
- **Pipeline parallelism (0.11.0):** `plan --pipeline-parallel {N|auto}` (alias `--pp`) splits a model's *layers* into N stages (`VRAMModel...pp=`) — weights + each stage's KV /N with **no head cap** (scales past `n_kv_heads`, unlike TP). `ThroughputModel.pp_decode_tps`: ~Nx bandwidth, only a small point-to-point activation pass (no all-reduce) so **barely degrades on PCIe where TP collapses** — but the GPipe **pipeline bubble** (`batch/(batch+pp-1)`) means PP needs batching (poor at batch 1, warns when under-filled). Estimate (bubble modelled). **TP and PP can't combine yet** (errors); `auto`=smallest PP that fits (may need higher for throughput); `pp=1` reproduces pre-0.11.0 exactly.
- **Mixture-of-Experts (0.14.0):** MoE splits the param count in two and each is correct in a different place -- **VRAM/concurrency use TOTAL** (every expert resident), **decode roofline + compute ceiling + prefill/TTFT use ACTIVE** (`ModelSpec.active_params_b`). Active is derived by *subtracting the routed experts a token does not select* (`n_moe_layers * (num_experts - experts_per_token) * MOE_EXPERT_MATRICES * hidden * moe_intermediate`), so attention/embeddings/shared-experts never need modelling. Matches published counts (Mixtral 12.9B exact, DS-V3 37.5 vs 37, Qwen3-A3B 3.32 vs 3.3). Resolver reads per-family config keys (`num_local_experts`/`n_routed_experts`/`num_experts`, `first_k_dense_replace`). **Incomplete geometry falls back to TOTAL** -- a guess would inflate throughput, so dense is the honest default. Expert parallelism + routing imbalance NOT modelled (warns). Dense models are byte-identical to 0.13.0.
- **Format gating + FP8 (0.15.0):** `BACKEND_QUANT_FAMILIES` / `backend_supports_quant()` restrict each backend to formats it serves -- **GGUF -> ollama only**, **float+FP8 -> vllm/tgi**. Before this the engine offered every GGUF level on every backend and priced it with a llama.cpp-measured multiplier (the corpus only ever measured FP16 on vllm/tgi). `FP8` = exact 8.0 bpw; its throughput multiplier comes from the existing nearest-bpw fallback (lands on Q8_0's 1.3x) rather than an invented constant; quality resolves via the FP16-baseline path as **estimated** (absent from the TR corpus), and it is **unscreened for safety** so `--safety-target` passes it warned per the lookup-only policy. `GPUSpec.fp8_supported` gates FP8 to Ada/Hopper/Blackwell/CDNA3 (`NO_FP8_GPUS` marks Ampere/Turing). Rejections land in the trace (`gate="format"`).
- **Attention cache shape (0.18.0):** KV sizing uses the model's real shape, not always GQA. `ModelSpec.kv_elems_per_token_per_layer` returns `kv_lora_rank + qk_rope_head_dim` for **MLA** (DeepSeek-V2/V3 = 576 vs GQA's 32,768 -- a 57x overstatement) else `2*n_kv_heads*d_head`. **SWA** caps local layers at `sliding_window` with 1 full-attention layer every `swa_global_every`, giving a layer-weighted effective context. `arch()` only advertises the window when the pattern is ALSO known -- an unplaceable window would shrink the estimate, and under-sizing KV claims a fit that isn't there (Mistral: window, no pattern -> full context). Dense/bare-arch-dict/legacy-cache paths byte-identical.
- **Variance-aware queueing:** two-moment wait `(1+Cs^2)/2 * M/M/1` (`Cs^2=0` reproduces M/D/1). `--workload {steady,chatbot,bursty,agent}` -> `WORKLOAD_CV2`; high variance inflates the tail + warns (analytical queueing silently approves broken fleets for agent traffic otherwise).
- **Pareto output:** `plan --pareto` -> `pareto_frontier()` (non-dominated on cost/p95/quality), the trade-off menu instead of one cost-sorted pick.
- **Cost:** `cost_per_1m_tok` uses N-GPU cost with N-GPU throughput (invariant in replica count).
- Numerical accuracy gates in `tests/test_accuracy.py` pin predictions to ground truth.

The `chimeraforge plan` CLI runs a 4-gate exhaustive search (plus an opt-in 5th safety gate) over (model x quant x backend x N_agents):

**Gate 1 — VRAM:** `weight_gb + kv_cache_gb + activations_gb <= hw_vram`
- Weight: `params_B * bits_per_weight / 8 * overhead_factor`
- KV-cache: `2 * n_layers * batch * context * n_kv_heads * d_head * kv_bytes`
- **KV-quant (0.9.0):** `plan --kv-quant {fp16,q8,q4}` sets `kv_bytes` (2/1/0.5 via `KV_QUANT_BYTES`), shrinking KV VRAM and lifting `max_concurrent_seqs` — biggest at long context. VRAM/concurrency only; KV-quant's quality impact is unscreened (warns). `kv_bytes` defaults to FP16, so pre-0.9.0 results are byte-identical.

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
- **Energy (0.8.0):** `GPUSpec.tdp_watts` drives a *separate* energy dimension — monthly kWh cost, `$/1M-tok (+energy)`, and `tok/s per watt` (`--electricity-rate`, default `DEFAULT_ELECTRICITY_RATE`; draw = `tdp_watts * POWER_UTILISATION`). Reported alongside, **not summed into**, `monthly_cost`/the budget gate: cloud `$/hr` already bundles power (double-count) while amortised consumer cost does not. `perf_per_watt` and per-token energy are replica-invariant.

**Gate 5 — Safety (opt-in):** `refusal_rate >= safety_target` (only when `--safety-target` is set)
- Lookup table (model|quant) of TR134 refusal rate + TR142 RTSI risk tier; GGUF quants only
- Lookup-only: unknown cells pass with a "not screened" warning (no extrapolation — TR142/TR146)
- Evaluated before the backend/N loop (safety is backend-independent in this data)
- Refusal is non-monotonic in quant (e.g. llama3.2-3b Q4_K_M < Q2_K) — the gate follows the data
- Regenerate the bundled `safety` block via `scripts/build_safety_data.py`

Results sorted by (cost asc, quality desc). Output: Rich panels + alternatives table, or JSON.

### Model-Agnostic Resolution (resolver.py / discovery.py)

The planner is no longer limited to the 7 bundled registry models. `plan --model <id>` and `suggest` accept arbitrary identifiers and resolve real params/architecture:

- **`ModelSpec`** (resolver.py): `params_b, n_layers, n_kv_heads, d_head, hidden_size, native_quant, family, source, registry_alias`. `resolve_spec()` tries sources in priority order: manual overrides → exact registry → on-disk cache (`~/.cache/chimeraforge/specs`, override `$CHIMERAFORGE_CACHE`) → Ollama `POST /api/show` (GGUF metadata) → HF `config.json` + `?expand[]=safetensors` param count → offline family/size approximation.
- **Routing:** slashed `org/name` → HF; `ollama:`-prefixed or colon-tag or `--ollama-url` set → Ollama (falls back to approximation if the live fetch fails); else registry/approx. HF is checked before Ollama so a repo is never sent to `/api/show`.
- **VRAM** is exact for any model (real arch drives weight + KV-cache). **Throughput** for genuinely off-registry models uses `ThroughputModel.roofline_tps()` — memory-bandwidth-bound decode `MBU * bandwidth / (2*params_GB) * quant_mult`, `MBU_DEFAULT=0.65` calibrated to the llama3.2-1b ollama FP16 datapoint (146 tok/s). **Quality** uses `QualityModel.estimate()` → measured (lookup) / estimated (fp16 baseline+delta or family prior) / unknown (0.5). **Safety** stays lookup-only (UNKNOWN off-registry — TR142/TR146).
- **`registry_alias`:** an offline approximation (e.g. `llama3.2:3b`) reuses the matched registry model's *measured* throughput/quality/safety rather than roofline; genuinely off-registry models (Ollama/HF/manual) do not.
- **Provenance:** every `Candidate` carries `params_b`, `model_source`, and a `provenance` dict (`vram/throughput/quality/safety` ∈ measured|estimated|unknown), surfaced in output (`~` = estimated) and as honest warnings. Never presents a roofline guess as measured.
- **Native quant pinning:** a fully-specified tag (`...:q8_0`) is evaluated only at that quant, not the whole quant ladder.
- **`suggest`** (discovery.py): pulls candidates from Ollama `/api/tags` (installed) and/or HF Hub (top text-generation by downloads) and/or the local catalog, resolves each, runs the gate search, shows the best config per model. `--source ollama,hf,catalog` (comma-sep).
- **Live catalog** (discovery.py + `catalog` command): `catalog --build` resolves a bundled curated seed (`data/model_catalog.json`, ~10 models spanning 0.36B-14.8B) plus optionally installed Ollama models, persists specs to `~/.cache/chimeraforge/catalog.json`. `suggest --source catalog` then ranks them **fully offline** (verified through a dead proxy). `catalog` (no flag) lists the cached set.
- **Measure-on-demand (the empirical loop, not guessing):** `measure` (chimeraforge/measure.py) and `plan --measure` benchmark a live model via the existing `bench` machinery — real N=1 throughput + service time, plus concurrency scaling at N agents → serial fraction via `serial_fraction_from_eta()` (inverts the Amdahl model) — then fold it into a local `fitted_models.json` through `refit_from_bench`. `load_effective_models()` makes `plan`/`suggest` prefer that measured corpus (path: `~/.cache/chimeraforge/fitted_models.json`) over bundled data automatically, so provenance flips to genuinely **measured**. Verified: roofline estimated 195.8 tok/s for llama3.2:1b-q8_0, measured was 174.5 (~12% high) — the guess was real but biased; measurement corrects it. Quality is deliberately NOT synthesised (the planner's quality scale is a TR benchmark composite; a quick text-similarity run is a different metric) — it stays labeled `estimated` with a note.
- **Rejection diagnostics:** `enumerate_candidates(trace=[...])` records `(model, quant, gate, detail)` for every rejected cell; `summarize_trace()` reports the *binding* gate per model. `plan` shows "Why nothing fit" on a 0-result instead of a generic message.
- **Optional dep:** network resolution needs `httpx` (the `resolve` extra); a clear error points there if missing. HF returns 401 for both gated AND nonexistent repos — the `X-Error-Code: GatedRepo` header disambiguates them.

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
pytest tests/ -v                    # 1027 total tests
pytest tests/ --cov=src             # With coverage
```

**Layout** (1027 tests, 34 files -- planner/bench split per-concern after 0.3.0):

- **Planner** (196): test_planner_models.py (76 - 7 predictive models: VRAM (+KV-quant +TP +PP)/
  throughput (+TP comms)/quality/latency/scaling/cost+energy/safety, incl. roofline +
  KV-batch concurrency + shared FP16-baseline resolver), test_planner_engine.py (67 - gate
  search, N-replica x B-batch, Pareto, variance guard, provenance, energy, KV-quant, TP, PP),
  test_planner_cli.py (18), test_planner_core.py (22 - serialization, find_models_for_size,
  GPU_DB + TDP + interconnect coverage), test_accuracy.py (13 - numerical falsifiability gates)
- **Model-agnostic** (53): test_resolver.py (35 - ModelSpec, registry/Ollama/HF/manual +
  cache + newer-family recognition), test_discovery.py (12 - suggest/catalog),
  test_measure.py (6 - measure-on-demand)
- **Safety** (54): test_safety.py - refusal lookup, RTSI tiers, identity resolution
- **Bench** (70): test_bench_metrics.py (28), test_bench_backends.py (20 - Ollama/vLLM/TGI),
  test_bench_runner.py (17 - runner, sweeps, resilience), test_bench_cli.py (5)
- **Refit/Eval/Report/Compare** (141): test_refit.py (47 - Bayesian blend + per-key
  weighting + validation), test_eval.py (42), test_report.py (32), test_compare.py (20)
- **Launch export** (27): test_launch.py - per-backend derived flags (context/TP/PP/batch/
  KV dtype), placeholder+note on id-source mismatch, `--json --launch` wrapper contract
- **MoE** (23): test_moe.py - active-param derivation vs PUBLISHED counts (Mixtral/
  DeepSeek-V3/Qwen3-A3B), per-family config keys, dense unaffected, degrade-to-total
  on incomplete geometry, engine uses total for VRAM + active for throughput/TTFT
- **FP8 / format gating** (36): test_fp8.py - FP8 bpw+ladder, per-backend format
  families (GGUF=ollama, float+fp8=vllm/tgi), FP8 tensor-core hardware gate,
  rejection reasons, estimated-not-measured quality, launch flags
- **Reasoning tokens** (13): test_reasoning_tokens.py - hidden-token decode
  accounting, peak-sequence guard, default-off, CLI/MCP surfaces, negative clamp
- **API cost / break-even** (28): test_apicost.py - hand-checked arithmetic, the
  at-breakeven-costs-are-equal property, staleness (incl. undated = stale),
  bundled-snapshot provenance, open-vs-frontier labeling, CLI + JSON contract
- **Attention shapes** (26): test_attention_shapes.py - MLA latent width vs GQA,
  SWA layer-weighted context, conservative when the window pattern is unknown,
  dense/legacy unchanged, engine warnings, concurrency ceiling 20 -> 503
- **Prefix cache** (22): test_prefix_cache.py - uncached-remainder prefill, TTFT
  linearity, default-off, KV deliberately NOT discounted, clamping, CLI/MCP
- **Cost realism** (26): test_cost_realism.py - duty-cycle effective cost vs
  at-capacity, price multiplier scales bill not physics, clamping, API-compare
  scaling, CLI/MCP surfaces
- **GitHub Action** (28): test_gha_plan_comment.py - argv build, both --json
  payload shapes, empty-plan message, bounded warnings, sticky-comment
  metadata, GITHUB_OUTPUT heredoc for multi-line values
- **Validation audit** (43): test_validate.py - matrix schema, fingerprint moves
  on any cell edit (anti-cherry-pick), provenance classing, MAPE does not cancel,
  worst cell survives aggregation, underpowered rows labeled, CLI offline scoring
- **SGLang** (17): test_sglang.py - registration, and the negative property that
  an unmeasured backend never inherits a measured one's rows
- **Goodput SLOs** (18): test_goodput.py - TTFT/TPOT gated separately inside the
  (N x B) search, actionable rejection reasons, point-estimate-not-attainment
- **CPU offload** (16): test_offload.py - priced instead of refused, bandwidth-
  driven derate, still refuses when KV alone busts VRAM
- **Repo conventions** (131): test_repo_conventions.py - per-file ASCII-only guard
  (parametrized over every src/ + tests/ .py) and server.json/pyproject/__version__
  sync + registry description limit + README mcp-name token
- **CLI hardening** (18): test_cli_fail_loud.py - clean errors + exit codes, no raw tracebacks
- **Monitoring** (5): test_monitoring.py - SLO eval, log parsing, thread-safe aggregation,
  recommender, monitor lifecycle
- **MCP/service** (12): test_mcp.py - run_plan shared core + MCP tool layer
  (plan/resolve/list-hardware, actionable errors); build_server guarded by importorskip

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
- **MCP server (0.12.0):** `chimeraforge mcp` (stdio; `mcp` extra) exposes plan/resolve/list-hardware to Claude/GPT/Cursor. Tool logic in `mcp_server.py` is plain + unit-testable (no `mcp` import); it calls the shared `planner/service.py:run_plan` core in-process (same path as the CLI), so CLI and MCP never diverge. Tool descriptions tell the model to prefer the tool over its parametric guess; results surface `provenance`. `plan --json` now emits `{"error": ...}` on failures (was Rich text)

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
GPU database (hardware.py): 22 GPUs — RTX 3080/3090/4060/4060Ti/4070/4070Ti/4080/4090, RTX 5070/5070Ti/5080/5090 (Blackwell), A100 (40/80GB), H100, H200, B200, L4, T4, and AMD MI300X. Reference GPU: RTX 4080 12GB (bandwidth ratio baseline).

---

## Engineering Standards (chimera-wide)

> **Canonical source:** `Banterpacks/CLAUDE.md`. This block is propagated verbatim to every
> chimera-ecosystem repo — Banterpacks, Banterhearts, Chimera_Multi_agent (Muse), Chimeraforge,
> Echo, jarvis-console, Banterblogs, Chimeradroid. Edit it in Banterpacks and re-propagate; don't fork it per-repo.

**The bar — all repos, all languages:**

- **Build it right or don't build it.** Tech debt by choice is a discipline failure, not pragmatism. "Fine for now" / "fix later" is rejected.
- **No toy/stub code when production is asked.** Hash-encodings standing in for models, unwired controllers, empty eval gates, placeholder returns — unacceptable. Verify end-to-end with real data, or explicitly flag it as scaffold.
- **Functional, not ceremonial.** Every system must *do* something real. Rubber-stamp consensus, keyword-matching "AI", orphan telemetry = ceremony. Advisory-only enforcement is not enforcement — make the gate real or don't ship it.
- **TDD.** Tests first (red → green → refactor), defining behavior — not retrofitted to match output. New behavior ships with a test.
- **Honesty over optimism.** Report outcomes faithfully: failing tests stated with their actual output; "done" only when verified end-to-end; "I don't know, need to check X" beats a plausible guess. Distinguish observed / inferred / guessed; read the artifact before claiming a root cause.
- **No silent failures.** Every `catch`/`except` logs with context; no bare swallow-and-continue.
- **Named constants.** No magic numbers — thresholds, timeouts, and parameters are named, with rationale.
- **Terse inline comments.** Comments say what's non-obvious; the *why* and the patch/arc history go in commit messages / patch notes, not verbose source docstrings.
- **No cross-repo filesystem coupling.** Inter-service comms are HTTP + pinned contracts (OpenAPI / JSON schema), never `../SiblingRepo` imports.
- **Secrets & config through one typed boundary.** Never commit secrets; read config/secrets via the service's settings layer, not scattered raw env reads in leaf modules.
- **Verify, don't trust "done".** Re-check claims (yours or an agent's) against real output before reporting complete.
- **Git hygiene.** Conventional commits (`type(scope): subject`). **Never** add `Co-Authored-By` or any AI-authorship trailer. Batch pushes (one per repo per batch). For repos whose `main` is a live deploy, keep unpolished/audience-facing WIP on a branch — docs/internal changes to main are fine.
- **Anthropic model lineup (current as of 2026-07).** When pinning Claude models in code, configs, or agents, use bare aliases from the current family: `claude-opus-4-8` (default for coding/agentic work), `claude-sonnet-5` (balanced), `claude-haiku-4-5` (fast/cheap judges & bulk work), `claude-fable-5` (only when explicitly chosen - premium pricing, always-on thinking). Never date-suffix aliases; never pin retired `claude-3-*`/`claude-2*` IDs (they 404). Claude 4.6+ API rules: adaptive thinking (`{"type": "adaptive"}`, no `budget_tokens`); never send `temperature` + `top_p` together (Opus 4.7+/Sonnet 5/Fable reject sampling params entirely); no assistant prefill (use `output_config.format`); system prompts go in the top-level `system` param. Agent tiering: main thread on the strongest available model (Fable 5 / Opus-tier); delegate mechanical, self-contained subtasks to Sonnet/Haiku subagents.

**Per-language specifics:**

| Lang | Rules |
|------|-------|
| **Python** | PEP 8, type hints, docstrings, 120-col (`.flake8`); `ruff` + `black` + `mypy` clean; no god files (~1000-line file / ~300-line fn ceiling); pre-compiled regex on hot paths; no raw `os.getenv` in app code — go through the settings boundary. |
| **Rust** | `cargo fmt` + `cargo clippy` clean; split handlers/modules (no god `main.rs`); typed config (figment); `SecretString` for secrets. |
| **TypeScript / Next.js** | `strict` TS (no leaked `any`), ESLint + Prettier clean; no secrets in client bundles; separate components from state/data logic. |
| **C# / Unity** | Standard C# conventions + analyzers; no magic numbers; keep `MonoBehaviour` thin — delegate logic to testable plain-C# services. |

**Before calling it done:** run the repo's verify gate (`npm run verify` / `pytest` / `cargo test` / `npm run lint`), paste the real output, fix, re-run.
