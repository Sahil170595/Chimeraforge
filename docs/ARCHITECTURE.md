# Architecture Documentation

## Overview

Chimeraforge is a benchmarking and research repository focused on LLM performance optimization. The architecture is designed for reproducibility, extensibility, and comprehensive performance analysis.

## Repository Structure

```
Chimeraforge/
├── src/                          # Source code
│   ├── python/                   # Python implementations
│   │   └── banterhearts/         # Main Python package
│   │       ├── demo_agent/       # Single-agent benchmarking
│   │       ├── demo_multiagent/  # Multi-agent benchmarking
│   │       ├── benchmarking/     # Shared benchmarking utilities
│   │       └── monitoring/       # Performance monitoring tools
│   └── rust/                     # Rust implementations
│       ├── demo_agent/           # Single-agent (mirrors Python)
│       └── demo_multiagent/      # Multi-agent (mirrors Python)
│
├── experiments/                  # Research experiments
│   ├── TR111/                    # Technical Report 111
│   ├── TR112/                    # Technical Report 112
│   ├── TR114/                    # Technical Report 114
│   └── TR115_runtime_optimization/  # Runtime optimization study
│
├── data/                         # Data files
│   ├── baselines/                # Baseline measurements
│   ├── csv/                      # CSV exports
│   └── research/                 # Research data
│
├── outputs/                      # Generated outputs
│   ├── artifacts/                # Build artifacts, profiles
│   ├── reports/                  # Intermediate reports
│   ├── runs/                     # Benchmark run outputs
│   └── publish_ready/            # Final publishable reports
│
├── benchmarks/                   # Benchmark results
│   ├── python/                   # Python benchmark outputs
│   └── rust/                     # Rust benchmark outputs
│
├── scripts/                      # Utility scripts
│   ├── compilation/              # Compilation benchmarks
│   ├── ollama/                   # Ollama utilities
│   ├── quantization/             # Quantization tools
│   └── windows/                  # Windows-specific scripts
│
├── docs/                         # Documentation
└── logs/                         # Log files
```

## Core Components

### 1. Agent Implementations

#### Python Agents (`src/python/banterhearts/`)

**Single-Agent** (`demo_agent/`):
- `agents/`: Agent implementations (baseline, chimera)
- `config/`: Configuration management
- `metrics/`: Metrics collection
- `run_demo.py`: Main entry point

**Multi-Agent** (`demo_multiagent/`):
- `agents/`: Multi-agent implementations (collector, insight)
- `coordinator.py`: Agent coordination
- `orchestrator.py`: Execution orchestration
- `run_multiagent_demo.py`: Main entry point

**Shared Utilities**:
- `benchmarking/`: Benchmark management and execution
- `monitoring/`: Performance monitoring and profiling

#### Rust Agents (`src/rust/`)

**Single-Agent** (`demo_agent/`):
- Mirrors Python single-agent functionality
- Async/await with Tokio runtime
- Direct Ollama API integration

**Multi-Agent** (`demo_multiagent/`):
- Mirrors Python multi-agent functionality
- Multiple runtime support (Tokio, async-std, smol)
- Dual Ollama instance support

### 2. Benchmarking Framework

#### Metrics Collection

**Primary Metrics**:
- **Throughput**: Tokens per second
- **TTFT**: Time to first token
- **Latency**: End-to-end response time
- **Resource Usage**: CPU, GPU, memory

**Multi-Agent Metrics**:
- **Speedup**: Concurrent vs sequential time
- **Efficiency**: Speedup / ideal speedup
- **Contention**: Resource contention events

#### Statistical Analysis

- Multiple runs per configuration (3-5 minimum)
- Outlier detection and removal
- Confidence intervals (mean ± stddev)
- Coefficient of variation (CV) for consistency

### 3. Experiment Management

#### Technical Reports (TR Series)

Each experiment follows a structured methodology:

1. **Hypothesis**: Clear research question
2. **Methodology**: Reproducible experimental design
3. **Execution**: Automated benchmark sweeps
4. **Analysis**: Statistical analysis and visualization
5. **Reporting**: Technical report with findings

#### Experiment Structure

```
experiments/TR###/
├── README.md              # Experiment overview
├── scripts/               # Analysis scripts
├── artifacts/             # Generated artifacts
└── results/               # Raw results (if applicable)
```

