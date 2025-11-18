# Chimera Agent Performance Demo

A research-grade demonstration comparing baseline vs Chimera-optimized LLM agent performance for benchmark analysis and technical report generation.

## Overview

This demo showcases Chimera's performance optimization capabilities by comparing two agents performing identical tasks:

1. **Baseline Agent**: Uses standard Ollama configuration (default settings)
2. **Chimera-Optimized Agent**: Uses top-performing configurations from Technical Report 108

Both agents ingest all benchmark data from `reports/` and `csv_data/` directories, analyze it, and generate Technical Report 108-style markdown reports. Full metrics tracking ensures rigorous performance comparison.

## System Requirements

- **Python**: 3.11+
- **Ollama**: Latest version with models installed
- **GPU**: NVIDIA GPU with CUDA support (recommended)
- **Memory**: 8GB+ RAM, 6GB+ VRAM
- **Models**: `gemma3:latest` or `llama3.1:8b-instruct-q4_0`

## Installation

1. **Ensure Ollama is running:**
   ```bash
   ollama serve
   ```

2. **Install required models:**
   ```bash
   ollama pull gemma3:latest
   # or
   ollama pull llama3.1:8b-instruct-q4_0
   ```

3. **Install Python dependencies:**
   ```bash
   pip install httpx pandas
   ```

## Usage

### Basic Demo
```bash
cd Banterhearts/demo_agent
python run_demo.py
```

### Advanced Options
```bash
# Use specific model
python run_demo.py --model llama3.1:8b-instruct-q4_0

# Run multiple times for statistical significance
python run_demo.py --runs 3

# Specify output directory
python run_demo.py --output-dir my_demo_results
```

### Command Line Arguments

- `--model`: Model to use (default: `gemma3:latest`)
- `--runs`: Number of runs for statistical significance (default: 1)
- `--output-dir`: Output directory for results (default: `demo_agent`)

## Expected Outputs

### Performance Metrics
- **Throughput**: Tokens per second during report generation
- **TTFT**: Time to first token (latency)
- **GPU Utilization**: Real-time GPU usage (if available)
- **Memory Usage**: VRAM consumption
- **Total Duration**: End-to-end execution time

### Generated Reports
- `baseline_report_run_X.md`: Baseline agent analysis report
- `chimera_report_run_X.md`: Chimera-optimized agent analysis report
- `comparison_report.md`: Side-by-side performance comparison
- `metrics.json`: Raw performance data for analysis

## Configuration Details

### Baseline Configuration
- **Model**: `gemma3:latest` (or specified model)
- **GPU Layers**: 999 (full offload)
- **Context**: 2048 tokens
- **Temperature**: 0.3
- **Top-p**: 0.9
- **Top-k**: 40

### Chimera-Optimized Configuration
Based on Technical Report 108 findings:

**For Gemma3:latest:**
- **GPU Layers**: 999 (full offload - optimal for Gemma3)
- **Context**: 4096 tokens (larger context - optimal for Gemma3)
- **Temperature**: 0.4 (balanced creativity/coherence)
- **Expected Performance**: 102.31 tok/s throughput, 0.128s TTFT

**For Llama3.1:q4_0:**
- **GPU Layers**: 40 (partial offload - optimal for Llama3.1)
- **Context**: 1024 tokens (smaller context - optimal for Llama3.1)
- **Temperature**: 0.4 (balanced creativity/coherence)
- **Expected Performance**: 78.42 tok/s throughput, 0.088s TTFT

## Performance Expectations

Based on Technical Report 108 benchmarks:

- **Throughput Improvement**: 15-30% over baseline
- **TTFT Reduction**: 10-20% improvement
- **Consistency**: Stable performance across multiple runs
- **GPU Efficiency**: Better resource utilization

## Troubleshooting

### Common Issues

1. **Ollama Connection Error**
   ```
   Error: Ollama API error: 500
   ```
   **Solution**: Ensure Ollama is running (`ollama serve`) and model is installed

2. **Model Not Found**
   ```
   Error: Model 'gemma3:latest' not found
   ```
   **Solution**: Install the model (`ollama pull gemma3:latest`)

3. **GPU Memory Error**
   ```
   Error: CUDA out of memory
   ```
   **Solution**: Reduce context size or use smaller model

4. **File Permission Error**
   ```
   Error: Permission denied writing to reports/
   ```
   **Solution**: Ensure write permissions to output directory

### Performance Issues

1. **Slow Performance**
   - Check GPU utilization (`nvidia-smi`)
   - Verify Ollama is using GPU (`ollama ps`)
   - Ensure adequate VRAM (6GB+ recommended)

2. **Inconsistent Results**
   - Run multiple times (`--runs 3`)
   - Check system load during execution
   - Verify no other GPU-intensive processes

## Research Standards

This demo follows research-grade standards:

- **Reproducibility**: Fixed configurations and seeds
- **Documentation**: Complete configuration details
- **Metrics**: Comprehensive performance tracking
- **Citations**: References to Technical Report 108
- **Validation**: Multiple runs for statistical significance

## References

- **Technical Report 108**: Comprehensive LLM Performance Analysis
- **Ollama Documentation**: https://ollama.ai/docs
- **Chimera Optimization**: Banterhearts benchmark results
- **Performance Methodology**: Industry-standard benchmarking practices

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review Technical Report 108 for configuration details
3. Verify Ollama installation and model availability
4. Check system requirements and GPU compatibility

---

**Demo Version**: 1.0.0  
**Last Updated**: 2025-01-08  
**Compatible with**: Technical Report 108 findings
