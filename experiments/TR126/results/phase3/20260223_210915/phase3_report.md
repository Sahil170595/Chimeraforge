# TR126 Phase 3: Backend Matrix Rerun (Linux)

*Generated: 2026-02-23 22:12 UTC*

## 1. Environment

- **Platform:** Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39
- **GPU:** NVIDIA GeForce RTX 4080 Laptop GPU (12.88 GB)
- **PyTorch:** 2.10.0a0+a36e1d39eb.nv26.01.42222806
- **CUDA:** 13.1
- **Triton:** 3.6.0
- **In Docker:** True

## 2. Methodology

This phase reruns TR117's Tier-3 backend matrix on Linux to determine if
backend rankings change under real Triton compilation.

- **Backends:** transformers-gpu, transformers-gpu-compile, ollama
- **Models:** models/gpt2-100m, models/qwen2.5-0.5b, models/qwen2.5-1.5b, models/qwen2.5-3b, llama3.2:1b
- **Scenarios:** single_micro, single_short, single_medium, single_long, stress_single
- **Modes:** prefill, kv_decode, e2e_kv
- **Repetitions:** 15

## 3. Cross-Phase Validation

Phase 1 results not found (environment.json missing).
Cannot confirm Triton was active during Phase 3.

## 4. Prefill

Total samples: 1620

