# Windows automation helpers

This folder groups the PowerShell wrappers that used to live in the repository
root. Moving them here keeps the workspace tidy and makes it obvious what is
safe to run on Windows hosts.

## Layout
- `benchmarks/` - wrappers around the Rust benchmarking workflows. Use these to
  kick off sweeps, run quick sanity checks, or inspect progress without digging
  through Python entrypoints.
- `monitoring/` - utilities that tail long-running jobs (for example the TR110
  comprehensive sweep).
- `ollama/` - host setup helpers, including the dual-instance launcher required
  for real multi-agent concurrency measurements.

All scripts are self-contained PowerShell files. Run them from the repository
root so relative paths resolve correctly:

```powershell
cd Chimeraforge            # repository root
.\scripts\windows\benchmarks\run_quick_rust_test.ps1
```

Whenever a Python entrypoint is easier to use cross-platform, prefer the Python
script in `scripts/` (or inside `banterhearts/`) and keep these wrappers for
Windows-first operators.
