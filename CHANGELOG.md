# Changelog

All notable changes to ChimeraForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **Non-ASCII characters removed from source** (4 em-dashes, 2 arrows, 1 delta).
  Three sat in `run_demo.py`'s *rendered report output*, not just comments. They
  render as mojibake on a cp1252 console and twice crashed a plain `print()` of
  tool output during development.

### Added
- **Convention guards** (`tests/test_repo_conventions.py`): a per-file ASCII-only
  check parametrized over every `src/` and `tests/` Python file, and a version-sync
  check tying `server.json` to `pyproject.toml` and `__version__`, plus the
  registry's 100-char description limit and the README `mcp-name` token. Both rules
  had already been broken more than once, invisibly.
- **The MCP Registry publish is now part of the release workflow.** A new
  `mcp-registry` job runs after the PyPI upload, authenticates with GitHub OIDC (no
  stored secret), waits for the release to be indexed on PyPI -- the registry proves
  ownership by reading the `mcp-name` token out of the published description -- and
  then publishes. It refuses to run if `server.json` disagrees with the tag, which
  is exactly how 0.12.3 shipped with the registry still pointing at 0.12.2.

## [0.15.0] - 2026-08-14

### Fixed
- **Backends are only offered formats they actually serve.** The planner enumerated
  every GGUF quant against every backend, so it would recommend "vLLM + Q2_K" -- a
  config vLLM does not serve in the normal path -- and price it with a throughput
  multiplier measured on llama.cpp. The bundled corpus only ever measured **FP16**
  on vLLM/TGI, so those GGUF cells were an extrapolation stacked on a format
  mismatch. GGUF is now Ollama-only; vLLM/TGI take float and FP8. Rejected
  combinations are recorded in the trace, so a 0-result says why.

### Added
- **FP8 quantization** for vLLM/TGI, the format people actually run there. VRAM is
  exact (8 bits/param, no block-scale overhead). Throughput reuses the existing
  nearest-bpw fallback, which lands on the measured 8-bit multiplier rather than
  inventing an FP8 number -- the conservative end of the published 1.3x-2.3x range,
  since the compute-bound gains at high batch are not modelled.
- **`GPUSpec.fp8_supported`.** FP8 is only offered where FP8 tensor cores exist
  (Ada, Hopper, Blackwell, CDNA3). On Ampere (RTX 30, A100) and Turing (T4) it is
  rejected with a stated reason rather than silently costed.
- `plan --launch` emits `--quantization fp8` (vLLM) / `--quantize fp8` (TGI), and
  drops the "serve a native-equivalent checkpoint" note, which no longer applies.

### Notes
- **FP8 quality is labeled `estimated`, never `measured`.** It is absent from the
  TR quality corpus, so it resolves through the FP16-baseline path with no
  fabricated delta added to the measured data.
- FP8 is likewise outside the TR134/TR142 safety corpus. Under `--safety-target`
  it therefore passes as *unscreened* and carries the existing "safety not
  screened" warning -- the documented lookup-only policy (no extrapolation). A
  test previously asserted that every candidate under a safety target had a known
  refusal rate; that held only because every surviving quant happened to be one
  the GGUF-only corpus covered. It now asserts the actual contract: known-unsafe
  cells are rejected, unscreened cells pass warned.
- Ollama + GGUF planning (the reference path) is unchanged.

## [0.14.0] - 2026-08-14

### Fixed
- **Mixture-of-Experts models are no longer planned as if they were dense.** An MoE
  model keeps every expert resident in VRAM but a decoded token only reads the
  experts it routed to. The planner previously used the *total* parameter count
  everywhere, so it under-predicted MoE throughput by the active/total ratio --
  **3.6x on Mixtral-8x7B, ~18x on DeepSeek-V3** -- and inflated TTFT by the same
  factor. Those are the flagship 2026 models, and the wrong answer looked
  confident. Now VRAM and the concurrency cap size on **total** params (unchanged),
  while the decode roofline, the decode compute ceiling, and prefill/TTFT use
  **active** params.

### Added
- `ModelSpec` carries MoE geometry (`num_experts`, `experts_per_token`,
  `moe_intermediate_size`, `n_dense_layers`) with `is_moe` and `active_params_b`.
  Active params are derived first-principles by subtracting the routed experts a
  token does *not* select -- which avoids having to model attention, embeddings,
  shared experts, or norms at all. Verified against published counts:
  **Mixtral-8x7B 12.9B (exact), DeepSeek-V3 37.5B vs 37B, Qwen3-30B-A3B 3.32B vs 3.3B.**
