# Rust Agent Benchmark Suite

Production-grade Rust implementation of the Chimera agent benchmark, designed for fair comparison against Python agents in Technical Report 111.

## Features

- ✅ **True TTFT Measurement**: Streaming API with precise first-token timing
- ✅ **Statistical Rigor**: Multiple runs with standard deviation tracking
- ✅ **Comprehensive Metrics**: Throughput, TTFT, prompt eval, generation time, load time
- ✅ **Python Parity**: Same prompt complexity and methodology as TR109/TR110
- ✅ **Production Ready**: Proper error handling, logging, and report generation

## Build

```bash
cargo build --release
```

## Quick Start

### Basic Benchmark (3 runs, default config)
```bash
cargo run --release -- \
  --model gemma3:latest \
  --runs 3 \
  --output-dir Demo_rust_agent_out_benchmark
```

### Chimera Optimized Benchmark
```bash
cargo run --release -- \
  --model gemma3:latest \
  --runs 5 \
  --output-dir Demo_rust_agent_out_benchmark \
  --chimera-num-gpu 80 \
  --chimera-num-ctx 2048 \
  --chimera-temperature 0.8
```

### Full Parameter Sweep (TR111 methodology)
```bash
# Test 1: GPU=60, CTX=512
cargo run --release -- --runs 5 --chimera-num-gpu 60 --chimera-num-ctx 512 --chimera-temperature 0.8 --output-dir rust_results/test_60_512_08

# Test 2: GPU=80, CTX=1024
cargo run --release -- --runs 5 --chimera-num-gpu 80 --chimera-num-ctx 1024 --chimera-temperature 0.8 --output-dir rust_results/test_80_1024_08

# Test 3: GPU=80, CTX=2048 (TR110 optimal)
cargo run --release -- --runs 5 --chimera-num-gpu 80 --chimera-num-ctx 2048 --chimera-temperature 1.0 --output-dir rust_results/test_80_2048_10
```

## Command-Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--model` | `gemma3:latest` | Ollama model to benchmark |
| `--base-url` | `http://localhost:11434` | Ollama API endpoint |
| `--runs` | `3` | Number of runs for statistical significance |
| `--output-dir` | `Demo_rust_agent_out_benchmark` | Output directory for reports and metrics |
| `--chimera-num-gpu` | *(default)* | GPU layers to offload (e.g., 80) |
| `--chimera-num-ctx` | *(default)* | Context window size (e.g., 2048) |
| `--chimera-temperature` | *(default)* | Sampling temperature (e.g., 0.8) |
| `--chimera-top-p` | *(default)* | Top-p sampling parameter |
| `--chimera-top-k` | *(default)* | Top-k sampling parameter |
| `--chimera-repeat-penalty` | *(default)* | Repeat penalty parameter |

## Output Structure

```
Demo_rust_agent_out_benchmark/
├── reports/
│   ├── comparison_report.md    # Side-by-side comparison
│   ├── baseline_report.md      # Baseline agent results
│   └── chimera_report.md       # Chimera agent results
└── data/
    └── metrics.json            # Raw metrics for analysis
```

## Metrics Collected

### Per-Run Metrics
- Time to First Token (TTFT)
- Throughput (tokens/second)
- Total generation duration
- Tokens generated
- Prompt evaluation time
- Generation evaluation time
- Model load time

### Aggregate Metrics
- Mean ± Standard Deviation for all metrics
- Coefficient of Variation (CV%)
- Total tokens across all runs
- Performance delta (baseline vs Chimera)

## Comparison to Python Agent

This Rust agent matches the Python agent's benchmark methodology:

1. **Same Prompt**: Identical 800-1000 word technical report generation task
2. **Same Metrics**: TTFT, throughput, eval times, load times
3. **Same Statistical Rigor**: Multiple runs with stddev tracking
4. **Same Configurations**: Supports all Chimera optimization parameters

## Technical Report 111 Integration

Results from this benchmark directly feed into TR111: Rust vs Python Agent Performance Analysis. The JSON output format is compatible with the TR111 visualization notebook.

### Expected Performance Characteristics

Based on TR111_v2/TR112_v2 findings:
- **Baseline**: 114.54 tok/s, TTFT ~603ms (gemma3:latest, Ollama defaults)
- **Chimera Optimized**: 115.94 tok/s peak (GPU=60, CTX=256, TEMP=0.6)
- **Rust Advantage**: 15.2% faster than Python baseline (114.54 vs 99.34 tok/s)

## Prerequisites

- Rust 1.70+ (2021 edition)
- Ollama running locally
- Model pulled: `ollama pull gemma3:latest`
- Sufficient VRAM (12GB recommended for gemma3)

## Troubleshooting

**TTFT timing issues**: Ensure streaming is working. Check Ollama logs if TTFT seems wrong.

**Timeout errors**: Increase timeout with longer prompts: edit `Client::builder().timeout(Duration::from_secs(300))`

**Memory errors**: Reduce `--chimera-num-ctx` or `--chimera-num-gpu`

**Inconsistent results**: Ensure no background GPU processes, run more iterations (`--runs 5` or higher)

## Contributing to TR111

To add Rust benchmark data to Technical Report 111:

1. Run comprehensive benchmarks with various configurations
2. Copy `metrics.json` to `PublishReady/notebooks/data/rust_metrics/`
3. Update TR111 analysis notebook to include Rust data
4. Compare against Python agent results from TR109

## License

MIT - Part of the Banterhearts Chimera optimization suite

