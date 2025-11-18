# Chimera Multi-Agent Demo

This demo highlights a **concurrent two-agent workflow** that cooperatively analyzes benchmark artifacts in the repository using true parallel execution with resource coordination.

## Concurrent Execution Architecture

The framework supports **three execution scenarios**:

1. **Data Collector (Baseline) vs Insight Agent (Chimera)** - compares Ollama default configuration against Chimera-optimized settings
2. **Chimera Heterogeneous** - runs two different Chimera configurations simultaneously  
3. **Chimera Homogeneous** - runs identical Chimera configurations for maximum resource sharing efficiency

## Key Features

- **True Concurrent Execution:** Agents run simultaneously using `asyncio.gather()`
- **Resource Coordination:** Semaphore-based GPU/memory management prevents contention
- **Performance Analysis:** Tracks concurrency speedup, efficiency, and resource utilization
- **Multiple Scenarios:** Supports baseline vs chimera, heterogeneous, and homogeneous configurations
- **Dedicated Ollama Endpoints:** Optional per-agent base URLs prevent warm/cold state overlap
- **Statistical Validation:** Comprehensive metrics across multiple runs

## Usage

### Basic Concurrent Execution
```bash
python -m banterhearts.demo_multiagent.run_multiagent_demo \
  --model gemma3:latest \
  --runs 3 \
  --scenario baseline_vs_chimera \
  --chimera-num-gpu 60 \
  --chimera-num-ctx 512 \
  --chimera-temperature 0.8
```

### Heterogeneous Chimera Configuration
```bash
python -m banterhearts.demo_multiagent.run_multiagent_demo \
  --scenario chimera_hetero \
  --runs 3 \
  --chimera-num-gpu 60 \
  --chimera-num-ctx 512 \
  --chimera-temperature 0.8 \
  --chimera2-num-gpu 80 \
  --chimera2-num-ctx 1024 \
  --chimera2-temperature 0.6
```

### Homogeneous Chimera Configuration
```bash
python -m banterhearts.demo_multiagent.run_multiagent_demo \
  --scenario chimera_homo \
  --runs 3 \
  --chimera-num-gpu 60 \
  --chimera-num-ctx 512 \
  --chimera-temperature 0.8
```

### Isolated Ollama Instances

For **true concurrent benchmarking without shared model state**, run each agent against its own Ollama service and provide explicit base URLs:

```bash
# Terminal 1
OLLAMA_HOST=127.0.0.1 OLLAMA_PORT=11434 ollama serve

# Terminal 2
OLLAMA_HOST=127.0.0.1 OLLAMA_PORT=11435 ollama serve

# Benchmark (powershell/bash)
python -m banterhearts.demo_multiagent.run_multiagent_demo \
  --scenario baseline_vs_chimera \
  --runs 3 \
  --collector-ollama-url http://localhost:11434 \
  --insight-ollama-url http://localhost:11435 \
  --chimera-num-gpu 60 \
  --chimera-num-ctx 512 \
  --chimera-temperature 0.8
```

## Arguments

| Flag | Description |
| ---- | ----------- |
| `--model` | Ollama model to use (default `gemma3:latest`) |
| `--runs` | Number of repetitions for statistical averaging |
| `--scenario` | Execution scenario: `baseline_vs_chimera`, `chimera_hetero`, `chimera_homo` |
| `--output-dir` | Root directory for results (defaults to `banterhearts/demo_multiagent/results`) |
| `--chimera-*` | Configuration overrides for first Chimera agent |
| `--chimera2-*` | Configuration overrides for second Chimera agent (heterogeneous scenario) |
| `--collector-ollama-url` | Base URL for agent 1 (baseline or Chimera config 1) |
| `--insight-ollama-url` | Base URL for agent 2 (Chimera or config 2) |

## Concurrent Execution Analysis

Each run creates a subdirectory containing:

- `collector_report.md` - First agent report
- `insight_report.md` - Second agent report  
- `combined_report.md` - Consolidated summary with concurrency analysis
- `metrics.json` - Raw metrics for both agents including concurrent execution data

The root directory receives `summary.json` and `summary.md` with aggregate statistics including:

- **Concurrency Speedup:** Sequential time / Concurrent time
- **Efficiency:** Speedup / ideal 2x speedup × 100%
- **Resource Contention:** Detection based on speedup thresholds
- **Wall Time:** Total concurrent execution duration

## Performance Characteristics

**Expected Results:**
- **Concurrency Speedup:** 1.8-2.0x (vs sequential execution)
- **Efficiency:** 90-98% (depending on configuration similarity)
- **Resource Utilization:** 65-70% VRAM usage
- **Contention:** Minimal with proper resource coordination

**Configuration Impact:**
- **Homogeneous configs:** Highest efficiency (98.5%)
- **Heterogeneous configs:** Moderate efficiency (95.5%)  
- **Baseline vs Chimera:** Lower efficiency (90.5%)

## Resource Coordination

The framework includes a `ResourceCoordinator` class that:

- Manages concurrent access to GPU/memory resources
- Prevents resource contention through semaphore control
- Tracks active agents and resource utilization
- Detects contention based on performance thresholds
- Provides comprehensive logging and monitoring

## Concurrent vs Sequential Execution

**Use Concurrent When:**
- Tasks are independent and identical
- Resource utilization is <80%
- Throughput is prioritized over individual agent performance
- Latency requirements allow for slight contention

**Use Sequential When:**
- Tasks have dependencies
- Resource utilization is >90%
- Individual agent performance is critical
- Memory constraints are tight

## Tests

The orchestrator is covered by `banterhearts/tests/test_demo_multiagent.py`, which patches the agents to avoid external Ollama calls. Run `python -m unittest` to verify that the pipeline generates reports and metrics correctly.

## Technical Reports

See `reports/Technical_Report_110.md` for comprehensive analysis of concurrent multi-agent performance characteristics, resource contention patterns, and optimization strategies.
