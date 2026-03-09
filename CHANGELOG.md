# Changelog

All notable changes to ChimeraForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
