# Changelog

All notable changes to ChimeraForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
