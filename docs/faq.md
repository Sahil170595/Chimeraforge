# Frequently Asked Questions

Common questions about Chimeraforge, the benchmark-only slice of Banterhearts.

## General Questions

### What is Chimeraforge?

Chimeraforge is a research-grade platform for LLM performance optimization and
benchmarking. It is the benchmarking-only breakout from Banterhearts and
provides comprehensive tools for evaluating single-agent and multi-agent LLM
performance across Python and Rust implementations.

### What models are supported?

Currently tested with `gemma3:latest` (4.3B parameters). The framework should work with any Ollama-compatible model, but performance characteristics will vary.

### Do I need a GPU?

Yes, a NVIDIA GPU with 12GB+ VRAM is recommended for optimal performance. CPU-only execution is possible but significantly slower.

## Benchmarking Questions

### How long do benchmarks take?

- **Single-agent**: ~2-3 minutes per configuration (5 runs)
- **Multi-agent**: ~2-5 minutes per configuration (5 runs)
- **Full parameter sweep**: 1-6 hours depending on scope

### How many runs should I do?

- **Minimum**: 3 runs for basic testing
- **Recommended**: 5 runs for statistical significance
- **Research**: 10+ runs for publication-quality data

### What's the difference between baseline and Chimera?

- **Baseline**: Ollama default configuration (no optimization)
- **Chimera**: Optimized configuration (GPU layers, context, temperature tuned)

## Multi-Agent Questions

### Why do I need dual Ollama instances?

Dual Ollama instances enable true concurrent execution by eliminating server-level resource contention. Single-instance deployments show 15-20pp efficiency loss in multi-agent scenarios.

### Can I use a single Ollama instance?

Yes, but performance will be degraded:
- **Python**: ~85-90% efficiency (vs 99% with dual)
- **Rust**: ~72% efficiency (vs 95% with dual)

Single-instance is acceptable for testing but not recommended for production.

### How do I set up dual Ollama?

**Windows**:
```powershell
.\scripts\windows\ollama\setup_dual_ollama.ps1
```

**Manual**:
```bash
# Terminal 1
OLLAMA_HOST=127.0.0.1:11434 ollama serve

# Terminal 2
OLLAMA_HOST=127.0.0.1:11435 ollama serve
```

## Rust vs Python Questions

### Which language should I use?

**Choose Python if**:
- Peak throughput is priority (99.25% vs 95.7% efficiency)
- Existing Python infrastructure
- Rapid prototyping needed

**Choose Rust if**:
- Consistency is priority (5.5pp vs 7.4pp StdDev)
- Memory safety required (regulated industries)
- Operational simplicity preferred

### Why is Rust slower in multi-agent?

Rust's tokio work-stealing scheduler and reqwest buffering add ~3-4pp overhead compared to Python's asyncio. This is a runtime overhead, not an architectural limitation.

### Can Rust match Python's performance?

With optimizations (LocalSet, smaller buffers, pinned workers), Rust could potentially reach 98-99% efficiency, closing the gap to Python.

## Configuration Questions

### What's the optimal configuration?

**Single-Agent**:
- GPU=60-80, CTX=512-1024, TEMP=0.6-0.8

**Multi-Agent (Python)**:
- GPU=80, CTX=2048, TEMP=1.0

**Multi-Agent (Rust)**:
- GPU=80, CTX=512, TEMP=1.0 (or GPU=80/100 hetero)

### Why does Rust prefer CTX=512 while Python prefers CTX=2048?

Rust's tokio work-stealing scheduler causes cache thrashing at large KV cache sizes. Python's single-threaded asyncio maintains better cache locality.

### How sensitive are results to configuration?

**Python**: Highly sensitive (3-15pp variance across configs)
**Rust**: Low sensitivity (0.5-1.3pp variance across configs)

Rust's flat performance curve enables "deploy-and-forget" configurations.

## Performance Questions

### What's a good throughput?

- **Baseline**: 95-100 tok/s (gemma3:latest)
- **Optimized**: 100-105 tok/s
- **Excellent**: >105 tok/s

### What's a good TTFT?

- **Baseline**: ~1400ms
- **Optimized**: <500ms
- **Excellent**: <450ms

### What's a good efficiency for multi-agent?

- **Acceptable**: >85%
- **Good**: >90%
- **Excellent**: >95%
- **Ideal**: >99%

## Troubleshooting Questions

### Benchmarks are inconsistent

- Increase number of runs (`--runs 5` or higher)
- Ensure no background GPU processes
- Check for thermal throttling
- Verify stable power supply

### Getting low throughput

- Check GPU utilization: `nvidia-smi`
- Verify model is loaded: `ollama list`
- Reduce `num_gpu` or `num_ctx` if VRAM limited
- Ensure no background processes

### High TTFT

- First run is slower (cold start)
- Verify streaming is working
- Check Ollama logs for errors
- Ensure sufficient VRAM

### Multi-agent contention

- Ensure dual Ollama instances are running
- Check ports 11434 and 11435 are both active
- Reduce context size or GPU layers
- Verify sufficient VRAM (12GB+ recommended)

## Technical Questions

### What's the difference between scenarios?

- **baseline_vs_chimera**: One agent baseline, one optimized (mixed deployment)
- **chimera_hetero**: Both optimized, different configurations (asymmetric)
- **chimera_homo**: Both optimized, identical configuration (symmetric)

### What metrics are collected?

**Single-Agent**:
- Throughput (tok/s)
- TTFT (ms)
- Prompt eval duration
- Generation eval duration
- Load duration
- Memory/CPU usage

**Multi-Agent**:
- Concurrency speedup
- Parallel efficiency
- TTFT delta
- Throughput delta
- Resource contention events

### How is efficiency calculated?

Efficiency = (Speedup / Ideal Speedup)  100%

Where:
- Speedup = Sequential Time / Concurrent Time
- Ideal Speedup = Number of Agents (2.0x for 2 agents)

## Research Questions

### Where can I find the research?

All technical reports are in [outputs/publish_ready/reports/](../outputs/publish_ready/reports/):
- TR108: Single-inference optimization
- TR109: Python agent workflows
- TR110: Python multi-agent concurrent
- TR111: Rust single-agent
- TR112: Rust vs Python single-agent
- TR113: Rust multi-agent (single Ollama)
- TR114: Rust multi-agent (dual Ollama)

### How do I cite this research?

See individual technical reports for citation information.

### Can I contribute benchmarks?

Yes! See [Contributing Guide](contributing.md) for details.

## Still Have Questions?

- **Documentation**: [Full Documentation Index](README.md)
- **Issues**: [GitHub Issues](https://github.com/your-org/Chimeraforge/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/Chimeraforge/discussions)

---

**Last Updated**: November 2025

