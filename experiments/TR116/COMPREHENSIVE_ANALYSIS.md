# TR116 Comprehensive Per-Run Granular Analysis

**Generated from 60 benchmark runs**

**Models:** Qwen 2.5 7B, Gemma 3, Llama 3.1 8B
**Runtimes:** Rust (tokio-default), Python (asyncio)
**Scenarios:** baseline-vs-chimera, chimera-homo

## 1. Rust: Qwen 2.5 7B - Baseline vs Chimera

| Run | Speedup | Efficiency (%) | Throughput Delta (tok/s) | TTFT Delta (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.7015x | 85.08 | +30.47 | +1422.8 | No |
| 2 | 1.7037x | 85.18 | +30.69 | +119.4 | No |
| 3 | 1.9916x | 99.58 | -0.35 | +17.7 | No |
| 4 | 1.9758x | 98.79 | -13.13 | +86.9 | No |
| 5 | 1.6239x | 81.20 | +14.33 | +49.8 | No |

**Efficiency Statistics:**
- Mean: 89.97%
- Std Dev: 8.57pp
- Min: 81.20% | Max: 99.58%
- Range: 18.38pp
- CV: 9.53%

## 2. Rust: Qwen 2.5 7B - Chimera Homo

| Run | Speedup | Efficiency (%) | Throughput Delta (tok/s) | TTFT Delta (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.9185x | 95.92 | -3.65 | -468.2 | No |
| 2 | 1.9481x | 97.40 | -3.49 | +111.6 | No |
| 3 | 1.7989x | 89.94 | -16.06 | +58.5 | No |
| 4 | 1.8360x | 91.80 | -6.18 | +89.0 | No |
| 5 | 1.4400x | 72.00 | -32.73 | +159.9 | Yes |

**Efficiency Statistics:**
- Mean: 89.41%
- Std Dev: 10.19pp
- Min: 72.00% | Max: 97.40%
- Range: 25.41pp
- CV: 11.40%

## 3. Rust: Gemma 3 - Baseline vs Chimera

| Run | Speedup | Efficiency (%) | Throughput Delta (tok/s) | TTFT Delta (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.9493x | 97.46 | +0.43 | +1270.3 | No |
| 2 | 1.9689x | 98.45 | +2.22 | +145.3 | No |
| 3 | 1.9140x | 95.70 | -5.75 | +116.4 | No |
| 4 | 1.9248x | 96.24 | -4.96 | +173.9 | No |
| 5 | 1.9744x | 98.72 | -1.57 | +159.9 | No |

**Efficiency Statistics:**
- Mean: 97.31%
- Std Dev: 1.33pp
- Min: 95.70% | Max: 98.72%
- Range: 3.02pp
- CV: 1.36%

## 4. Rust: Gemma 3 - Chimera Homo

| Run | Speedup | Efficiency (%) | Throughput Delta (tok/s) | TTFT Delta (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.9821x | 99.11 | -7.39 | -1563.3 | No |
| 2 | 1.9972x | 99.86 | +0.45 | +164.0 | No |
| 3 | 1.9829x | 99.15 | +1.11 | +259.9 | No |
| 4 | 1.9945x | 99.73 | -0.25 | +163.0 | No |
| 5 | 1.9651x | 98.26 | +2.27 | +275.0 | No |

**Efficiency Statistics:**
- Mean: 99.22%
- Std Dev: 0.64pp
- Min: 98.26% | Max: 99.86%
- Range: 1.61pp
- CV: 0.64%

## 5. Rust: Llama 3.1 8B - Baseline vs Chimera

| Run | Speedup | Efficiency (%) | Throughput Delta (tok/s) | TTFT Delta (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.9235x | 96.18 | +4.33 | +1441.1 | No |
| 2 | 1.9333x | 96.66 | -3.13 | +149.6 | No |
| 3 | 1.9034x | 95.17 | -5.35 | +128.1 | No |
| 4 | 1.9100x | 95.50 | -4.31 | +127.5 | No |
| 5 | 1.9847x | 99.23 | +0.81 | +140.6 | No |

**Efficiency Statistics:**
- Mean: 96.55%
- Std Dev: 1.61pp
- Min: 95.17% | Max: 99.23%
- Range: 4.06pp
- CV: 1.67%

## 6. Rust: Llama 3.1 8B - Chimera Homo

| Run | Speedup | Efficiency (%) | Throughput Delta (tok/s) | TTFT Delta (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.9809x | 99.05 | -0.71 | -487.8 | No |
| 2 | 1.9505x | 97.52 | -2.79 | +75.6 | No |
| 3 | 1.9701x | 98.51 | -1.42 | +149.3 | No |
| 4 | 1.9861x | 99.30 | -0.51 | +94.3 | No |
| 5 | 1.9672x | 98.36 | -1.57 | +78.9 | No |

**Efficiency Statistics:**
- Mean: 98.55%
- Std Dev: 0.69pp
- Min: 97.52% | Max: 99.30%
- Range: 1.78pp
- CV: 0.70%

## 7. Python: Qwen 2.5 7B - Baseline vs Chimera

| Run | Speedup | Efficiency (%) | Throughput Delta (tok/s) | TTFT Delta (ms) | Contention |
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

| Run | Speedup | Efficiency (%) | Throughput Delta (tok/s) | TTFT Delta (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.6309x | 81.54 | +13.18 | -97.4 | No |
| 2 | 1.6858x | 84.29 | +14.64 | -5.3 | No |
| 3 | 1.6565x | 82.83 | +16.26 | +6.5 | No |
| 4 | 1.6784x | 83.92 | +15.01 | +0.5 | No |
| 5 | 1.7601x | 88.01 | +10.52 | N/A | No |

**Efficiency Statistics:**
- Mean: 84.12%
- Std Dev: 2.42pp
- Min: 81.54% | Max: 88.01%
- Range: 6.46pp
- CV: 2.88%

## 9. Python: Gemma 3 - Baseline vs Chimera

| Run | Speedup | Efficiency (%) | Throughput Delta (tok/s) | TTFT Delta (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.2023x | 60.12 | +10.16 | +35.3 | No |
| 2 | 1.6815x | 84.07 | +16.05 | +0.6 | No |
| 3 | 1.7503x | 87.51 | +11.43 | -0.5 | No |
| 4 | 1.6788x | 83.94 | +16.57 | -1.0 | No |
| 5 | 1.7108x | 85.54 | +13.99 | N/A | No |

**Efficiency Statistics:**
- Mean: 80.24%
- Std Dev: 11.34pp
- Min: 60.12% | Max: 87.51%
- Range: 27.40pp
- CV: 14.13%

## 10. Python: Gemma 3 - Chimera Homo

| Run | Speedup | Efficiency (%) | Throughput Delta (tok/s) | TTFT Delta (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.5950x | 79.75 | +12.49 | -43.5 | No |
| 2 | 1.7251x | 86.25 | +13.03 | -0.5 | No |
| 3 | 1.7082x | 85.41 | +13.74 | +0.1 | No |
| 4 | 1.6842x | 84.21 | +15.31 | N/A | No |
| 5 | 1.7729x | 88.64 | +9.83 | -0.2 | No |

**Efficiency Statistics:**
- Mean: 84.85%
- Std Dev: 3.28pp
- Min: 79.75% | Max: 88.64%
- Range: 8.89pp
- CV: 3.87%

## 11. Python: Llama 3.1 8B - Baseline vs Chimera

| Run | Speedup | Efficiency (%) | Throughput Delta (tok/s) | TTFT Delta (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.2039x | 60.19 | +9.78 | -5.1 | No |
| 2 | 1.8258x | 91.29 | +6.47 | N/A | No |
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

| Run | Speedup | Efficiency (%) | Throughput Delta (tok/s) | TTFT Delta (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.3911x | 69.56 | +15.70 | -72.9 | No |
| 2 | 1.7874x | 89.37 | +8.43 | -0.1 | No |
| 3 | 1.8054x | 90.27 | +7.18 | N/A | No |
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

**Hypothesis:** Models with higher throughput imbalance (absolute delta) show lower efficiency.

- **QWEN2.5 (RUST)**: r = -0.007
  - Weak/no correlation
- **QWEN2.5 (PYTHON)**: r = -0.069
  - Weak/no correlation
- **GEMMA3 (RUST)**: r = 0.439
  - Moderate positive correlation
- **GEMMA3 (PYTHON)**: r = 0.327
  - Weak/no correlation
- **LLAMA3.1 (RUST)**: r = 0.391
  - Weak/no correlation
- **LLAMA3.1 (PYTHON)**: r = -0.654
  - Moderate negative correlation


## 2. Variance Decomposition (Rust)

- **Between-Model Variance:** 22.64 pp^2
- **Within-Model Variance (avg):** 27.78 pp^2
- **Total Variance:** 50.42 pp^2
- **Between-Model % of Total:** 44.9%

**Interpretation:** 45% of variance in Rust comes from model choice, not run-to-run variation.

## 3. Efficiency Distribution by Runtime

### RUST

- **Mean:** 95.17%
- **Median (P50):** 97.49%
- **P5:** 82.94% | **P95:** 99.66%
- **Range:** 72.00% - 99.86% (27.86pp)
- **Std Dev:** 6.44pp

### PYTHON

- **Mean:** 82.73%
- **Median (P50):** 84.25%
- **P5:** 60.15% | **P95:** 91.31%
- **Range:** 55.31% - 91.68% (36.37pp)
- **Std Dev:** 9.28pp