- The resolver reads MoE fields from HF `config.json` across family spellings
  (Mixtral `num_local_experts`, DeepSeek `n_routed_experts` + `first_k_dense_replace`,
  Qwen `num_experts`).
- `Candidate.active_params_b` exposes the split, and an MoE plan warns which count
  drove which prediction.

### Notes
- When the expert geometry is incomplete, `active_params_b` falls back to the
  **total** count. An under-informed guess would *inflate* predicted throughput,
  so the conservative dense answer is the honest one.
- Expert parallelism and routing load-imbalance are still not modelled (the
  imbalance ratio is workload-dependent and would have to be measured, not
  assumed) -- the MoE warning says so.
- Dense models are byte-identical to 0.13.0: `active == total` on every path.

## [0.13.0] - 2026-08-09

### Added
- **Launch-command export (`plan --launch`) — the plan now tells you how to run it.**
  Emits a copy-paste `vllm serve` / `ollama run` / TGI `docker run` command for the
  recommended config, with the flags *derived from the plan itself*: context length
  (`--max-model-len` / `--max-total-tokens` / `num_ctx`), tensor-parallel degree
  (`--tensor-parallel-size` / `--num-shard`), pipeline-parallel degree, concurrent
  batch (`--max-num-seqs` / `--max-concurrent-requests` / `OLLAMA_NUM_PARALLEL`), and
  KV-cache dtype. These are precisely the values that are error-prone to hand-compute
  from a plan, and they are the last gap between "here's the config" and a running
  server. New `planner/launch.py` (`build_launch_command`, `LaunchCommand`).
- **The MCP `chimeraforge_plan` tool returns the same command** in a new `launch`
  field, so an assistant answering "what GPU do I need" can also answer the
  question that always follows it without inventing flags.

### Changed
- `plan --json --launch` emits one document, `{"candidates": [...], "launch": {...}}`.
  Without `--launch`, `--json` still emits the bare candidate array exactly as before,
  so the 0.12.3 JSON contract is unchanged for every existing consumer.

### Notes
- The exporter refuses to fake what it cannot derive, matching the planner's
  provenance principle: a model whose source doesn't match the backend's expected
  identifier format (an Ollama tag handed to `vllm serve`) yields a `<placeholder>`
  plus an explaining note rather than a plausible-but-wrong id; a GGUF quant level
  (`Q4_K_M`) becomes a note to serve the native-equivalent checkpoint rather than a
  fabricated `--quantization Q4_K_M` flag; `--gpu-memory-utilization` is labeled a
  starting point; and where a backend's smallest KV dtype (fp8) is coarser than the
  quantization the plan modeled (q4), the note says real VRAM will exceed the plan.

## [0.12.3] - 2026-08-09

Four correctness defects, found by probing the published package the way an outside
user meets it rather than by reading the source. All four produced a confident answer
that was wrong, or no answer with no reason — the two outcomes a planner can least
afford, because neither looks like a failure. Full findings and reproductions in
[`docs/ax-audit-2026-08.md`](docs/ax-audit-2026-08.md).

### Fixed
- **`--model-size` substituted silently instead of refusing.** `find_models_for_size`
  fell back to the single *nearest* registry model when nothing matched within 50%,
  and to *every* model when the string would not parse. The registry tops out at
  8.03B, so every request above roughly 12B took the first path: `--model-size 70b`
  answered with llama3.1-8b's 8.03B parameters and 4.55 GB of VRAM, and
  `--model-size banana` planned happily across 129 rows. Nothing in the output said
  the request had been changed. Both paths now raise `ResolverError`, and the message
  names the registry's span and both escape hatches — `--model` for a real HF/Ollama
  resolve, `--params-b` to override — because a refusal that does not say what would
  work is a dead end.
- **`--json` was not a contract.** Human-readable text went to the same stream as the
  payload, so output stopped being JSON while the exit code still said success. Fixed
  in four places: the unknown-hardware warning, `catalog`'s empty-state message, and
  `--list-hardware` / `--list-models`, which ignored `--json` entirely and printed
  box-drawing tables. `--list-hardware` mattered most — it is the only way to discover
  a valid `--hardware` value, so it is the listing an automated caller most needs to
  read. Diagnostics now go to a stderr console.
- **An empty result did not explain itself.** `summarize_trace()` already existed and
  already said why nothing fit; it was gated behind `not output_json`, so the
  explanation was withheld from exactly the caller that cannot infer it. The commonest
  case is the default `--budget` of 100 USD/month excluding every datacenter GPU — an
  H100 at the DB's own $2.50/hr is about $1,825/month. It now prints to stderr under
  `--json`, so stdout stays exactly one array and `| jq` keeps working:
  `blocked at budget gate - ollama: $1800/mo (N=1) > $100`.