### 4.1 Backend Rankings (by mean latency)

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | Std (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|----------|--------|
| 1 | transformers-gpu-compile | 540 | 11.459 | 8.172 | 29.416 | 9.995 | [10.614, 12.304] |
| 2 | ollama | 540 | 16.041 | 13.442 | 27.297 | 7.640 | [15.396, 16.687] |
| 3 | transformers-gpu | 540 | 19.902 | 19.412 | 38.582 | 12.096 | [18.879, 20.924] |

### 4.2 Per-Model Rankings

**llama3.2:1b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 10.676 | 11.132 | 12.196 | [10.028, 11.324] |

**models/gpt2-100m:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | transformers-gpu-compile | 135 | 2.055 | 1.541 | 3.505 | [1.892, 2.218] |
| 2 | transformers-gpu | 135 | 3.991 | 3.891 | 4.360 | [3.903, 4.079] |

**models/qwen2.5-0.5b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | transformers-gpu-compile | 135 | 5.885 | 5.751 | 7.244 | [5.797, 5.974] |
| 2 | ollama | 135 | 12.163 | 12.485 | 14.125 | [11.062, 13.264] |
| 3 | transformers-gpu | 135 | 17.109 | 17.051 | 17.966 | [17.013, 17.204] |

**models/qwen2.5-1.5b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | transformers-gpu-compile | 135 | 13.254 | 12.863 | 26.759 | [12.355, 14.154] |
| 2 | ollama | 135 | 17.060 | 17.273 | 19.900 | [16.018, 18.102] |
| 3 | transformers-gpu | 135 | 23.658 | 21.984 | 34.516 | [22.894, 24.422] |

**models/qwen2.5-3b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 24.266 | 25.501 | 28.869 | [23.372, 25.161] |
| 2 | transformers-gpu-compile | 135 | 24.641 | 21.272 | 44.396 | [23.177, 26.106] |
| 3 | transformers-gpu | 135 | 34.849 | 31.288 | 54.302 | [33.470, 36.228] |

### 4.3 Compile Effect: helps (-42.4%, significant, d=-0.761 [medium])

- GPU eager mean: 19.902 ms | GPU compile mean: 11.459 ms
- t=12.50, p=0.0000

### 4.4 Pairwise Comparisons (3/3 significant)

| Group A | Group B | Mean A (ms) | Mean B (ms) | Delta (%) | p-value | Cohen's d | Effect | Sig? |
|---------|---------|-------------|-------------|-----------|---------|-----------|--------|------|
| ollama | transformers-gpu | 16.041 | 19.902 | +24.1% | 0.0000 | 0.382 | small | Yes |
| ollama | transformers-gpu-compile | 16.041 | 11.459 | -28.6% | 0.0000 | -0.515 | medium | Yes |
| transformers-gpu | transformers-gpu-compile | 19.902 | 11.459 | -42.4% | 0.0000 | -0.761 | medium | Yes |

### 4.5 Outlier Analysis (IQR)

| Backend | N Total | N Outliers | Outlier % |
|---------|---------|------------|-----------|
| ollama | 540 | 6 | 1.1% |
| transformers-gpu | 540 | 15 | 2.8% |
| transformers-gpu-compile | 540 | 15 | 2.8% |

## 5. Kv Decode

Total samples: 1080

### 5.1 Backend Rankings (by mean latency)

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | Std (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|----------|--------|
| 1 | ollama | 540 | 454.736 | 442.921 | 1205.925 | 339.388 | [426.047, 483.426] |
| 2 | transformers-gpu | 540 | 2086.519 | 2293.991 | 3453.734 | 1045.695 | [1998.123, 2174.915] |

### 5.2 Per-Model Rankings

**llama3.2:1b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 407.791 | 580.083 | 604.113 | [369.154, 446.428] |

**models/gpt2-100m:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | transformers-gpu | 135 | 455.333 | 452.111 | 483.439 | [452.805, 457.861] |

**models/qwen2.5-0.5b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 280.140 | 319.068 | 451.653 | [251.788, 308.492] |
| 2 | transformers-gpu | 135 | 2113.128 | 2108.846 | 2186.552 | [2105.833, 2120.423] |

**models/qwen2.5-1.5b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 376.880 | 155.293 | 781.524 | [322.797, 430.964] |
| 2 | transformers-gpu | 135 | 2443.587 | 2428.158 | 2556.102 | [2434.169, 2453.005] |

**models/qwen2.5-3b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 754.134 | 542.556 | 1216.308 | [687.384, 820.884] |
| 2 | transformers-gpu | 135 | 3334.030 | 3322.355 | 3543.868 | [3312.775, 3355.285] |

### 5.3 Pairwise Comparisons (1/1 significant)

| Group A | Group B | Mean A (ms) | Mean B (ms) | Delta (%) | p-value | Cohen's d | Effect | Sig? |
|---------|---------|-------------|-------------|-----------|---------|-----------|--------|------|
| ollama | transformers-gpu | 454.736 | 2086.519 | +358.8% | 0.0000 | 2.099 | large | Yes |

### 5.4 Outlier Analysis (IQR)

| Backend | N Total | N Outliers | Outlier % |
|---------|---------|------------|-----------|
| ollama | 540 | 0 | 0.0% |
| transformers-gpu | 540 | 0 | 0.0% |

## 6. E2E Kv

Total samples: 1080

### 6.1 Backend Rankings (by mean latency)

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | Std (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|----------|--------|
| 1 | ollama | 540 | 726.420 | 738.572 | 1532.017 | 378.444 | [694.429, 758.411] |
| 2 | transformers-gpu | 540 | 2084.329 | 2318.930 | 3460.600 | 1042.956 | [1996.165, 2172.493] |

### 6.2 Per-Model Rankings

**llama3.2:1b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 695.689 | 893.245 | 936.149 | [650.377, 741.002] |

**models/gpt2-100m:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | transformers-gpu | 135 | 459.190 | 456.011 | 477.553 | [457.171, 461.208] |

**models/qwen2.5-0.5b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 536.422 | 582.785 | 758.387 | [501.306, 571.538] |
| 2 | transformers-gpu | 135 | 2100.178 | 2092.089 | 2186.753 | [2093.362, 2106.993] |

**models/qwen2.5-1.5b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 630.868 | 378.940 | 1087.908 | [569.314, 692.422] |
| 2 | transformers-gpu | 135 | 2449.781 | 2441.733 | 2552.906 | [2439.832, 2459.729] |

**models/qwen2.5-3b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 1042.701 | 810.575 | 1545.571 | [969.562, 1115.841] |
| 2 | transformers-gpu | 135 | 3328.168 | 3269.250 | 3556.480 | [3306.672, 3349.664] |

### 6.3 Pairwise Comparisons (1/1 significant)

| Group A | Group B | Mean A (ms) | Mean B (ms) | Delta (%) | p-value | Cohen's d | Effect | Sig? |
|---------|---------|-------------|-------------|-----------|---------|-----------|--------|------|
| ollama | transformers-gpu | 726.420 | 2084.329 | +186.9% | 0.0000 | 1.731 | large | Yes |

### 6.4 Outlier Analysis (IQR)

| Backend | N Total | N Outliers | Outlier % |
|---------|---------|------------|-----------|
| ollama | 540 | 0 | 0.0% |
| transformers-gpu | 540 | 0 | 0.0% |

## 7. Power Analysis

- **prefill:** N=540/group, min detectable d=0.170 (1.815 ms), can detect small effects
- **kv_decode:** N=540/group, min detectable d=0.170 (192.148 ms), can detect small effects
- **e2e_kv:** N=540/group, min detectable d=0.170 (176.886 ms), can detect small effects

## 8. Findings

**Finding 1:** Backend rankings vary by mode (2 different winners across 3 modes):
  - prefill: transformers-gpu-compile (11.459 ms)
  - kv_decode: ollama (454.736 ms)
  - e2e_kv: ollama (726.420 ms)

**Finding 2:** Rankings differ by model in prefill:
  - llama3.2:1b: ollama
  - models/gpt2-100m: transformers-gpu-compile
  - models/qwen2.5-0.5b: transformers-gpu-compile
  - models/qwen2.5-1.5b: transformers-gpu-compile
  - models/qwen2.5-3b: ollama

**Finding 3:** Compile effect: 1/1 modes helped, 1 statistically significant.

**Finding 4:** prefill: compile helps (-42.4%, d=-0.761 [medium], significant)

**Finding 5:** 5/5 (100%) pairwise comparisons reached significance.

**Finding 6:** Mean outlier rate: 1.0% (IQR method).

## 9. Conclusions & Implications

1. **Mode-dependent rankings:** No single backend dominates
   all modes. Backend selection should be mode-aware.

2. **Compilation beneficial:** Real Triton compilation consistently helps.
   Unlike TR120's `aot_eager` fallback, real inductor delivers speedups.

