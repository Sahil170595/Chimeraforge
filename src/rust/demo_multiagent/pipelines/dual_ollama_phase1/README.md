# Dual Ollama Phase 1 Pipeline

This pipeline isolates the Phase 1 (core sweep) portion of the TR114 dual-Ollama benchmark so we can rerun the same 18 configurations on demand, capture results in a single location, and feed clean artifacts into TR115.

## Folder Contents

- `config_phase1.json`  Declarative matrix describing the 18 Phase 1 scenarios.
- `manage_dual_ollama.py`  Helper to start/stop/status two dedicated Ollama instances (ports 11434/11435) with isolated model stores.
- `run_phase1_pipeline.py`  Orchestrates the benchmark runs using the config file and writes a structured summary for analysis.
- `dual_ollama_state.json`  Generated when the helper script starts Ollama processes (stores PIDs so we can stop them cleanly).

## Usage

1. **Start dual Ollama** (only once per session):
   ```powershell
   python Demo_rust_multiagent\pipelines\dual_ollama_phase1\manage_dual_ollama.py start
   ```
   - Verifies `ollama` is on PATH.
   - Launches two instances with separate model caches under `%USERPROFILE%\.banter_dual_ollama` (or `$HOME/.banter_dual_ollama` on POSIX).
   - Persists `dual_ollama_state.json` so `stop`/`status` know which processes to manage.

2. **Run the benchmark sweep** (re-run anytime):
   ```powershell
   python Demo_rust_multiagent\pipelines\dual_ollama_phase1\run_phase1_pipeline.py \
     --config Demo_rust_multiagent/pipelines/dual_ollama_phase1/config_phase1.json
   ```
   - Builds `Demo_rust_multiagent` in release mode if needed.
   - Executes each configuration sequentially with `--runs 5` using the dual instances.
   - Stores outputs under `Demo_rust_multiagent_phase1_dual_results/<scenario>_<name>`.
   - Writes `phase1_summary.json` beside the config to capture timestamps, commands, and status per config for TR115 comparisons.

3. **Stop dual Ollama** when finished:
   ```powershell
   python Demo_rust_multiagent\pipelines\dual_ollama_phase1\manage_dual_ollama.py stop
   ```

## Notes

- The pipeline uses the existing `setup_dual_ollama.ps1` instructions but packages them into a reusable Python helper so it works the same on Windows/macOS/Linux.
- `run_phase1_pipeline.py` only covers "Point 1" (Phase 1 core sweep) so we can re-benchmark the most critical comparisons quickly. Additional phases can be added by creating new config files in the same folder.
- If you already have dual Ollama instances running elsewhere, run `manage_dual_ollama.py status` to confirm before launching the sweep.