- **An unknown `--hardware` was substituted, not refused.** It warned and then planned
  on RTX 4080 12GB specs, returning a full result set about a GPU nobody asked for —
  and because the warning went to stdout, a caller stripping non-JSON lines to recover
  the payload got those rows with nothing recording the substitution. Now refused,
  with the known GPUs listed.

### Changed
- `[project.urls]` `Homepage` now points at <https://chimeraforge.vercel.app> rather
  than the repository, and `Changelog` and `Issues` were added. The site and the
  package did not link to each other in either direction, so a reader arriving from
  `pip install` had no way to find it.
- Five tests were rewritten because they specified the defect: one asserted that
  `"100b"` returns `llama3.1-8b`, another that `"abc"` returns every model. The
  instinct behind them — "should not crash" — is right, and a clean refusal satisfies
  it while a wrong number does not. The replacements assert the refusal, that the
  message names the way forward, and that the size classes the registry *does* hold
  still resolve.

## [0.12.2] - 2026-08-08

### Fixed
- **MCP server launch via `uvx` now installs the `mcp` extra.** The documented
  `uvx chimeraforge mcp` created an ephemeral environment with only the core
  dependencies, so `build_server()`'s `from mcp.server.fastmcp import FastMCP`
  raised and the server never started. The README client configs (Claude Code,
  Claude Desktop / Cursor) and the MCP registry manifest now use
  `uvx --from "chimeraforge[mcp]" chimeraforge mcp` — expressed in `server.json`
  via `runtimeArguments` so registry clients compose the identical command.

## [0.12.1] - 2026-08-08

### Added
- **MCP registry manifest (`server.json`) and `mcp-name` ownership token** in the
  README, so the package can be claimed and listed on
  registry.modelcontextprotocol.io under `io.github.Sahil170595/chimeraforge`.

### Changed
- **README rewritten as the PyPI/GitHub shopfront** for the current 0.12.0 feature
  set: leads with the provenance/trust principle (`measured`/`estimated`/`unknown`
  on every number), documents all 11 commands including `mcp`, tensor/pipeline
  parallelism, KV-cache quantization, and energy modeling, and adds zero-install
  `uvx`/`pipx run` quickstarts plus an MCP setup section (Claude Code one-liner and
  a Claude Desktop / Cursor config snippet).
- **PyPI metadata refreshed**: `keywords` expanded (vram, gpu-sizing, quantization,
  ollama, vllm, llama-cpp, gguf, capacity-planning, mcp), classifier moved from
  `Development Status :: 3 - Alpha` to `4 - Beta`, and a `Documentation` URL added
  under `[project.urls]`. No functional/code changes.

## [0.12.0] - 2026-08-07

### Added
- **MCP server — ChimeraForge is now callable by Claude / GPT / Cursor and any MCP
  client.** `chimeraforge mcp` runs a stdio server (new `mcp` extra:
  `pip install "chimeraforge[mcp]"`) exposing three tools: `chimeraforge_plan`
  (the full gate search), `chimeraforge_resolve_model` (grounds a model's real
  params/architecture), and `chimeraforge_list_hardware`. GPU-sizing is exactly
  where assistants fail — stale training-cutoff prices/specs plus error-prone KV/
  batching arithmetic — so the tools let an assistant answer "what GPU do I need /
  will it fit / how much will it cost" from measured data instead of guessing.
  Every result surfaces the `provenance` (measured/estimated/unknown) contract, and
  the tool descriptions tell the model to prefer the tool over its own knowledge.
- **Shared planning core (`planner/service.py: run_plan`).** The CLI and the MCP
  server now go through one presentation-free orchestration path (load → resolve →
  gate search → pareto) instead of duplicating logic — the MCP tools call it
  in-process, not by shelling out to the CLI.

### Fixed
- **`plan --json` now emits `{"error": ...}` on failure paths** instead of
  Rich-styled text, so an automated consumer parsing stdout gets valid JSON on
  errors too (previously validation/resolution errors printed markup regardless of
  `--json`, breaking `json.loads`).

## [0.11.0] - 2026-08-07

