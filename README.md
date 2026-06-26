# Chimeraforge

[![PyPI version](https://img.shields.io/pypi/v/chimeraforge.svg)](https://pypi.org/project/chimeraforge/)
[![Python](https://img.shields.io/pypi/pyversions/chimeraforge.svg)](https://pypi.org/project/chimeraforge/)
[![CI](https://github.com/Sahil170595/Chimeraforge/actions/workflows/ci.yml/badge.svg)](https://github.com/Sahil170595/Chimeraforge/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**~204,000 primary measurements. 32 technical reports. One consumer GPU. A CLI that plans LLM deployments on performance, cost — and safety.**

```bash
pip install chimeraforge
```

This repository contains everything behind Technical Reports TR108 through TR137 (plus the TR142/TR146 safety provenance) -- source code, benchmark harnesses, datasets, logs, publish-ready technical reports, and the `chimeraforge` CLI that operationalizes the findings into deployment decisions. Every performance claim is backed by reproducible benchmarks, every number traces to raw data, and every finding is documented with full methodology.

> **New in v0.5.0 — model-agnostic planning.** `plan --model <id>` now plans *any* model —
> a registry name, an Ollama tag, or a Hugging Face repo — by resolving its real parameters
> and architecture (Ollama `/api/show`, HF `config.json`). New commands: **`suggest`** (discover
> and rank deployable models from your Ollama install / the HF Hub), **`catalog`** (a curated,
> offline-rankable model set), and **`measure`** (benchmark a live model and plan on the *measured*
> numbers, not estimates). Also fixes two planner correctness bugs: throughput now scales linearly
> across GPU replicas (was capped at ~1.8×, rejecting models ≥7B) and `cost_per_1m_tok` is no longer
> understated by the instance count. See the [CHANGELOG](CHANGELOG.md).

---

## What This Repository Is About

Chimeraforge is the research and benchmarking breakout from the Banterhearts program. It contains every asset required to measure LLM inference performance, run the TR-series test plans, publish the technical reports, and ship the predictive capacity planner. This repo stays focused on measurement, analysis, and deployment tooling.

> **Program context:** the parent Banterhearts program now spans **~1,337,000 primary + judge measurements across 54 technical reports** (as of 2026-06-23) — including the safety attack-surface and serving-stack research that lives in dedicated sibling repos. **ChimeraForge is the actionable splice of that program**: the ~204,000-measurement subset (TR108–137 + the TR142/TR146 safety provenance) distilled into a shipping CLI for deployment decisions.

The research program spans three completed phases:

- **Phase 1 (TR108-TR122):** Language comparison (Python vs Rust), multi-agent concurrency, backend benchmarking, cost/energy economics, scaling laws. 8,000+ runs.
- **Phase 2 (TR123-TR133):** KV-cache economics, quality baselines, quantization decision matrix, compile paradox resolution, context scaling, production workloads, N-agent scaling, serving stack comparison, GPU kernel profiling, and predictive capacity planning. ~106,000 measurements.
- **Phase 3 (TR134-TR137):** Safety alignment under inference optimization — alignment robustness under quantization, safety under multi-agent concurrency, cross-backend consistency, and the "safety tax" synthesis. Operationalized in v0.3.0 as the planner's opt-in safety gate (backed by TR142 RTSI + TR146 mechanistic findings).

Through **~204,000 primary measurements** across 32 technical reports, we've answered the core deployment questions: which backend, which quantization level, which serving stack, how many agents, what context budget, how to plan capacity, and how to operationalize evaluation on a single consumer GPU (RTX 4080 Laptop, 12 GB VRAM).

---

## Why Chimeraforge Exists

### For Decision Makers (CTOs, Engineering Leads, Product Managers)

**The Problem:** Choosing between Python and Rust for LLM agents is often a gut-feel decision. "Rust is faster" or "Python is easier" are common refrains, but what does "faster" actually mean? How much faster? Under what conditions? What are the trade-offs?

**The Solution:** This repository provides **quantified, reproducible answers** to these questions. Every performance claim includes:
- The exact hardware and software configuration used
- The methodology for measurement
- Raw data you can inspect and verify
- Statistical analysis showing confidence levels

**The Value:** Make informed decisions based on data, not assumptions. Understand when Rust's performance gains justify its development overhead. Know when Python's velocity is the right trade-off.

### For Engineers

**The Problem:** You need to optimize LLM agent performance, but configuration space is vast. GPU layer allocation, context window size, temperature settings, runtime choices — each affects performance differently. What's optimal for single-agent might not work for multi-agent. What works in Python might not translate to Rust.

**The Solution:** This repository provides:
- **Proven optimal configurations** for different scenarios
- **Reproducible benchmark harnesses** you can run yourself
- **Analysis tools** for understanding your own results
- **Source code** showing exactly how optimizations are implemented

**The Value:** Skip the trial-and-error phase. Start with configurations that are known to work, then customize based on your specific needs.

### For Researchers

**The Problem:** LLM performance research often lacks reproducibility. Papers cite numbers without providing code. Benchmarks use different hardware, different models, different methodologies. Comparing results across studies is difficult.

**The Solution:** This repository provides:
- **Complete methodology documentation** for every experiment
- **Raw data** in structured formats (CSV, JSON)
- **Reproducible code** that runs the exact same benchmarks
- **Statistical analysis** with confidence intervals and variance measures

**The Value:** Build on solid foundations. Reproduce our results, extend our analysis, or use our methodology for your own research.

---

## Quick Takeaways: What We Discovered

All findings below are verified against the TR108-TR137 corpus, spanning roughly 204,000 primary measurements across Phase 1, Phase 2, and Phase 3. Every number is reproducible and traceable to raw data.

### Single-Agent Performance: Rust vs Python

| Metric | What It Means | Python | Rust | Winner | Why It Matters |
|--------|---------------|--------|------|--------|----------------|
| **Throughput** | How fast the agent generates text (tokens per second) | 99.34 tok/s | 114.54 tok/s | 🏆 Rust (+15.2%) | Higher throughput = more work done per second. For high-volume systems, 15% faster means 15% more capacity or 15% lower costs. |
| **TTFT (Time to First Token)** | How long until the agent starts responding (milliseconds) | 1,437 ms | 603 ms | 🏆 Rust (-58%) | Lower latency = better user experience. Users perceive 58% faster response time as significantly more responsive. |
| **Memory Usage** | How much RAM the agent consumes | ~250 MB | ~75 MB | 🏆 Rust (-67%) | Less memory = more agents per server, lower infrastructure costs, better resource utilization. |
| **Startup Time** | How long until the agent is ready to work | 1.5 seconds | 0.2 seconds | 🏆 Rust (-83%) | Faster startup = better for serverless, containers, and auto-scaling scenarios. |
| **Consistency (CV)** | How much performance varies between runs (lower is better) | 4.8% | 2.6% | 🏆 Rust (-46%) | More consistent = more predictable = easier to plan capacity and set SLAs. |

**Source:** Technical Report 112_v2 (111 benchmark runs, 37 configurations)

**Bottom Line:** For single-agent workloads, Rust is faster, uses less memory, starts faster, and is more consistent. The performance advantage is substantial and consistent across all metrics.

### Multi-Agent Performance: Concurrent Execution

When running multiple agents simultaneously, the question becomes: **Can we achieve near-perfect parallelism, or does coordination overhead eat into the gains?**

| Scenario | What It Means | Python Result | Rust Result | Winner | Why It Matters |
|----------|---------------|---------------|-------------|--------|----------------|
| **Peak Efficiency** | Best-case parallel efficiency (how close to 2x speedup with 2 agents) | 99.25% | 99.396% | 🏆 Rust (+0.15pp) | Near-perfect parallelism means you can double capacity with <1% overhead. Both languages achieve this, but Rust edges ahead. |
| **Mean Efficiency** | Average efficiency across all configurations | 95.8% | 98.281% | 🏆 Rust (+2.48pp) | Higher mean = more reliable performance across different workloads. Rust's advantage is more pronounced in average scenarios. |
| **Contention Rate** | How often agents compete for resources (lower is better) | 10-15% | 0.74% | 🏆 Rust (20x better) | Lower contention = more predictable performance, fewer slowdowns, better resource utilization. |

**Critical Requirement:** Both languages require **dual Ollama instances** (separate LLM servers on different ports) to achieve these results. Using a single Ollama instance caps Rust at 82.2% efficiency due to server-level serialization.

**Sources:** 
- Python: Technical Report 110 (150 benchmark runs, 30 configurations)
- Rust: Technical Report 114_v2 (135 benchmark runs, 27 configurations)

**Bottom Line:** For multi-agent workloads, both languages can achieve near-perfect parallelism, but Rust maintains a slight edge in consistency and contention handling.

### Optimization Success Rates

Not all configuration changes improve performance. Some make it worse. The question is: **How often do optimizations actually help?**

| Language | Success Rate | What It Means |
|----------|--------------|---------------|
| **Rust** | 72.2% of configs beat baseline | When you try a new configuration, there's a 72% chance it will improve performance. This makes optimization more predictable and reliable. |
| **Python** | 38.9% of configs beat baseline | When you try a new configuration, there's only a 39% chance it will help. More trial-and-error required, but when it works, gains can be larger. |

**Sources:** Technical Report 109 (Python) and Technical Report 111_v2 (Rust)

**Bottom Line:** Rust's optimization is more reliable (higher success rate), but Python occasionally achieves larger peak improvements when optimization works. Rust is better for predictable, incremental gains. Python is better for exploratory optimization where you're willing to try many configurations.

### Runtime Choice (Rust Only)

Rust supports multiple async runtimes (Tokio, async-std, smol). **Which one should you use for production?**

| Runtime | Peak Efficiency | Mean Efficiency | Consistency (σ) | Recommendation |
|---------|----------------|-----------------|-----------------|----------------|
| **Tokio-default** | 99.89% | 98.72% | 1.21pp | 🏆 **Recommended for production** - Best consistency, reliable performance |
| **Smol-1KB** | 99.94% | 98.61% | 1.32pp | ✅ **Alternative** - Slightly smaller binary, nearly as consistent |
| **Tokio-localset** | 99.99% | 97.95% | 4.03pp | ⚠️ **Avoid** - Highest peak but too variable (unpredictable) |
| **Smol** | 99.87% | 97.72% | 4.87pp | ❌ **Avoid** - Pathological failures (drops to 72.8% in some cases) |
| **Async-std** | 50.00% | 50.00% | N/A | ❌ **Unusable** - Perfect serialization (no parallelism) due to ecosystem conflicts |

**Source:** Technical Report 115_v2 (150 benchmark runs, 5 runtimes, 6 configurations each)

**Bottom Line:** Use **Tokio-default** for production. It's the most consistent and reliable. All working runtimes achieve ~100% peak efficiency, so consistency matters more than peak performance.

### Cross-Model Benchmarks (TR116)

**Question:** Does model choice (Gemma, Llama, Qwen) impact multi-agent coordination efficiency?

| Model | Rust Efficiency | Python Efficiency | Verdict |
|-------|----------------|-------------------|---------|
| **Gemma 3** | **99.2%** | 84.9% | 🏆 **Best Scaling** |
| **Llama 3.1** | 98.5% | 85.8% | ✅ Excellent |
| **Qwen 2.5** | 90.0% | 77.6% | ⚠️ Throughput Imbalance |

**Key Findings:**
1. **Rust Dominates:** Rust is **+12-17pp more efficient** than Python across ALL models.
2. **Gemma 3 is King:** Achieves near-perfect 99.2% efficiency in Rust.
3. **Qwen Issues:** Throughput imbalance (+12 tok/s delta) hurts efficiency in both languages.
4. **Python Ceiling:** Python never exceeds 86% efficiency, regardless of model.

### Phase 2: Deployment Decisions (TR123-TR133)

Phase 2 produces a complete, artifact-backed deployment framework from ~106,000 measurements:

| Decision | Recommendation | Evidence |
|----------|---------------|----------|
| **Single-agent backend** | Ollama Q4_K_M | Highest throughput/dollar; quality within -4.1pp (TR123-TR125) |
| **Multi-agent backend (N>=4)** | vLLM FP16 | 2.25x advantage from continuous batching (TR130-TR132) |
| **Compile policy** | Prefill only, Linux, Inductor+Triton | 24-60% speedup; decode crashes 100% (TR126) |
| **Quantization** | Q4_K_M default; Q8_0 quality-critical; never Q2_K | Universal sweet spot across 5 models (TR125) |
| **Context budget** | Ollama for >4K tokens on 12 GB | VRAM spillover = 25-105x cliffs (TR127) |
| **Capacity planning** | `chimeraforge plan` | Validated R²>=0.859; beats M/D/1 by 20.4x (TR133) |
| **Safety screening** | `plan --safety-target` (opt-in) | Refusal-rate + RTSI risk per config; rejects safety-collapsing cells (TR134/TR142) |

### `chimeraforge` CLI — 10 Commands, One Tool

Install from PyPI and get all 10 commands:

```bash
pip install chimeraforge            # Core (plan only)
pip install chimeraforge[resolve]   # + model-agnostic resolution (Ollama/HF metadata)
pip install chimeraforge[bench]     # + live benchmarking
pip install chimeraforge[eval]      # + quality evaluation (BERTScore, ROUGE)
pip install chimeraforge[safety]    # + live refusal screen
pip install chimeraforge[refit]     # + coefficient refitting (numpy, scipy)
pip install chimeraforge[all]       # Everything including dev tools
```

#### `chimeraforge plan` — Predictive Capacity Planner

```bash
chimeraforge plan --model-size 8b --hardware "RTX 4090 24GB" --request-rate 2.0
chimeraforge plan --model Qwen/Qwen2.5-7B-Instruct --hardware "RTX 4090 24GB"   # any HF repo
chimeraforge plan --model ollama:qwen3:14b --ollama-url http://localhost:11434  # any Ollama tag
chimeraforge plan --model qwen3:14b --measure                                   # bench live, plan on real numbers
chimeraforge plan --model-size 3b --safety-target 0.85
chimeraforge plan --model-size 3b --json
```

- Plans **any** model: registry size class, HF repo (`org/name`), Ollama tag, or manual overrides
- Searches (model x quantization x backend x N-instances) space in <1 second
- 5-gate pipeline: VRAM -> quality -> safety (opt-in) -> latency -> budget
- Per-prediction provenance (`measured` / `estimated` / `unknown`); explains the binding gate when nothing fits
- Validated on registry data: VRAM R^2=0.968, throughput R^2=0.859, quality RMSE=0.062, latency MAPE=1.05%
- No ML needed -- empirical lookup tables with first-principles interpolation (roofline for off-registry)

#### `chimeraforge suggest` — Discover & Rank Models

```bash
chimeraforge suggest --source ollama --hardware "RTX 4090 24GB" --budget 500
chimeraforge suggest --source hf --hf-limit 8 --hardware "RTX 4080 12GB"
chimeraforge suggest --source catalog --hardware "RTX 4080 12GB"   # offline, after `catalog --build`
```

- Pulls candidate models from a live Ollama (`/api/tags`), the HF Hub (top text-generation), and/or the local catalog
- Resolves each to real params/arch, runs the same gate search, and shows the best config per model

#### `chimeraforge measure` — Benchmark Live, Plan on Real Numbers

```bash
chimeraforge measure --model qwen3:14b --ollama-url http://localhost:11434
chimeraforge plan --model qwen3:14b --measure   # measure then plan in one step
```

- Benchmarks the live model (real N=1 throughput, service time, concurrency scaling) and folds it into a local corpus
- `plan` / `suggest` then prefer the measured numbers automatically (provenance flips to `measured`)

#### `chimeraforge catalog` — Local Model Catalog

```bash
chimeraforge catalog --build         # resolve a curated seed (+ --with-ollama) and cache specs
chimeraforge catalog                 # list the cached catalog
```

- Persists resolved specs so `suggest --source catalog` ranks a known-good set fully offline

#### `chimeraforge safety` — Live Refusal Screen

```bash
chimeraforge safety --model llama3.2-3b --prompts harmful.txt --quant Q4_K_M --safety-target 0.85
chimeraforge safety --model llama3.2-3b --prompts harmful.txt --json
```

- Where `plan --safety-target` *decides* from bundled TR134/TR142 data, `safety` *measures*: it runs your probe prompts against a live model, classifies refusals (rule-based — the TR134 regex baseline), and reports the measured refusal rate.
- Compares to the bundled gate data — expected refusal, drift, and RTSI risk tier. Ollama tags (`llama3.2:1b-instruct-q2_K`) resolve to the registry model by architecture-family + parameter count, so the comparison works against live backend tags.
- Exits 1 if the measured refusal rate falls below `--safety-target`.
- **You provide the prompts** (`--prompts`, one per line); no attack corpus ships with the package. Point it at HarmBench / AdvBench / your own set.
- Needs `chimeraforge[safety]` + a running backend (Ollama; vLLM/TGI not yet).

#### `chimeraforge bench` — Live Inference Benchmarking

```bash
chimeraforge bench --model llama3.2-3b --runs 5
chimeraforge bench --model llama3.2-3b --all-quants --json
chimeraforge bench --model llama3.2-3b --context 512,1024,2048,4096
chimeraforge bench --model llama3.2-3b --workload server --rate 2.0
chimeraforge bench --model llama3.2-3b --backend vllm --base-url http://localhost:8000
```

- Three workload profiles: single (sequential), batch (concurrent), server (Poisson arrivals)
- Measures throughput (tok/s), TTFT, latency with p50/p90/p95/p99 percentiles
- CV-based stability detection with automatic warnings
- JSON output for programmatic consumption

#### `chimeraforge eval` — Quality Evaluation

```bash
chimeraforge eval --task general_knowledge --json
chimeraforge eval --predictions preds.txt --references refs.txt --model llama3.2-3b
chimeraforge eval --list-tasks
```

- Metrics: exact match, ROUGE-L (with LCS fallback), BERTScore, coherence
- Composite scoring: 0.2*EM + 0.3*ROUGE + 0.3*BERT + 0.2*coherence
- Quality tiers from TR125: negligible (>=-3pp), acceptable (>=-10pp), concerning, unacceptable
- 3 built-in tasks: general_knowledge, summarization, code

#### `chimeraforge compare` — Diff Benchmark Runs

```bash
chimeraforge compare --baseline run1.json --candidate run2.json
chimeraforge compare --baseline run1.json --candidate run2.json,run3.json --json
```

- Matches configs by (model, backend, quant, workload, context_length)
- Computes throughput/TTFT/duration deltas with color-coded Rich output
- Aggregate summary with improvement/regression counts

#### `chimeraforge refit` — Update Planner Coefficients

```bash
chimeraforge refit --bench-dir ./results/ --output fitted_models.json --validate
chimeraforge refit --bench-files run1.json,run2.json --json
```

- Bayesian blending: confidence weight scales with total run count
- Hardware offsets: measured/predicted ratios per (model, backend)
- Power-law refitting for throughput scaling curves
- 10-check validation suite (`--validate` flag)

#### `chimeraforge report` — Generate Reports

```bash
chimeraforge report --results-dir ./results/ --format markdown --output report.md
chimeraforge report --results-files run1.json,run2.json --format html --output report.html
```

- Markdown (GitHub-compatible) and self-contained HTML output
- Statistical analysis: RMSE, MAE, MAPE, R-squared
- Per-config detail tables with percentile breakdowns
- XSS-safe HTML generation with inline CSS

### Backend & Infrastructure Studies (TR117-TR121)

**Inference Backend Performance (TR117):**
- **Best Mean Latency:** GPU-compile (389ms) - but reveals "compile paradox" (wins mean, loses median)
- **Best Median Latency:** Plain GPU (323ms) - more consistent
- **Python Efficiency Ceiling:** 86% maximum due to event loop lag (16ms spikes)
- **Scale:** 3,017 inference runs across multiple backends

**Specialized Runtime Performance (TR118_v2.2):**
- **Best Prefill:** TensorRT-fp16 (2.48ms, -87% vs baseline)
- **Best Generate:** ONNX Runtime-CPU (43.3ms, -73% vs baseline)
- **Degraded Rate:** 25% of runs with explicit reasons documented
- **Key Insight:** Specialized runtimes offer substantial gains but require careful optimization

**Cost & Energy Economics (TR119):**
- **Best Cost Efficiency:** onnxruntime-gpu ($0.1279/1M tokens on-demand)
- **Spot Pricing:** 69.8% savings vs on-demand
- **Energy Efficiency:** 503M tokens/kWh
- **Carbon Impact:** ~1.0 gCO2e per 1M tokens

**Root Cause Analysis (TR120):**
- **Compile Paradox Explained:** TR117 compile label was misattributed; shape stability is the critical factor
- **Key Insight:** Shape stability matters more than compilation for consistent performance
- **Production Impact:** Padding/bucketing strategies can collapse compiled tail to sub-millisecond

**Model Scaling (TR121v1):**
- **Scale Range:** 5M to 20B parameters
- **Pipeline Established:** Consistent phase definitions (prefill vs decode)
- **Two-Family Study:** HuggingFace local models (5M-124M) + Ollama models (270M-20B)

---

## Research Journey: Technical Reports TR108-TR137

The research progressed systematically — **~204,000 primary measurements** across **32 technical
reports** (TR108-TR137 + the TR142/TR146 safety provenance), covering single-agent performance,
multi-agent concurrency, runtime optimization, backend comparisons, cost/energy economics, scaling
studies, quantization, compilation, context scaling, serving-stack comparison, GPU kernel profiling,
predictive capacity planning, and safety alignment.

See the **[Report Guide](#report-guide-what-each-technical-report-answers)** below for a one-line
question + outcome per report, and `outputs/publish_ready/reports/` for the full archive.

---

## Understanding the Metrics

### Throughput (Tokens per Second)
**What it is:** How many tokens the agent generates per second. A token is roughly 0.75 words.  
**Why it matters:** Higher throughput = more work done per second = better capacity utilization = lower costs.  
**Real-world impact:** 15% faster throughput means you can handle 15% more requests with the same hardware, or use 15% less hardware for the same workload.

### TTFT (Time to First Token)
**What it is:** How long from when you send a request until the agent starts generating a response.  
**Why it matters:** Users perceive latency, not throughput. 58% faster TTFT feels significantly more responsive.  
**Real-world impact:** Faster TTFT = better user experience = higher user satisfaction = better product metrics.

### Memory Usage
**What it is:** How much RAM the agent process consumes.  
**Why it matters:** Less memory = more agents per server = better resource utilization = lower infrastructure costs.  
**Real-world impact:** 67% less memory means you can run 3x more Rust agents than Python agents on the same hardware.

### Parallel Efficiency
**What it is:** For multi-agent systems, how close you get to perfect parallelism. 100% = perfect (2 agents = 2x speedup), 50% = no benefit (2 agents = 1x speedup).  
**Why it matters:** High efficiency means you can scale horizontally with minimal overhead. Low efficiency means adding agents doesn't help much.  
**Real-world impact:** 99% efficiency means doubling your agent count nearly doubles your capacity with <1% overhead. This is critical for scaling.

### Contention Rate
**What it is:** How often agents compete for the same resources (GPU, memory, network), causing slowdowns.  
**Why it matters:** Lower contention = more predictable performance = easier capacity planning = better SLAs.  
**Real-world impact:** 0.74% contention means agents rarely interfere with each other. 15% contention means frequent slowdowns and unpredictable performance.

### Coefficient of Variation (CV)
**What it is:** A measure of consistency. Lower CV = more consistent performance.  
**Why it matters:** Consistent performance = predictable capacity = easier planning = better user experience.  
**Real-world impact:** 2.6% CV means performance is very predictable. 4.8% CV means more variation, making capacity planning harder.

---

## Report Guide: What Each Technical Report Answers

| Report | Core Question | Headline Outcome | Why It Matters |
|--------|---------------|------------------|----------------|
| **TR108** | What is the best single-inference baseline? | GPU 80 / CTX 512 / TEMP 0.8 is the reference config. | Establishes baseline for all comparisons. Shows that single-inference optimization is different from agent optimization. |
| **TR109** | Do agent workflows need different tuning? | Yes: 512–1024 ctx, only 39% of configs beat baseline. | Proves you can't copy single-inference settings to agents. Agent workflows have different characteristics. |
| **TR110** | Can Python run agents concurrently? | Dual Ollama yields 99.25% peak, 95.8% mean efficiency. | Validates that multi-agent systems can achieve near-perfect parallelism. Critical for scaling. |
| **TR111_v2** | How fast can a Rust agent go? | 114.54 tok/s baseline (+15.2% vs Python). | First comprehensive Rust agent benchmark. Proves Rust's performance advantage is real. |
| **TR112_v2** | Apples-to-apples Python vs Rust? | Rust: –58% TTFT, –67% memory, 2.6% CV, +83% faster startup. | Definitive comparison with identical workflows. Provides data for decision-making. |
| **TR113** | What if we keep one Ollama? | Rust stalls at 82.2% efficiency (contention). | Identifies architectural bottleneck. Proves dual Ollama is necessary. |
| **TR114_v2** | Does dual Ollama unblock Rust? | 98.281% mean, 99.396% peak, 0.74% contention. | Validates Rust can exceed Python in multi-agent scenarios with proper architecture. |
| **TR115_v2** | Which Rust runtime should we ship? | Tokio-default: 99.89% peak / 98.72% mean / 1.21 pp sigma. | Production guidance. Consistency matters more than peak performance. |
| **TR116** | Does model choice matter for multi-agent? | Rust + Gemma 3 is king (99.2%). Qwen shows imbalance. | Proves Rust's advantage holds across models (+12-17pp efficiency). |
| **TR117** | Which inference backend is fastest? | GPU-compile wins mean (389ms), plain GPU wins median (323ms) - "compile paradox". Python 86% ceiling from event loop lag. | Backend choice matters for latency. Python's structural limitations prevent >86% efficiency. |
| **TR117_multi_agent** | Why does Python have an 86% efficiency ceiling? | Event loop saturation: 5.33ms mean lag, 15.22ms max. CPU-bound JSON parsing monopolizes single-threaded loop. | Python limitation is structural. Rust's multi-threaded runtime eliminates this bottleneck. |
| **TR118_v2.2** | Can specialized runtimes beat PyTorch? | TensorRT-fp16: 2.48ms prefill (-87% vs baseline). ONNX Runtime-CPU: 43.3ms generate (-73% vs baseline). | Specialized runtimes provide significant latency improvements but require infrastructure investment. |
| **TR119** | What are the cost/energy implications? | onnxruntime-gpu: $0.1279/1M tokens (on-demand), best cost efficiency. | Backend choice significantly impacts operational costs and energy consumption. |
| **TR120** | Why does GPU-compile win mean but lose median? | TR117 compile label misattributed; shape stability is critical, not compilation. | Understanding true cause enables better optimization. Shape stability matters more than compilation. |
| **TR121v1** | How does performance scale with model size? | Scaling pipeline established from 5M to 20B parameters. | Understanding scaling behavior essential for choosing appropriate model sizes. |
| **TR122** | What are the physics of inference on consumer GPUs? | RTX 4080 idles at 20.71W, V2 poller achieves 100ms grid. | Foundational power/thermal characterization for all subsequent work. |
| **TR123** | What does KV-cached inference actually cost? | Best cost $0.013/1M tokens (GPT-2/compile, chat blend). | Phase-split economics across 5 models, 3 backends, 5 workloads. |
| **TR124** | Does backend choice affect output quality? | No — 0/7 ANOVA metrics significant across 5 models. | Enables pure cost-driven backend selection. |
| **TR125** | Which quantization level should we deploy? | Q4_K_M universal sweet spot (-4.1pp max); Q2_K unacceptable. | 26,000 samples, 34 model-quant variants, real MMLU+ARC benchmarks. |
| **TR126** | Does torch.compile actually help? | Yes on Linux (24-60% prefill speedup); crashes decode. | Resolves Phase 1 compile paradox; 916 real Triton kernels generated. |
| **TR127** | What happens at long context lengths? | VRAM spillover causes 25-105x cliffs; sub-linear below capacity. | Two-regime discovery reshapes all context-length planning. |
| **TR128** | How does production load behave? | NUM_PARALLEL is a no-op (0/30 significant); M/D/1 deviates 20.4x. | Refutes two common assumptions about GPU inference scaling. |
| **TR129** | How do N agents scale on one GPU? | Amdahl s=0.39-0.54; throughput plateaus at N=2. | Per-agent efficiency degrades monotonically; fairness excellent. |
| **TR130** | Which serving stack scales best? | vLLM 2.25x advantage at N=8 via continuous batching. | First head-to-head: Ollama vs vLLM vs TGI at scale. |
| **TR131** | What's the real scaling bottleneck? | GPU memory bandwidth (+74% stress at N=8), not serving stack. | Overturns TR130; PyTorch Direct degrades worse than Ollama. |
| **TR132** | How does continuous batching work at kernel level? | 77-80% kernel reduction, 79-83% bandwidth-per-token reduction. | Proves the mechanism; vLLM and TGI use identical amortization. |
| **TR133** | Can we automate capacity planning? | Yes — 4/4 validation targets met; `chimeraforge plan` shipped. | Empirical lookup tables outperform theoretical queueing models. |

**Full report links:** See `outputs/publish_ready/reports/` for all 32 technical reports plus conclusive syntheses.

---

## How to Use This Repository

### Getting Started (5 Minutes)

1. **Install from PyPI:**
   ```bash
   pip install chimeraforge[all]
   ```
   - Python 3.10+, Rust 1.70+ (optional, for Rust agents), CUDA 11.8+ (optional)
   - RTX 4080-class GPU (12GB+ VRAM recommended for bench/plan)
   - Windows/macOS/Linux supported

2. **Get a first run working** – Follow `docs/quick_start.md`
   - Walks through Python and Rust single-agent benchmarks
   - Shows how to interpret results
   - Takes about 10-15 minutes for first run

3. **Enable true concurrency** – Follow `docs/dual_ollama_setup.md`
   - Required for multi-agent benchmarks (TR110/TR114)
   - Shows how to run two Ollama instances on ports 11434/11435
   - Critical for reproducing multi-agent results

### Going Deeper

4. **Understand the methodology** – Read `docs/benchmarking.md` and `docs/methodology.md`
   - How we ensure fair comparisons
   - Statistical analysis techniques
   - How to interpret results

5. **Compare languages** – Read `docs/rust_vs_python.md`
   - Detailed comparison tables
   - When to use each language
   - Trade-off analysis

6. **Optimize performance** – Read `docs/performance_tuning.md` and `docs/chimera_optimization.md`
   - Configuration optimization strategies
   - Parameter tuning guidance
   - Common pitfalls to avoid

### Automation and Analysis

7. **Automate benchmarks** – Use `scripts/benchmark_cli.py` for cross-platform runs
   - Or use PowerShell helpers in `scripts/windows/` on Windows
   - Batch processing for multiple configurations
   - Results automatically written to `benchmarks/` or `outputs/`

8. **Analyze your data** – Use notebooks in `outputs/publish_ready/notebooks/`
   - Jupyter notebooks for data analysis
   - Visualization tools
   - Statistical analysis scripts

All scripts write outputs into `benchmarks/` or `outputs/` so the data stays co-located with the research.

---

## Repository Structure: Where Everything Lives

| Path | Contents | When to Use |
|------|----------|-------------|
| **`src/python/banterhearts/`** | Python agent source code | When you want to understand or modify Python implementations |
| **`src/rust/demo_agent/`** | Rust single-agent implementation | When you want to understand or modify Rust single-agent code |
| **`src/rust/demo_multiagent/`** | Rust multi-agent implementation | When you want to understand or modify Rust multi-agent code |
| **`experiments/research/tr108/`** through **`tr139/`** | Canonical mirrored research code, configs, and task definitions | When you want the public reproduction scaffold for specific technical reports |
| **`experiments/TR116/`** and **`experiments/TR117/`** | Legacy experiment folders with still-unique source/docs | When you need older non-mirrored experiment material not yet folded into `experiments/research/` |
| **`scripts/`** | Python automation scripts | When you want to automate benchmarks or analysis |
| **`scripts/windows/`** | PowerShell wrappers for Windows | When running on Windows and need platform-specific helpers |
| **`benchmarks/`** | Replayable benchmark artifacts | When you want to inspect raw benchmark data |
| **`data/baselines/`** | Canonical baseline measurements | When you need reference points for regression testing |
| **`data/csv/`** | CSV exports of benchmark data | When you want to analyze data in Excel, Python, or other tools |
| **`data/research/`** | Research data from experiments | When you want to access experiment-specific datasets |
| **`outputs/reports/`** | Exploratory, legacy, and scratch report outputs | When you want working notes or historical report artifacts that are not canonical |
| **`src/chimeraforge/`** | ChimeraForge CLI (plan, suggest, measure, catalog, safety, bench, eval, report, compare, refit) | The full CLI toolchain |
| **`outputs/publish_ready/reports/`** | Canonical TR archive (TR108-TR137) + conclusive syntheses | **Start here** for comprehensive findings and analysis |
| **`outputs/publish_ready/docs/`** | Publish-ready benchmark narratives and supporting writeups | When you want public-facing benchmark context beyond the TR archive |
| **`outputs/runs/`** | Benchmark run outputs | When you want to inspect individual benchmark execution logs |
| **`logs/benchmarks/`** | Archived benchmark logs | When you need historical log data |
| **`resources/`** | Legacy research resources | Historical reference only |
| **`docs/`** | All documentation | **Start here** for guides, API docs, and explanations |

**Rule of thumb:** 
- Code lives in `src/`
- Automation lives in `scripts/`
- Generated data lives in `benchmarks/` or `outputs/`
- Explanations live in `docs/`
- Final reports live in `outputs/publish_ready/reports/`

---

## Trust but Verify: How We Ensure Accuracy

Every number in this repository is reproducible and verifiable. Here's how we ensure accuracy:

### Experimental Rigor

- **Process isolation:** Each benchmark run launches a fresh Ollama process to avoid warm-cache bias
- **Multiple runs:** Every configuration is tested 3-5 times for statistical confidence (except TR113's exploratory single-run sweep, which is clearly labeled in the report)
- **Cold starts:** Forced model reloads between runs to ensure fair comparisons
- **Structured logging:** All metrics collected in structured formats (JSON, CSV) with timestamps

### Data Provenance

- **Metadata tracking:** Every dataset, CSV, and figure includes metadata showing:
  - The exact command that produced it
  - The configuration used
  - The hardware and software environment
  - The date and time of execution
- **Version control:** All code, data, and reports are version-controlled
- **Reproducibility:** Anyone can clone this repo and reproduce our results

### Verification Process

To audit any number in this repository:

1. **Find the claim** in a Technical Report (e.g., "Rust is 15.2% faster")
2. **Check the report** in `outputs/publish_ready/reports/` for methodology
3. **Follow the reference** to the data folder (e.g., `benchmarks/rust/demo_agent/...`)
4. **Inspect the raw data** (CSV files, JSON logs)
5. **Reproduce the analysis** using the provided scripts or notebooks

### Statistical Validation

All reports include:
- **Mean, median, standard deviation** for all metrics
- **Confidence intervals** where applicable
- **Coefficient of variation** (CV) for consistency measures
- **Percentile analysis** (p50, p95, p99) for latency metrics
- **Multiple runs** to establish statistical significance

---

## Need More Detail?

### For Specific Topics

- **`docs/rust_vs_python.md`** – Extended comparison tables with detailed metrics
- **`docs/performance_tuning.md`** – Guidance on optimizing agent performance
- **`docs/chimera_optimization.md`** – Configuration optimization strategies
- **`docs/statistical_analysis.md`** – How we analyze and interpret benchmark data
- **`docs/multi_agent.md`** – Multi-agent architecture and setup
- **`docs/dual_ollama_setup.md`** – Critical setup for multi-agent benchmarks
- **`docs/API.md`** – Code reference and API documentation

### For Understanding the Research

- **`docs/technical_reports.md`** – Complete index of all technical reports
- **`outputs/publish_ready/reports/`** – All technical reports (TR108-TR137) with full analysis
- **`outputs/publish_ready/notebooks/`** – Jupyter notebooks for data analysis

### For Getting Help

- **Open an issue** on GitHub for questions or problems
- **Start from the relevant Technical Report** that cites the data you need
- **Check `docs/faq.md`** for common questions
- **Review `docs/README.md`** for documentation navigation

---

## Research Scale and Methodology

### Total Research Investment

- **~204,000 primary measurements** across Phase 1, Phase 2, and Phase 3 (de-duplicated: TR137 and TR142 are syntheses of already-counted data)
- **32 technical reports** (TR108-TR137 + TR142/TR146) plus 4 conclusive synthesis families
- Parent Banterhearts program: **~1,337,000 primary + judge measurements across 54 technical reports** (as of 2026-06-23) — ChimeraForge is the actionable-CLI splice
- **4 serving stacks** benchmarked (Ollama, vLLM, TGI, PyTorch Direct)
- **7 quantization levels** tested across 5 models with real MMLU/ARC benchmarks
- **GPU kernel profiling** with Nsight Systems (~2 GB traces)
- **1 PyTorch upstream contribution** (pytorch/pytorch#175557, PR #175562)
- **1 shipped CLI tool** (`chimeraforge` — 10 commands: plan, suggest, measure, catalog, safety, bench, eval, report, compare, refit) published to PyPI

### Methodology Highlights

- **Process isolation:** Fresh processes for every run to avoid bias
- **Cold starts:** Forced model reloads between runs
- **Multiple repetitions:** 3-5 runs per configuration for statistical confidence (TR113 noted as single-run exploratory)
- **Structured data collection:** All metrics in machine-readable formats
- **Reproducible code:** Every benchmark is runnable with provided scripts
- **Full documentation:** Methodology documented in every technical report

### Hardware and Software

- **GPU:** NVIDIA RTX 4080 Laptop GPU (12 GB GDDR6 VRAM, 256-bit, 432 GB/s, AD104)
- **CPU:** Intel Core i9-13900HX (24 cores, 32 threads)
- **RAM:** 64 GB DDR5-4800
- **OS:** Windows 11 + WSL2/Ubuntu 22.04 for Docker/Linux workloads
- **Models tested:** GPT-2 (124M) through LLaMA-3.1-8B (8B), 7 quantization levels
- **Serving stacks:** Ollama 0.6.x, vLLM 0.7.x, TGI, PyTorch Direct
- **Python:** 3.11+ with asyncio
- **Rust:** 1.70+ with Tokio/async-std/smol runtimes

---

## Contributing

We welcome contributions! See [`CONTRIBUTING.md`](CONTRIBUTING.md) for guidelines.

**Areas for contribution:**
- Additional benchmark configurations
- New optimization strategies
- Documentation improvements
- Analysis tools and visualizations
- Support for additional models or hardware

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

## Acknowledgments

This research was conducted as part of the Banterhearts LLM Performance Research Program. Phase 1 (TR108-TR122) established the measurement methodology and cross-language comparison. Phase 2 (TR123-TR133) produced the deployment framework and capacity planner. Phase 3 (TR134-TR137) measured the safety cost of inference optimization — alignment robustness and the "safety tax" — now operationalized as the planner's safety gate (v0.3.0). Production APIs and orchestration services remain in the main Banterhearts repository.

---

**Last Updated:** June 25, 2026 (v0.6.0)
**Repository:** https://github.com/Sahil170595/Chimeraforge
**PyPI:** https://pypi.org/project/chimeraforge/
**Status:** Phase 1 + Phase 2 + Phase 3 Complete | v0.6.0