### 4. Data Management

#### Data Organization

- **Baselines**: Canonical baseline measurements
- **CSV Exports**: Structured data for analysis
- **Research Data**: Experiment-specific data

#### Data Flow

1. **Collection**: Benchmarks generate raw metrics
2. **Storage**: Metrics stored in JSON/CSV format
3. **Analysis**: Scripts process and analyze data
4. **Reporting**: Results compiled into reports

### 5. Output Management

#### Output Categories

- **Artifacts**: Build outputs, profiles, visualizations
- **Reports**: Intermediate analysis reports
- **Runs**: Raw benchmark run outputs
- **Publish Ready**: Final, curated reports

#### Report Generation

- Markdown-based reports
- Jupyter notebooks for analysis
- Automated report generation scripts
- Version-controlled outputs

## Design Principles

### 1. Reproducibility

- **Version Control**: All code and configurations versioned
- **Deterministic**: Seeds and fixed parameters where possible
- **Documentation**: Comprehensive methodology documentation
- **Isolation**: Process isolation to avoid interference

### 2. Extensibility

- **Modular Design**: Clear separation of concerns
- **Plugin Architecture**: Easy to add new agents/metrics
- **Configuration-Driven**: Flexible configuration system
- **Language Agnostic**: Support for multiple languages

### 3. Performance

- **Efficient Execution**: Optimized benchmark execution
- **Resource Management**: Proper resource allocation
- **Parallel Execution**: Multi-agent concurrent execution
- **Profiling**: Built-in performance profiling

### 4. Maintainability

- **Clear Structure**: Logical directory organization
- **Documentation**: Comprehensive inline and external docs
- **Testing**: Automated testing where applicable
- **Code Quality**: Consistent coding standards

## Technology Stack

### Python Stack

- **Core**: Python 3.11+
- **Async**: asyncio, aiohttp
- **Data**: pandas, numpy
- **Monitoring**: Custom monitoring tools
- **Profiling**: torch profiler, nvidia tools

### Rust Stack

- **Core**: Rust 1.70+
- **Async**: Tokio (default), async-std, smol
- **HTTP**: reqwest
- **Serialization**: serde, serde_json
- **Logging**: tracing, tracing-subscriber

### Infrastructure

- **Model Serving**: Ollama
- **GPU**: NVIDIA CUDA
- **Profiling**: Nsight Compute, Nsight Systems
- **Analysis**: Jupyter notebooks, pandas

## Extension Points

### Adding New Agents

1. Implement agent interface (Python or Rust)
2. Add configuration options
3. Integrate with benchmarking framework
4. Add metrics collection
5. Update documentation

### Adding New Metrics

1. Define metric in metrics collector
2. Add collection logic
3. Update report generation
4. Add to analysis scripts
5. Document in methodology

### Adding New Experiments

1. Create experiment directory in `experiments/`
2. Define hypothesis and methodology
3. Create analysis scripts
4. Run benchmarks
5. Generate technical report

## Performance Considerations

### Benchmark Execution

- **Cold Starts**: Force model unloads between runs
- **Process Isolation**: Separate processes per run
- **Resource Cleanup**: Proper cleanup between runs
- **Warm-up**: Optional warm-up runs (excluded from results)

### Multi-Agent Execution

- **Dual Ollama**: Separate instances for true concurrency
- **Synchronization**: Coordinated start times
- **Resource Coordination**: Semaphore-based coordination
- **Contention Detection**: Automatic contention detection

### Data Collection

- **Minimal Overhead**: Efficient metrics collection
- **Streaming**: Stream-based data collection
- **Batching**: Batch processing for analysis
- **Compression**: Compress large datasets

## Security Considerations

- **Local Execution**: Benchmarks run locally
- **No External Dependencies**: Self-contained execution
- **Input Validation**: Validate all inputs
- **Resource Limits**: Prevent resource exhaustion

## Future Enhancements

- **Distributed Execution**: Support for distributed benchmarks
- **Cloud Integration**: Cloud-based benchmark execution
- **Real-time Monitoring**: Real-time performance monitoring
- **Automated Analysis**: Automated statistical analysis
- **Report Automation**: Automated report generation

---

**Last Updated**: January 2025

