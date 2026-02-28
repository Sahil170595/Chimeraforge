# ChimeraForge CLI — Product Spec & Development Plan

## Vision

**ChimeraForge** becomes the first pip-installable LLM deployment optimization toolkit for consumer hardware. One install, multiple commands — benchmark, evaluate, plan, and report.

No existing tool does this end-to-end:

| Tool | What it does | Gap |
|------|-------------|-----|
| [Bench360](https://github.com/slinusc/bench360) | Benchmarks LLM inference across backends | No planning, no cost model, no quality eval, Linux-only |
| [GuideLLM](https://pypi.org/project/guidellm/) | Load-tests OpenAI endpoints | Server-side only, no local GPU, no VRAM prediction |
| [LLMPerf](https://github.com/ray-project/llmperf) | Load + correctness testing | Cloud-focused, no consumer GPU support |
| VRAM calculators | Formula-based VRAM guesses | Web-only, no empirical data, no throughput/latency |

**ChimeraForge's moat**: 70,000+ real measurements across 26 TRs on consumer hardware, distilled into a toolkit that works out of the box.

---

## Research Foundation — All 26 TRs Mapped to CLI

Every TR maps to a capability in the toolkit:

### Phase 1 TRs (TR108-TR122) — Agent & Backend Benchmarking

| TR | Title | Measurements | CLI Feature |
|----|-------|-------------|-------------|
| TR108 | Single-Agent Baseline | 150 | `bench --mode agent` baseline data |
| TR109 | Agent Workflow Optimization | 90 | `bench --mode agent` config sweeps |
| TR110 | Python Multi-Agent | 150 | `bench --mode multiagent --lang python` |
| TR111 | Rust Single-Agent | 57 | `bench --mode agent --lang rust` |
| TR112 | Rust vs Python Comparison | 111 | `report --compare rust-vs-python` |
| TR113 | Rust Multi-Agent (1 Ollama) | 19 | Architecture validation data |
| TR114 | Rust Multi-Agent (Dual Ollama) | 135 | `bench --mode multiagent --lang rust` |
| TR115 | Async Runtime Optimization | 150 | `report` runtime recommendations |
| TR116 | Cross-Model Multi-Agent | 60 | `bench --mode multiagent --models gemma,llama,qwen` |
| TR117 | Cross-Backend Inference | 3,017 | `bench --backend transformers,onnx,tensorrt` |
| TR118 | ONNX/TensorRT Deep Dive | 720 | `bench --backend onnx,tensorrt` |
| TR119 | Cost & Energy Analysis | 350 | `bench --measure energy,cost` |
| TR120 | Compile Paradox Root-Cause | 546 | Documentation + `bench --compile` mode |
| TR121 | Model Scaling Study | 684 | `bench --scale 5m,124m,1b,3b,8b,20b` |
| TR122 | Physics of Inference | 2,041 | `bench --measure power` baseline calibration |

### Phase 2 TRs (TR123-TR133) — Quality, Cost, Planning

| TR | Title | Measurements | CLI Feature |
|----|-------|-------------|-------------|
| TR123 | KV-Cache Economics | 350 | `plan` cost model (cached decode $/tok) |
| TR124 | Quality Baseline | 1,000 | `eval` quality metrics (BERTScore, ROUGE-L) |
| TR125 | Quantization Decision Matrix | 25,890 | `eval --quant-sweep` quality x 7 quant levels |
| TR126 | Docker/Linux Validation | 25,400 | `bench --docker` Linux reproducibility |
| TR127 | Long-Context Characterization | 1,144 | `plan` VRAM model (ctx scaling) |
| TR128 | Production Workloads | 3,172 | `bench --workload server` latency under load |
| TR129 | N-Agent Scaling Laws | 5,310 | `plan` scaling model (Amdahl's s per backend) |
| TR130 | Serving Stack Comparison | 4,797 | `bench --backend ollama,vllm,tgi` |
| TR131 | GPU Kernel Profiling | 26 | `profile` kernel-level analysis |
| TR132 | In-Container GPU Profiling | 25 | `profile --docker` container profiling |
| TR133 | Predictive Capacity Planner | 0 (tool) | `plan` -- the capstone command |

**Total: 70,000+ measurements feeding into the CLI.**

---

## Target UX

```bash
# Install (planner only)
pip install chimeraforge

# Install optional features (keeps base install lightweight)
pip install "chimeraforge[bench]"   # benchmarking
pip install "chimeraforge[eval]"    # quality evaluation
pip install "chimeraforge[all]"     # everything

# Phase 1 -- Capacity Planning (works instantly, no GPU needed)
chimeraforge plan --model-size 3b --request-rate 2 --budget 50
chimeraforge plan --list-hardware
chimeraforge plan --list-models
chimeraforge plan --model-size 3b --json

# Phase 2 -- Benchmarking (needs GPU + a local runtime like Ollama; some backends may require Linux/Docker)
chimeraforge bench --model llama3.2-3b --backend ollama
chimeraforge bench --model llama3.2-3b --backend ollama --all-quants
chimeraforge bench --model llama3.2-3b --backend ollama --scale 1,2,4,8
chimeraforge bench --model llama3.2-3b --backend vllm --workload server --rate 2.0

# Phase 3 -- Quality Evaluation (needs GPU + model runtime + eval datasets)
chimeraforge eval --model llama3.2-3b --quant Q4_K_M
chimeraforge eval --model llama3.2-3b --quant-sweep

# Phase 4 -- Report Generation
chimeraforge report --results ~/.chimeraforge/results/latest/
chimeraforge report --format html --compare Q4_K_M,Q8_0,FP16

# Phase 5 -- Model Re-fitting (advanced)
chimeraforge refit --results ~/.chimeraforge/results/
chimeraforge refit --validate
```

---

## Design Principles

### 1. PyTorch is NOT a pip dependency

`torch` is huge (~2GB), platform-specific (CPU/CUDA/ROCm/MPS), and installing it via plain `pip` often gives you the wrong variant. ChimeraForge does NOT declare `torch` as a pip dependency. Instead:

- **Base install** (`pip install chimeraforge`): No torch. Planner works immediately.
- **Bench/eval install** (`pip install "chimeraforge[bench]"`): Lists `psutil`, `httpx`, `pyyaml` — but NOT `torch`. Torch is an **execution-time check**.
- At runtime, if torch is needed and missing, ChimeraForge prints a Rich-formatted message:
  ```
  PyTorch not found. Install it for your platform:
    https://pytorch.org/get-started/locally/
  ```
- Same approach for `vllm`, `tgi` Docker images, and `bert-score`/`rouge-score` (eval). These are checked at runtime, not declared as hard deps.

### 2. Data freshness — OTA model updates

The baked-in `fitted_models.json` ships with the package, but the AI landscape moves fast. Users shouldn't wait for a PyPI release to get predictions for new models.

```bash
# Fetch latest model weights from GitHub releases
chimeraforge update-data

# Check current data version
chimeraforge update-data --check

# Pin to baked-in data (offline mode)
chimeraforge plan --offline
```

Mechanism:
- `chimeraforge update-data` fetches the latest `fitted_models.json` from a GitHub release asset (e.g., `https://github.com/user/Chimeraforge/releases/latest/download/fitted_models.json`)
- Cached in `platformdirs.user_cache_dir("chimeraforge") / "fitted_models.json"`
- Planner checks: cached version first, falls back to baked-in package data
- `--offline` flag forces baked-in data only (air-gapped environments)
- No auto-update on every run. User-initiated only.

**Supply chain security:** OTA data is prediction coefficients only (JSON of floats), never executable code or model download URLs. Integrity is verified on every fetch:
- Each release asset ships with a SHA256 checksum file (`fitted_models.json.sha256`) signed via GitHub's release artifact chain
- `chimeraforge update-data` verifies the checksum before replacing the cached file; on mismatch, the download is rejected with a clear error
- The JSON schema is fixed and validated on load — unexpected keys or non-numeric values are rejected
- Even a compromised `fitted_models.json` can only produce wrong *predictions*, never execute code or redirect to external downloads

### 3. Units and defaults — explicit everywhere

All CLI arguments use explicit units in their help text and defaults:

| Flag | Unit | Default | Example |
|------|------|---------|---------|
| `--budget` | USD per month | 100 | `--budget 50` = $50/month |
| `--request-rate` | requests per second | 1.0 | `--request-rate 2` = 2 req/s |
| `--latency-slo` | milliseconds (p95) | 5000 | `--latency-slo 500` = 500ms p95 |
| `--quality-target` | composite score 0-1 | 0.5 | `--quality-target 0.6` |
| `--avg-tokens` | tokens per response | 128 | `--avg-tokens 256` |
| `--context-length` | tokens | 2048 | `--context-length 8192` |

Help text example:
```
--budget FLOAT  Max monthly cost in USD [default: 100.0]
```

### 4. Pre-flight checks — fail fast with actionable errors

Every command runs pre-flight checks before doing work. Failures are Rich-formatted panels with fix instructions, not raw tracebacks.

Examples:
```
ERROR  Ollama is not running

  The bench command requires a running Ollama instance.

  To start Ollama:
    ollama serve

  To install Ollama:
    https://ollama.com/download
```

```
ERROR  Model not found: llama3.2-3b

  This model is not pulled in Ollama.

  To pull it:
    ollama pull llama3.2:3b
```

```
ERROR  HuggingFace token required

  The model 'meta-llama/Llama-3.2-3B' is gated.

  To authenticate:
    huggingface-cli login

  Or set HF_TOKEN environment variable.
```

Pre-flight checks per command:
- `plan`: None needed (works offline, no GPU, no backends)
- `bench`: Check backend is running, model is available, GPU is detected (if applicable)
- `eval`: Check backend + verify eval datasets are cached or downloadable
- `deploy`: Check backend binary exists, port is available, sufficient VRAM

### 5. Target personas

ChimeraForge serves three distinct users with different needs:

| Persona | Use case | Primary commands | Hardware |
|---------|----------|-----------------|----------|
| **Local AI hobbyist** | "What model fits my GPU?" | `plan`, `bench` | RTX 3060/4060/4090, Mac M-series |
| **ML engineer** | "Optimize our inference stack" | `bench`, `eval`, `report`, `refit` | Lab GPUs, cloud instances |
| **DevOps / platform team** | "Deploy and monitor LLM serving" | `deploy`, `monitor`, `plan --json` | Production servers, CI/CD |

The base install (`plan`) serves everyone. Optional extras unlock per-persona workflows. The planner's hardware DB includes both consumer GPUs (with amortized $/hr) and cloud instances (with rental $/hr).

### 6. Privacy and telemetry

**ChimeraForge collects zero telemetry by default.** No phone-home, no analytics, no usage tracking. Everything runs locally.

Community data upload (Phase 7) is strictly opt-in:
- Requires explicit `--upload` flag on every command
- Only performance metrics are sent (throughput, latency, VRAM, GPU name)
- **Never uploads**: prompts, model outputs, file paths, IP addresses, usernames
- Upload schema is public and auditable in the repo
- Users can inspect exactly what would be sent before confirming: `chimeraforge bench --upload --dry-run`
- No account required. Uploads are anonymous.

---

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| CLI framework | **Typer** + **Rich** | Auto-generated help, beautiful terminal output, tables, panels, progress bars |
| Packaging | **pyproject.toml** + setuptools | Standard Python packaging |
| Data bundling | **importlib.resources** | Ship fitted_models.json as package data |
| Paths | **platformdirs** | Cross-platform config/cache/results directories |
| Distribution | **PyPI** | `pip install chimeraforge` from anywhere |
| Testing | **pytest** | Already used in both repos |
| Test isolation | **Mocking layer** | Hardware-decoupled CI/CD (see below) |
| Python | **>=3.10** | Type unions, match statements |

### Testing without GPUs

Standard CI runners (GitHub Actions, GitLab CI) don't have GPUs. ChimeraForge's test strategy explicitly decouples hardware from logic:

**Layer 1 — Pure logic (runs everywhere, no mocking):**
- Planner engine, models, constants, hardware DB, formatters — all tested with real `fitted_models.json`
- 57+ tests run in < 1 second, zero hardware dependency

**Layer 2 — Backend mocking (runs everywhere, mocks HTTP):**
- `chimeraforge.bench.backends` each define an abstract interface. Tests mock HTTP responses (Ollama `/api/generate`, vLLM `/v1/completions`, TGI `/generate`) with recorded real responses
- VRAM measurement mocked via `unittest.mock.patch("torch.cuda.get_device_properties")` returning fixture data
- `nvidia-smi` calls mocked with subprocess fixtures
- Coverage: full benchmarking pipeline without a GPU present

**Layer 3 — Integration (self-hosted GPU runner):**
- A single self-hosted runner with an actual GPU runs end-to-end benchmarks on merge to main
- These tests validate that mocks haven't drifted from real backend behavior
- Optional: community contributors with GPUs can run `pytest tests/integration/ -v` locally

This means CI/CD is green on every PR (Layer 1+2), and real hardware validation happens on merge (Layer 3).

---

## Package Architecture

```
Chimeraforge/
|-- pyproject.toml
|-- README.md
|-- LICENSE
|
|-- src/
|   +-- chimeraforge/
|       |-- __init__.py                    # __version__, top-level exports
|       |-- cli.py                         # Typer app -- subcommand registration
|       |
|       |-- planner/                       # Phase 1: Capacity Planner (TR133)
|       |   |-- __init__.py
|       |   |-- engine.py                  # 4-gate search algorithm
|       |   |-- models.py                  # 6 predictive models (predict-only)
|       |   |-- hardware.py                # GPU specs database
|       |   |-- constants.py               # Quant levels, model registry, backends
|       |   |-- formatter.py               # Rich terminal output + JSON
|       |   +-- data/
|       |       +-- fitted_models.json     # Baked-in model weights (~5KB)
|       |
|       |-- bench/                         # Phase 2: Benchmarking (TR108-TR122, TR126-TR130)
|       |   |-- __init__.py
|       |   |-- runner.py                  # Benchmark orchestrator
|       |   |-- backends/
|       |   |   |-- base.py                # Abstract backend interface
|       |   |   |-- ollama.py              # Ollama adapter
|       |   |   |-- vllm.py                # vLLM adapter
|       |   |   |-- tgi.py                 # TGI adapter
|       |   |   +-- transformers.py        # HuggingFace Transformers adapter
|       |   |-- metrics.py                 # Throughput, latency, VRAM, energy
|       |   |-- profiles.py                # Workload: single, batch, server (Poisson)
|       |   +-- scaling.py                 # Multi-instance scaling test (N=1..16)
|       |
|       |-- eval/                          # Phase 3: Quality Evaluation (TR124-TR125)
|       |   |-- __init__.py
|       |   |-- runner.py                  # Eval orchestrator
|       |   |-- metrics.py                 # BERTScore, ROUGE-L, exact match, coherence
|       |   |-- tasks.py                   # Task definitions (summarize, QA, code, etc.)
|       |   +-- quant_sweep.py             # Run all quant levels and compare quality
|       |
|       |-- report/                        # Phase 4: Report Generation
|       |   |-- __init__.py
|       |   |-- generator.py               # Markdown/HTML report generation
|       |   |-- analysis.py                # RMSE, MAE, MAPE, R-squared, statistical tests
|       |   +-- templates/                 # Report templates
|       |
|       +-- refit/                         # Phase 5: Model Re-fitting (TR133 lab code)
|           |-- __init__.py
|           |-- data_loader.py             # Raw data ingestion from benchmark results
|           |-- fitter.py                  # Fit all 6 models from data
|           +-- validator.py               # Validation metrics + spot checks
|
|-- tests/
|   |-- test_planner.py
|   |-- test_bench.py
|   |-- test_eval.py
|   |-- test_report.py
|   +-- test_refit.py
|
|-- experiments/                           # Existing TR108-TR123 research (unchanged)
|-- docs/                                  # Existing documentation (unchanged)
+-- outputs/                               # Existing reports (unchanged)
```

---

**Note (repo reality)**: This repo already contains `src/python/` and `src/rust/` research code. Make sure packaging only ships `src/chimeraforge/` (see the `include = ["chimeraforge*"]` fix in the `pyproject.toml` snippet below).

## Phased Development

### Phase 1: Capacity Planner (MVP)

**Goal**: `pip install chimeraforge && chimeraforge plan --model-size 3b --budget 50` works instantly.

**Acceptance criteria (MVP):**
- Runs with *base* install (no optional extras required).
- Works without a GPU present (planner-only mode).
- `--json` emits machine-readable JSON to stdout (no Rich formatting) suitable for CI.
- Deterministic for identical inputs (same ranked candidates).
- Uses clear non-zero exit codes for invalid inputs / infeasible constraints.

**Data sources**: TR123 (cost), TR124-TR125 (quality), TR127 (VRAM), TR128 (latency), TR129-TR130 (scaling), TR133 (planner logic).

**Source code to adapt from Banterhearts `research/tr133/`:**

| # | New File | Source in Banterhearts | Adaptation |
|---|---------|----------------------|------------|
| 1 | `pyproject.toml` | New | Package config with Typer + Rich deps |
| 2 | `src/chimeraforge/__init__.py` | New | `__version__ = "0.2.0"` |
| 3 | `src/chimeraforge/cli.py` | New | Typer app with `plan` subcommand |
| 4 | `src/chimeraforge/planner/__init__.py` | New | Package init |
| 5 | `src/chimeraforge/planner/engine.py` | `research/tr133/plan.py` | Rewire imports, extract search logic |
| 6 | `src/chimeraforge/planner/models.py` | `research/tr133/shared/models.py` | Strip `fit()` methods, remove `data_loader` dep, keep predict-only |
| 7 | `src/chimeraforge/planner/hardware.py` | `research/tr133/shared/hardware_db.py` | Direct copy (no Banterhearts imports) |
| 8 | `src/chimeraforge/planner/constants.py` | `research/tr133/shared/utils.py` | Extract constants only, remove repo paths |
| 9 | `src/chimeraforge/planner/formatter.py` | New | Rich panels + tables (replaces plain print) |
| 10 | `src/chimeraforge/planner/data/fitted_models.json` | `research/tr133/results/20260228_102350/fitted_models.json` | Direct copy (~5KB) |
| 11 | `tests/test_planner.py` | `tests/unit/test_tr133.py` | Adapt imports for new package structure |

**Key adaptations:**

1. **Import rewiring**: All `from research.tr133.shared.*` become `from chimeraforge.planner.*`
2. **Strip fitting code from models.py**: Remove all `fit()` methods, `serialize_models()`, and `data_loader` imports. Keep only `predict_*()` methods + `load_models()` + `PlannerModels` dataclass.
3. **Data path**: Use `importlib.resources` to find baked-in `fitted_models.json`:
   ```python
   from importlib.resources import files
   DEFAULT_MODELS_PATH = files("chimeraforge.planner.data").joinpath("fitted_models.json")
   ```
4. **Rich output**: Replace plain print statements with Rich panels, tables, and colors.

**6 predictive models (predict-only):**

| Model | Formula | Backed by |
|-------|---------|-----------|
| VRAMModel | `params_B * bpw/8 * overhead + KV_cache_GB` | TR127 (1,144 VRAM measurements) |
| ThroughputModel | Lookup + quant multipliers + size power law | TR123, TR127, TR129, TR130 (~10,000 records) |
| ScalingModel | Amdahl's `eta(N) = 1/(s + (1-s)*N)` per (model, backend) | TR129 (5,310), TR130 (4,797) |
| QualityModel | Lookup + FP16 baseline + avg quant deltas | TR124 (1,000), TR125 (25,890) |
| CostModel | `hw_cost/hr / (tok/s * 3600)` | TR119 (350), TR123 (350) |
| LatencyModel | M/D/1 queueing, 70% safety cap | TR128 (3,172), TR130 (4,797) |

**Decision algorithm (engine.py):**
```
For each (model, quant, backend, N=1..16):
  Gate 1 -- VRAM:    skip if predicted VRAM > GPU VRAM
  Gate 2 -- Quality: skip if predicted quality < target
  Gate 3 -- Latency: skip if predicted p95 > SLO
  Gate 4 -- Budget:  skip if predicted monthly cost > budget
  -> Add to candidates
Sort by cost (asc), quality (desc). Return best + top 4.
```

**Rich terminal output example:**
```
+--------------------------------------------------+
|        ChimeraForge Capacity Planner             |
+--------------------------------------------------+

  Constraints
  +------------------+------------------------+
  | Request rate     | 2.0 req/s              |
  | Latency SLO      | 500 ms (p95)           |
  | Quality target   | 0.6                    |
  | Budget           | $50/mo                 |
  | Hardware         | RTX 4080 Laptop (12GB) |
  +------------------+------------------------+

  Recommendation
  +------------------+------------------------+
  | Model            | llama3.2-3b (3.21B)    |
  | Quantization     | Q4_K_M (4.5 bpw)      |
  | Backend          | ollama                 |
  | Instances        | 1                      |
  | VRAM             | 2.64 GB                |
  | Throughput       | 181.9 tok/s            |
  | p95 Latency      | 146.2 ms               |
  | Quality          | 0.624 (negligible)     |
  | Monthly cost     | $25.20                 |
  +------------------+------------------------+

  Alternatives (top 4)
  +---+----------------------+--------+--------+---------+
  | # | Config               | $/mo   | Quality| p95 ms  |
  +---+----------------------+--------+--------+---------+
  | 1 | llama3.2-3b Q5_K_M   | $25.20 | 0.625  | 152.1   |
  | 2 | llama3.2-3b Q6_K     | $25.20 | 0.626  | 161.3   |
  | 3 | qwen2.5-1.5b Q4_K_M  | $25.20 | 0.584  | 98.4    |
  | 4 | llama3.2-3b FP16     | $25.20 | 0.538  | 189.7   |
  +---+----------------------+--------+--------+---------+
```

**pyproject.toml:**
```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "chimeraforge"
version = "0.2.0"
description = "LLM deployment optimizer -- backed by 70,000+ real measurements"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
dependencies = [
    "numpy>=1.24,<3.0",
    "scipy>=1.11,<2.0",
    "typer>=0.9,<1.0",
    "rich>=13.0,<14.0",
    "platformdirs>=4.0,<5.0",
]

[project.scripts]
chimeraforge = "chimeraforge.cli:app"

[project.optional-dependencies]
bench = ["psutil>=5.9", "pyyaml>=6.0,<7.0", "httpx>=0.25"]
eval = ["pyyaml>=6.0,<7.0", "httpx>=0.25"]
dev = ["pytest>=7.4,<9.0", "pytest-cov>=4.1,<6.0", "ruff>=0.3,<1.0"]
all = ["chimeraforge[bench,eval,dev]"]

[tool.setuptools.packages.find]
where = ["src"]
include = ["chimeraforge*"]

[tool.setuptools.package-data]
"chimeraforge.planner" = ["data/*.json"]
```

**Verification:**
```bash
pip install -e ".[dev]"
chimeraforge plan --help
chimeraforge plan --list-hardware
chimeraforge plan --list-models
chimeraforge plan --model-size 3b --request-rate 2 --budget 50
chimeraforge plan --model-size 3b --json
pytest tests/test_planner.py -v
```

---

### Phase 2: Benchmarking Engine

**Goal**: `chimeraforge bench --model llama3.2-3b --backend ollama` runs real benchmarks.

**Data sources**: TR108-TR122 patterns (agent benchmarking), TR126 (Docker), TR127 (long-context), TR128 (workload profiles), TR129 (scaling), TR130 (backend comparison).

**Commands:**
```bash
chimeraforge bench --model llama3.2-3b --backend ollama
chimeraforge bench --model llama3.2-3b --backend ollama --all-quants
chimeraforge bench --model llama3.2-3b --backend ollama --scale 1,2,4,8
chimeraforge bench --model llama3.2-3b --backend vllm --workload server --rate 2.0
chimeraforge bench --model llama3.2-3b --backend ollama --measure vram,energy
chimeraforge bench --model llama3.2-3b --backend ollama --context 512,2048,8192,32768
```

**Features:**
- Backend adapters: Ollama (HTTP), vLLM (OpenAI-compatible), TGI (HTTP), Transformers (local)
- Metrics: throughput (tok/s), latency (TTFT, p50/p95/p99), VRAM, GPU utilization, energy (optional)
- Workload profiles: single-stream, batch, server (Poisson arrivals from TR128)
- Scaling test: N=1..16 instances, measures Amdahl's serial fraction (TR129 methodology)
- Context sweep: VRAM and latency vs context length (TR127 methodology)
- Output: JSON/CSV in `~/.chimeraforge/results/`
- Repro metadata: record OS, GPU, driver/CUDA, backend version, model name/tag, and CLI version in every result artifact
- Rich progress: live progress bars, real-time metrics

**Differentiators vs Bench360:**
- **Cross-platform planning** (Windows/macOS/Linux) and **Ollama-first benchmarking**; other backends supported where available (often Linux/Docker)
- **Ollama-first** (most accessible local LLM runtime for consumer GPUs)
- **Consumer GPU focus** (8-24GB VRAM, not A100/H100)
- **Integrated with planner** -- results feed back into model re-fitting

---

### Phase 3: Quality Evaluation

**Goal**: `chimeraforge eval --model llama3.2-3b --quant-sweep` measures quality across quantization levels.

**Data sources**: TR124 (quality baseline methodology), TR125 (quant sweep methodology).

**Commands:**
```bash
chimeraforge eval --model llama3.2-3b --quant Q4_K_M
chimeraforge eval --model llama3.2-3b --quant-sweep           # all 7 quant levels
chimeraforge eval --model llama3.2-3b --tasks mmlu,arc        # specific benchmarks
chimeraforge eval --compare Q4_K_M,Q8_0,FP16                  # side-by-side
```

**Features:**
- Quality metrics: BERTScore, ROUGE-L, exact match, coherence (from eval framework)
- Real benchmarks: MMLU (285 questions), ARC-Challenge (200 questions) from TR125
- Quant sweep: Automatically test all 7 levels (FP16 to Q2_K) and rank
- Quality tiers: Negligible / Acceptable / Concerning / Unacceptable (from TR125 findings)
- Cross-reference: quality vs throughput vs cost (TR125's quality-performance curves)
- Dataset hygiene: do not ship restricted benchmark data; fetch datasets on-demand and cache locally (document licensing clearly)

**Key TR125 finding baked in**: Q4_K_M is the universal sweet spot (all models within -4.1pp of baseline).

---

### Phase 4: Report Generation

**Goal**: `chimeraforge report` generates publishable analysis from benchmark/eval results.

**Data sources**: All TRs -- report format follows TR108-TR133 standards.

**Commands:**
```bash
chimeraforge report                                            # latest results
chimeraforge report --results ~/.chimeraforge/results/latest/
chimeraforge report --format markdown                          # GitHub-ready
chimeraforge report --format html                              # shareable
chimeraforge report --compare ollama,vllm,tgi                  # cross-backend
```

**Features:**
- Auto-analysis: RMSE, MAE, MAPE, R-squared (from TR133 analyze.py methodology)
- Statistical tests: CI, effect sizes, Holm correction (from TR131/TR132 methodology)
- Comparison tables: model x quant x backend performance matrix
- Decision matrix: for each constraint set, the optimal configuration
- Export: Markdown, HTML, JSON

---

### Phase 5: Model Re-fitting

**Goal**: `chimeraforge refit` lets users improve the planner with their own benchmark data.

**Data sources**: TR133's fitting pipeline (data_loader.py, run.py, analyze.py).

**Commands:**
```bash
chimeraforge refit --results ~/.chimeraforge/results/          # re-fit from user data
chimeraforge refit --validate                                  # run validation suite
chimeraforge refit --export custom_models.json                 # export for sharing
chimeraforge plan --models-path custom_models.json             # use custom models
```

**This closes the loop:**
1. `chimeraforge bench` -- collect data on your hardware
2. `chimeraforge refit` -- update predictive models with your data
3. `chimeraforge plan` -- get hardware-specific recommendations

The planner gets smarter with every benchmark run.

**Overfitting protection — Bayesian blending, not replacement:**

`refit` does NOT replace the global models with local data. A user who tests 3 models on 1 backend would get a hopelessly overfit planner if we did that. Instead, refitting uses the 70,000+ baked-in measurements as a strong prior and applies hardware-specific corrections:

1. **Global prior**: The shipped `fitted_models.json` (fit on 70k+ measurements) defines the baseline for every prediction
2. **Hardware offset**: User benchmarks compute `measured_tps / predicted_tps` ratios for each (model, backend) they test. The median ratio becomes a per-GPU throughput multiplier (e.g., "my RTX 3060 runs 0.72x of what the RTX 4080 model predicts")
3. **Minimum data gate**: At least 5 benchmark runs are required before any offset is applied. Below that, refitting is rejected with a message explaining why
4. **Confidence weighting**: Offsets are blended proportional to sample size. 5 runs = low weight (mostly global prior). 50 runs = high weight (mostly local data). This follows a simple `w = min(1.0, n_samples / 50)` schedule
5. **Validation check**: After refitting, `chimeraforge refit --validate` runs the TR133 spot-check suite against the blended model. If any spot check fails, the refit is rolled back with a warning

This ensures the planner never gets *worse* from user data, only more hardware-specific.

---

## Source Code Reference (Banterhearts)

All Phase 1 source code lives in `research/tr133/` in the Banterhearts (private) repo:

| Banterhearts File | Purpose | Phase 1 Action |
|------------------|---------|----------------|
| `research/tr133/shared/models.py` (~650 lines) | 6 predictive models with fit + predict | Strip fit(), keep predict + load |
| `research/tr133/shared/hardware_db.py` (~80 lines) | GPU specs database | Direct copy |
| `research/tr133/shared/utils.py` (~100 lines) | Constants, quant levels, model registry | Extract constants only |
| `research/tr133/plan.py` (~414 lines) | CLI planner with argparse | Adapt to Typer, rewire imports |
| `research/tr133/shared/data_loader.py` (~400 lines) | Raw data ingestion from TR123-TR132 | Phase 5 only (not needed for MVP) |
| `research/tr133/run.py` (~200 lines) | Model fitting orchestrator | Phase 5 only |
| `research/tr133/analyze.py` (~424 lines) | Validation metrics + spot checks | Phase 5 only |
| `research/tr133/results/20260228_102350/fitted_models.json` | Serialized model weights | Bake into package data |
| `tests/unit/test_tr133.py` (~729 lines, 71 tests) | Comprehensive test suite | Adapt imports for Phase 1 |

### Validation Targets (from TR133)

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Throughput R-squared | > 0.85 | 0.859 | PASS |
| VRAM R-squared | > 0.95 | 0.968 | PASS |
| Quality RMSE | < 0.10 | 0.062 | PASS |
| Latency MAPE | < 0.25 | 0.011 | PASS |
| Spot checks | 10/10 | 10/10 | PASS |

---

## What Stays in Banterhearts (Private)

- Raw experiment code for all TRs (`research/tr108-tr133/`)
- Raw benchmark data (CSVs, JSONs from 26 experiments)
- Config files with internal paths
- Eval framework source (`scripts/eval/`)
- Full test suite
- Experiment status tracking

## What Goes to ChimeraForge (Public)

- Packaged CLI tool (`src/chimeraforge/`)
- Fitted model weights (`fitted_models.json`)
- GPU hardware database
- Technical reports (existing TR108-TR121 + new TR124-TR133)
- Tests for the packaged tool
- Updated README with tool-first narrative

## Existing ChimeraForge Content (Unchanged)

- `experiments/` -- TR108-TR123 experiment artifacts
- `src/python/banterhearts/` -- Python agent implementations
- `src/rust/demo_agent/` -- Rust agent implementation
- `docs/` -- existing documentation
- `outputs/publish_ready/reports/` -- existing TR108-TR121 reports
- `benchmarks/` -- existing benchmark results
- `data/` -- existing benchmark data

---

## Known Limitations (document honestly)

1. **Single GPU source (current fit)**: All shipped planner weights are fit primarily on a single machine (NVIDIA GeForce RTX 4080 Laptop GPU, ~12GB VRAM). Other GPUs use bandwidth/compute scaling heuristics.
2. **Model-size fit range (planner)**: Planner weights are best within the fitted range (roughly 0.5B-8B). Larger models rely on extrapolation (TR121 scaling data to 20B exists but is not yet fully integrated into the shipped weights).
3. **3 serving backends**: Ollama, vLLM, TGI. No SGLang, LMDeploy.
4. **GGUF quants only**: Q2_K through FP16. No AWQ, GPTQ.
5. **M/D/1 latency**: Approximate at high utilization (mitigated by 70% safety cap from TR128).
6. **Quality data from 5 models**: Quality predictions for unseen models use average deltas.

All limitations addressable by running Phase 2 benchmarks on more hardware and feeding into Phase 5 re-fitting.

---

## Implementation Priority

**Phase 1 is the MVP.** Ship it first. Everything else builds on it.

```
Phase 1 (Planner)          <-- Can build now, no GPU needed to use
  |
Phase 2 (Bench)            <-- Needs GPU + Ollama/vLLM/TGI
  |
Phase 3 (Eval)             <-- Needs GPU + Ollama + eval datasets
  |
Phase 4 (Report)           <-- Needs Phase 2 or 3 results
  |
Phase 5 (Refit)            <-- Needs Phase 2 results, closes the loop
  |
  |  ---- MVP complete, tool is self-contained ----
  |
Phase 6 (Deploy & Monitor) <-- Auto-deploy + production observability
  |
Phase 7 (Community)        <-- Crowdsourced hardware DB, network effects kick in
  |
Phase 8 (Safety)           <-- Safety-aware evaluation (the Anthropic hook)
  |
Phase 9 (Universal)        <-- Apple Silicon, AMD, multi-GPU, all quant formats
  |
Phase 10 (Standard)        <-- Industry standard, publications, vendor adoption
```

---

## Long-Term Vision: Phases 6-10

### Why This Matters Beyond a Portfolio Project

By 2030, local LLM deployment will be as common as running a web server. Anthropic will ship Claude Local. OpenAI will ship GPT Local. Meta already ships Llama. Google has Gemini Nano. Apple Intelligence runs local models on every iPhone.

When that happens, every developer, every enterprise, and every AI lab needs answers to the same question: **"How do I deploy this model optimally on this hardware?"**

The tool that answers that question with empirical data — across thousands of hardware configurations, quantization formats, serving stacks, and safety evaluations — becomes infrastructure. Not a nice-to-have. Infrastructure.

**ChimeraForge's endgame is to become the MLPerf of local LLM inference.** But unlike MLPerf (datacenter-only, throughput-only, no quality, no safety, no cost), ChimeraForge measures everything that matters for deployment decisions: performance + quality + safety + cost + energy, on the hardware people actually use.

---

### Phase 6: Deploy & Monitor

**Goal**: `chimeraforge deploy` doesn't just recommend — it sets up and runs the optimal configuration. `chimeraforge monitor` watches it in production.

**Commands:**
```bash
# Auto-deploy the recommended configuration
chimeraforge deploy --model-size 3b --budget 50
# -> Pulls model from Ollama/HuggingFace
# -> Applies recommended quant level
# -> Starts serving backend with optimal settings
# -> Verifies it's running and meeting SLOs

# Monitor a running deployment
chimeraforge monitor --port 11434
# -> Live throughput, latency, VRAM, GPU utilization
# -> SLO violation alerts
# -> Prometheus/Grafana export

# Optimize a running deployment without downtime
chimeraforge optimize --target latency
# -> Tries different batch sizes, context lengths
# -> A/B tests configurations
# -> Applies the best one
```

**Design decision — config generation, not service management:**

Cross-OS daemon management (systemd, launchd, Windows Services) is a well-known minefield of permissions, edge cases, and silent failures. ChimeraForge does NOT try to be an orchestrator. Instead, `deploy` generates standardized config files for the user's platform and lets battle-tested tooling do the actual process management:

| Platform | `chimeraforge deploy` generates | User runs |
|----------|--------------------------------|-----------|
| Linux (systemd) | `chimeraforge-llama3.2-3b.service` + env file | `systemctl start chimeraforge-llama3.2-3b` |
| Linux/Mac (Docker) | `docker-compose.yml` with optimal settings | `docker compose up -d` |
| macOS (launchd) | `com.chimeraforge.llama3.2-3b.plist` | `launchctl load ...` |
| Any (Ollama) | Modelfile + recommended `OLLAMA_NUM_PARALLEL` | `ollama serve` |

This separation means ChimeraForge handles the *what* (optimal model, quant, backend, concurrency settings), and proven infrastructure tooling handles the *how* (keeping the process alive, restart on crash, log management).

**Features:**
- Model auto-pull: fetch from Ollama registry or HuggingFace Hub
- Config generation: produces deployment configs for systemd, Docker Compose, launchd, or plain Ollama
- Health checks: `chimeraforge deploy --verify` pings the running service to confirm it's loaded and responding
- SLO monitoring: `chimeraforge monitor` watches a running endpoint for latency/throughput violations
- Prometheus exporter: `chimeraforge monitor --export prometheus` for Grafana dashboards
- Hardware monitoring: Uses NVML (NVIDIA), ROCm SMI (AMD), or `powermetrics` (macOS) — with clear errors when privileged access is needed

**Why labs care:** Customer success. "Install ChimeraForge, run `deploy`, apply the generated config, it works." Deterministic, auditable, no magic.

---

### Phase 7: Community & Crowdsourced Hardware Database

**Goal**: Every user who runs `chimeraforge bench` can opt-in to contribute their results. The planner gets better for everyone.

**This is where network effects kick in.** But network effects need a cold-start strategy and careful aggregation to be trustworthy.

**The cold-start problem and bootstrap strategy:**

Why would someone spend hours running benchmarks and power for free? Three incentives:
1. **Self-interest**: Running `chimeraforge bench --upload` gives the user hardware-specific predictions that are *better for them*. Upload is a byproduct of their own benchmarking.
2. **Leaderboard ego**: "My RTX 4090 achieves 312 tok/s on llama3.2-3b — top 5 worldwide." Gamification drives contributions.
3. **Seed the database ourselves**: Before relying on community, we bootstrap with cloud GPU rentals (Lambda Labs, RunPod, Vast.ai). A weekend of ~$200 on 10 GPU SKUs generates the initial 10-GPU seed database. Partner with hardware reviewers (e.g., LTT, GN, Tom's Hardware) who already benchmark GPUs — offer ChimeraForge as a standard LLM benchmarking step.

**Commands:**
```bash
# Run benchmark and upload results (opt-in)
chimeraforge bench --model llama3.2-3b --backend ollama --upload

# Download community-fitted models for a specific GPU
chimeraforge community pull --hardware "RTX 4090 24GB"

# Browse the hardware leaderboard
chimeraforge community leaderboard

# Submit your GPU to the database
chimeraforge community register-hardware
```

**Environment fingerprinting — the variance problem:**

An RTX 3060 on Windows/WSL2/Ollama performs drastically differently from an RTX 3060 on native Ubuntu/vLLM. The GPU name alone is insufficient. Every uploaded benchmark includes a full environment fingerprint:

```json
{
  "gpu": "RTX 3060 12GB",
  "gpu_driver": "560.35.03",
  "cuda_version": "12.4",
  "os": "Ubuntu 22.04 (native)",
  "runtime": "bare-metal",
  "backend": "ollama",
  "backend_version": "0.5.4",
  "python": "3.12.1",
  "chimeraforge": "0.4.0"
}
```

Aggregation groups by the **full environment tuple** `(GPU_family, OS_class, runtime, backend)`, not just GPU name. This means:
- `RTX 3060 | Linux-native | ollama` = one prediction cluster
- `RTX 3060 | Windows-WSL2 | ollama` = a different prediction cluster
- Community models are fit per-cluster, with cross-cluster bandwidth scaling as fallback

**Architecture:**
- **Central API** (hosted): receives anonymized benchmark results with environment fingerprints, aggregates into community-fitted models per environment cluster
- **Hardware database**: grows from 15 GPUs (current) to thousands, with real measurement data for each environment tuple
- **Community-fitted models**: separate `fitted_models.json` per (GPU family, OS class, backend) cluster
- **Leaderboard**: public rankings filterable by hardware, OS, backend
- **Data privacy**: only performance metrics + environment metadata uploaded. No prompts, no outputs, no identifying info. Schema is public and auditable.
- **Outlier rejection**: uploads with >3 sigma deviation from cluster mean are flagged for review, not silently included

**Growth model:**
```
Phase 1-5: 1 GPU (RTX 4080), predictions use scaling heuristics for others
Pre-launch: $200 cloud GPU weekend seeds 10 GPU SKUs
Phase 7 launch: 10-50 GPUs from early adopters
6 months: 200-500 environment tuples from community
1 year: 1000+ environment tuples, predictions are empirically grounded for most consumer setups
2 years: ChimeraForge IS the hardware database. No one else has this data at this granularity.
```

**Why labs care:** Hardware qualification at zero cost. Anthropic doesn't need to buy 50 GPU SKUs in 3 OS configurations to know how Claude Local performs. The community already tested it — with environment context.

---

### Phase 8: Safety-Aware Evaluation

**Goal**: `chimeraforge safety` measures whether inference optimizations (quantization, concurrency, serving stack) degrade safety behaviors.

**This is the feature that makes ChimeraForge essential for responsible AI labs.** No other tool does this. The gap in the literature is total.

**Research foundation:** TR134-TR137 (The Safety Pivot) — planned experiments with concrete methodology:
- TR134: Alignment robustness under quantization (does Q4_K_M break refusal?)
- TR135: Multi-agent concurrency x safety (does load degrade alignment?)
- TR136: Cross-backend safety consistency (does vLLM produce different safety behavior than Ollama?)
- TR137: Unified safety tax analysis (the synthesis)

**Commands:**
```bash
# Safety evaluation across quantization levels
chimeraforge safety --model llama3.2-3b --quant-sweep
# -> Runs AdvBench/HarmBench harmful prompts at each quant level
# -> Runs TruthfulQA for sycophancy/hallucination
# -> Runs BBQ for bias
# -> Plots capability vs safety degradation curves

# Safety under concurrency
chimeraforge safety --model llama3.2-3b --concurrency 1,2,4,8

# Cross-backend safety comparison
chimeraforge safety --model llama3.2-3b --backends ollama,vllm,tgi

# Full safety audit (all axes)
chimeraforge safety --model llama3.2-3b --full-audit
# -> Output: "Q4_K_M retains 97% capability but only 82% refusal rate"
# -> Output: "SAFETY WARNING: Below Q3_K_S, refusal rate drops 25%"
```

**Safety metrics:**
- Refusal rate on harmful prompts (AdvBench/HarmBench)
- Truthfulness (TruthfulQA)
- Bias resistance (BBQ benchmark)
- Instruction following under degraded conditions
- Soft refusal detection (hedging, warnings, partial compliance)

**The judge problem — who evaluates safety outputs?**

Evaluating whether a model "refused" a harmful prompt is not a string-matching problem. A model might softly comply ("As an AI I shouldn't, but here's how..."), hedge with disclaimers, or give a refusal that's technically correct but practically useless. Three evaluation tiers, escalating in accuracy and resource cost:

| Tier | Method | Accuracy | Resource cost | When to use |
|------|--------|----------|---------------|-------------|
| 1 | **Rule-based classifier** | ~75% | Zero (no extra model) | Default. Fast screening. |
| 2 | **Local judge model** | ~90% | +2-4GB VRAM | `--judge local` (Llama-Guard-3-1B or similar small safety classifier) |
| 3 | **External judge API** | ~97% | API cost (~$0.01/eval) | `--judge api --api-key $KEY` (GPT-4o, Claude) |

**Tier 1 (default — no extra resources):** A rule-based classifier using keyword matching, regex patterns, and output structure heuristics. Catches clear refusals ("I cannot", "I'm not able to") and clear compliance (outputs containing harmful content markers from the benchmark's expected-output field). This is brittle for edge cases but sufficient for detecting large-scale safety degradation across quant levels (the primary use case). False positive rate is acceptable because we're measuring *trends*, not absolute refusal rates.

**Tier 2 (local judge):** A small safety classifier (Llama-Guard-3-1B, ~1.2B params, ~2GB VRAM) runs alongside the model under test. ChimeraForge handles the VRAM budget: if the model under test + judge exceed available VRAM, the judge runs sequentially (model loaded, tested, unloaded, then judge loaded for evaluation). This doubles wall time but keeps VRAM within bounds. Quality benchmarks are adjusted to exclude the judge's VRAM from the model's measurements.

**Tier 3 (API judge):** For publication-grade safety audits, an external LLM-as-judge (GPT-4o, Claude) evaluates each output via API. Requires an API key and incurs cost (~$0.01 per evaluation, ~$10 for a full 1000-prompt audit). The `--judge api` flag makes this explicit and opt-in. Results include the judge model's identity for reproducibility.

The default (Tier 1) ensures `chimeraforge safety` works out of the box with zero extra resources, maintaining the "local only" ethos. Tiers 2-3 are for users who need higher accuracy.

**Key output — The Safety Degradation Curve:**
```
Two curves plotted on the same axes:
  X-axis: Quantization level (FP16 -> Q2_K)
  Y-axis: Score (0-1)

  Capability curve: gradual decline (FP16: 0.85, Q4_K_M: 0.82, Q2_K: 0.71)
  Safety curve:     steeper decline (FP16: 0.95, Q4_K_M: 0.88, Q2_K: 0.62)

  If safety drops faster than capability, that's the finding.
  If they track together, that's also useful (safety is robust).
  Either way, nobody has measured this.
```

**Why labs NEED this:**
1. **Regulatory compliance**: As AI regulation increases (EU AI Act, executive orders), labs may need to prove their models maintain safety properties under deployment conditions. ChimeraForge provides the evidence.
2. **Liability**: If a customer quantizes Claude Local to Q2_K and it stops refusing harmful prompts, Anthropic has a liability problem. ChimeraForge quantifies the risk.
3. **Deployment guidelines**: "Use Q4_K_M or higher for safety-critical applications" — backed by data, not gut feel.
4. **Competitive differentiation**: "Our model retains 95% safety at Q4_K_M while Competitor X drops to 70%." ChimeraForge provides the vendor-neutral benchmark.

**Publication target:** Paper 7 — "The Safety Tax of Inference Optimization" (AAAI Safe AI / NeurIPS Safety Workshop)

---

### Phase 9: Universal Hardware & Format Coverage

**Goal**: ChimeraForge works on every GPU, every quant format, every serving stack.

**Hardware expansion:**
```bash
# Apple Silicon (MLX backend)
chimeraforge bench --model llama3.2-3b --backend mlx --hardware "M4 Pro 18GB"

# AMD GPUs (ROCm)
chimeraforge bench --model llama3.2-3b --backend ollama --hardware "RX 7900 XTX 24GB"

# Intel GPUs (XPU)
chimeraforge bench --model llama3.2-3b --backend ollama --hardware "Arc A770 16GB"

# Multi-GPU
chimeraforge bench --model llama3.2-70b --backend vllm --gpus 2 --parallel tensor

# Edge/mobile (future)
chimeraforge bench --model phi-3-mini --backend onnxruntime --hardware "Snapdragon 8 Gen 3"
```

**Quantization format expansion:**
- GGUF (current): Q2_K through FP16
- GPTQ: 2-8 bit, asymmetric/symmetric
- AWQ: 4-bit, activation-aware
- FP8 (E4M3/E5M2): emerging standard for H100/B200
- bitsandbytes: NF4, INT8
- ExLlamaV2: optimized GPTQ runtime
- Mixed precision: different layers at different bit widths

**Backend plugin architecture:**
```python
# Anyone can add a backend
class MyBackend(ChimeraForgeBackend):
    name = "my-custom-backend"

    def start(self, model, config): ...
    def generate(self, prompt, params): ...
    def measure_vram(self): ...
    def stop(self): ...

# Register via entry points in pyproject.toml
[project.entry-points."chimeraforge.backends"]
my-backend = "my_package:MyBackend"
```

**Model scale expansion:**
- Current: 0.5B-8B (measured)
- Target: 0.5B-70B (13B and 70B via multi-GPU or quantized)
- Future: 100B+ (multi-node, speculative decoding)

**Why labs care:** Universal coverage means their model is tested everywhere their customers deploy it. Not just A100s in datacenters, but MacBook Pros, gaming PCs, and edge devices.

---

### Phase 10: Industry Standard

**Goal**: ChimeraForge becomes the accepted standard for local LLM deployment evaluation — cited in papers, used by labs, trusted by the community.

**Components:**

**1. The ChimeraForge Score**
A single composite score that captures deployment readiness:
```
CF Score = w1*Throughput + w2*Quality + w3*Safety + w4*Efficiency + w5*Cost
```
- Like 3DMark for GPUs, but for LLM deployment
- Comparable across hardware, models, and configurations
- Published methodology, reproducible by anyone
- Breakdown subscores for each dimension

**2. Academic Publications (7+ papers)**

| # | Paper | Venue | Status |
|---|-------|-------|--------|
| 1 | The Compile Paradox | MLSys / NeurIPS | Data ready (TR120+TR126) |
| 2 | Phase-Dependent Inference Scaling Laws | MLSys | Data ready (TR121+TR127) |
| 3 | Multi-Agent Orchestration Overhead | USENIX ATC / EuroSys | Data ready (TR129+TR130+TR131) |
| 4 | Validated LLM Energy Measurement | ISPASS / IGSC | Data ready (TR119+TR122) |
| 5 | Quality-Cost Pareto Frontiers | NeurIPS D&B / EMNLP | Data ready (TR124+TR125) |
| 6 | Consumer Benchmark Suite | MLSys / NeurIPS D&B | Needs Phase 7 data |
| 7 | The Safety Tax of Inference Optimization | AAAI Safe AI / NeurIPS | Needs TR134-137 |

Published papers = citations = credibility = adoption. MLPerf became the standard because it was published, peer-reviewed, and vendor-neutral. Same path.

**3. CI/CD Integration**
```yaml
# GitHub Action: benchmark on every model release
name: ChimeraForge Benchmark
on:
  release:
    types: [published]

jobs:
  benchmark:
    runs-on: [self-hosted, gpu]
    steps:
      - uses: chimeraforge/benchmark-action@v1
        with:
          model: ${{ github.event.release.tag_name }}
          backends: [ollama, vllm]
          report: true
          upload: true  # contribute to community DB
```

**4. Python SDK**
```python
from chimeraforge import Planner, Benchmark

# Programmatic planning
planner = Planner.from_default()
result = planner.recommend(
    model_size="3b",
    request_rate=2.0,
    latency_slo=500,
    budget=50,
    hardware="RTX 4080 12GB",
)
print(result.best.model)        # "llama3.2-3b"
print(result.best.quant)        # "Q4_K_M"
print(result.best.monthly_cost) # 25.20

# Programmatic benchmarking
bench = Benchmark(backend="ollama", model="llama3.2-3b")
results = bench.run(quants=["FP16", "Q4_K_M", "Q2_K"])
```

**5. REST API**
```bash
# Self-hosted API server
chimeraforge serve --port 8080

# Query
curl localhost:8080/plan \
  -d '{"model_size":"3b","budget":50,"hardware":"RTX 4080 12GB"}'
```

**6. Vendor Adoption Program**
- Labs submit their models to ChimeraForge for evaluation
- ChimeraForge runs standardized benchmarks across community hardware
- Results published on the leaderboard
- "ChimeraForge Certified" badge for models that meet quality + safety + performance thresholds
- Labs get hardware coverage data they couldn't collect themselves

---

## Why Anthropic and OpenAI Would Need This

### The 2030 Scenario

Both companies will ship local models. When they do, they face problems they've never had with cloud APIs:

| Cloud API (today) | Local Model (2030) | ChimeraForge solves |
|-------------------|--------------------|---------------------|
| Anthropic controls the hardware | Customer controls the hardware | Community hardware DB tells Anthropic how Claude runs on 1000+ GPU SKUs |
| Anthropic controls quantization | Customer quantizes however they want | Safety evaluation proves which quant levels are safe to recommend |
| Single deployment config | Thousands of configs (GPU x quant x backend x concurrency) | Planner recommends the right config for each customer |
| Anthropic monitors quality | No visibility post-deployment | ChimeraForge Score provides a deployment quality standard |
| One inference stack | Customer chooses Ollama/vLLM/TGI/llama.cpp | Backend benchmarks show which stack works best per hardware |

### What They Can't Build Internally

1. **Vendor-neutral credibility**: Anthropic benchmarking Claude with their own tool has zero credibility. A community standard has credibility.
2. **Hardware diversity**: Anthropic can't buy every GPU SKU. The community already owns them.
3. **Safety validation at scale**: Running safety benchmarks across (7 quant levels x 3 backends x 8 concurrency levels x 100+ GPU SKUs) = 16,800 configurations. No single lab can do this. A community tool can.
4. **Competitive benchmarking**: Labs need a neutral third party to compare models. ChimeraForge is that party.

### The Pitch

> "We built ChimeraForge — the first open-source tool that measures performance + quality + safety together for local LLM deployment on consumer hardware. We have 70,000+ measurements, 7 planned publications, and a crowdsourced hardware database growing to 1000+ GPUs. When you ship Claude Local, your customers will use this tool to deploy it. We'd like to be the first to evaluate it."

---

## Critique & Risk Mitigation

| Critique | Response |
|----------|----------|
| "One GPU's data isn't enough" | Exactly why Phase 7 exists. Each user adds data. Bootstrap with $200 cloud GPU weekend. Network effects compound. |
| "MLPerf already exists" | MLPerf is datacenter-only, throughput-only, no quality, no safety, no cost. Different market. |
| "Too ambitious for one person" | Phases 1-5 are one person. Phases 6-10 are community-driven. The tool grows because users contribute. |
| "Labs will build their own" | They need VENDOR-NEUTRAL benchmarks. Same reason MLPerf exists. |
| "Safety angle is speculative" | TR134-137 methodology is concrete. Even null result is publishable. |
| "Typer/CLI won't scale to enterprise" | Core logic is decoupled from CLI. SDK and API are thin layers on top. |
| "No funding model" | Open source core + premium features (hosted API, enterprise support, certified benchmarks). Same as Grafana, GitLab, Hugging Face. |
| "Competition could emerge" | First-mover + crowdsourced data = moat. The hardware database is the defensible asset. |
| "Community data will be noisy" | Aggregation groups by full environment tuple (GPU + OS + runtime + backend), not just GPU name. Outlier rejection at 3 sigma. |
| "Refit will overfit on sparse data" | Refit uses Bayesian blending — 70k baked-in measurements as prior, user data as hardware-specific offset. Min 5 runs required. |
| "Deploy can't manage cross-OS daemons" | Deploy generates config files (systemd units, docker-compose, launchd plists), not a bespoke service manager. Proven tooling runs the process. |
| "Safety eval needs LLM-as-judge" | Three tiers: rule-based (default, zero cost), local judge (Llama-Guard, +2GB), API judge (GPT-4o, opt-in). Default works offline. |
| "OTA updates are a supply chain risk" | OTA data is coefficients-only JSON, never code. SHA256 checksum verification on every fetch. Schema validated on load. |
| "Can't CI test a GPU tool without GPUs" | Three-layer test strategy: pure logic (no GPU), mocked backends (no GPU), integration (self-hosted GPU runner on merge). |

---

## Success Metrics by Phase

| Phase | Metric | Target |
|-------|--------|--------|
| 1 | PyPI installs | 100 in first month |
| 2-3 | Users running benchmarks | 50 unique GPUs benchmarked |
| 4-5 | Self-sustaining feedback loop | Users refit models from their own data |
| 6 | Deployments managed | 100 active `chimeraforge deploy` instances |
| 7 | Community hardware DB | 500+ GPUs with real measurement data |
| 8 | Safety evaluations run | 1000+ safety audit reports generated |
| 9 | Hardware coverage | 50+ GPU SKUs with community-fitted models |
| 10 | Citations | ChimeraForge cited in 10+ papers; 1+ lab using it for model validation |
