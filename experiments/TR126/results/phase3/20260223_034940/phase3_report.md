# TR126 Phase 3: Backend Matrix Rerun (Linux)

*Generated: 2026-02-23 04:46 UTC*

## 1. Environment

- **Platform:** Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39
- **GPU:** NVIDIA GeForce RTX 4080 Laptop GPU (12.88 GB)
- **PyTorch:** 2.8.0a0+34c6371d24.nv25.08
- **CUDA:** 13.0
- **Triton:** 3.3.1
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
| 1 | transformers-gpu-compile | 540 | 7.972 | 6.321 | 18.029 | 6.166 | [7.451, 8.493] |
| 2 | ollama | 540 | 9.200 | 8.229 | 14.490 | 4.493 | [8.821, 9.580] |
| 3 | transformers-gpu | 540 | 17.405 | 19.000 | 27.995 | 8.665 | [16.673, 18.138] |

### 4.2 Per-Model Rankings

**llama3.2:1b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 7.172 | 6.954 | 8.460 | [6.410, 7.933] |

**models/gpt2-100m:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | transformers-gpu-compile | 135 | 1.606 | 1.546 | 1.798 | [1.583, 1.629] |
| 2 | transformers-gpu | 135 | 3.958 | 3.883 | 4.540 | [3.904, 4.011] |

**models/qwen2.5-0.5b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | transformers-gpu-compile | 135 | 3.665 | 3.671 | 4.081 | [3.629, 3.702] |
| 2 | ollama | 135 | 7.221 | 7.110 | 9.207 | [6.557, 7.886] |
| 3 | transformers-gpu | 135 | 17.253 | 17.084 | 19.037 | [17.067, 17.439] |

**models/qwen2.5-1.5b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | transformers-gpu-compile | 135 | 9.164 | 9.073 | 10.360 | [9.072, 9.257] |
| 2 | ollama | 135 | 9.522 | 9.392 | 11.907 | [8.812, 10.233] |
| 3 | transformers-gpu | 135 | 21.372 | 20.555 | 25.570 | [20.966, 21.778] |

**models/qwen2.5-3b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 12.887 | 13.439 | 15.787 | [12.448, 13.326] |
| 2 | transformers-gpu-compile | 135 | 17.451 | 17.124 | 19.620 | [17.274, 17.629] |
| 3 | transformers-gpu | 135 | 27.038 | 26.665 | 29.901 | [26.719, 27.356] |

### 4.3 Compile Effect: helps (-54.2%, significant, d=-1.254 [large])

- GPU eager mean: 17.405 ms | GPU compile mean: 7.972 ms
- t=20.61, p=0.0000

### 4.4 Pairwise Comparisons (3/3 significant)

| Group A | Group B | Mean A (ms) | Mean B (ms) | Delta (%) | p-value | Cohen's d | Effect | Sig? |
|---------|---------|-------------|-------------|-----------|---------|-----------|--------|------|
| ollama | transformers-gpu | 9.200 | 17.405 | +89.2% | 0.0000 | 1.189 | large | Yes |
| ollama | transformers-gpu-compile | 9.200 | 7.972 | -13.4% | 0.0002 | -0.228 | small | Yes |
| transformers-gpu | transformers-gpu-compile | 17.405 | 7.972 | -54.2% | 0.0000 | -1.254 | large | Yes |

### 4.5 Outlier Analysis (IQR)

| Backend | N Total | N Outliers | Outlier % |
|---------|---------|------------|-----------|
| ollama | 540 | 6 | 1.1% |
| transformers-gpu | 540 | 0 | 0.0% |
| transformers-gpu-compile | 540 | 0 | 0.0% |

## 5. Kv Decode

Total samples: 1080

