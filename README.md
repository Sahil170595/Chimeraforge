# Chimeraforge

[![PyPI version](https://img.shields.io/pypi/v/chimeraforge.svg)](https://pypi.org/project/chimeraforge/)
[![Python](https://img.shields.io/pypi/pyversions/chimeraforge.svg)](https://pypi.org/project/chimeraforge/)
[![CI](https://github.com/Sahil170595/Chimeraforge/actions/workflows/ci.yml/badge.svg)](https://github.com/Sahil170595/Chimeraforge/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**A model-agnostic LLM deployment planner. Pick the backend, quantization, GPU count, and context budget for any model -- backed by ~204,000 real measurements on consumer GPUs.**

```bash
pip install chimeraforge
```

Give `chimeraforge` a model -- a size class, a Hugging Face repo, or an Ollama tag -- and it searches the (model x quantization x backend x GPU count) space against VRAM, quality, latency, cost, and an opt-in safety gate, then hands back the cheapest config that meets your SLO in under a second. Every prediction is labeled `measured` / `estimated` / `unknown`, so you never mistake a guess for data, and the empirical corpus traces to Technical Reports TR108-TR137.

**10 commands, one tool:** `plan` - `suggest` - `measure` - `catalog` - `safety` - `bench` - `eval` - `compare` - `refit` - `report`.

> **New in v0.6.0 -- a serving model that matches the literature.** vLLM/TGI are now modelled with **continuous batching** (one GPU can replace several single-stream Ollama replicas), latency splits into **prefill/TTFT + decode/TPOT**, `plan --pareto` prints the non-dominated cost/latency/quality menu instead of a single pick, and `plan --workload {steady,chatbot,bursty,agent}` inflates the tail for variance-heavy traffic. Built on v0.5.0's **model-agnostic planning** (`plan --model <hf-repo|ollama-tag>`, plus `suggest` / `catalog` / `measure`). See the [CHANGELOG](CHANGELOG.md).

---

## Install

```bash
pip install chimeraforge            # core: plan (registry size classes)
pip install chimeraforge[resolve]   # + plan any HF repo / Ollama tag (metadata resolution)
pip install chimeraforge[bench]     # + live benchmarking
pip install chimeraforge[eval]      # + quality evaluation (BERTScore, ROUGE-L)
pip install chimeraforge[safety]    # + live refusal screen
pip install chimeraforge[refit]     # + coefficient refitting (numpy, scipy)
pip install chimeraforge[all]       # everything + dev tools
```

Python 3.10+. `plan` works fully offline; `resolve` adds HF/Ollama metadata lookup; `bench` / `measure` / `safety` need a running backend (Ollama, vLLM, or TGI). Windows / macOS / Linux.

## Quickstart

```bash
# Plan a registry size class on your GPU
chimeraforge plan --model-size 8b --hardware "RTX 4090 24GB" --request-rate 2.0

# Plan ANY model -- a Hugging Face repo or an Ollama tag (needs [resolve])
chimeraforge plan --model Qwen/Qwen2.5-7B-Instruct --hardware "RTX 4090 24GB"
chimeraforge plan --model ollama:qwen3:14b --ollama-url http://localhost:11434

# Print the cost/latency/quality trade-off menu, not just one pick
chimeraforge plan --model-size 8b --hardware "RTX 4090 24GB" --pareto

# Benchmark a live model and plan on the MEASURED numbers
chimeraforge plan --model qwen3:14b --measure

# Discover + rank what fits your GPU and budget
chimeraforge suggest --source ollama --hardware "RTX 4090 24GB" --budget 500
```

---

## Commands

### `plan` -- predictive capacity planner

```bash
chimeraforge plan --model-size 8b --hardware "RTX 4090 24GB" --request-rate 2.0
chimeraforge plan --model Qwen/Qwen2.5-7B-Instruct --hardware "RTX 4090 24GB"   # any HF repo
chimeraforge plan --model ollama:qwen3:14b --ollama-url http://localhost:11434  # any Ollama tag
chimeraforge plan --model qwen3:14b --measure                                   # bench live, plan on real numbers
chimeraforge plan --model-size 3b --pareto                                      # trade-off menu
chimeraforge plan --model-size 3b --workload agent --safety-target 0.85 --json
```

- Plans **any** model: registry size class, HF repo (`org/name`), Ollama tag, or manual overrides (`--params-b/--n-layers/...`).
- Searches (model x quantization x backend x N-replicas x batch/GPU) through a 5-gate pipeline: VRAM -> quality -> safety (opt-in) -> latency -> budget.
- Models real serving physics: continuous batching (vLLM/TGI), prefill/decode split (TTFT + TPOT), KV-cache-bound concurrency, and variance-aware queueing.
- Per-prediction provenance (`measured` / `estimated` / `unknown`); explains the binding gate when nothing fits.
- Validated on registry data: VRAM R^2=0.968, throughput R^2=0.859, quality RMSE=0.062, latency MAPE=1.05% (beats analytical M/D/1 by 20.4x, TR133). No ML -- empirical lookup tables with first-principles interpolation (roofline for off-registry models).

### `suggest` -- discover & rank models

```bash
chimeraforge suggest --source ollama --hardware "RTX 4090 24GB" --budget 500
chimeraforge suggest --source hf --hf-limit 8 --hardware "RTX 4080 12GB"
chimeraforge suggest --source catalog --hardware "RTX 4080 12GB"   # offline, after `catalog --build`
```

Pulls candidates from a live Ollama (`/api/tags`), the HF Hub (top text-generation), and/or the local catalog; resolves each to real params/arch, runs the same gate search, and shows the best config per model.

### `measure` -- benchmark live, plan on real numbers

```bash
chimeraforge measure --model qwen3:14b --ollama-url http://localhost:11434
chimeraforge plan --model qwen3:14b --measure   # measure then plan in one step
```

Benchmarks the live model (real N=1 throughput, service time, concurrency scaling) and folds it into a local corpus. `plan` / `suggest` then prefer the measured numbers automatically (provenance flips to `measured`).

### `catalog` -- local model catalog

```bash
chimeraforge catalog --build         # resolve a curated seed (+ --with-ollama) and cache specs
chimeraforge catalog                 # list the cached catalog
```

Persists resolved specs so `suggest --source catalog` ranks a known-good set fully offline.

### `safety` -- live refusal screen

```bash
chimeraforge safety --model llama3.2-3b --prompts harmful.txt --quant Q4_K_M --safety-target 0.85
```

Where `plan --safety-target` *decides* from bundled TR134/TR142 data, `safety` *measures*: it runs your probe prompts against a live model, classifies refusals (rule-based -- the TR134 regex baseline), reports the measured refusal rate vs the bundled gate data (expected, drift, RTSI risk tier), and exits 1 below `--safety-target`. **You provide the prompts** (`--prompts`, one per line) -- no attack corpus ships with the package; point it at HarmBench / AdvBench / your own set. Needs `chimeraforge[safety]` + a running Ollama.

### `bench` -- live inference benchmarking

```bash
chimeraforge bench --model llama3.2-3b --runs 5
chimeraforge bench --model llama3.2-3b --all-quants --json
chimeraforge bench --model llama3.2-3b --context 512,1024,2048,4096
chimeraforge bench --model llama3.2-3b --workload server --rate 2.0
chimeraforge bench --model llama3.2-3b --backend vllm --base-url http://localhost:8000
```

Three workload profiles (single / batch / server-Poisson); measures throughput, TTFT, and latency with p50/p90/p95/p99; CV-based stability warnings; JSON output.

### `eval` -- quality evaluation

```bash
chimeraforge eval --task general_knowledge --json
chimeraforge eval --predictions preds.txt --references refs.txt --model llama3.2-3b
chimeraforge eval --list-tasks
```

Metrics: exact match, ROUGE-L (LCS fallback), BERTScore, coherence -> composite (`0.2*EM + 0.3*ROUGE + 0.3*BERT + 0.2*coherence`). Quality tiers from TR125; 3 built-in tasks (general_knowledge, summarization, code). Pass `--fp16-baseline` to classify the drop tier.

### `compare` -- diff benchmark runs

```bash
chimeraforge compare --baseline run1.json --candidate run2.json,run3.json --json
```

Matches configs by (model, backend, quant, workload, context_length); computes throughput/TTFT/duration deltas with an aggregate improvement/regression summary.

### `refit` -- update planner coefficients

```bash
chimeraforge refit --bench-dir ./results/ --output fitted_models.json --validate
```

Bayesian blending (per-key confidence weighting), hardware offsets, power-law refitting, and a 10-check validation suite that gates the write (`--validate`).

### `report` -- generate reports

```bash
chimeraforge report --results-dir ./results/ --format markdown --output report.md
chimeraforge report --results-files run1.json,run2.json --format html --output report.html
```

Markdown (GitHub-compatible) and self-contained, XSS-safe HTML; statistical analysis (RMSE, MAE, MAPE, R^2) with per-config percentile tables.

---

## What the research decided

Phase 2 (TR123-TR133, ~106,000 measurements) distilled into an artifact-backed deployment framework -- the same rules the planner applies:

| Decision | Recommendation | Evidence |
|----------|---------------|----------|
| **Single-agent backend** | Ollama Q4_K_M | Highest throughput/dollar; quality within -4.1pp (TR123-TR125) |
| **Multi-agent backend (N>=4)** | vLLM FP16 | 2.25x advantage from continuous batching (TR130-TR132) |
| **Compile policy** | Prefill only, Linux, Inductor+Triton | 24-60% speedup; decode crashes 100% (TR126) |
| **Quantization** | Q4_K_M default; Q8_0 quality-critical; never Q2_K | Universal sweet spot across 5 models (TR125) |
| **Context budget** | Ollama for >4K tokens on 12 GB | VRAM spillover = 25-105x cliffs (TR127) |
| **Capacity planning** | `chimeraforge plan` | Validated R^2>=0.859; beats M/D/1 by 20.4x (TR133) |
| **Safety screening** | `plan --safety-target` (opt-in) | Refusal-rate + RTSI risk per config; rejects safety-collapsing cells (TR134/TR142) |

**Headline findings** (full data in the TRs):
- **Rust vs Python (single-agent):** Rust +15.2% throughput, -58% TTFT, -67% memory, more consistent (2.6% vs 4.8% CV) -- TR112.
- **Multi-agent:** both reach near-perfect parallelism (~99% peak) *with dual Ollama*; a single instance caps efficiency at 82.2% -- TR110/TR113/TR114.
- **Rust runtime:** ship **Tokio-default** (98.72% mean, 1.21pp sigma); async-std serializes, smol has pathological tails -- TR115.
- **Serving stack at scale:** vLLM's continuous batching gives a **2.25x** edge at N=8; the real bottleneck is GPU memory bandwidth, not the stack -- TR130-TR132.
- **Quantization:** Q4_K_M is the universal sweet spot (-4.1pp max quality drop); Q2_K is unacceptable -- TR125 (26k samples, real MMLU+ARC).

**Full research:** [`docs/technical_reports.md`](docs/technical_reports.md) indexes all 32 reports (one question + outcome each); the full archive with methodology and raw-data references lives in [`outputs/publish_ready/reports/`](outputs/publish_ready/reports/).

---

## How the numbers are made

- **~204,000 primary measurements** across 32 technical reports (TR108-TR137 + the TR142/TR146 safety provenance), on an RTX 4080 Laptop (12 GB). De-duplicated: TR137/TR142 are syntheses of already-counted data.
- **Rigor:** fresh-process isolation per run (no warm-cache bias), forced cold starts, 3-5 runs per config for statistical confidence, structured JSON/CSV logging with full provenance. Every claim traces to raw data you can re-run.
- **Program context:** ChimeraForge is the actionable CLI splice of the parent Banterhearts program (~1,337,000 primary + judge measurements across 54 TRs); the safety attack-surface and serving-stack research lives in sibling repos.

Reproduce any number: find the claim in a report under `outputs/publish_ready/reports/`, follow its reference to the data folder, inspect the CSV/JSON, and re-run the provided scripts or notebooks. See [`docs/methodology.md`](docs/methodology.md).

## Repository layout

| Path | Contents |
|------|----------|
| `src/chimeraforge/` | The `chimeraforge` CLI + capacity planner (the pip package) |
| `src/python/banterhearts/` | Python agent benchmarking, monitoring, profiling |
| `src/rust/` | Rust single- and multi-agent implementations (Tokio + 4 alt runtimes) |
| `outputs/publish_ready/reports/` | Canonical TR archive (TR108-TR137) + syntheses -- **start here for findings** |
| `docs/` | Guides, API reference, and the technical-report index -- **start here for how-to** |
| `experiments/`, `data/`, `benchmarks/` | Reproduction scaffold, baselines, and raw benchmark artifacts |

## Documentation

- **[`docs/README.md`](docs/README.md)** -- documentation index and navigation
- **[`docs/quick_start.md`](docs/quick_start.md)** -- first benchmark run (Python + Rust)
- **[`docs/API.md`](docs/API.md)** -- Python API reference for the package
- **[`docs/technical_reports.md`](docs/technical_reports.md)** -- index of all 32 technical reports
- **[`docs/dual_ollama_setup.md`](docs/dual_ollama_setup.md)** -- required for reproducing multi-agent results
- **[`docs/methodology.md`](docs/methodology.md)** / **[`docs/rust_vs_python.md`](docs/rust_vs_python.md)** -- methodology and the full language comparison

## Contributing

Contributions welcome -- see [`CONTRIBUTING.md`](CONTRIBUTING.md). Good areas: additional benchmark configs, new optimization strategies, more models/hardware, docs, and analysis tools.

## License

MIT -- see [LICENSE](LICENSE).

## Acknowledgments

Conducted as part of the Banterhearts LLM Performance Research Program: Phase 1 (TR108-TR122) established the measurement methodology and cross-language comparison, Phase 2 (TR123-TR133) produced the deployment framework and capacity planner, and Phase 3 (TR134-TR137) measured the safety cost of inference optimization -- now the planner's opt-in safety gate.

---

**Repository:** https://github.com/Sahil170595/Chimeraforge - **PyPI:** https://pypi.org/project/chimeraforge/ - **Status:** Phases 1-3 complete, v0.6.0