### Added
- **Pipeline parallelism.** New `plan --pipeline-parallel {N|auto}` (alias `--pp`):
  split a model's *layers* into N sequential stages across N GPUs — another way to
  fit a model too big for one GPU. Complements 0.10.0's tensor parallelism; the two
  suit different interconnects.
  - **VRAM**: weights and each stage's KV shard 1/N with **no attention-head cap**
    (unlike TP), so PP scales past `n_kv_heads` for GQA models.
  - **Throughput** (`ThroughputModel.pp_decode_tps`): N stages give ~N× aggregate
    HBM bandwidth, and PP's only comms is a **small point-to-point activation pass**
    (no all-reduce) — so PP barely degrades on slow PCIe where TP collapses (per
    vLLM's own guidance). The cost is the **GPipe pipeline bubble**: a decode step
    traverses every stage, so PP needs enough in-flight sequences to stay full
    (efficiency `batch/(batch+pp-1)`) — near-ideal at high batch, poor at batch 1.
    Warns when under-filled. First-principles **estimate** (bubble modelled, not
    measured).
  - `auto` picks the smallest PP degree that *fits* (fewest GPUs); a high-throughput
    load may need a higher explicit degree. `Candidate` gains `pipeline_parallel`.
  - **TP and PP cannot be combined yet** (MVP) — setting both above 1 errors cleanly.
  - `pp=1` (the default) reproduces the pre-0.11.0 single-GPU results exactly.

## [0.10.0] - 2026-08-07

### Added
- **Multi-GPU tensor parallelism.** New `plan --tensor-parallel {N|auto}` (alias
  `--tp`): the planner can now size a model that does not fit one GPU by splitting
  it across `N` GPUs. Weights shard 1/N and KV shards across attention heads
  (`VRAMModel.predict`/`max_concurrent_seqs` gained a `tp` arg), so e.g. a 70B FP16
  fits on 4x H100 or 2x B200. `auto` picks the smallest TP degree that fits.
  - **Comms-modelled throughput** (`ThroughputModel.tp_decode_tps`): a TP group of
    `N` GPUs gets ~N x aggregate HBM bandwidth, minus Megatron all-reduce overhead
    (2 per layer, ring `2(N-1)/N` bytes, FP16 activations) scaled by the GPU's
    interconnect bandwidth. So TP is near-ideal on NVLink at low batch but erodes on
    PCIe or at high batch, matching the literature (Pope et al. 2022; vLLM docs).
    Throughput is a first-principles **estimate** (comms modelled, not measured) and
    is flagged as such; PCIe interconnects and crossing the NVLink domain also warn.
  - `GPUSpec` gains `interconnect_gbps` for all 22 GPUs (NVLink 3/4/5, AMD Infinity
    Fabric, or PCIe 4/5). Cost and energy scale with the full fleet (`N replicas x
    TP GPUs`); `Candidate` carries `tensor_parallel` and `gpus_total`.
  - `tp=1` (the default) reproduces the pre-0.10.0 single-GPU results exactly.

## [0.9.0] - 2026-08-05

### Added
- **KV-cache quantization modeling.** New `plan --kv-quant {fp16,q8,q4}`. Backends
  can quantize the KV cache independently of the weights (llama.cpp
  `--cache-type-k`, vLLM fp8 KV); the planner now models it (q8 = 1 byte, q4 = 0.5
  byte per element vs FP16's 2). A quantized cache **lowers VRAM and raises the
  KV-bound concurrency cap** — largest at long context, where KV dominates.
  `VRAMModel.predict` / `kv_cache_gb` / `max_concurrent_seqs` take a `kv_bytes`
  argument (default FP16, so existing results are byte-identical).
  - Only VRAM/concurrency are modelled; KV-quant's (small) **quality impact is NOT
    screened** (no bundled measurements) — `plan` warns when it is enabled and
    never reports a fabricated quality delta.

### Changed
- **Dependency ranges refreshed** against verified-passing versions (the full
  suite runs green on all of these): runtime `rich` cap widened `<14.0` → `<16.0`
  (the old cap force-downgraded rich in users' environments); dev tools
  `pytest` → `<10.0`, `pytest-cov` → `<8.0`, `pytest-asyncio` → `<2.0`.

## [0.8.0] - 2026-08-05

### Added
- **Energy & power cost modeling.** `GPUSpec` gains `tdp_watts` (board power, from
  vendor datasheets) for all 22 GPUs, and `plan` now reports, per configuration:
  monthly electricity cost, a `$/1M-tok (+energy)` figure, and throughput
  efficiency (**tok/s per watt**). New `--electricity-rate` flag ($/kWh, default
  the US commercial average). Power draw is modelled as `tdp_watts x 0.85`
  (sustained decode rarely holds full TDP; the factor is the named constant
  `POWER_UTILISATION`).
  - Energy is reported as a **separate** line, deliberately NOT folded into the
    hardware cost or the budget gate: a cloud `$/hr` rate already bundles power
    (folding it in would double-count), while an amortised consumer-card cost
    does not -- so the energy figure is most meaningful for self-hosted hardware.
  - `perf_per_watt` and the per-token energy cost are invariant in replica count
    (both the aggregate throughput and the total power scale with N).

## [0.7.0] - 2026-08-05

### Added
- **7 current-generation GPUs in `GPU_DB` (15 -> 22).** Consumer Blackwell
  (RTX 5070 / 5070 Ti / 5080 / 5090, GDDR7), datacenter NVIDIA (H200 141 GB,
  B200 180 GB), and the first AMD entry (Instinct MI300X 192 GB). Every VRAM /
  bandwidth / `fp16_tflops` figure is sourced from vendor datasheets on the
  table's existing basis (dense FP16 Tensor Core, FP32-accumulate, non-sparse):
  consumer Blackwell = 2x FP32 shader (= the whitepaper's FP32-accumulate row);
  H200 shares H100's GH100 compute (989); B200 dense = datasheet 4500-with-
  sparsity / 2; MI300X 1307 from AMD's dense-FP16 figure. This also sharpens the
  roofline throughput path for *any* off-registry model on the new hardware.
- **Newer model families recognised** in identifier parsing: `qwen3`,
  `llama3.3`, `gemma3`, `smollm` (joining `qwen2.5` / `llama3.x` / `phi` /
  `gemma2` / `mistral`), so tags like `qwen3:8b` parse their family correctly
  when resolved via a live backend. No bundled measurements exist for these, so
  they resolve to **estimated / roofline** numbers with honest provenance -- never
  a "measured" masquerade (a regression test locks this in).
- **9 newer models in the offline catalog seed** (`model_catalog.json`, 10 -> 19):
  Qwen3 (0.6B-14B), Phi-4 + Phi-4-mini, SmolLM3-3B, Mistral-7B-Instruct-v0.3.
  All verified publicly ungated so `catalog build` resolves them to real specs
  tokenless; gated repos (Gemma, Llama) are deliberately excluded.

## [0.6.2] - 2026-07-25

### Fixed
- **`quality_tier` and the quality float now agree for `llama3.1-8b` FP16**
  (#4 follow-up). 0.6.1 fixed `quality_tier` but left `estimate()` / `predict()`
  on the old baseline chain, so the FP16 config reported quality `0.5` with
  provenance `unknown` -- ranking the *highest-precision* option below `Q2_K`
  (`0.59`) -- while its tier said `negligible`. All three methods now share one
  `_fp16_baseline` resolver (measured FP16 -> the model's highest measured quant
  -> family mean), so quality, provenance, and tier can never diverge. FP16 now
  reports `0.635` (estimated), consistent with its `negligible` tier.

## [0.6.1] - 2026-07-04

### Fixed
- **Clean errors for missing extras.** `bench` / `measure` / `safety` (and
  `plan --measure`) now fail with a clear `install "chimeraforge[bench|safety]"`
  message instead of a raw `ModuleNotFoundError` traceback when the serving
  backends' `httpx` dependency is absent (the backends import it at module load).
- Install-hint error messages no longer have their `[extra]` swallowed by Rich
  markup (the resolver hint rendered as `pip install chimeraforge`, dropping
  `[resolve]`); dynamic error text is now escaped.
- **`quality_tier` no longer returns `unknown` for `llama3.1-8b`** (#4). Its FP16
  was never measured (16 GB exceeds the RTX 4080), so TR125 used Q8_0 as the
  baseline; `quality_tier` now mirrors that, anchoring to the model's
  highest-precision measured quant when no FP16 baseline exists.
- **Quick-start install fixed** (#5): `docs/quick_start.md` used
  `pip install -r requirements.txt` (a comment-only stub that installs nothing),
  so the agent demo failed with `ModuleNotFoundError: httpx`. It now installs
  `-e ".[bench]"` (which provides `httpx`) and points the clone at the real repo.

### Changed
- **`httpx` is now a core dependency**, so the network-facing commands
  (model-agnostic `plan --model`, `suggest`, `catalog`, `measure`, `safety`,
  `bench`) work on a plain `pip install chimeraforge` instead of erroring until an
  extra is added. The `[resolve]`/`[safety]` extras are kept as no-op back-compat
  aliases. Thanks @sumaiya1303 (#6).
- **Corrected optional-dependency groups.** `[bench]` dropped `psutil`, `pyyaml`,
  and `structlog` (none are imported by the shipped `chimeraforge` package) and
  added `pynvml` (used for GPU environment metadata, previously undeclared, so
  `[bench]` silently lacked it). `psutil` and `structlog` moved to `[dev]` (they
  are test-only, for the `banterhearts` monitoring subsystem the suite exercises);
  `pyyaml` removed entirely (unused). `[refit]` added `platformdirs` (used by its
  output-path resolution). `[all]` no longer pulls the `dev` tools (pytest/ruff)
  onto end users; CI installs `.[all,dev]`.

## [0.6.0] - 2026-06-25

State-of-the-art serving model: the planner now reflects how LLM inference
actually behaves (per the literature - PagedAttention, continuous batching,
prefill/decode disaggregation, goodput/Pareto), not replicas-of-single-stream.

### Added
- **Continuous-batching throughput.** vLLM/TGI are modelled with per-GPU
  continuous batching instead of single-stream replicas: aggregate decode
  throughput rises with batch size up to the KV-cache cap, anchored to the
  measured/roofline single-stream rate so it stays quant-correct. One GPU can now
  replace several Ollama replicas (e.g. a 7B at 3 req/s on a 4090: Ollama 5 GPUs
  vs vLLM 1 GPU at batch 8). `Candidate.effective_batch`.
- **Prefill/decode split.** Separate **TTFT** (prefill, compute-bound, from GPU
  FP16 TFLOPS) and **TPOT** (decode, bandwidth-bound); end-to-end p95 now includes
  prefill. `GPUSpec.fp16_tflops` for all GPUs; `plan --prompt-tokens`.
- **KV-cache-bound max concurrency** per GPU (`max_concurrent_seqs`), the real
  concurrency limiter for batched backends.
- **Pareto frontier** (`plan --pareto`): the non-dominated cost/latency/quality
  trade-off menu (tags cheapest / fastest / best-quality), not a single pick.
- **Variance-aware queueing** (`plan --workload steady|chatbot|bursty|agent`):
  two-moment wait so high-variance/agent workloads inflate the tail and carry a
  "validate with a load test" warning - analytical queueing otherwise silently
  approves fleets that miss SLOs for heavy-tailed traffic.
- Numerical accuracy tests pinning throughput, the roofline calibration anchor,
  the VRAM formula, TTFT, and batching invariants to ground truth (falsifiability).

### Changed
- **Throughput scales linearly across GPU replicas** (replaced the Amdahl
  serial-fraction model, which capped total throughput at ~1.8x regardless of
  instance count and rejected models >=7B). Per-GPU batching is modelled
  separately (above).
- **`cost_per_1m_tok` no longer understated by the instance count** (uses N-GPU
  cost with N-GPU throughput; $/token is invariant in replica count).
- Broader quant support (legacy + i-quants: `Q4_0`, `Q5_1`, `IQ4_XS`, ...) with
  effective bits-per-weight, so a model's native quant is costed correctly.
- Docs realigned to the planner product (research guides moved to an archive
  section); ASCII-only source.

### Fixed
- **Activation memory is now O(context), not O(context^2).** The quadratic term
  diverged unphysically at long context (~130 GB at 32k for a 3B model), which
  spuriously failed the VRAM gate and zeroed `max_concurrent_seqs` (killing
  batching) at >=8k context. Flash/paged attention never materialises the
  attention matrix, so it scales linearly; coefficient re-pinned to preserve the
  calibrated 2k value. (Found by a blind code audit.)
- **`--json` is now valid when piped** for `bench`, `refit`, `compare`, and
  `report` (added `highlight=False, soft_wrap=True`, matching the other six
  commands). Rich previously reflowed long string values at width 79 and produced
  invalid JSON for `... --json | jq`.
- **`refit --validate` is a real gate**: validation runs *before* the write, so
  invalid coefficients are no longer persisted ahead of the failing exit.
- **Quality tier is family-aware** for off-registry models (consistent with the
  reported quality), so the "concerning drop" advisory can fire instead of the
  tier silently collapsing to `unknown`.
- **Per-key confidence weighting in `refit`**: each entry is blended by its own
  successful-run count, not the global run total (which over-trusted
  lightly-measured configs in a multi-config refit).
- Measured-corpus staleness warning: `plan`/`suggest` now warn (instead of
  silently shadowing) when the cached corpus predates the installed version.
- Robust error handling: `measure` surfaces an unknown `--backend` cleanly;
  backend `check_model` handles timeouts/HTTP errors (not just connect); the
  resolver/discovery raise `ResolverError` (not a raw traceback) on a non-JSON
  200 response; a degenerate `...0b` identifier no longer raises ZeroDivisionError.
- `bench --context ... --quant Q` no longer drops the quant label; non-Ollama
  context sweeps warn that the per-request context override was not applied.
- Roofline throughput is bandwidth-correct above FP16 (e.g. FP32 ~ 0.5x FP16);
  Ollama `F16`/`F32` native-quant strings are normalised to `FP16`/`FP32`.
- `eval --fp16-baseline` exposes tier classification (previously always
  `unknown` from the CLI). Build floor corrected to `setuptools>=77` (PEP 639).

### Notes
- Per-backend MFU/MBU *calibration* is deferred: the `measure` loop already
  supersedes the roofline estimate with real measurements for any benchmarked
  model, which is stronger than tuning a global constant.
- Known minor limitations (low impact, deferred): VRAM mixes decimal-GB weight
  with binary-GiB KV (~7.4%, conservative); ambiguous partial GPU names (e.g.
  "RTX 4080") resolve to the first DB match by VRAM; a genuine 0.0 BERTScore is
  treated as "unavailable".

## [0.5.0] - 2026-06-24

### Added
- **Model-agnostic planning.** `plan --model <id>` accepts any model identifier —
  a registry name, an Ollama tag (`ollama:NAME` / colon tags), or a Hugging Face
  repo (`org/name`) — and resolves real parameters + attention geometry instead
  of being limited to the bundled registry. Sources (priority order): manual
  overrides (`--params-b/--n-layers/--n-kv-heads/--d-head`), registry, on-disk
  spec cache, Ollama `/api/show`, HF `config.json` + `safetensors` param count,
  then offline family/size approximation (`planner.resolver`).
- **`suggest`** — discover and rank deployable models from a live Ollama
  (`/api/tags`), the HF Hub (top text-generation), and/or the local catalog,
  through the same gate search (`planner.discovery`).
- **`catalog`** — build a persisted spec catalog from a curated seed
  (`catalog --build`) so `suggest --source catalog` ranks models fully offline.
- **`measure`** / **`plan --measure`** — benchmark a live model (real N=1
  throughput, service time, and concurrency scaling → serial fraction) and fold
  it into a local `fitted_models.json` via the `refit` loop, so plans run on
  measured numbers (provenance: `measured`) rather than estimates.
- **Per-prediction provenance** (`measured` / `estimated` / `unknown`) on every
  candidate, surfaced in output (`~` markers) and as warnings.
- **Rejection diagnostics** — `plan` reports the binding gate ("Why nothing fit")
  on an empty result.
- Roofline throughput estimate for off-registry models (memory-bandwidth bound).
- Broader quant support: legacy and i-quants (`Q4_0`, `Q5_1`, `IQ4_XS`, …) are
  recognised with effective bits-per-weight, so a model's native quant is costed
  correctly instead of silently defaulting to FP16.
- `resolve` extra (`httpx`) for network metadata resolution.

### Fixed
- **Throughput scaling across instances is now linear.** `n_agents` counts
  independent GPU replicas (VRAM and cost are per-GPU), so total throughput scales
  linearly; the previous Amdahl serial-fraction model wrongly capped it at ~1.8×
  regardless of instance count, rejecting essentially every model ≥7B. (Per-GPU
  batching throughput is intentionally future work.)
- **`cost_per_1m_tok` no longer understated by the instance count** — it now uses
  the N-GPU cost to match the N-GPU throughput, so adding identical replicas
  leaves $/token unchanged (was N× too low).

### Changed
- `plan` / `suggest` prefer a measured corpus
  (`~/.cache/chimeraforge/fitted_models.json`) over bundled coefficients when present.

## [0.4.1] - 2026-06-22

### Added
- CI matrix now covers Python 3.13 and 3.14 (was 3.10–3.12); added the 3.14
  classifier.

### Fixed
- `safety` and `eval` `--json` emit plain JSON (Rich syntax-highlighting disabled
  via `highlight=False`), so `--json | jq` is clean and parsing is robust when
  colour is forced (e.g. on CI).
- Hardened the `safety --help` test to strip ANSI before matching option names —
  the v0.4.0 CI failure (Rich colourises `--help`, so `--prompts` was not a
  literal substring of the raw output).

## [0.4.0] - 2026-06-19

### Added
- `chimeraforge safety` — live refusal screen. Runs user-provided probe prompts
  against a running model, classifies refusals (rule-based, the TR134 regex
  baseline), and reports the measured refusal rate against the bundled gate data
  (expected, drift, RTSI tier); exits 1 below `--safety-target`. Behind the
  `chimeraforge[safety]` extra. Ollama backend (vLLM/TGI not yet); no attack
  corpus is bundled — bring your own benchmark.
- `Backend.generate_text()` returning response text (used by the safety screen).
- Model-identity resolution (`planner.identity`): maps Ollama tags / HF paths to
  registry models by architecture-family + parameter count (not exact name), so
  `safety`'s bundled-data comparison works against live backend model tags.

## [0.3.0] - 2026-06-16

### Added
- Planner safety gate (Gate 5): `plan --safety-target` rejects configs whose
  refusal rate (TR134/TR142) falls below the bar. Opt-in; off by default.
- `SafetyModel` exposing per-(model, quant) refusal rate + RTSI risk tier,
  bundled in `fitted_models.json` (GGUF quants only, lookup-only — no
  extrapolation, since safety does not generalise across cells per TR142/TR146).
- Safety surfaced in `plan` output: refusal rate + RTSI risk in the
  recommendation panel, Safety column in the alternatives table, and
  `safety_refusal` + `rtsi_risk` fields in `--json`.
- `scripts/build_safety_data.py` ETL plus vendored TR142 source CSVs under
  `data/safety/tr142/`.

### Changed
- Split the monolithic `cli.py` (863 lines) into per-command modules under
  `chimeraforge/commands/`; `cli.py` is now a thin Typer registrar.
- Split the `test_bench.py` and `test_planner.py` god files into focused
  per-concern modules; moved the `bundled_models` fixture to `conftest.py`.

### Fixed
- CLI commands fail loud (clean message + exit 1) instead of leaking a raw
  traceback on: missing/malformed `--models-path` (plan), malformed or
  non-result JSON (report/compare/refit), and unknown `--backend` (bench).
- `plan --latency-slo` rejects non-positive values (previously accepted).
- `report` rejects JSON that is not a bench result (e.g. `{}`) instead of
  emitting an empty report.
- `bench` no longer crashes with a UnicodeEncodeError when stdout is a
  non-UTF-8 pipe/redirect on Windows (progress spinner disabled when not a TTY).

## [0.2.0] - 2026-03-08

### Added
- `chimeraforge bench` CLI — live LLM inference benchmarking (Ollama, vLLM, TGI)
- `chimeraforge eval` CLI — quality evaluation (exact match, ROUGE-L, BERTScore, coherence)
- `chimeraforge report` CLI — Markdown/HTML report generation with statistical analysis
- `chimeraforge compare` CLI — diff benchmark results across runs with delta analysis
- `chimeraforge refit` CLI — Bayesian blending to update planner coefficients from bench data
- Backend adapter pattern: OllamaBackend, VLLMBackend, TGIBackend
- Three workload profiles: single, batch, server (Poisson arrivals)
- Quantization sweep and context-length sweep modes
- CV-based stability detection with automatic warnings
- Error-resilient runner (partial failures preserved)
- GPU metrics collection via pynvml
- JSON result serialization with environment metadata
- 10-check validation suite for fitted_models consistency (`--validate` flag)
- 3 built-in eval tasks: general_knowledge, summarization, code
- Composite quality scoring with tier classification (negligible/acceptable/concerning/unacceptable)
- Hardware offset computation and power-law refitting from bench data
- Self-contained HTML reports with inline CSS and XSS prevention
- Shared test fixtures via `tests/helpers.py` and `tests/conftest.py`
- GitHub Actions CI (Python 3.10/3.11/3.12 matrix)
- Published to PyPI: `pip install chimeraforge`
- 292 tests (80 planner + 73 bench + 42 eval + 26 report + 47 refit + 19 compare + 5 monitoring)
- Technical reports TR117-TR133

### Fixed
- Planner: ZeroDivisionError in find_models_for_size("0b")
- Planner: N-search now checks both throughput AND latency per N
- Planner: LatencyModel zero-service-time fallback (mu=1e6 not 0.001)
- Planner: QualityModel FP16 baseline inference from lookup
- Planner: formatter uses asdict() instead of manual dict
- CLI: input validation for all numeric parameters
- Narrowed all `except Exception` to specific exception types
- Proper `Console` typing via `TYPE_CHECKING` (removed all `type: ignore` suppressions)
- Extracted magic numbers to named constants in refit module

## [0.1.0] - 2025-01-15

### Added
- `chimeraforge plan` CLI — predictive capacity planner
- 4-gate pipeline: VRAM, quality, latency, budget
- 6 predictive models: VRAM, throughput, scaling, quality, cost, latency
- Hardware DB with 15 GPUs
- Pre-fitted coefficients from TR133 (fitted_models.json)
- Python single-agent benchmarking (BaselineAgent, ChimeraAgent)
- Python multi-agent benchmarking (asyncio.gather, ResourceCoordinator)
- Rust single-agent (Tokio, reqwest streaming)
- Rust multi-agent (5 runtime features)
- 16-module monitoring subsystem
- Technical reports TR108-TR116
- Comprehensive documentation (18 guides)
- Dual Ollama instance support
- Multiple async runtime support (Tokio, async-std, smol)

---

**Note**: For detailed change history, see the git commit log.
