# Quick Start Guide

Get up and running with Chimeraforge (the Banterhearts benchmarking breakout)
in minutes. Commands assume you are in the repository root.

## 5-Minute Setup

### 1. Install Prerequisites

```bash
# Python 3.11+
python --version

# Rust 1.70+ (optional, for Rust agents)
rustc --version

# Ollama
ollama --version
```

### 2. Clone and Install

```bash
git clone https://github.com/your-org/Chimeraforge.git
cd Chimeraforge

# Python dependencies
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Rust agents (optional)
cd src/rust/demo_agent && cargo build --release
cd ../demo_multiagent && cargo build --release
cd ../../..
```

### 3. Pull Model

```bash
ollama pull gemma3:latest
```

### 4. Run Your First Benchmark

**Python Single-Agent**:
```bash
python src/python/banterhearts/demo_agent/run_demo.py \
  --model gemma3:latest \
  --runs 3
```

**Rust Single-Agent**:
```bash
cd src/rust/demo_agent
cargo run --release -- --model gemma3:latest --runs 3
cd ../../..
```

## Common Use Cases

### Compare Baseline vs Optimized

**Python**:
```bash
python src/python/banterhearts/demo_agent/run_demo.py \
  --runs 5 \
  --chimera-num-gpu 80 \
  --chimera-num-ctx 512 \
  --chimera-temperature 0.8
```

**Rust**:
```bash
cd src/rust/demo_agent
cargo run --release -- \
  --runs 5 \
  --chimera-num-gpu 80 \
  --chimera-num-ctx 512 \
  --chimera-temperature 0.8
cd ../../..
```

### Run Multi-Agent Benchmark

**Setup Dual Ollama** (required):
```bash
.\scripts\windows\ollama\setup_dual_ollama.ps1  # Windows
```

**Python**:
```bash
python -m banterhearts.demo_multiagent.run_multiagent_demo \
  --scenario chimera_homo \
  --runs 3 \
  --chimera-num-gpu 80 \
  --chimera-num-ctx 2048 \
  --chimera-temperature 1.0
```

**Rust**:
```bash
cd src/rust/demo_multiagent
cargo run --release -- \
  --scenario chimera_homo \
  --runs 3 \
  --chimera-num-gpu 80 \
  --chimera-num-ctx 2048 \
  --chimera-temperature 1.0 \
  --collector-ollama-url http://localhost:11434 \
  --insight-ollama-url http://localhost:11435
cd ../../..
```

## Understanding Results

### Single-Agent Output

**Location**: `src/python/banterhearts/demo_agent/demo_agent_*/` or `src/rust/demo_agent/rust_results/`

**Key Files**:
- `comparison_report.md`: Human-readable comparison
- `metrics.json`: Raw data for analysis

**Key Metrics**:
- **Throughput**: Tokens per second (higher is better)
- **TTFT**: Time to first token in ms (lower is better)
- **CV**: Coefficient of variation (lower = more consistent)

### Multi-Agent Output

**Location**: `src/python/banterhearts/demo_multiagent/comprehensive_test_results/` or `src/rust/demo_multiagent/Demo_rust_multiagent_results_tr110_dual/`

**Key Metrics**:
- **Speedup**: Concurrent vs sequential time (higher is better, ideal = 2.0x)
- **Efficiency**: Speedup / ideal speedup (higher is better, ideal = 100%)
- **Contention**: Resource contention events (lower is better, ideal = 0%)

## Next Steps

1. **Read Technical Reports**: [outputs/publish_ready/reports/](../outputs/publish_ready/reports/)
2. **Explore Configuration Options**: [Chimera Optimization Guide](chimera_optimization.md)
3. **Run Comprehensive Benchmarks**: [Benchmarking Guide](benchmarking.md)
4. **Compare Languages**: [Rust vs Python](rust_vs_python.md)

## Need Help?

- **FAQ**: [Frequently Asked Questions](faq.md)
- **Benchmarking Guide**: [Deep Dive](benchmarking.md)
- **Issues**: [GitHub Issues](https://github.com/your-org/Chimeraforge/issues)

---

**Ready to benchmark?** Start with [Benchmarking Guide](benchmarking.md) for detailed instructions.

