# Demo_rust_multiagent

Rust rewrite of the Chimera multi-agent benchmark (see `banterhearts/demo_multiagent`). It launches two asynchronous agents in parallel, captures throughput/TTFT deltas, and reports concurrency speedup/efficiency for three scenarios:

1. `baseline_vs_chimera` - Ollama defaults vs Chimera overrides
2. `chimera_hetero` - Two Chimera agents with distinct overrides
3. `chimera_homo` - Two Chimera agents sharing the same overrides

## Build

```bash
cargo build --release
```

## Run

```bash
./target/release/Demo_rust_multiagent \
  --model gemma3:latest \
  --runs 3 \
  --scenario baseline_vs_chimera \
  --output-dir Demo_rust_multiagent_results/baseline_vs_chimera_gpu80_ctx512_temp0p8 \
  --collector-ollama-url http://localhost:11434 \
  --insight-ollama-url http://localhost:11435 \
  --chimera-num-gpu 80 \
  --chimera-num-ctx 512 \
  --chimera-temperature 0.8 \
  --chimera-top-p 0.9 \
  --chimera-top-k 40 \
  --chimera-repeat-penalty 1.1
```

Each run creates `run_<n>` folders with agent-specific reports (`collector_report.md`, `insight_report.md`), a combined concurrency summary, and raw `metrics.json`. The root output directory contains `summary.json` + `summary.md` with aggregated statistics.

## Runtime Variants (TR115)

The codebase supports multiple async runtime backends via Cargo features:

```bash
# Default Tokio runtime
cargo build --release --features runtime-tokio-default

# Tokio LocalSet (single-threaded)
cargo build --release --features runtime-tokio-localset

# Async-std runtime (⚠️ 50% efficiency - not recommended)
cargo build --release --features runtime-async-std

# Smol runtime
cargo build --release --features runtime-smol

# Smol with custom 1KB HTTP buffering
cargo build --release --features runtime-smol-1kb
```

**Performance**: All successful runtimes (tokio/smol) achieve 98-99% peak efficiency. Tokio-default recommended (98.72% mean, 1.21pp σ). See [TR115_v2](../PublishReady/reports/Technical_Report_115_v2.md) for detailed analysis.

## Notes

- Use two separate Ollama instances (ports 11434 / 11435) for contention-free comparisons, mirroring TR110's methodology.
- The agent prompts are tuned for quick synthetic workloads so we can run large sweep matrices (GPU layers × context windows × temperature) without hand-editing inputs.
- **Dual Ollama mandatory** for production - single Ollama reduces efficiency to 82% (see TR113).
