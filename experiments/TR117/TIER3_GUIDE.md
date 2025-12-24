# TR117 Tier 3: Frontier Lab Quality Benchmark

This guide explains how to run the complete TR117 benchmark at PhD+ frontier lab standards.

## What You Get

**Statistical Rigor:**

- 7 repetitions per configuration
- 95% confidence intervals
- Hypothesis testing (t-tests, ANOVA)
- P-values and effect sizes (Cohen's d)
- Bootstrap confidence intervals

**Comprehensive Metrics:**

- ROUGE-1, ROUGE-2, ROUGE-L scores
- BLEU scores
- Semantic similarity (embedding-based)
- Edit distance / Levenshtein
- Exact match rates

**Resource Profiling:**

- CPU utilization (mean, peak)
- Memory usage (mean, peak, percentage)
- GPU utilization (mean, peak)
- GPU memory (mean, peak)
- GPU temperature monitoring

**Cost Analysis:**

- $/1M tokens per backend
- $/hour per backend
- Tokens per dollar
- Memory efficiency (tokens/MB)
- Compute efficiency (tokens/ms)

**TensorRT Integration:**

- Automated engine building from ONNX
- FP32, FP16, INT8 precision testing
- Dynamic shape optimization
- Latency comparison vs other backends

**Reproducibility:**

- Docker environment
- Frozen dependencies
- Seed control
- Temperature/top_p settings documented

## Prerequisites

### System Requirements

- NVIDIA GPU with CUDA 12.8+
- 16GB+ RAM
- 50GB+ disk space
- Ubuntu 22.04 or Windows 11 with WSL2

### Software

- Python 3.13
- CUDA 12.8
- TensorRT 10.12
- Docker (optional, for reproducibility)
- Ollama (for Ollama backend tests)

### Models

- `models/tiny-gpt2` (124M) - Already available
- `gemma3:270m` (270M) - Download via Ollama
- `gemma3:latest` (2B+) - Download via Ollama

Additional models for extended testing:

- `gpt2-medium` (355M)
- `gpt2-large` (774M)
- Llama models via Ollama

## Quick Start

### Option 1: Automated (Linux/WSL)

```bash
# Make script executable
chmod +x scripts/tr117/run_tier3_complete.sh

# Run full suite (4-8 hours)
./scripts/tr117/run_tier3_complete.sh
```

### Option 2: Docker (Reproducible)

```bash
# Build image
cd scripts/tr117
docker build -t tr117-tier3 .

# Run benchmark
docker run --gpus all -v $(pwd)/../../results:/workspace/results \
    tr117-tier3 bash run_tier3_complete.sh
```

### Option 3: Step-by-Step

```bash
# 1. Set environment
export PYTHONPATH="."
export HF_HUB_OFFLINE="1"
export BANTER_TRANSFORMER_MODEL="models/tiny-gpt2"
export BANTER_OLLAMA_MODEL="gemma3:latest"

# 2. Build TensorRT engines
python scripts/tr117/build_tensorrt_engines.py \
    --models-dir models \
    --output-dir artifacts/tensorrt_engines \
    --precision fp32 fp16 int8

# 3. Run benchmark (4-6 hours)
python scripts/tr117/run_matrix.py \
    --config scripts/tr117/configs/matrix_tier3.yaml \
    --output-root results/tr117_tier3/runs \
    --prepare-quant

# 4. Analyze results
python scripts/tr117/analyze_tr117.py \
    --runs-root results/tr117_tier3/runs \
    --output results/tr117_tier3/metrics.csv

# 5. Statistical analysis
python scripts/tr117/statistical_analysis.py

# 6. Cost analysis
python scripts/tr117/cost_analysis.py \
    --metrics results/tr117_tier3/metrics.csv \
    --output results/tr117_tier3/cost_analysis.json

# 7. Capture environment
python scripts/tr117/env_capture.py
```

## Configuration

### Matrix Size

**Default (Tier 3):**

- 9 scenarios (micro, short, medium, long, batch, dual, stress)
- 3 models (tiny-gpt2 124M, gemma3:270m, gemma3:latest 2B)
- 7 backends (transformers CPU/GPU/compile, ORT, TRT, Ollama)
- 3 quant modes (fp32, fp16, int8)
- 7 repetitions
- **Total: ~1,300+ runs**

### Reducing Scope

For faster testing, edit `matrix_tier3.yaml`:

```yaml
repetitions: 3  # Reduce from 7
# Comment out some scenarios
# Comment out some backends
# Reduce quantization modes
```

### Adding Models

Download additional models:

```bash
# Ollama models
ollama pull gemma3:270m
ollama pull llama2:7b
ollama pull mistral

# HuggingFace models
cd models
git lfs install
git clone https://huggingface.co/gpt2-medium
git clone https://huggingface.co/gpt2-large
```

Update `matrix_tier3.yaml`:

```yaml
models:
  - name: models/gpt2-medium
    params_millions: 355
  - name: models/gpt2-large
    params_millions: 774
```

## Output Structure

```
results/tr117_tier3/
├── runs/                           # Raw run data
│   ├── single_short/
│   │   ├── transformers-cpu/
│   │   │   ├── fp32/
│   │   │   │   ├── tiny-gpt2/
│   │   │   │   │   └── run_*.json
│   │   │   └── fp16/
│   │   ├── ollama/
│   │   └── tensorrt/
│   ├── single_medium/
│   └── ...
├── metrics.csv                     # Aggregated metrics
├── statistical_analysis.json       # Statistical tests
├── cost_analysis.json              # Cost breakdown
├── latency_by_backend.png          # Visualization
└── env.json                        # Environment capture
```

## Analysis Outputs

### Statistical Analysis JSON

```json
{
  "summaries": {
    "transformers-cpu": {
      "mean": 520.3,
      "median": 515.4,
      "std": 75.9,
      "ci_95_lower": 485.2,
      "ci_95_upper": 555.4,
      "n": 36
    }
  },
  "pairwise_comparisons": [
    {
      "group_a": "transformers-cpu",
      "group_b": "transformers-cpu-compile",
      "difference": -4.2,
      "percent_change": -0.8,
      "t_statistic": -1.23,
      "p_value": 0.225,
      "significant": false,
      "effect_size_cohens_d": -0.05
    }
  ],
  "anova": {
    "f_statistic": 125.3,
    "p_value": 1.2e-45,
    "significant": true
  }
}
```

### Cost Analysis JSON

```json
{
  "profiles": [
    {
      "backend": "transformers-cpu",
      "tokens_per_second": 1.9,
      "cost_per_million_tokens_usd": 7.35,
      "cost_per_hour_usd": 0.05,
      "tokens_per_dollar": 136054,
      "memory_efficiency": 0.0038,
      "compute_efficiency": 0.0037
    }
  ]
}
```

## Key Metrics Explained

### Statistical Significance

- **p < 0.05**: Statistically significant difference
- **Effect size (Cohen's d)**:
  - Small: 0.2-0.5
  - Medium: 0.5-0.8
  - Large: > 0.8

### Cost Efficiency

- **$/1M tokens**: Direct cost comparison
- **tokens/$**: How many tokens per dollar spent
- Lower $/1M tokens = better cost efficiency

### Resource Efficiency

- **Memory efficiency**: tokens/MB - higher is better
- **Compute efficiency**: tokens/ms - higher is better

## Interpreting Results

### Performance Ranking

1. Sort by `avg_latency_ms` (lower is better)
2. Check `status=ok` (exclude degraded)
3. Verify `n_samples >= 7` for statistical validity

### Cost-Performance Tradeoff

Plot:

- X-axis: `cost_per_million_tokens_usd`
- Y-axis: `tokens_per_second`
- Best backends: high throughput, low cost (top-left)

### Production Recommendations

- **Lowest latency**: Pick backend with min `avg_latency_ms`
- **Best cost**: Pick backend with min `$/1M tokens`
- **Balanced**: Optimize `tokens_per_dollar`

## Next Steps

1. **Review statistical_analysis.json**
   - Which backends are significantly different?
   - What's the effect size of optimizations?

2. **Analyze cost_analysis.json**
   - Which backend offers best $/1M tokens?
   - Is the cost worth the performance gain?

3. **Write Technical Report**
   - Use template from TR114_v2
   - Include all statistical tests
   - Add cost-performance curves
   - Production deployment guide

4. **Compare to Baselines**
   - vLLM performance
   - LLaMA.cpp benchmarks
   - Industry standards

## Troubleshooting

### Out of Memory

- Reduce `batch_size` in scenarios
- Test one model at a time
- Use smaller models first

### Slow Execution

- Reduce `repetitions` to 3-5
- Comment out slow backends
- Run scenarios in parallel

### TensorRT Build Fails

- Check CUDA/TensorRT versions
- Verify ONNX export succeeded
- Try simpler models first

### Ollama Connection Errors

- Ensure Ollama is running: `ollama serve`
- Pull models: `ollama pull gemma3:latest`
- Check `BANTER_OLLAMA_URL`

## Support

For issues or questions:

1. Check terminal output for errors
2. Review `results/tr117_tier3/runs/*/error.txt`
3. Verify environment with `env_capture.py`
4. Consult TR117 codebase documentation

## Citation

If using TR117 in research:

```bibtex
@techreport{tr117_tier3,
  title={TR117: Cross-Backend Frontier Benchmark with Statistical Rigor},
  year={2025},
  institution={Banterhearts Research},
  note={Tier 3 Frontier Lab Quality}
}
```

