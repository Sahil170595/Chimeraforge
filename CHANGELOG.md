# Changelog

All notable changes to ChimeraForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
