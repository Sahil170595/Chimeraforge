# Changelog

All notable changes to ChimeraForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