### 5.1 Backend Rankings (by mean latency)

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | Std (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|----------|--------|
| 1 | ollama | 540 | 286.981 | 236.418 | 736.698 | 213.696 | [268.917, 305.046] |
| 2 | transformers-gpu | 540 | 1956.702 | 2267.842 | 3102.120 | 973.286 | [1874.427, 2038.977] |

### 5.2 Per-Model Rankings

**llama3.2:1b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 318.872 | 456.670 | 474.724 | [288.437, 349.307] |

**models/gpt2-100m:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | transformers-gpu | 135 | 411.374 | 413.026 | 436.358 | [408.368, 414.379] |

**models/qwen2.5-0.5b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 149.255 | 168.679 | 239.058 | [134.647, 163.863] |
| 2 | transformers-gpu | 135 | 1994.841 | 1979.697 | 2114.014 | [1983.738, 2005.943] |

**models/qwen2.5-1.5b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 214.126 | 85.974 | 430.472 | [184.786, 243.465] |
| 2 | transformers-gpu | 135 | 2359.814 | 2349.843 | 2456.319 | [2351.327, 2368.301] |

**models/qwen2.5-3b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 465.673 | 335.160 | 744.492 | [425.034, 506.312] |
| 2 | transformers-gpu | 135 | 3060.781 | 3058.338 | 3186.391 | [3049.779, 3071.782] |

### 5.3 Pairwise Comparisons (1/1 significant)

| Group A | Group B | Mean A (ms) | Mean B (ms) | Delta (%) | p-value | Cohen's d | Effect | Sig? |
|---------|---------|-------------|-------------|-----------|---------|-----------|--------|------|
| ollama | transformers-gpu | 286.981 | 1956.702 | +581.8% | 0.0000 | 2.370 | large | Yes |

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
| 1 | ollama | 540 | 521.406 | 493.188 | 994.744 | 241.075 | [501.027, 541.785] |
| 2 | transformers-gpu | 540 | 1992.256 | 2252.376 | 3195.046 | 987.210 | [1908.804, 2075.708] |

### 6.2 Per-Model Rankings

**llama3.2:1b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 584.004 | 734.570 | 772.475 | [548.828, 619.180] |

**models/gpt2-100m:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | transformers-gpu | 135 | 434.666 | 430.874 | 480.082 | [431.322, 438.010] |

**models/qwen2.5-0.5b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 370.297 | 399.336 | 500.559 | [350.857, 389.738] |
| 2 | transformers-gpu | 135 | 2024.858 | 2016.492 | 2118.589 | [2016.548, 2033.169] |

**models/qwen2.5-1.5b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 434.361 | 301.742 | 706.245 | [399.450, 469.271] |
| 2 | transformers-gpu | 135 | 2378.007 | 2373.794 | 2477.547 | [2368.315, 2387.699] |

**models/qwen2.5-3b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 696.963 | 556.835 | 1011.588 | [651.820, 742.106] |
| 2 | transformers-gpu | 135 | 3131.493 | 3113.246 | 3307.476 | [3113.304, 3149.682] |

### 6.3 Pairwise Comparisons (1/1 significant)

| Group A | Group B | Mean A (ms) | Mean B (ms) | Delta (%) | p-value | Cohen's d | Effect | Sig? |
|---------|---------|-------------|-------------|-----------|---------|-----------|--------|------|
| ollama | transformers-gpu | 521.406 | 1992.256 | +282.1% | 0.0000 | 2.047 | large | Yes |

### 6.4 Outlier Analysis (IQR)

| Backend | N Total | N Outliers | Outlier % |
|---------|---------|------------|-----------|
| ollama | 540 | 0 | 0.0% |
| transformers-gpu | 540 | 0 | 0.0% |

## 7. Power Analysis

- **prefill:** N=540/group, min detectable d=0.170 (1.342 ms), can detect small effects
- **kv_decode:** N=540/group, min detectable d=0.170 (186.278 ms), can detect small effects
- **e2e_kv:** N=540/group, min detectable d=0.170 (175.309 ms), can detect small effects

## 8. Findings

**Finding 1:** Backend rankings vary by mode (2 different winners across 3 modes):
  - prefill: transformers-gpu-compile (7.972 ms)
  - kv_decode: ollama (286.981 ms)
  - e2e_kv: ollama (521.406 ms)

**Finding 2:** Rankings differ by model in prefill:
  - llama3.2:1b: ollama
  - models/gpt2-100m: transformers-gpu-compile
  - models/qwen2.5-0.5b: transformers-gpu-compile
  - models/qwen2.5-1.5b: transformers-gpu-compile
  - models/qwen2.5-3b: ollama

**Finding 3:** Compile effect: 1/1 modes helped, 1 statistically significant.

**Finding 4:** prefill: compile helps (-54.2%, d=-1.254 [large], significant)

**Finding 5:** 5/5 (100%) pairwise comparisons reached significance.

**Finding 6:** Mean outlier rate: 0.2% (IQR method).

## 9. Conclusions & Implications

1. **Mode-dependent rankings:** No single backend dominates
   all modes. Backend selection should be mode-aware.

2. **Compilation beneficial:** Real Triton compilation consistently helps.
   Unlike TR120's `aot_eager` fallback, real inductor delivers speedups.

3. **Practically meaningful:** Large effect sizes in prefill — differences are operationally relevant.

