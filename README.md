# Chimeraforge

[![PyPI version](https://img.shields.io/pypi/v/chimeraforge.svg)](https://pypi.org/project/chimeraforge/)
[![Python](https://img.shields.io/pypi/pyversions/chimeraforge.svg)](https://pypi.org/project/chimeraforge/)
[![CI](https://github.com/Sahil170595/Chimeraforge/actions/workflows/ci.yml/badge.svg)](https://github.com/Sahil170595/Chimeraforge/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

<!-- mcp-name: io.github.Sahil170595/chimeraforge -->

**A local-first, model-agnostic LLM deployment planner.** It turns "which model, quantization, GPU, and backend -- how many, will it fit, will it hit my SLO, what will it cost" into a fast, honest, measured answer, from your shell, your Python, or your AI assistant.

```bash
uvx chimeraforge plan --model-size 8b --hardware "RTX 4090 24GB"
```

## The trust principle

**Every number is labeled `measured`, `extrapolated`, `derived`, `estimated`, or `unknown`, and the tool refuses to fake the ones it can't stand behind.** VRAM and KV-cache are `derived` -- exact arithmetic over the model's real architecture, not a measurement. Throughput is a measured lookup only on the rig the corpus was measured on; on any other GPU that row is scaled by memory bandwidth and reported as `extrapolated`, with the factor named, because a 13.8x bandwidth extrapolation is not a measurement of your card. Failing that it is an explicit roofline `estimate` -- never presented as data it isn't. Quality below the bundled corpus reports `unknown`, not a made-up score. A 0-result plan names the exact gate that rejected every candidate instead of a generic "nothing found." No telemetry, no phone-home, works air-gapped.

Give it a model -- a size class, a Hugging Face repo, an Ollama tag, or manual overrides for an unreleased model -- and it searches the (model x quantization x backend x GPU count x tensor/pipeline parallelism) space against VRAM, quality, latency, cost, energy, and an opt-in safety gate, then hands back the cheapest config that meets your SLO.

**13 commands, one tool:** `plan` - `suggest` - `measure` - `workload` - `validate` - `catalog` - `safety` - `bench` - `eval` - `compare` - `refit` - `report` - `mcp`.

The empirical corpus traces to Technical Reports TR108-TR137 (~204,000 real measurements on consumer GPUs). See the [CHANGELOG](CHANGELOG.md) for the full feature history.

---

## Install

Try it with no install:

```bash
uvx chimeraforge plan --model-size 8b --hardware "RTX 4090 24GB"
pipx run chimeraforge plan --model-size 8b --hardware "RTX 4090 24GB"
```

Install for real:

```bash
pip install chimeraforge            # planner + model resolution (HF/Ollama) + suggest/measure/safety/bench
pip install chimeraforge[bench]     # + GPU environment metadata for benchmarks (pynvml)
pip install chimeraforge[mcp]       # + MCP server so Claude/GPT/Cursor can call the planner
pip install chimeraforge[eval]      # + quality evaluation (BERTScore, ROUGE-L)
pip install chimeraforge[refit]     # + coefficient refitting (numpy, scipy)
pip install chimeraforge[all]       # everything
```

Python 3.10+. The core install covers the planner and network-facing commands (`httpx` is a core dep). `plan` / `suggest` / `catalog` run fully offline; `bench` / `measure` / `safety` need a running backend (Ollama, vLLM, or TGI). Windows / macOS / Linux.

## Quickstart

```bash
# Plan a registry size class on your GPU
chimeraforge plan --model-size 8b --hardware "RTX 4090 24GB" --request-rate 2.0

# Plan ANY model -- a Hugging Face repo or an Ollama tag
chimeraforge plan --model Qwen/Qwen2.5-7B-Instruct --hardware "RTX 4090 24GB"
chimeraforge plan --model ollama:qwen3:14b --ollama-url http://localhost:11434

# Split a model too big for one GPU across several (tensor parallelism)
chimeraforge plan --model meta-llama/Llama-3.3-70B-Instruct --hardware "H100 80GB" --tp 4

# Shrink the KV-cache, print the cost/latency/quality trade-off menu
chimeraforge plan --model-size 8b --hardware "RTX 4080 12GB" --kv-quant q8 --pareto

# Benchmark a live model and plan on the MEASURED numbers
chimeraforge plan --model qwen3:14b --measure

# Discover + rank what fits your GPU and budget
chimeraforge suggest --source ollama --hardware "RTX 4090 24GB" --budget 500
```

---

## Plan with your traffic, not your guesses

```bash
chimeraforge workload --from-log requests.jsonl --out workload.json
chimeraforge plan --model-size 8b --hardware "RTX 4090 24GB" --workload-profile workload.json
```

Derives the request rate, prompt and output lengths, traffic variance and prefix-cache hit rate from a request log or a live vLLM/SGLang `/metrics` endpoint. The variance one matters most: `plan` otherwise takes it as one of four presets, and it drives the whole queueing tail.

Metric names are per-engine and explicit -- vLLM has renamed two of these between versions, and a scraper that silently falls back to a stale name reports a fabricated measurement. An unknown engine is an error, and a field the source did not expose stays absent rather than acquiring a default.

## Decision briefs

```bash
chimeraforge plan --model-size 8b --hardware "RTX 4090 24GB" --request-rate 2 --report brief.md
```

Writes a markdown record of the decision: the recommendation, every assumption as an input rather than a finding, the alternatives table, the planner's warnings verbatim, and the exact command that regenerates it. Each number is tagged `measured` / `extrapolated` / `derived` / `estimated` / `unknown` in prose, not just with a symbol.

It refuses to render on a stale price snapshot and exits non-zero, rather than printing an old price in a nicer font -- a formatted document reads as more durable than a terminal line, and its reader will not re-derive the arithmetic.

## MCP server -- give Claude / GPT / Cursor the same numbers

GPU sizing is exactly where assistants fail: training-cutoff hardware prices and specs, plus error-prone KV-cache/batching arithmetic done from memory. `chimeraforge mcp` runs a stdio MCP server so an assistant calls the real planner against measured data instead of guessing.

```bash
pip install "chimeraforge[mcp]"
```

Claude Code:

```bash
claude mcp add --transport stdio chimeraforge -- uvx --from "chimeraforge[mcp]" chimeraforge mcp
```

Claude Desktop / Cursor (add to your MCP config file):

```json
{
  "mcpServers": {
    "chimeraforge": {
      "command": "uvx",
      "args": ["--from", "chimeraforge[mcp]", "chimeraforge", "mcp"]
    }
  }
}
```

The `--from "chimeraforge[mcp]"` pulls in the MCP SDK; `uvx` runs the server in a self-contained environment. If you have already `pip install "chimeraforge[mcp]"` into the environment your client launches, you can instead use `"command": "chimeraforge", "args": ["mcp"]`.

Exposes five tools: `chimeraforge_plan` (the full gate search), `chimeraforge_suggest` (the inverse -- rank what actually fits a given GPU), `chimeraforge_compare_api` (self-host vs hosted-API cost and the break-even volume), `chimeraforge_resolve_model` (grounds a model id in its real params/architecture), and `chimeraforge_list_hardware`. Every result carries the same `measured` / `extrapolated` / `estimated` / `unknown` provenance as the CLI, and the tool descriptions tell the model to prefer them over its own knowledge. `chimeraforge_plan` also returns a `launch` field -- the serve command for the recommended config -- so the assistant can answer "and how do I run it" without inventing flags. `chimeraforge_compare_api` prices against a *dated* snapshot and reports its age, so an assistant quotes a price with its capture date rather than presenting a stale figure as current.

---

## Commands

### `plan` -- predictive capacity planner

```bash
chimeraforge plan --model-size 8b --hardware "RTX 4090 24GB" --request-rate 2.0
chimeraforge plan --model Qwen/Qwen2.5-7B-Instruct --hardware "RTX 4090 24GB"   # any HF repo
chimeraforge plan --model ollama:qwen3:14b --ollama-url http://localhost:11434  # any Ollama tag
chimeraforge plan --model meta-llama/Llama-3.3-70B-Instruct --hardware "H100 80GB" --tp 4   # multi-GPU
chimeraforge plan --model-size 3b --kv-quant q4 --pareto                       # smaller KV cache, trade-off menu
chimeraforge plan --model-size 8b --hardware "RTX 4090 24GB" --launch          # + the serve command to actually run it
chimeraforge plan --model-size 3b --workload agent --safety-target 0.85 --json
```

- Plans **any** model: registry size class, HF repo (`org/name`), Ollama tag, or manual overrides (`--params-b/--n-layers/...`).
- Searches (model x quantization x backend x N-replicas x batch/GPU) through a 5-gate pipeline: VRAM -> quality -> safety (opt-in) -> latency -> budget.
- Models real serving physics: continuous batching (vLLM/TGI), prefill/decode split (TTFT + TPOT), KV-cache-bound concurrency, and variance-aware queueing (`--workload`).
- **Fits models too big for one GPU:** `--tensor-parallel/--tp {N|auto}` shards weights + KV across N GPUs (Megatron-style, comms-modelled); `--pipeline-parallel/--pp {N|auto}` splits layers across N stages instead (cheaper on slow interconnects, needs batching to fill the pipeline). Not combinable yet.
- **Serves what the backend serves:** GGUF quants are offered on Ollama; vLLM/TGI get FP16 and **FP8** (only on GPUs with FP8 tensor cores -- Ada/Hopper/Blackwell/CDNA3). The planner no longer suggests a GGUF checkpoint on vLLM priced with a llama.cpp speedup.
- **KV-cache quantization** (`--kv-quant {fp16,q8,q4}`) shrinks the cache and raises max concurrency -- biggest win at long context.
- **Heterogeneous fleets** (`--fleet "H100 80GB,A100 80GB,L4 24GB"`): sizes a mix of GPU types instead of N copies of one, because a cheap GPU can win at loose SLOs and small requests while an expensive one wins at tight SLOs and long requests. On an 8B at 64 req/s that is 1x H100 + 1x L4 at **$2,160/mo** against the best single type at **$2,304** -- the last 0.9 req/s is cheaper on a small GPU than on a second big one. A mix presumes a capability-aware router that no serving engine ships, so every mixed plan says so, and the reported provenance is the worst across the types used rather than the best.
- **Cost realism** (`--duty-cycle`, `--gpu-price-multiplier`): the headline $/1M-tok prices a saturated fleet. You also pay for provisioned headroom and for every idle hour, so the effective figure on an 8B at 2 req/s is **$2.71/1M at full duty and $9.04/1M at 30%**, against $0.92 at capacity. Spot/reserved pricing is your input, not a bundled guess.
- **Self-host vs API break-even** (`--compare-api`): prices your workload against hosted APIs and reports the monthly volume where self-hosting starts winning. Prices are a **dated snapshot with a source URL per provider**, flagged stale past 90 days -- never presented as a live quote -- and a frontier API is labeled as a different quality tier rather than passed off as like-for-like.
- **Prefix caching** (`--prefix-cache-hit-rate`): chatbot and agent traffic reuse a long system prompt, so most of the prefill is already cached. At a 4k prompt and a 90% hit rate an 8B goes from 166ms to 17ms TTFT. Defaults to 0 and is never inferred, and the KV a shared prefix saves is deliberately not deducted -- under-sizing KV is what turns "it fits" into an OOM.
- **Reasoning models** (`--reasoning-tokens N`): hidden thinking tokens are decoded by the GPU and held in KV even though the caller never sees them. Counting only visible output under-counts decode by the reasoning ratio -- 1000 hidden tokens took an 8B plan from 363ms to 6128ms p95 in our own check. Defaults to 0 and is never inferred: the ratio is a property of your workload, not the weights.
- **Attention-shape aware KV:** MLA (DeepSeek-V2/V3) caches a compressed latent rather than per-head K/V -- sizing it as GQA overstates DeepSeek-V3's cache by **57x** -- and sliding-window models stop growing the cache past the window. A window whose layer pattern isn't declared is *not* applied, because under-sizing KV is what turns "it fits" into an OOM.
- **Mixture-of-Experts aware:** VRAM sizes on *total* params (every expert stays resident) while throughput and TTFT use *active* params (a token only reads the experts it routes to). Treating an MoE model as dense under-predicts its throughput by 3.6x on Mixtral-8x7B and ~18x on DeepSeek-V3. Active counts are derived from the model's real expert geometry and match published figures.
- **Energy** (`--electricity-rate`): monthly kWh cost, `$/1M-tok (+energy)`, and tok/s-per-watt, reported alongside (not folded into) the budget gate.
- **Launch-command export** (`--launch`): emits the `vllm serve` / `ollama run` / TGI `docker run` command for the winning config, with the plan's own context length, TP/PP degree, batch size, and KV dtype filled in -- the flags that are error-prone to hand-compute. It won't fabricate what it can't derive: a GGUF quant level becomes a note to serve the native-equivalent checkpoint, not an invented `--quantization` flag.
- Per-prediction provenance (`measured` / `extrapolated` / `derived` / `estimated` / `unknown`); explains the binding gate when nothing fits.
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

### `workload` -- derive plan inputs from real traffic

```bash
chimeraforge workload --from-log requests.jsonl --out workload.json
chimeraforge workload --from-metrics http://localhost:8000/metrics --engine vllm --out workload.json
chimeraforge plan --model-size 8b --hardware "RTX 4090 24GB" --workload-profile workload.json
```

Reads the request rate, prompt/output lengths, traffic variance and prefix-cache hit rate off a JSONL request log or a live vLLM/SGLang `/metrics` endpoint, so `plan` stops taking them as typed-in guesses. The variance one matters most -- it drives the whole queueing tail, and a measured CV^2 is not one of four presets.

Metric names are per-engine and explicit; an unknown `--engine` is an error and pointing the wrong one at an endpoint fails loud, because a scraper that silently falls back to a renamed metric reports a fabricated measurement. A log yields `measured` mean and variance; a Prometheus histogram yields an exact mean but a bucket-approximated variance, labeled `estimated`. A single scrape is not a rate, so `request_rate` stays absent rather than being divided out of an unmeasured uptime -- and any field the source did not expose stays a required input to `plan`, never a default. An explicit flag always beats the profile.

### `validate` -- audit predictions against measurements

```bash
chimeraforge validate --matrix matrix.json --measurements captured.json
```

Scores the planner's own predictions by provenance class, so "estimated" carries a number instead of a vibe. The config matrix is **fingerprinted into the audit** (SHA-256, order-independent), so a matrix edited after seeing results no longer matches its own report -- pre-registration, not post-hoc selection. Every cell is published, the worst case survives aggregation rather than being averaged away, and a class with too few cells is labeled underpowered instead of quoted as a rate.

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

Where `plan --safety-target` *decides* from bundled TR134/TR142 data, `safety` *measures*: it runs your probe prompts against a live model, classifies refusals (rule-based -- the TR134 regex baseline), reports the measured refusal rate vs the bundled gate data (expected, drift, RTSI risk tier), and exits 1 below `--safety-target`. **You provide the prompts** (`--prompts`, one per line) -- no attack corpus ships with the package; point it at HarmBench / AdvBench / your own set. Needs a running Ollama.

### `bench` -- live inference benchmarking

```bash
chimeraforge bench --model llama3.2-3b --runs 5
chimeraforge bench --model llama3.2-3b --all-quants --context 512,1024,2048,4096 --json
chimeraforge bench --model llama3.2-3b --backend vllm --base-url http://localhost:8000
```

Three workload profiles (single / batch / server-Poisson); measures throughput, TTFT, and latency with p50/p90/p95/p99; CV-based stability warnings; JSON output.

### `eval` -- quality evaluation

```bash
chimeraforge eval --task general_knowledge --json
chimeraforge eval --predictions preds.txt --references refs.txt --model llama3.2-3b
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
```

Markdown (GitHub-compatible) and self-contained, XSS-safe HTML; statistical analysis (RMSE, MAE, MAPE, R^2) with per-config percentile tables.

### `mcp` -- serve the planner to AI assistants

```bash
chimeraforge mcp
```

Runs the stdio MCP server described above. Requires `pip install "chimeraforge[mcp]"`.

---

## What's modeled

| Dimension | How it's computed | Provenance |
|-----------|-------------------|------------|
| VRAM / KV-cache | First-principles from real model architecture; KV-quant and TP/PP-aware sharding | derived (exact arithmetic) |
| Max concurrency | KV-cache-bound sequences per GPU | exact |
| Throughput (decode) | Measured lookup on the reference rig; bandwidth-scaled off it elsewhere; else roofline | measured / extrapolated / estimated |
| TTFT (prefill) | Compute-bound, GPU FP16 TFLOPS x MFU | estimated |
| Quality | Measured composite lookup, family-prior estimate, or unknown | measured / estimated / unknown |
| Cost | GPU $/hr x fleet size ($/1M-tok invariant in replica count) | exact |
| Energy | TDP-driven monthly kWh, $/1M-tok (+energy), tok/s-per-watt | estimated |
| Safety | TR134/TR142 refusal-rate lookup (opt-in gate) | measured / unknown |

**Hardware:** 22 GPUs -- consumer Ada + Blackwell (RTX 30/40/50-series), datacenter (A100 40/80GB, H100, H200, B200, L4, T4), and AMD MI300X -- each with VRAM, bandwidth, FP16 TFLOPS, TDP, and interconnect (NVLink/Infinity Fabric/PCIe).

**Known limits (honest):** Speculative decoding is not yet modeled. Prefix caching models the prefill saving but not the KV saving (deliberately conservative). Reasoning tokens are modeled but the ratio is your input (`--reasoning-tokens`), never inferred. For MoE, active-vs-total params *are* modeled, but expert parallelism and routing load-imbalance are not. Multi-LoRA sizes adapter VRAM exactly, but its decode cost is a rank-indexed estimate from a single published sweep, and per-adapter KV fragmentation is not modeled. Heterogeneous fleets solve the allocation exactly but assume a request router that no engine currently provides, and inherit the throughput-estimate error of every GPU type in the mix. Quant coverage for vLLM/TGI/SGLang is FP16 + FP8 + AWQ/GPTQ; FP8 and W4A16 quality are estimated, not measured -- the TR quality corpus only covers GGUF k-quants. TP and PP throughput are comms-modelled *estimates*, not measured, and can't be combined in one plan. Queueing is analytical (variance-aware), not a discrete-event simulator. The bundled corpus is fit primarily on one rig (RTX 4080 12GB); other GPUs scale from bandwidth/compute until you `measure` on yours. The MCP server is stdio-only (Claude Code/Desktop, local Cursor) -- no hosted remote transport yet.

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

**Headline findings** (full data in the TRs): Rust beats Python single-agent (+15.2% throughput, -58% TTFT, -67% memory -- TR112); dual Ollama reaches near-perfect multi-agent parallelism (~99%) vs 82.2% on one instance (TR110/TR113/TR114); vLLM's continuous batching gives a 2.25x edge at N=8, bottlenecked on GPU memory bandwidth, not the stack (TR130-TR132).

**Full research:** [`docs/archive/technical_reports.md`](docs/archive/technical_reports.md) indexes all 32 reports; the full archive with methodology and raw-data references lives in [`outputs/publish_ready/reports/`](outputs/publish_ready/reports/).

---

## How the numbers are made

- **~204,000 primary measurements** across 32 technical reports (TR108-TR137 + the TR142/TR146 safety provenance), on an RTX 4080 Laptop (12 GB; 192-bit GDDR6, 432 GB/s), which is the reference rig every cross-GPU estimate is scaled from. De-duplicated: TR137/TR142 are syntheses of already-counted data.
- **Rigor:** fresh-process isolation per run (no warm-cache bias), forced cold starts, 3-5 runs per config for statistical confidence, structured JSON/CSV logging with full provenance. Every claim traces to raw data you can re-run.
- **Program context:** ChimeraForge is the actionable CLI splice of the parent Banterhearts program (~1,337,000 primary + judge measurements across 54 TRs); the safety attack-surface and serving-stack research lives in sibling repos.
- **1,429 automated tests** (`pytest tests/`) cover the planner models, gate search, resolver, discovery, safety, bench backends, and the MCP server -- GPU-decoupled, no live backend required for the core suite.

Reproduce any number: find the claim in a report under `outputs/publish_ready/reports/`, follow its reference to the data folder, inspect the CSV/JSON, and re-run the provided scripts or notebooks. See [`docs/archive/methodology.md`](docs/archive/methodology.md).

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
- **[`docs/archive/technical_reports.md`](docs/archive/technical_reports.md)** -- index of all 32 technical reports
- **[`docs/archive/dual_ollama_setup.md`](docs/archive/dual_ollama_setup.md)** -- required for reproducing multi-agent results
- **[`docs/archive/methodology.md`](docs/archive/methodology.md)** / **[`docs/archive/rust_vs_python.md`](docs/archive/rust_vs_python.md)** -- methodology and the full language comparison

## Contributing

Contributions welcome -- see [`CONTRIBUTING.md`](CONTRIBUTING.md). Good areas: additional benchmark configs, new optimization strategies, more models/hardware, docs, and analysis tools.

## License

MIT -- see [LICENSE](LICENSE).

## Acknowledgments

Conducted as part of the Banterhearts LLM Performance Research Program: Phase 1 (TR108-TR122) established the measurement methodology and cross-language comparison, Phase 2 (TR123-TR133) produced the deployment framework and capacity planner, and Phase 3 (TR134-TR137) measured the safety cost of inference optimization -- now the planner's opt-in safety gate.

---

**Repository:** https://github.com/Sahil170595/Chimeraforge - **PyPI:** https://pypi.org/project/chimeraforge/ - **Status:** Beta, actively developed
