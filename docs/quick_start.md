# Quick Start Guide

**Kubernetes declarations (since 0.81.0):** `deploy --format kubernetes` exports
every supported original member as bounded JSON, and `deploy-verify --format
kubernetes` checks independently supplied intent. See [CLI/API examples and
fidelity limits](kubernetes-deployment.md). Hosted server dry-run qualifies API
admission, without scheduling, inference-image execution or GPU/fit claims.

**Original-fleet regression decisions (since 0.80.0):** `gate --kind fleet-trace`
and `api.gate_fleet_traces` compare one complete fleet per arm under a closed
policy, preserving member evidence and native global metrics. Inconclusive
evidence takes precedence over known regression; see [CLI/API and protected
JSON/JUnit outputs](fleet-trace-gate.md). This is not physical independence
or GPU/scientific qualification.

**Original-fleet scheduled trace (since 0.79.0):** `trace-fleet` and async
`api.replay_fleet_trace` retain the original saved fleet and all routed rows
under one native schedule, concurrency limit and deadline. Execution, SLOs,
configuration and cooperative cleanup remain separate; see [complete CLI/API
examples and receiving limits](fleet-trace.md). Protocol and native CPU
acceptance do not qualify GPU execution or physical capacity.

**Runtime secure monitoring (since 0.78.0):** standalone, saved-plan and declared-
fleet monitoring support verified HTTPS, named-environment bearer and optional
client certificates for metrics and all metadata. Settings stay runtime-only
and per endpoint. See [complete CLI/API and trust limits](secure-monitoring.md);
CPU TLS protocol fixtures do not qualify a running inference deployment.

**Queried inventory and saved arithmetic (since 0.77.0):** `inventory-check` and
async `api.check_inventory` retain every original ordered GPU selector and compare
reported free memory with the saved per-GPU batch-one baseline. Every result keeps
`deployment_ready: null`; UUID/MIG observations do not establish physical
independence, allocation or runtime fit. See [complete CLI/API examples and
exit statuses](inventory-check.md).

**Passive declared-fleet monitoring (since 0.76.0):** [passive declared-fleet monitoring](fleet-monitoring.md)
adds `monitor-fleet` and typed async `api.monitor_fleet`. Repeat explicit ID=URL
declarations for the original saved replica count. Shared budgets, retained
partial windows/metadata, required identity and cleanup qualify declared coverage
without GPU or physical-independence claims. Existing endpoint-only `monitor`
retains its behavior.

Get up and running with Chimeraforge (the Banterhearts benchmarking breakout)
in minutes. Commands assume you are in the repository root.

Chimeraforge 0.81.0 includes native streaming trace observations and
[queue-inclusive trace gates](trace-regression-gate.md),
[serial trace campaigns](trace-campaign.md),
[signed contributions and private replay](signed-contribution-v2.md) with the optional `sign` extra,
[frozen prediction scorecards](prediction-scorecards.md),
[whole-campaign regression gates](trace-campaign-gates.md),
[plan-bound request traces](plan-bound-trace.md),
[observed finite load points](trace-envelope.md),
[private prediction evidence bundles](prediction-bundles.md), and
[signed native regression gates](signed-native-gates.md).
Benchmark gating remains the default.

Since 0.72.0, `study` supports offline hardware alternatives: see
[the complete case and Python examples](planning-api.md#frozen-context-sensitivity).
Ordinary cases retain saved hardware; no host probe or measured GPU qualification occurs.

Since 0.73.0, `deploy` supports repeatable `--gpu-device` and
Compose-only `--host-port`, plus direct `export_deployment` keywords. See
[complete examples and limits](deployment.md#explicit-device-selection-and-host-ports).
Default exports retain their GPU count and ports; no GPU placement is verified.

Since 0.74.0, `deploy` supports `--replica-devices GROUP
--replica-port PORT` for every original online vLLM/SGLang Compose replica. See
[complete CLI/API examples](deployment.md#homogeneous-compose-replicas); these
are manually targeted offline declarations, not measured fleet capacity.

Since 0.75.0, `deploy-verify --plan --config --image --json` verifies declarations
against independently retained saved-plan and full render intent. See
[complete CLI/API examples and exit statuses](deployment-verification.md). A match
means current-renderer consistency, not source authenticity or running GPU proof.

## 5-Minute Setup

### 1. Install Prerequisites

```bash
# Python 3.10+
python --version

# Rust 1.70+ (optional, for Rust agents)
rustc --version

# Ollama
ollama --version
```

### 2. Clone and Install

```bash
git clone https://github.com/Sahil170595/Chimeraforge.git
cd Chimeraforge

# Python dependencies (httpx is core; bench adds benchmark environment metadata).
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e ".[bench]"

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

**Location**: the directory passed via `--output-dir` (Python defaults to `demo_agent/` in the working directory) or `src/rust/demo_agent/rust_results/`

**Key Files**:
- `comparison_report.md`: Human-readable comparison
- `metrics.json`: Raw data for analysis

**Key Metrics**:
- **Throughput**: Tokens per second (higher is better)
- **TTFT**: Time to first token in ms (lower is better)
- **CV**: Coefficient of variation (lower = more consistent)

### Multi-Agent Output

**Location**: the directory passed via `--output-dir` (Python defaults to `experiments/TR116/results/multi/python/`) or `src/rust/demo_multiagent/Demo_rust_multiagent_results_tr110_dual/`

**Key Metrics**:
- **Speedup**: Concurrent vs sequential time (higher is better, ideal = 2.0x)
- **Efficiency**: Speedup / ideal speedup (higher is better, ideal = 100%)
- **Contention**: Resource contention events (lower is better, ideal = 0%)

## Next Steps

1. **Read Technical Reports**: [outputs/publish_ready/reports/](../outputs/publish_ready/reports/)
2. **Explore Configuration Options**: [Chimera Optimization Guide](archive/chimera_optimization.md)
3. **Run Comprehensive Benchmarks**: [Benchmarking Guide](archive/benchmarking.md)
4. **Compare Languages**: [Rust vs Python](archive/rust_vs_python.md)

## Need Help?

- **FAQ**: [Frequently Asked Questions](archive/faq.md)
- **Benchmarking Guide**: [Deep Dive](archive/benchmarking.md)
- **Issues**: [GitHub Issues](https://github.com/your-org/Chimeraforge/issues)

---

**Ready to benchmark?** Start with [Benchmarking Guide](archive/benchmarking.md) for detailed instructions.

