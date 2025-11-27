# TR116 Comprehensive Per-Run Granular Analysis

**Generated from 60 benchmark runs**

**Models:** Qwen 2.5 7B, Gemma 3, Llama 3.1 8B
**Runtimes:** Rust (tokio-default), Python (asyncio)
**Scenarios:** baseline-vs-chimera, chimera-homo

## 1. Rust: Qwen 2.5 7B - Baseline vs Chimera

| Run | Speedup | Efficiency (%) | Throughput Δ (tok/s) | TTFT Δ (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | N/A | N/A | N/A | N/A | No |
| 2 | N/A | N/A | N/A | N/A | No |
| 3 | N/A | N/A | N/A | N/A | No |
| 4 | N/A | N/A | N/A | N/A | No |
| 5 | N/A | N/A | N/A | N/A | No |
## 2. Rust: Qwen 2.5 7B - Chimera Homo

| Run | Speedup | Efficiency (%) | Throughput Δ (tok/s) | TTFT Δ (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | N/A | N/A | N/A | N/A | No |
| 2 | N/A | N/A | N/A | N/A | No |
| 3 | N/A | N/A | N/A | N/A | No |
| 4 | N/A | N/A | N/A | N/A | No |
| 5 | N/A | N/A | N/A | N/A | No |
## 3. Rust: Gemma 3 - Baseline vs Chimera

| Run | Speedup | Efficiency (%) | Throughput Δ (tok/s) | TTFT Δ (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | N/A | N/A | N/A | N/A | No |
| 2 | N/A | N/A | N/A | N/A | No |
| 3 | N/A | N/A | N/A | N/A | No |
| 4 | N/A | N/A | N/A | N/A | No |
| 5 | N/A | N/A | N/A | N/A | No |
## 4. Rust: Gemma 3 - Chimera Homo

| Run | Speedup | Efficiency (%) | Throughput Δ (tok/s) | TTFT Δ (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | N/A | N/A | N/A | N/A | No |
| 2 | N/A | N/A | N/A | N/A | No |
| 3 | N/A | N/A | N/A | N/A | No |
| 4 | N/A | N/A | N/A | N/A | No |
| 5 | N/A | N/A | N/A | N/A | No |
## 5. Rust: Llama 3.1 8B - Baseline vs Chimera

| Run | Speedup | Efficiency (%) | Throughput Δ (tok/s) | TTFT Δ (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | N/A | N/A | N/A | N/A | No |
| 2 | N/A | N/A | N/A | N/A | No |
| 3 | N/A | N/A | N/A | N/A | No |
| 4 | N/A | N/A | N/A | N/A | No |
| 5 | N/A | N/A | N/A | N/A | No |
## 6. Rust: Llama 3.1 8B - Chimera Homo

| Run | Speedup | Efficiency (%) | Throughput Δ (tok/s) | TTFT Δ (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | N/A | N/A | N/A | N/A | No |
| 2 | N/A | N/A | N/A | N/A | No |
| 3 | N/A | N/A | N/A | N/A | No |
| 4 | N/A | N/A | N/A | N/A | No |
| 5 | N/A | N/A | N/A | N/A | No |
## 7. Python: Qwen 2.5 7B - Baseline vs Chimera

| Run | Speedup | Efficiency (%) | Throughput Δ (tok/s) | TTFT Δ (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.1063x | 55.31 | +14.32 | -11.7 | No |
| 2 | 1.6568x | 82.84 | +16.26 | +0.8 | No |
| 3 | 1.6800x | 84.00 | +14.71 | +4.3 | No |
| 4 | 1.6309x | 81.54 | +17.53 | +6.5 | No |
| 5 | 1.6827x | 84.14 | +15.15 | +0.2 | No |

**Efficiency Statistics:**
- Mean: 77.57%
- Std Dev: 12.48pp
- Min: 55.31% | Max: 84.14%
- Range: 28.82pp
- CV: 16.09%

## 8. Python: Qwen 2.5 7B - Chimera Homo

| Run | Speedup | Efficiency (%) | Throughput Δ (tok/s) | TTFT Δ (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.6309x | 81.54 | +13.18 | -97.4 | No |
| 2 | 1.6858x | 84.29 | +14.64 | -5.3 | No |
| 3 | 1.6565x | 82.83 | +16.26 | +6.5 | No |
| 4 | 1.6784x | 83.92 | +15.01 | +0.5 | No |
| 5 | 1.7601x | 88.01 | +10.52 | +0.0 | No |

**Efficiency Statistics:**
- Mean: 84.12%
- Std Dev: 2.42pp
- Min: 81.54% | Max: 88.01%
- Range: 6.46pp
- CV: 2.88%

## 9. Python: Gemma 3 - Baseline vs Chimera

| Run | Speedup | Efficiency (%) | Throughput Δ (tok/s) | TTFT Δ (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.2023x | 60.12 | +10.16 | +35.3 | No |
| 2 | 1.6815x | 84.07 | +16.05 | +0.6 | No |
| 3 | 1.7503x | 87.51 | +11.43 | -0.5 | No |
| 4 | 1.6788x | 83.94 | +16.57 | -1.0 | No |
| 5 | 1.7108x | 85.54 | +13.99 | +0.0 | No |

**Efficiency Statistics:**
- Mean: 80.24%
- Std Dev: 11.34pp
- Min: 60.12% | Max: 87.51%
- Range: 27.40pp
- CV: 14.13%

## 10. Python: Gemma 3 - Chimera Homo

| Run | Speedup | Efficiency (%) | Throughput Δ (tok/s) | TTFT Δ (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.5950x | 79.75 | +12.49 | -43.5 | No |
| 2 | 1.7251x | 86.25 | +13.03 | -0.5 | No |
| 3 | 1.7082x | 85.41 | +13.74 | +0.1 | No |
| 4 | 1.6842x | 84.21 | +15.31 | +0.0 | No |
| 5 | 1.7729x | 88.64 | +9.83 | -0.2 | No |

**Efficiency Statistics:**
- Mean: 84.85%
- Std Dev: 3.28pp
- Min: 79.75% | Max: 88.64%
- Range: 8.89pp
- CV: 3.87%

## 11. Python: Llama 3.1 8B - Baseline vs Chimera

| Run | Speedup | Efficiency (%) | Throughput Δ (tok/s) | TTFT Δ (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.2039x | 60.19 | +9.78 | -5.1 | No |
| 2 | 1.8258x | 91.29 | +6.47 | +0.0 | No |
| 3 | 1.7514x | 87.57 | +10.08 | -0.6 | No |
| 4 | 1.8266x | 91.33 | +6.31 | +0.5 | No |
| 5 | 1.7722x | 88.61 | +9.17 | +0.8 | No |

**Efficiency Statistics:**
- Mean: 83.80%
- Std Dev: 13.30pp
- Min: 60.19% | Max: 91.33%
- Range: 31.14pp
- CV: 15.87%

## 12. Python: Llama 3.1 8B - Chimera Homo

| Run | Speedup | Efficiency (%) | Throughput Δ (tok/s) | TTFT Δ (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.3911x | 69.56 | +15.70 | -72.9 | No |
| 2 | 1.7874x | 89.37 | +8.43 | -0.1 | No |
| 3 | 1.8054x | 90.27 | +7.18 | +0.0 | No |
| 4 | 1.8337x | 91.68 | +5.91 | +0.6 | No |
| 5 | 1.7599x | 88.00 | +9.84 | +0.6 | No |

**Efficiency Statistics:**
- Mean: 85.77%
- Std Dev: 9.17pp
- Min: 69.56% | Max: 91.68%
- Range: 22.13pp
- CV: 10.69%

---

# Multi-Level Statistical Analysis

## 1. Correlation: Throughput Delta vs Efficiency

**Hypothesis:** Models with higher throughput imbalance (abs(Δ)) show lower efficiency.

- **QWEN2.5 (PYTHON)**: r = -0.069
  - Weak/no correlation
- **GEMMA3 (PYTHON)**: r = 0.327
  - Weak/no correlation
- **LLAMA3.1 (PYTHON)**: r = -0.654
  - Moderate negative correlation


## 2. Variance Decomposition (Rust)

- **Between-Model Variance:** nan pp²
- **Within-Model Variance (avg):** nan pp²
- **Total Variance:** nan pp²
- **Between-Model % of Total:** nan%

**Interpretation:** nan% of variance in Rust comes from model choice, not run-to-run variation.

## 3. Efficiency Distribution by Runtime

### PYTHON

- **Mean:** 82.73%
- **Median (P50):** 84.25%
- **P5:** 60.15% | **P95:** 91.31%
- **Range:** 55.31% - 91.68% (36.37pp)
- **Std Dev:** 9.28pp
