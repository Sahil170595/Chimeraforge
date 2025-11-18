# Chimeraforge

Chimeraforge is the benchmark-only breakout from the Banterhearts program. It
contains every asset required to measure agent performance (Python and Rust),
run the TR-series test plans, and publish the technical reports that feed the
production decision process. Production APIs, orchestration services, and UX
assets stayed behind in the Banterhearts monolith so this repository can stay
lean, reproducible, and laser-focused on measurement.

## Scope at a Glance
- **Bench harnesses**: `src/python/banterhearts/demo_agent`, `src/python/banterhearts/demo_multiagent`,
  plus the Rust demos (`src/rust/demo_agent`, `src/rust/demo_multiagent`) and runtime optimization suites.
- **Research data**: `benchmarks/python/chimera_sweep`, `benchmarks/python/demo_agent_benchmark`,
  `benchmarks/rust/quick_test`, `data/`, and archived logs.
- **Outputs**: All reports, artifacts, and run results are consolidated in `outputs/`.
- **Experiments**: All TR-series experiments are organized in `experiments/`.
- **Operator tooling**: Python helper scripts in `scripts/` and Windows-specific
  wrappers in `scripts/windows/`.
- **Documentation**: Everything relevant lives under `docs/` (see map below).

Anything production-critical (APIs, product requirements, infrastructure) lives
back in the Banterhearts repo and is intentionally absent here.

## Directory Map
| Path | Purpose |
| --- | --- |
| **Source Code** | |
| `src/python/banterhearts/` | Python source code package |
| `src/python/banterhearts/benchmarking` | Shared benchmarking utilities imported by the demo agents. |
| `src/python/banterhearts/demo_agent` | Python single-agent harness, configs, results, and analysis helpers. |
| `src/python/banterhearts/demo_multiagent` | Python multi-agent harness plus TR110/111 pipelines. |
| `src/python/banterhearts/monitoring` | Monitoring and performance tracking utilities. |
| `src/rust/demo_agent` | Rust single-agent implementation that mirrors the Python demo. |
| `src/rust/demo_multiagent` | Rust multi-agent implementation that mirrors the Python demo. |
| **Experiments** | |
| `experiments/TR111/` | Technical Report 111 experiment artifacts and scripts. |
| `experiments/TR112/` | Technical Report 112 experiment artifacts and scripts. |
| `experiments/TR114/` | Technical Report 114 experiment artifacts and scripts. |
| `experiments/TR115_runtime_optimization/` | Runtime comparison suite (Tokio, async-std, smol, etc.). |
| **Data** | |
| `data/baselines/` | Canonical baseline JSON/TXT snapshots. |
| `data/csv/` | CSV exports and data files. |
| `data/research/` | Research data from various experiments. |
| **Outputs** | |
| `outputs/artifacts/` | Generated artifacts (profiles, visualizations, etc.). |
| `outputs/reports/` | Intermediate technical reports and analysis. |
| `outputs/runs/` | Benchmark run outputs and results. |
| `outputs/publish_ready/` | Final, ready-to-share technical reports and notebooks. |
| **Benchmarks** | |
| `benchmarks/python/*` | Python sweep outputs (`chimera_sweep`, `demo_agent_benchmark`) and other replayable artifacts (see `benchmarks/README.md`). |
| `benchmarks/rust/quick_test` | Latest Rust quick-test drops captured by the PowerShell helper. |
| **Other** | |
| `logs/benchmarks/` | Archived benchmark logs. |
| `scripts/` | Cross-platform helper scripts (Python). |
| `scripts/windows/` | PowerShell wrappers for Windows-specific operations. |
| `resources/prompts/` | Benchmark and test prompts. |
| `resources/patches/` | Patch notes and changelogs. |
| `docs/` | Documentation and guides. |

## Getting Started
1. Install prerequisites (`Python 3.11+`, `Rust 1.70+`, `Ollama`, `CUDA 11.8+`).
2. Clone this repository and create a Python virtual environment.
3. Build the Rust demos:
   - `cd src/rust/demo_agent && cargo build --release`
   - `cd src/rust/demo_multiagent && cargo build --release`
4. Pull the target model via Ollama (`ollama pull gemma3:latest`).
5. Follow `docs/quick_start.md` for your first single-agent and multi-agent runs.

Need platform specifics? See `docs/installation.md` for OS-specific setup,
`docs/dual_ollama_setup.md` for concurrent runs, and `docs/benchmarking.md` for
full walkthroughs.

## Documentation Map
- `docs/quick_start.md` - fastest path to a working benchmark.
- `docs/installation.md` - environment preparation for Windows/macOS/Linux.
- `docs/benchmarking.md` / `docs/methodology.md` - how we execute, collect, and
  interpret results across TR-series runs.
- `docs/multi_agent.md` / `docs/dual_ollama_setup.md` - concurrency, dual Ollama
  orchestration, and troubleshooting for TR110/TR111.
- `docs/python_agents.md` / `docs/rust_agents.md` / `docs/rust_vs_python.md` -
  implementation details and comparison guidance.
- `docs/performance_tuning.md`, `docs/chimera_optimization.md`, and
  `docs/statistical_analysis.md` - how to squeeze more performance out of the
  agents and how to validate that the gains are real.
- Root playbooks (`EXECUTE_TR111_BENCHMARK.md`, `MONITORING_SYSTEM_SUMMARY.md`,
  `SPLIT_PLAN.md`) capture the operational recipes that were lifted verbatim
  from the Banterhearts effort.

## Windows Script Relocation
PowerShell wrappers now live under `scripts/windows/` with a README that
describes each helper. Update any local automation, CI jobs, or personal notes
that referenced the old root-level `.ps1` names to point at the new paths:

```powershell
.\scripts\windows\ollama\setup_dual_ollama.ps1
.\scripts\windows\benchmarks\run_rust_benchmark_minimal.ps1
.\scripts\windows\benchmarks\check_benchmark_status.ps1
```

## Reports and Baselines
The latest ready-to-share reports stay in `outputs/publish_ready/reports/`. Intermediate
artifacts, raw CSV exports, and Nsight captures live in `outputs/reports/`, `outputs/artifacts/`,
`logs/`, and the `benchmarks/` subtree. Canonical sample/baseline artifacts are now
under `data/baselines/`. All data exports are consolidated in `data/csv/` and research
data in `data/research/`.

If you are producing a new TR or integrating fresh data, start with
`docs/technical_reports.md` and `docs/statistical_analysis.md` to stay aligned
with the established methodology.

## Contributing / Notes
- Make changes in this repo; upstream integration back into Banterhearts is a
  separate workflow owned by the production team.
- Keep documentation ASCII-only so it renders cleanly everywhere.
- When adding new helper scripts, prefer `scripts/` for cross-platform Python
  utilities and `scripts/windows/` for Windows-only PowerShell.
