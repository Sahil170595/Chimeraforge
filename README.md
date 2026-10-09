# Chimeraforge

[![PyPI version](https://img.shields.io/pypi/v/chimeraforge.svg)](https://pypi.org/project/chimeraforge/)
[![Python](https://img.shields.io/pypi/pyversions/chimeraforge.svg)](https://pypi.org/project/chimeraforge/)
[![CI](https://github.com/Sahil170595/Chimeraforge/actions/workflows/ci.yml/badge.svg)](https://github.com/Sahil170595/Chimeraforge/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

<!-- mcp-name: io.github.Sahil170595/chimeraforge -->

**A local-first, model-agnostic LLM deployment planner.** It turns "which model, quantization, GPU, and backend -- how many, will it fit, will it hit my SLO, what will it cost" into a fast answer with explicit evidence and assumptions, from your shell, your Python, or your AI assistant.

```bash
uvx chimeraforge plan --model-size 8b --hardware "RTX 4090 24GB"
```

## The trust principle

**Every number is labeled `measured`, `extrapolated`, `derived`, `estimated`, or `unknown`, and the tool refuses to fake the ones it can't stand behind.** VRAM and KV-cache are `derived` -- exact arithmetic over the model's real architecture, not a measurement. Throughput is a measured lookup only on the rig the corpus was measured on; on any other GPU that row is scaled by memory bandwidth and reported as `extrapolated`, carrying the row it came from, the rig it was measured on and the ratio applied, because a 17.8x bandwidth extrapolation (RTX 4080 Laptop 432 GB/s -> B200 7700 GB/s) is not a measurement of your card. Failing that it is an explicit roofline `estimate` -- never presented as data it isn't. Quality below the bundled corpus reports `unknown`, not a made-up score. A 0-result plan names the exact gate that rejected every candidate instead of a generic "nothing found." No telemetry, no phone-home, works air-gapped.

Give it a model -- a size class, a Hugging Face repo, an Ollama tag, or manual overrides for an unreleased model -- and it searches the (model x quantization x backend x GPU count x tensor/pipeline parallelism) space against VRAM, quality, latency, cost, energy, and an opt-in safety gate, then hands back the cheapest config that meets your SLO.

**21 commands, one tool:** `plan` - `check` - `bundle` - `study` - `deploy` - `suggest` - `measure` - `workload` - `monitor` - `validate` - `doctor` - `contribute` - `catalog` - `safety` - `bench` - `eval` - `compare` - `refit` - `report` - `mcp` - `serve`.

The empirical corpus traces to Technical Reports TR108-TR137 (~204,000 real measurements on consumer GPUs). See the [CHANGELOG](CHANGELOG.md) for the full feature history.

<!-- corpus-shape:start (scripts/corpus_shape.py --write; do not edit by hand) -->
**What the planner itself reads.** The ~204,000 measurements are the research program's total across its reports. The tables `plan` looks numbers up in are far smaller:

| Table | Size | Shape |
|---|---|---|
| Decode throughput | 23 rows | FP16 only; 7 models, the largest llama3.2-3b at 3.21B; 9 rows on serving engines (ollama 3, tgi 3, vllm 3) and 14 on transformers research harnesses; every row measured on one GPU, the RTX 4080 Laptop 12GB (192-bit GDDR6, 432 GB/s) |
| Quantization speedups | 7 multipliers | applied to an FP16 row; a quantized throughput is never a measurement of that quant |
| Quality | 35 model x quant cells | n=20 items each (TR125) |
| Safety | 40 model x quant cells | refusal rate (TR134/TR142) |
| Latency service times | 9 | model x backend |
| Third-party audit | 42 scored cells on 17 GPUs | published benchmarks ([scorecard](corpora/SCORECARD.md)); 26 more published but too underspecified to score |

Anything outside those rows is `extrapolated` (scaled by memory bandwidth from the reference GPU), `derived` (exact arithmetic) or `estimated` (roofline), and every number in a plan says which. The data records its own limits:

- Every throughput row is FP16. Quantized throughput is the FP16 row times a quant multiplier, not a measurement of that quant.
- Every row was measured on one GPU. Other hardware is bandwidth-extrapolated and labelled 'extrapolated', not 'measured'.
- The largest model measured is 3.21B; predictions above that extrapolate the power law.
- No SGLang rows exist; that backend falls through to the fp16/power-law path.
<!-- corpus-shape:end -->

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
pip install "chimeraforge[bench]"     # + GPU environment metadata for benchmarks (pynvml)
pip install "chimeraforge[mcp]"       # + MCP server so Claude/GPT/Cursor can call the planner
pip install "chimeraforge[eval]"      # + quality evaluation (ROUGE-L; BERTScore additionally needs `bert-score` + torch)
pip install "chimeraforge[refit]"     # + coefficient refitting (numpy, scipy)
pip install "chimeraforge[all]"       # everything
```

Python 3.10+. The core install covers the planner and network-facing commands (`httpx` is a core dep). Registry planning and the local catalog work offline; HF/Ollama resolution or discovery needs explicit network access. `bench` / `measure` / `safety` need a running backend (Ollama, vLLM, TGI, or SGLang; `safety` supports Ollama only). Windows / macOS / Linux.

**Release and source scope (2026-10-09).** PyPI's released version is
[0.51.0](https://github.com/Sahil170595/Chimeraforge/releases/tag/v0.51.0).
This source README also covers the open review stack
[#105](https://github.com/Sahil170595/Chimeraforge/pull/105) through
[#109](https://github.com/Sahil170595/Chimeraforge/pull/109): saved-plan `check`,
plan-bound `bench` and `monitor`, Streamable HTTP MCP, and contribution
`review`/`replay`. Those additions require the reviewed source rather than the
0.51.0 package. To try that exact source, including MCP:

```bash
pip install "chimeraforge[mcp] @ git+https://github.com/Sahil170595/Chimeraforge.git@97595a4b53d2439c4af25655362b017455a824ab"
```

The checkpoint, bundle and sensitivity options below are further **unreleased source features**. They
require this feature's checkout; neither PyPI 0.51.0 nor the older source pin
above contains them. From this checkout, install with `pip install '.[mcp]'`.

## Quickstart

```bash
# Plan a registry size class on your GPU
chimeraforge plan --model-size 8b --hardware "RTX 4090 24GB" --request-rate 2.0

# Plan ANY model -- a Hugging Face repo or an Ollama tag
chimeraforge plan --model Qwen/Qwen2.5-7B-Instruct --hardware "RTX 4090 24GB"
chimeraforge plan --model ollama:qwen3:14b --ollama-url http://localhost:11434

# Split a model too big for one GPU across several (tensor parallelism)
chimeraforge plan --model Qwen/Qwen2.5-72B-Instruct --hardware "H100 80GB" --tp 4

# Shrink the KV-cache, print the cost/latency/quality trade-off menu
chimeraforge plan --model-size 8b --hardware "RTX 4080 12GB" --kv-quant q8 --pareto

# Benchmark a live model and plan on the MEASURED numbers
chimeraforge plan --model qwen3:14b --measure

# Discover + rank what fits your GPU and budget
chimeraforge suggest --source ollama --hardware "RTX 4090 24GB" --budget 500

# Save and recheck an offline plan (reviewed source; see release scope above)
chimeraforge plan --model-size 3b --hardware "RTX 4090 24GB" --no-network --save offline-plan.json
chimeraforge check offline-plan.json --json
```

### Keep one Hub checkpoint through planning and export

```bash
# Metadata/config only: no model weights are downloaded by the planner
chimeraforge plan --model HuggingFaceTB/SmolLM2-135M-Instruct \
  --revision 12fd25f77366fa6b3b4b768ec3050bf629380bac \
  --hardware "RTX 4080 12GB" --platform linux --request-rate 0.01 \
  --quality-target 0 --budget 100000 --save checkpoint-plan.json --json
chimeraforge check checkpoint-plan.json --json           # offline
chimeraforge check checkpoint-plan.json --network --json # explicit Hub inspection
```

Branches and tags are accepted too; resolution first establishes one immutable
commit, then reads that commit's config and declared file metadata. Repeat
`--revision MODEL=REF` when planning multiple HF models. A cached moving ref is
a dated producing observation, not proof of its current state.

Select a supported saved candidate before [deployment export](docs/deployment.md).
vLLM, TGI and SGLang commands carry `--revision` with the resolved commit; an
Ollama conversion cannot retain that pin and is refused. The receipt hashes the
config bytes actually consumed and records **declared** weight metadata. It
does not verify downloaded weight/tokenizer bytes or identify a running server.
Legacy plans still load with their original identity gaps. See the
[Python checkpoint loop](docs/planning-api.md#checkpoint-identity).

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

For an HTTP-capable MCP client, start the native Streamable HTTP transport:

```bash
chimeraforge mcp --transport streamable-http --port 8766
# Connect the client to http://127.0.0.1:8766/mcp
```

HTTP binds to loopback and defaults to offline model resolution. Only the server
operator can enable Hugging Face lookups/discovery with `--allow-network`; HTTP
tool callers cannot supply local file paths, endpoint URLs, or network overrides.
Ollama endpoint resolution/discovery remains a stdio capability. The SDK rejects
browser Origins, foreign Hosts, and bodies above 64 KiB, including chunked uploads.
Native sessions are capped at 32 and expire after 300 idle seconds. These settings
and the fixed two-worker capacity are configurable through `mcp --help`.
HTTP Hugging Face discovery is capped at 16 models per call before network work
is admitted; stdio keeps its existing discovery options.

HTTP tools run off the protocol event loop. A response times out after 30 seconds;
timed-out or cancelled synchronous work keeps its worker slot until it actually
finishes. Further calls receive a busy error when capacity is occupied, while
protocol ping/discovery stays responsive. Python threads are not forcibly stopped:
server shutdown drains owned work and can wait for a slow underlying resolver.
The transport uses the supported MCP 1.x SDK (`>=1.30,<2`), with its native
Streamable HTTP session and request guards.

Exposes five tools: `chimeraforge_plan` (the full gate search), `chimeraforge_suggest` (the inverse -- rank what actually fits a given GPU), `chimeraforge_compare_api` (self-host vs hosted-API cost and the break-even volume), `chimeraforge_resolve_model` (grounds a model id in its real params/architecture), and `chimeraforge_list_hardware`. Every result carries the same `measured` / `extrapolated` / `estimated` / `unknown` provenance as the CLI, and the tool descriptions tell the model to prefer them over its own knowledge. `chimeraforge_plan` also returns a `launch` field -- the serve command for the recommended config -- so the assistant can answer "and how do I run it" without inventing flags. `chimeraforge_compare_api` prices against a *dated* snapshot and reports its age, so an assistant quotes a price with its capture date rather than presenting a stale figure as current.

---

## Commands

### `plan` -- predictive capacity planner

```bash
chimeraforge plan --model-size 8b --hardware "RTX 4090 24GB" --request-rate 2.0
chimeraforge plan --model Qwen/Qwen2.5-7B-Instruct --hardware "RTX 4090 24GB"   # any HF repo
chimeraforge plan --model ollama:qwen3:14b --ollama-url http://localhost:11434  # any Ollama tag
chimeraforge plan --model Qwen/Qwen2.5-72B-Instruct --hardware "H100 80GB" --tp 4   # multi-GPU
chimeraforge plan --model-size 3b --kv-quant q4 --pareto                       # smaller KV cache, trade-off menu
chimeraforge plan --model-size 8b --hardware "RTX 4090 24GB" --launch          # + the serve command to actually run it
chimeraforge plan --model-size 3b --workload agent --safety-target 0.85 --json
```

- Plans **any** model: registry size class, HF repo (`org/name`), Ollama tag, or manual overrides (`--params-b/--n-layers/...`).
- Searches (model x quantization x backend x N-replicas x batch/GPU) through a 5-gate pipeline: VRAM -> quality -> safety (opt-in) -> latency -> budget.
- Models real serving physics: continuous batching (vLLM/TGI), prefill/decode split (TTFT + TPOT), KV-cache-bound concurrency, and variance-aware queueing (`--workload`).
- **Fits models too big for one GPU:** `--tensor-parallel/--tp {N|auto}` shards weights + KV across N GPUs (Megatron-style, comms-modelled); `--pipeline-parallel/--pp {N|auto}` splits layers across N stages instead (cheaper on slow interconnects, needs batching to fill the pipeline). Not combinable yet.
- **Serves what the backend serves:** GGUF quants are offered on Ollama; vLLM/TGI get FP16 and **FP8** (only on GPUs with FP8 tensor cores -- Ada/Hopper/Blackwell/CDNA3). The planner no longer suggests a GGUF checkpoint on vLLM priced with a llama.cpp speedup.
- **Runs where the engine runs (`--platform linux|windows|wsl2|macos`; default linux, or this machine's OS with `--hardware auto`):** each engine is offered only where its own docs say it runs on that OS and GPU. Refusals happen only on a documented statement, and each one cites the doc:
  - vLLM on native Windows;
  - SGLang or TGI on a consumer Radeon card, where their ROCm docs are Instinct-only;
  - vLLM AWQ/GPTQ on AMD, or FP8 on Intel;
  - TGI AWQ on ROCm.

  Where an engine's docs are silent the plan warns that the configuration is unverified rather than refusing it, and TGI's maintenance mode is always stated.
- **KV-cache quantization** (`--kv-quant {fp16,q8,q4}`) shrinks the cache and raises max concurrency -- biggest win at long context.
- **Heterogeneous fleets** (`--fleet "H100 80GB,A100 80GB,L4 24GB"`): sizes a mix of GPU types instead of N copies of one, because a cheap GPU can win at loose SLOs and small requests while an expensive one wins at tight SLOs and long requests. On an 8B at 250 req/s that is 3x H100 + 1x L4 at **$5,760/mo** against 6x A100 at **$6,912** -- 16.7% cheaper, because the last few req/s are cheaper on a small GPU than on another big one (`plan --model-size 8b --request-rate 250 --fleet "H100 80GB,A100 80GB,L4 24GB" --budget 100000`). A mix presumes a capability-aware router that no serving engine ships, so every mixed plan says so, and the reported provenance is the worst across the types used rather than the best.
- **Cost realism** (`--duty-cycle`, `--gpu-price-multiplier`): the headline $/1M-tok prices a saturated fleet. You also pay for provisioned headroom and for every idle hour, so the effective figure on an 8B at 2 req/s on an H100 is **$2.71/1M at full duty and $9.04/1M at 30%**, against $0.71 at capacity (`plan --model-size 8b --request-rate 2 --hardware "H100 80GB" --budget 100000 --duty-cycle 0.3`). Spot/reserved pricing is your input, not a bundled guess.
- **Hyperscaler on-demand prices** (`--cloud aws|azure`): the bundled datacenter prices are marketplace rates, roughly 4-5x below what AWS and Azure bill on demand. `--cloud` prices the fleet from a dated snapshot of each cloud's public list prices: AWS's EC2 price list for us-east-1, and the Azure Retail Prices API for eastus. Prices are Linux, on-demand and shared tenancy.
  - **Whole instances:** a TP/PP group must fit in one instance, and a partly-filled instance bills every GPU in it.
  - **Example:** the same 8B on one H100 is $1,800/mo at the marketplace rate, $4,954 on AWS (one 1-GPU p5.4xlarge), and $70,790 on Azure. Azure sells the H100 only in an 8-GPU VM, and the plan says 7 of those 8 sit idle (`plan --model-size 8b --request-rate 2 --hardware "H100 80GB" --budget 100000 --cloud azure`).
  - **Sourcing:** each offer's GPU model comes from the cloud's own instance or VM-series page, and its GPU count and memory are checked against the hardware DB. Different cards with similar names are excluded with a reason: Azure's H100 NVL and A100 PCIe VMs, for example. The snapshot is regenerated by `scripts/build_cloud_prices.py` and flagged stale after 90 days.
- **Batch mode** (`--mode batch`): for an offline backlog (a nightly summarisation job, an embedding backfill, an eval sweep) that nobody is waiting on. The latency gate and the 70% utilisation headroom are dropped. Each GPU runs the batch that maximises its throughput, the fleet is the smallest that drains `--request-rate` at full utilisation, and results rank by $/1M tokens rather than by monthly bill.
  - Example: an 8B at 2 req/s on an H100 goes from **$0.66/1M** (Ollama Q2_K, the cheapest online pick) to **$0.065/1M** (vLLM AWQ at batch 267), with the same one GPU at $1,800/mo (`plan --model-size 8b --request-rate 2 --hardware "H100 80GB" --budget 100000 --mode batch`). That throughput is a roofline estimate, and the output says so.
  - A latency target (`--latency-slo`, `--ttft-slo`, `--tpot-slo`) together with batch mode is an error, not ignored. The reported request time is service only, with no queue wait, because a backlog's wait depends on its size. `--pareto` trades $/1M tokens against quality.
- **Self-host vs API break-even** (`--compare-api`): prices your workload against hosted APIs and reports the monthly volume where self-hosting starts winning. Prices are a **dated snapshot with a source URL per provider**, flagged stale past 90 days -- never presented as a live quote -- and a frontier API is labeled as a different quality tier rather than passed off as like-for-like.
- **Disaggregation advisory**: prefill/decode disaggregation is not modelled. There is no closed-form prefill:decode ratio, and vLLM's own docs say it "DOES NOT improve throughput". What the planner does instead is mark candidates that sit where the published sources say it is worth considering, quote those sources, and predict nothing.
  - **When it appears:** the plan gates both `--ttft-slo` and `--tpot-slo`, it is serving online, it uses more than one GPU, and the engine (vLLM or SGLang) documents the feature. Every condition maps to a sentence in DistServe (OSDI 2024) or in the engine's docs at the planner's pinned tags.
  - **What it reports:** this plan's prefill share of modeled request service time, using the session-limited TTFT when residency is enabled, and the GPU's interconnect, since the KV handoff needs a fast link.
- **Prefix caching** (`--prefix-cache-hit-rate`): chatbot and agent traffic reuse a long system prompt, so most of the prefill is already cached. At a 4k prompt and a 90% hit rate an 8B on an H100 goes from 166ms to 17ms TTFT (`plan --model-size 8b --prompt-tokens 4096 --hardware "H100 80GB" --budget 100000 --prefix-cache-hit-rate 0.9`); the same query on the reference RTX 4080 is 2051ms to 205ms. Defaults to 0 and is never inferred, and the KV a shared prefix saves is deliberately not deducted -- under-sizing KV is what turns "it fits" into an OOM.
- **Multi-turn session residency** (`--think-time SECONDS --session-turns T`): a conversation's next turn hits the prefix cache only if its KV survived the user's think time. Between turns the conversation is idle (it is not decoding, and the concurrency ceiling does not count it), but its prefix still has to sit in the KV pool.
  - **How it is computed:** by Little's law the fleet holds `rate x (T-1)/T x think time` idle conversations at once. The planner computes how many of their prefixes each (replicas x batch) config's free KV can hold, and limits the stated hit rate to that share. TTFT is computed from the limited rate inside the search, so more replicas genuinely help.
  - **Example:** an 8B at 2 req/s with 4k prompts and 60 s between turns has 108 idle conversations. One RTX 4090's free KV holds 19 of them, so a stated 90% hit rate becomes 16%, and TTFT goes from 100ms to 837ms (`plan --model-size 8b --hardware "RTX 4090 24GB" --request-rate 2 --prompt-tokens 4096 --context-length 8192 --prefix-cache-hit-rate 0.9 --think-time 60 --session-turns 10`).
  - **Assumptions, stated in the output:** session-affinity routing, so a returning turn reaches the replica holding its prefix, and eviction that keeps idle conversations at random relative to when they return. Ollama keeps one conversation per replica slot. Off unless both flags are given.
- **Reasoning models** (`--reasoning-tokens N`): hidden thinking tokens are decoded by the GPU and held in KV even though the caller never sees them. Counting only visible output under-counts decode by the reasoning ratio -- 1000 hidden tokens take an 8B plan on an H100 from 193ms to 3664ms p95 (`plan --model-size 8b --hardware "H100 80GB" --budget 100000 --reasoning-tokens 1000`). Defaults to 0 and is never inferred: the ratio is a property of your workload, not the weights.
- **Attention-shape aware KV:** MLA (DeepSeek-V2/V3) caches a compressed latent rather than per-head K/V -- sizing it as GQA overstates DeepSeek-V3's cache by **57x** -- and sliding-window models stop growing the cache past the window. A window whose layer pattern isn't declared is *not* applied, because under-sizing KV is what turns "it fits" into an OOM.
- **Mixture-of-Experts aware:** VRAM sizes on *total* params (every expert stays resident) while throughput and TTFT use *active* params (a token only reads the experts it routes to). Treating an MoE model as dense under-predicts its throughput by 3.6x on Mixtral-8x7B and ~18x on DeepSeek-V3. Active counts are derived from the model's real expert geometry and match published figures.
- **Energy** (`--electricity-rate`): monthly kWh cost, `$/1M-tok (+energy)`, and tok/s-per-watt, reported alongside (not folded into) the budget gate.
- **Operational carbon** (`--grid-region USA|DEU|France|...` or `--carbon-intensity G`): gCO2e per 1M tokens and kg per month, computed as that same energy times the grid's carbon intensity. An 8B at 2 req/s on an H100 comes to **60 gCO2e per 1M tokens on the US grid and 6.5 on France's** (`plan --model-size 8b --request-rate 2 --hardware "H100 80GB" --budget 100000 --grid-region USA`).
  - Intensity is Ember's annual-average lifecycle figure per country, via Our World in Data, pinned to an OWID commit and regenerated by `scripts/build_carbon_data.py`. The year is printed with every figure, and a figure more than 2 years old is flagged stale.
  - It is the SCI operational term only (O = E x I). Embodied emissions are not modelled, so it is not a full SCI score.
  - E is board power with no host or datacenter PUE, so the figure is a lower bound. An unknown TDP gives unknown carbon, never zero.
- **Launch-command export** (`--launch`): emits the `vllm serve` / `ollama run` / TGI `docker run` command for the winning config, with the plan's own context length, TP/PP degree, batch size, and KV dtype filled in -- the flags that are error-prone to hand-compute. It won't fabricate what it can't derive: a GGUF quant level becomes a note to serve the native-equivalent checkpoint, not an invented `--quantization` flag.
- Per-prediction provenance (`measured` / `extrapolated` / `derived` / `estimated` / `unknown`); explains the binding gate when nothing fits.
- Validated on registry data: VRAM R^2=0.968, throughput R^2=0.859, quality RMSE=0.062, latency MAPE=1.05% (beats analytical M/D/1 by 20.4x, TR133). No ML -- empirical lookup tables with first-principles interpolation (roofline for off-registry models).

### `check` -- recheck a saved plan offline

```bash
chimeraforge plan --model-size 3b --no-network --save plan.json
chimeraforge check plan.json --json
```

Compare consumed inputs, local pricing, feasibility, candidate order and modeled
deltas without changing the saved file. New snapshots bind full model geometry,
GPU/platform and input receipts; legacy snapshots report missing bindings as
unverified. Checks never enable network access from a saved permission or probe
a new host for an `auto` plan. Exit 0 means required modeled components are
unchanged, 1 means changed/expired/unverified required evidence, and 2 means
malformed input. A stable modeled recommendation does not prove serving
performance or identify immutable model weights. See [the API contract](docs/planning-api.md).

### `bundle` -- portable saved-plan handoff

This is an unreleased feature of this checkout, beyond PyPI 0.51.0 and the older
review-stack install pin above. Install this checkout with `pip install .`.

**Harness files may contain private prompts or other data. Review the exact
inputs before sharing a bundle.** Creation copies only the original plan and its
bound coefficient/quality files; original bytes, paths and fingerprint stay intact.

```bash
chimeraforge bundle create plan.json --out handoff
# Move the whole handoff directory to the receiving machine.
chimeraforge bundle verify handoff --json
chimeraforge bundle check handoff --json
```

Rechecks use verified input bytes offline even after producer files are removed.
JSON shows producer and local source locations separately. Current tool, policy,
hardware and applicable price/cloud changes remain actionable; verification alone
is not a passed plan check. `verify` exits 0 for verified content, `check` exits
0 for unchanged required facts or 1 for changed, expired or required unverified
facts, and malformed/unsupported bundles exit 2. Legacy plans without byte
bindings and nonempty contribution dependencies are refused before writing.
Integrity does not authenticate a source or prove served weights or performance.
See [the portable workflow](docs/planning-api.md#portable-plan-bundles).

### `study` -- frozen-context workload and cost sensitivity

An unreleased feature of this checkout. Use `pip install .` from this source.
Compare explicit assumptions against one saved plan or portable bundle offline:

```json
[
  {"name": "twice-the-load", "changes": {"request_rate": 2}},
  {"name": "half-duty", "changes": {"duty_cycle": 0.5}},
  {"name": "no-budget", "changes": {"budget": 0}}
]
```

Save that list as `cases.json`, then run:

```bash
chimeraforge study plan.json --cases cases.json --out study.json --json
# A portable bundle works even with the producer's input files absent.
chimeraforge study handoff --cases cases.json --json
```

The ordinary search uses the same bound model/GPU geometry and verified
coefficient/quality bytes for every case. Current engine-support, applicable
cloud prices, grid intensity, quarantine records and their time observations
are captured once. The report distinguishes those current facts from producer
receipts, retains infeasible cases with gate reasons, and compares configurations
and estimates in native units. A changed policy identity aborts the study.

Supply 1-16 unique cases for up to 16 bound model targets. Workload, context,
SLOs, quality/safety targets, budget, duty and cost assumptions may change;
model, physical hardware and platform stay fixed. `gpu_cost_per_hour` is an
operator price assumption, is refused for cloud instance pricing, and zero
keeps the native unknown-price behavior. Output cannot overwrite known inputs.
Exit 0 means a completed modeled study, including infeasible cases; invalid or
unavailable inputs exit 2. No weights are downloaded or serving traffic generated.
Integrity and modeled deltas do not authenticate inputs or qualify performance.
See [the Python and case contract](docs/planning-api.md#frozen-context-sensitivity).

### `deploy` -- export serving configuration

Export one saved candidate as Compose, a systemd user service, an Ollama macOS
LaunchAgent, or a Modelfile. No engines are installed, started or deployed.

```bash
mkdir deployment
chimeraforge plan --model Qwen/Qwen2.5-1.5B-Instruct --hardware "RTX 4090 24GB" --ttft-slo 500 --tpot-slo 50 --save plan.json
# Bash: select a single-replica, resident vLLM FP16 candidate from this artifact.
CANDIDATE_INDEX=$(python -c "import json; p=json.load(open('plan.json')); print(next(i for i,c in enumerate(p['result']['candidates']) if c['backend']=='vllm' and c['quant']=='FP16' and c['n_agents']==1 and c['offload_fraction']==0))")
chimeraforge deploy --plan plan.json --candidate-index "$CANDIDATE_INDEX" --format compose --image vllm/vllm-openai:v0.30.0 --out deployment/compose.yaml
```

On PowerShell, assign the same Python selection with `$CANDIDATE_INDEX = python -c "..."`.
Inspect the saved candidate before exporting; the selection fails if none matches.
The first candidate is not necessarily vLLM or the checkpoint's native precision.
The image tag is an explicit example, not an assertion that it was run; use your
qualified engine image or a digest for fixed image bytes. Output files must be new.
Select a candidate matching the explicit image's backend. Unsupported fleets,
offload, unresolved adapter paths and checkpoint/KV mismatches fail clearly.
Ollama emits daemon settings and a companion Modelfile with required provisioning
steps. Native units require an explicit installed executable path. See
[supported templates and config validation](docs/deployment.md). Config acceptance
does not establish GPU execution or prediction accuracy.

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

SGLang ships with no measured rows, and the planner says so rather than borrowing vLLM's. Measure your own: `chimeraforge measure --backend sglang --model <served-model-name> --base-url http://localhost:30000`. The vLLM, TGI and SGLang adapters stream and time the first and last token, so they record the **decode** rate the planner predicts rather than tokens over wall clock, which includes prefill. TTFT is reported separately. The token count comes from the server (the `usage` block, or TGI's final `generated_tokens`). A response without one is discarded, not estimated.

### `workload` -- derive plan inputs from real traffic

```bash
chimeraforge workload --from-log requests.jsonl --out workload.json
chimeraforge workload --from-metrics http://localhost:8000/metrics --engine vllm --out workload.json
chimeraforge workload --from-metrics http://localhost:8000/metrics --interval 60 --engine vllm --hardware "H100 80GB"
chimeraforge plan --model-size 8b --hardware "RTX 4090 24GB" --workload-profile workload.json
```

Reads the request rate, prompt/output lengths, traffic variance and prefix-cache hit rate off a JSONL request log or a live vLLM/SGLang `/metrics` endpoint, so `plan` stops taking them as typed-in guesses. The variance one matters most -- it drives the whole queueing tail, and a measured CV^2 is not one of four presets.

- **A window** (`--interval 60`) scrapes twice and times the real gap. Two saved scrapes with `--interval` work too, and the output labels that interval as stated rather than measured. A window turns the counters into a **measured request rate**, and the means, variance and cache hit rate describe the window rather than the engine's lifetime. A counter reset between the scrapes (an engine restart) is an error.
- **KV-cache pressure** is read from vLLM's `kv_cache_usage_perc` and SGLang's `token_usage`, plus its SWA and Mamba pools when they are non-zero. All are fractions 0-1, and each is labeled instantaneous.
- **MFU and MBU** come from each engine's FLOP and byte counters over a window, against the `--hardware` card's dense FP16 peak and memory bandwidth. They are labeled `estimated`, because the counts come from the engine's own analytical model rather than hardware counters. The counters exist only when the server runs with `--enable-mfu-metrics`, and the profile says so when they are missing.
- Names were read from vLLM v0.30.0 and SGLang v0.5.20 source. The test fixtures are real `prometheus_client` output from those declarations (`scripts/make_engine_metrics_fixtures.py`). A hand-typed fixture had hidden that the vLLM prefix-cache counters are exposed with a `_total` suffix, so that hit rate was never read from a real endpoint until now.

Metric names are per-engine and explicit; an unknown `--engine` is an error and pointing the wrong one at an endpoint fails loud, because a scraper that silently falls back to a renamed metric reports a fabricated measurement. A log yields `measured` mean and variance; a Prometheus histogram yields an exact mean but a bucket-approximated variance, labeled `estimated`. A single scrape is not a rate, so `request_rate` stays absent rather than being divided out of an unmeasured uptime -- and any field the source did not expose stays a required input to `plan`, never a default. An explicit flag always beats the profile.

### `validate` -- audit predictions against measurements

```bash
chimeraforge validate --matrix matrix.json --measurements captured.json
```

Scores the planner's own predictions by provenance class, so "estimated" carries a number instead of a vibe. The config matrix is **fingerprinted into the audit** (SHA-256, order-independent). Pass that hash back with `--expect-fingerprint <hash>` and the command fails unless the matrix still hashes to it, so a matrix edited after seeing results cannot be passed off as the one that was registered -- pre-registration, not post-hoc selection. Without the flag the fingerprint is recomputed from whatever matrix was loaded and only printed, which proves nothing on its own. Every cell is published, the worst case survives aggregation rather than being averaged away, and a class with too few cells is labeled underpowered instead of quoted as a rate.

Measurements are sourced records, not bare numbers. Each cell states:

- who measured it: `own-rig-measured` or `third-party-measured`, which are separate scorecard rows and never averaged together;
- where it came from: a `source_url`, or for own-rig runs the recorded bench environment;
- a `captured_at` date;
- whether the source omitted its serving config (`underspecified`), which keeps the cell out of the headline rows but still publishes it;
- which quantity each number is: `decode_tps_single_stream`, `e2e_tps_single_stream`, `prefill_tps` (converted to TTFT at the cell's prompt length), `ttft_ms`, `e2e_latency_ms` (one request, batch 1, scored against the planner's service time), `e2e_latency_p95_ms` or `aggregate_tps_at_concurrency`.

An end-to-end or aggregate rate is kept in the raw output but never scored against the planner's decode prediction, and `ambiguous` does not load. A third-party cell citing the TR corpus the planner was fitted on is refused. The v1 shape, `{cell: {metric: value}}`, is refused as unsourced.

```json
{"schema_version": 2, "hardware": "RTX 4090 24GB", "cells": {
  "<model|quant|backend|c..|p..|o..|b1>": {
    "evidence": "third-party-measured", "source_url": "https://...", "captured_at": "2026-09-25",
    "underspecified": false, "config_quote": "llama-bench -ngl 99 -fa 1",
    "metrics": [{"definition": "decode_tps_single_stream", "value": "<tok/s>", "quote": "tg128 | ..."}]}}}
```

The scorecard reports in-band pass rate (against a `bands` tolerance pre-registered in the matrix; `n/a` when none was), median absolute error, GMFE (geometric mean fold error, so 2x high and 2x low score the same), signed bias, and the worst cell. Bands, the consulted-source list and any per-cell `spec` (architecture pinned for offline prediction) are part of the fingerprint. Predictions always come from the bundled corpus unless `--models-path` is given, so a published audit does not depend on what `measure` left in your cache. A batched cell is skipped rather than compared to a single-stream prediction.

**The published audit.** [`corpora/SCORECARD.md`](corpora/SCORECARD.md) grades the planner against 42 cells from 8 published third-party benchmark sources on 17 GPUs. The raw JSON, every exclusion with its rule, and the pre-registered source list are all committed, and the write-up is [TR147](outputs/publish_ready/reports/Technical_Report_147.md). Every audited prediction is a roofline estimate.

On fully specified cells, decode is inside +-25% only **13%** of the time, with a median absolute error of **35.9%** (n=15). The errors split by memory type in opposite directions:

- **HBM datacenter parts:** decode is **over**-predicted by a median of **+58%**, up to +206% on a B200. llama.cpp measures 200-308 tok/s across A100/H100/H200/B200/MI300X, while the roofline scales with bandwidth.
- **GDDR consumer cards:** decode is **under**-predicted by a median of **-36%**.

Read a roofline decode figure on an HBM part as an upper bound. Regenerate the audit with `python scripts/build_validation_corpus.py --write --audit`. A test fails if the published audit goes stale or its error bands widen.

### `monitor` -- observe explicit latency SLOs

```bash
chimeraforge monitor --backend vllm --url http://localhost:8000 --model YOUR_SERVED_MODEL \
  --ttft-slo 500 --tpot-slo 50 --interval 30 --windows 1 --json
# After starting the selected candidate and generating traffic, bind its saved targets.
chimeraforge monitor --from-plan plan.json --candidate-index "$CANDIDATE_INDEX" \
  --backend vllm --url http://localhost:8000 --model Qwen/Qwen2.5-1.5B-Instruct --windows 1 --json
```

Observes existing traffic through two-scrape histogram windows. Reports P95 bucket bounds against explicit millisecond targets, with `pass` (exit 0), `breach` (3), or `unknown` (4); an operational error exits 1. Missing data, no traffic, resets and buckets straddling a target cannot pass. SGLang TTFT is supported; its ITL histogram cannot establish per-request TPOT. `--from-plan plan.json --candidate-index 0` binds the saved candidate and target sources to passive serving metadata. Known identity/configuration disagreements exit 5 separately from native SLO outcomes; unavailable required endpoint identity exits 4. GPU geometry, fleet topology, workload and immutable weights remain explicitly unverified when unavailable. Independent plan-binding and native SLO Prometheus gauges are documented in [the monitoring guide](docs/monitoring.md). This does not claim calibrated prediction drift or generate traffic.

### `doctor` -- check this machine (read-only)

```bash
chimeraforge doctor            # detected GPUs, what the planner can do with each, local engines
chimeraforge doctor --json     # the same report as JSON
```

This command detects the local platform with each vendor's own tool and changes nothing. Each probe names the tool it used, and a missing tool is reported as a finding, not an error.

- **NVIDIA:** `nvidia-smi` for devices, pynvml for the CUDA version.
- **AMD on Linux:** `amd-smi`, or the deprecated `rocm-smi`. When a card is unlisted, its own reported bandwidth fills `--gpu-bandwidth-gbps`.
- **Apple Silicon:** `system_profiler`, reported as unified memory.
- **Intel:** `xpu-smi`. Its PCI-ID device names are never guessed into a product.
- **Windows, any vendor:** CIM plus the display-class registry. `Win32_VideoController.AdapterRAM` is a uint32 and caps at 4 GB, so the driver's `qwMemorySize` is read instead. An integrated GPU's figure is labelled a shared-memory aperture, not VRAM.
- **WSL:** detected from `WSL` in the kernel release. Microsoft notes "microsoft" alone appears in non-WSL kernels.

Exit codes are not trusted, since `rocm-smi` exits 0 with nothing to report. The parsers are golden-tested against real captures, with each source and license listed in `tests/fixtures/doctor/SOURCES.md`.

Every device gets a planner status:

- `matched`: a database entry, plus the flag to plan it with.
- `supply-figures`: not in the database, so the `--gpu-*` flags it needs are listed. A number is filled in only where the tool reported dedicated VRAM.

Local serving engines are probed on the same default URLs `bench` uses. An engine counts as running only when it identifies itself through its version endpoint. A generic web app answering `/health` on :8000 is reported as "answers but did not identify as vllm", not as vLLM. (`check` is reserved for plan drift detection.)

`doctor` also shows the **engine-support matrix** row for the platform it detected. The rows are linux-cuda, linux-rocm, linux-xpu, windows-native, windows-wsl2, macos-apple-silicon and cpu.

Each cell comes from the engine's own docs, at a pinned release: vLLM v0.30.0, SGLang v0.5.20, TGI v3.3.7 and Ollama v0.34.4. Every claim carries a verbatim quote and a `/blob/<tag>/` URL, and silence is recorded as `not documented`, not guessed.

What the matrix says:

- vLLM does not run natively on Windows; it runs under WSL2.
- On ROCm, vLLM lists consumer Radeon cards (RDNA3/4), while SGLang and TGI are Instinct-only.
- Ollama is the one engine documenting native Windows AMD support.
- TGI's repository is archived and in maintenance mode.

`scripts/build_engine_support.py` rebuilds and validates the matrix. `doctor` warns once it is more than 90 days old.

### `contribute` -- share bench results, quarantine others'

```bash
# Serve the FP16 checkpoint first; --quant records its precision.
chimeraforge bench --model llama3.2-3b --backend vllm --quant FP16 --runs 5 --output-dir results/
chimeraforge contribute export results/bench_*.json --out contributions/   # one file per result
chimeraforge contribute verify contributions/*.json              # schema + content hash
chimeraforge contribute import theirs.contribution.json          # into the local quarantine
chimeraforge contribute list
chimeraforge contribute review theirs.contribution.json --decision retain --reason "Replay needed" --json
chimeraforge contribute replay theirs.contribution.json --prompt "Explain KV caching briefly." --output-tokens 128 --runs 3 --base-url http://localhost:8000 --out replay.json --json
chimeraforge plan --model-size 3b --hardware "RTX 4090 24GB" --contributions
```

The first step toward a shared measured corpus.

- **What a contribution holds:** one `bench` result with its full environment fingerprint (GPU, memory, driver, CUDA, OS, engine and version, chimeraforge version), the per-run decode and TTFT figures, and a SHA-256 content id.
- **What export refuses:** a result with no GPU name, fewer than 3 runs, unknown backend-default precision, or a quant sweep label that was not applied. `--quant` declares the served checkpoint's precision; it does not change the server's loaded model. Invalid fingerprints, timestamps, samples, and inconsistent derived statistics are also refused. A decode CV above 5% is flagged as unstable but kept.
- **What the id proves:** contributions are **unsigned**. The id shows the file is unaltered since export, not who ran it or that the numbers are real. That is why imports go into a local quarantine, and nothing there ever reaches the bundled corpus or the `measure` corpus.
- **How `plan --contributions` uses them:** only for an exact model, engine, quant and GPU match, at the median of the matching contributions. The number is labelled `contributed` (`*`), a class below `extrapolated`, along with the contribution ids and the engine/driver clusters it came from. This project's own measured row still wins on the reference rig.

`review` records an unsigned `pending` / `retain` / `reject` disposition and reason,
bound to the original full content id and envelope digest. It reads a file or a
full quarantined id and preserves the source, quarantine and corpus. Disposition
receipts never certify a producer or alter planner eligibility.

`replay` executes the existing benchmark runner against an explicitly contacted
endpoint, requiring a prompt and output-token cap. It records applied workload,
actual tokens, all requested/successful/failed counts, native samples and
before/after serving metadata. Known CPU, engine, quant, model or configuration
disagreements remain distinct from unavailable evidence. GPU names are canonicalized
using observed memory; a client NVML GPU never proves remote execution.

Current contribution v1 omits the original prompt/options/concurrency, immutable
model and remote configuration bindings. Native decode/TTFT differences therefore
remain arithmetic with unverified replay equivalence. Exit 0 means a completed
review or replay operation without a known mismatch, **not a passed reproduction**.
Replay exits 1 for known mismatch, failed/partial execution, and 2 for malformed
input/options or receipt output errors. New receipts cannot overwrite contribution
inputs or be written into quarantine; their endpoint URLs omit credentials/query.

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
# Requires the selected vLLM candidate from the deploy example to be running.
chimeraforge bench --plan plan.json --candidate-index "$CANDIDATE_INDEX" --model Qwen/Qwen2.5-1.5B-Instruct --base-url http://localhost:8000 --prompt "Explain KV caching briefly." --runs 5 --json
```

`bench --plan` binds an immutable saved candidate to actual serving observations
and the applied workload. It records modeled/measured native values, arithmetic
differences, config mismatches and unavailable evidence; supplied quant/TP labels
cannot verify an endpoint. Partial requests and different timing bases cannot
pass a modeled SLO. See [the planning API guide](docs/planning-api.md#benchmark-a-saved-candidate)
for receipts, adapter limits and exit codes. Hosted CPU checks exercise this path
without claiming GPU prediction accuracy.

Three workload profiles (single / batch / server-Poisson); measures throughput, TTFT, and latency with p50/p90/p95/p99; CV-based stability warnings; JSON output.

Before the first request, `bench` (and `measure`) confirms the server at the URL is the engine you named: vLLM through `/version`, TGI through `/info`, SGLang through `/server_info`, and Ollama through its root banner. A port that answers `/health` but does not identify itself is refused, so another web app's numbers are never filed as vLLM.

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

### `serve` -- local planning HTTP API

`chimeraforge serve --port 8765` exposes the validated planner over loopback HTTP, offline by default. `POST /v1/plan` returns a saved-plan artifact; malformed inputs return structured errors. See [the local API contract](docs/rest-api.md).

### `mcp` -- serve the planner to AI assistants

```bash
chimeraforge mcp
chimeraforge mcp --transport streamable-http --port 8766
```

Runs the MCP server described above; stdio is the default, and Streamable HTTP is
an explicit loopback option. Requires `pip install "chimeraforge[mcp]"`.

---

## What's modeled

| Dimension | How it's computed | Provenance |
|-----------|-------------------|------------|
| VRAM / KV-cache | First-principles from real model architecture; KV-quant and TP/PP-aware sharding; MLA/SWA cache shapes; hybrid models cache on attention layers only and carry their recurrent state per sequence | derived (exact arithmetic) |
| Max concurrency | KV-cache-bound sequences per GPU | exact |
| Throughput (decode) | Measured lookup on the reference rig; bandwidth-scaled off it elsewhere; else roofline. An `extrapolated` value carries its anchor: the row, the rig, the ratio | measured / extrapolated / estimated |
| TTFT (prefill) | Compute-bound (GPU FP16 TFLOPS x MFU), floored at the memory-bound weight-read time; chunked prefill via `--max-num-batched-tokens` | estimated |
| Quality | Measured composite lookup, family-prior estimate, or unknown -- every cell carries its sample size and the smallest difference that sample size can resolve; `--quality-from` ingests a real lm-evaluation-harness run | measured / estimated / unknown |
| Cost | GPU $/hr x fleet size ($/1M-tok invariant in replica count) | derived (exact arithmetic) |
| Energy | TDP-driven monthly kWh, $/1M-tok (+energy), tok/s-per-watt | estimated |
| Carbon (opt-in) | Energy x grid intensity (Ember lifecycle gCO2e/kWh via OWID, per country and year); SCI operational term only | estimated |
| Safety | TR134/TR142 refusal-rate lookup (opt-in gate) | measured / unknown |

**Hardware:** 50 GPUs:

- **Consumer:** Ampere/Ada/Blackwell (RTX 30/40/50-series) and AMD RDNA4 (RX 9070 / 9070 XT / 9060 XT).
- **Workstation:** RTX PRO 6000 Blackwell (Workstation, Max-Q, Server), Radeon AI PRO R9700, and Intel Arc Pro B60/B65.
- **Datacenter:** A100 40/80GB, H100, H200, B200, L4, T4, and AMD MI300X/MI325X/MI350X/MI355X/MI455X.
- **Unified memory:** every Apple Silicon chip in a Mac sold today (A18 Pro, M4, M5, M5 Pro/Max/Ultra and M6, by GPU-core variant), plus AMD Ryzen AI Max+ 395 and NVIDIA DGX Spark.

Each has VRAM, bandwidth, FP16 TFLOPS, TDP and interconnect (NVLink/Infinity Fabric/PCIe). Each carries its source URL, capture date, the datasheet column its TFLOPS figure came from, and whether its `$/hr` is a rental rate or an amortised purchase.

**Unified-memory devices** share one pool between the CPU and GPU, so the whole pool is never treated as VRAM:

- `--unified-memory-fraction` states the share the GPU may use. It is required, with no default, because the OS and other apps need theirs.
- Each entry lists every memory configuration sold (the M5 Max 40-core GPU comes with 48, 64 or 128 GB). A named plan assumes the largest and says so, and `--gpu-vram-gb` corrects it. `--hardware auto` uses the installed memory instead.
- The plan warns that one bandwidth figure serves the CPU and GPU, so decode is an upper bound.
- Apple Silicon plans against the macOS row, where vLLM is CPU-only, and Strix Halo against the ROCm row.

A figure the vendor does not publish stays unknown, and unknown is not zero:

- **No price** (RTX PRO 6000, Instinct, Arc Pro, R9700): the budget gate refuses the card instead of pricing it at $0. Pass `--gpu-price-per-hour`.
- **No dense FP16 figure** (Arc Pro, and the RTX PRO 6000 Server Edition, whose "1 PFLOP" is unlabeled): TTFT is reported as the memory-bound floor, a lower bound, and a `--ttft-slo` is refused rather than checked against it. Regenerate and validate with `scripts/build_hardware_data.py`. An **unlisted** GPU is no longer a wall: `--gpu-vram-gb` and `--gpu-bandwidth-gbps` (plus optional `--gpu-fp16-tflops` / `--gpu-tdp-w` / `--gpu-interconnect-gbps` / `--gpu-price-per-hour`) plan any card, and `--hardware auto` reads the installed one.

**Known limits (honest):** Speculative decoding is not yet modeled. The prefill floor is a *bound* derived from `MBU_DEFAULT`, which is calibrated on a single datapoint -- read it as "no faster than", not as a prediction. Chunked-prefill overhead is derived from the KV re-read the mechanism implies and then clamped at the one published ceiling (25% at a 512-token budget, Sarathi-Serve arXiv:2403.02310); the tile-quantization cliff (a 257-token budget measured ~32% slower than 256) is real, sharp, and deliberately *not* modeled -- the planner warns instead. Prefix caching models the prefill saving but not the KV saving (deliberately conservative). Reasoning tokens are modeled but the ratio is your input (`--reasoning-tokens`), never inferred. For MoE, active-vs-total params *are* modeled, but expert parallelism and routing load-imbalance are not. For hybrids, the attention-layer split and the Mamba-2/Mamba-1/gated-DeltaNet recurrent state are read from the model's own config and derived from shapes in transformers source; Kimi's KDA state is inferred from the DeltaNet convention and says so, and a family whose layer pattern cannot be placed (Falcon-H1, a parallel hybrid) keeps full KV on every layer rather than being guessed at. Multi-LoRA sizes adapter VRAM exactly, but its decode cost is a rank-indexed estimate from a single published sweep, and per-adapter KV fragmentation is not modeled. Heterogeneous fleets solve the allocation exactly but assume a request router that no engine currently provides, and inherit the throughput-estimate error of every GPU type in the mix. Quant coverage for vLLM/TGI/SGLang is FP16 + FP8 + AWQ/GPTQ; FP8 and W4A16 quality are estimated, not measured -- the TR quality corpus only covers GGUF k-quants. **The bundled quality corpus is 20 items, which resolves nothing smaller than ~21 percentage points** (Miller, arXiv:2411.00640 Eq. 9), so every measured quant delta in it is reported as indistinguishable from its FP16 baseline rather than as a difference -- run a real harness and pass it with `--quality-from` to get a cell that can support one. Quality is measured at 2K context and reported UNKNOWN for narrow quants at >=64K, where published losses reach 59% (arXiv:2505.20276). TP and PP throughput are comms-modelled *estimates*, not measured, and can't be combined in one plan. Queueing is analytical (variance-aware), not a discrete-event simulator. The bundled corpus is fit primarily on one rig (RTX 4080 12GB); other GPUs scale from bandwidth/compute until you `measure` on yours. How far that scaling misses is now published rather than assumed: against third-party benchmarks the roofline is optimistic on HBM parts (median +58% decode) and pessimistic on GDDR cards (median -36%), and its TTFT errors run the other way ([TR147](outputs/publish_ready/reports/Technical_Report_147.md)). Unified-memory devices plan on a share of the pool that you state (`--unified-memory-fraction`, no default). The OS reserve is your figure, one bandwidth serves the CPU and GPU so decode is an upper bound, and no vendor publishes their GPU FP16 or a per-device price. Engine availability per platform is enforced from each engine's own docs, but the deployment OS is an input (`--platform`, default linux), not something the planner can see. Where an engine's docs are silent on a platform the plan warns rather than refuses. A user-supplied card has no known vendor, so its engine support is not checked, and every candidate says so. `--hardware auto` reads the local GPU through `doctor`'s per-vendor probes and plans for this machine's OS unless `--platform` says otherwise. On a Mac, auto matches the chip and its installed memory to the variant sold in that configuration. MCP supports stdio and an opt-in loopback Streamable HTTP transport in the reviewed source. HTTP is offline by default, has bounded sessions/workers and is not a publicly hosted service; timed-out synchronous work occupies its worker until it finishes.

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

- **~204,000 primary measurements** across 32 technical reports (TR108-TR137 + the TR142/TR146 safety provenance), on an RTX 4080 Laptop (12 GB; 192-bit GDDR6, 432 GB/s), which is the reference rig every cross-GPU estimate is scaled from. De-duplicated: TR137/TR142 are syntheses of already-counted data. The planner's own lookup tables are a small subset of this (23 throughput rows); the table under the introduction gives their exact size.
- **Rigor:** fresh-process isolation per run (no warm-cache bias), forced cold starts, 3-5 runs per config for statistical confidence, structured JSON/CSV logging with full provenance. Every claim traces to raw data you can re-run.
- **Program context:** ChimeraForge is the actionable CLI splice of the parent Banterhearts program (~1,337,000 primary + judge measurements across 54 TRs); the safety attack-surface and serving-stack research lives in sibling repos.
- **3,630 automated tests** (`pytest tests/`) cover the planner models, gate search, resolver, discovery, safety, bench backends, and the MCP server -- GPU-decoupled, no live backend required for the core suite. The [dated local run](validation/2026-10-09-plan-sensitivity/README.md) collected 3,630 cases: 3,627 passed and three skipped.

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

Grid carbon intensity: Ember, Yearly Electricity Data (2026), processed by Our World in Data (energy-data, Ritchie, Rosado and Roser), both CC BY 4.0. The bundled snapshot records the exact OWID commit it was read at.

Conducted as part of the Banterhearts LLM Performance Research Program: Phase 1 (TR108-TR122) established the measurement methodology and cross-language comparison, Phase 2 (TR123-TR133) produced the deployment framework and capacity planner, and Phase 3 (TR134-TR137) measured the safety cost of inference optimization -- now the planner's opt-in safety gate.

---

**Repository:** https://github.com/Sahil170595/Chimeraforge - **PyPI:** https://pypi.org/project/chimeraforge/ - **Status:** Beta, actively developed

### Saved plans and Python integrations

`chimeraforge plan --model-size 3b --no-network --save plan.json` preserves the effective inputs, resolved facts and candidate provenance in a versioned artifact. The validated Python API accepts `PlanRequest` and returns the same planning core's results. See [the API and artifact contract](docs/planning-api.md).
