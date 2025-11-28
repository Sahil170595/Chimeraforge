# Documentation Index

Comprehensive documentation for Chimeraforge, a benchmarking and research repository for LLM performance optimization.

## Quick Start

- **[Quick Start Guide](quick_start.md)** - Get up and running in minutes with your first benchmark
- **[Installation Guide](installation.md)** - OS-specific setup instructions and prerequisites

## Core Documentation

### Setup & Configuration
- **[Installation](installation.md)** - Complete installation guide for all platforms
- **[Dual Ollama Setup](dual_ollama_setup.md)** - Setting up dual Ollama instances for true concurrency
- **[Architecture](ARCHITECTURE.md)** - System architecture and design principles

### Running Benchmarks
- **[Benchmarking Guide](benchmarking.md)** - Comprehensive guide to running all benchmark types
- **[Multi-Agent Guide](multi_agent.md)** - Multi-agent concurrent execution scenarios
- **[Python Agents](python_agents.md)** - Python agent implementation details
- **[Rust Agents](rust_agents.md)** - Rust agent implementation details

### Optimization & Tuning
- **[Chimera Optimization](chimera_optimization.md)** - Configuration optimization strategies
- **[Performance Tuning](performance_tuning.md)** - Performance tuning techniques and best practices

### Analysis & Reporting
- **[Statistical Analysis](statistical_analysis.md)** - Statistical rigor, sample sizes, and analysis methods
- **[Rust vs Python](rust_vs_python.md)** - Cross-language performance comparison
- **[Technical Reports](technical_reports.md)** - Complete index of all technical reports (TR108-TR115)
- **[Methodology](methodology.md)** - Research methodology and experimental design

### Reference
- **[FAQ](faq.md)** - Frequently asked questions and troubleshooting
- **[Benchmarks README](../benchmarks/README.md)** - Directory map for stored benchmark artifacts

## Project Documentation

### Contributing
- **[Contributing Guide](../CONTRIBUTING.md)** - How to contribute to the project
- **[Code of Conduct](../CODE_OF_CONDUCT.md)** - Community standards and expectations

### Project Information
- **[Changelog](../CHANGELOG.md)** - Version history and changes
- **[Security Policy](../SECURITY.md)** - Security reporting and best practices
- **[Architecture](ARCHITECTURE.md)** - System architecture documentation

## Documentation Structure

### By User Type

**New Users**:
1. Start with [Quick Start](quick_start.md)
2. Follow [Installation](installation.md)
3. Run your first benchmark
4. Read [Benchmarking Guide](benchmarking.md) for details

**Researchers**:
1. Review [Methodology](methodology.md)
2. Study [Technical Reports](technical_reports.md)
3. Understand [Statistical Analysis](statistical_analysis.md)
4. Review [Architecture](ARCHITECTURE.md)

**Developers**:
1. Read [Architecture](ARCHITECTURE.md)
2. Review [Contributing Guide](../CONTRIBUTING.md)
3. Study agent implementations ([Python](python_agents.md) / [Rust](rust_agents.md))
4. Understand benchmarking framework

**Operators**:
1. Follow [Installation](installation.md)
2. Set up [Dual Ollama](dual_ollama_setup.md)
3. Run benchmarks using [Benchmarking Guide](benchmarking.md)
4. Troubleshoot using [FAQ](faq.md)

### By Topic

**Performance Optimization**:
- [Chimera Optimization](chimera_optimization.md)
- [Performance Tuning](performance_tuning.md)
- [Rust vs Python](rust_vs_python.md)

**Multi-Agent Systems**:
- [Multi-Agent Guide](multi_agent.md)
- [Dual Ollama Setup](dual_ollama_setup.md)
- Technical Reports: TR110, TR113, TR114

**Language-Specific**:
- [Python Agents](python_agents.md)
- [Rust Agents](rust_agents.md)
- [Rust vs Python](rust_vs_python.md)

**Research & Analysis**:
- [Methodology](methodology.md)
- [Statistical Analysis](statistical_analysis.md)
- [Technical Reports](technical_reports.md)

## Technical Reports

All technical reports are available in `outputs/publish_ready/reports/`:

- **TR108**: Single-Inference Optimization
- **TR109**: Python Agent Workflows
- **TR110**: Python Multi-Agent Concurrent
- **TR111**: Rust Single-Agent
- **TR112**: Rust vs Python Single-Agent
- **TR113**: Rust Multi-Agent (Single Ollama)
- **TR114**: Rust Multi-Agent (Dual Ollama)
- **TR115**: Rust Runtime Optimization
- **TR116**: Cross-Model Benchmarks (Qwen 2.5 vs Gemma 3) ✅ Complete
- **TR117**: Root Cause Analysis of Efficiency Anomalies ✅ Complete

See [Technical Reports](technical_reports.md) for detailed summaries.

## Repository Structure

```
Chimeraforge/
├── src/              # Source code (Python & Rust)
├── experiments/      # Research experiments (TR series)
├── data/             # Data files (baselines, CSV, research)
├── outputs/          # Generated outputs (artifacts, reports, runs)
├── benchmarks/       # Benchmark results
├── scripts/          # Utility scripts
├── docs/             # Documentation (this directory)
└── logs/             # Log files
```

See [Architecture](ARCHITECTURE.md) for detailed structure documentation.

## Getting Help

- **FAQ**: Check [FAQ](faq.md) for common questions
- **Issues**: Open an issue on GitHub
- **Discussions**: Use GitHub Discussions
- **Contributing**: See [Contributing Guide](../CONTRIBUTING.md)

## Documentation Standards

- All documentation is ASCII-only for universal compatibility
- Commands assume execution from repository root unless noted
- Code examples are tested and verified
- Links are relative to documentation structure
- Last updated dates are maintained

---

**Last Updated**: January 2025
