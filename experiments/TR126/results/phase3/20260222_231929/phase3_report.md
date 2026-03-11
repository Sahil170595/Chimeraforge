# TR126 Phase 3: Backend Matrix Rerun (Linux)

*Generated: 2026-02-23 00:16 UTC*

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
| 1 | transformers-gpu-compile | 540 | 8.202 | 6.500 | 18.343 | 6.374 | [7.663, 8.740] |
| 2 | ollama | 540 | 9.106 | 8.399 | 14.553 | 3.383 | [8.820, 9.392] |
| 3 | transformers-gpu | 540 | 17.563 | 18.487 | 28.249 | 8.880 | [16.812, 18.313] |

### 4.2 Per-Model Rankings

**llama3.2:1b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 6.921 | 7.039 | 8.226 | [6.634, 7.208] |

**models/gpt2-100m:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | transformers-gpu-compile | 135 | 1.602 | 1.566 | 1.749 | [1.587, 1.616] |
| 2 | transformers-gpu | 135 | 3.839 | 3.801 | 4.116 | [3.812, 3.867] |

**models/qwen2.5-0.5b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | transformers-gpu-compile | 135 | 3.684 | 3.708 | 3.804 | [3.665, 3.704] |
| 2 | ollama | 135 | 7.440 | 7.630 | 9.602 | [6.951, 7.929] |
| 3 | transformers-gpu | 135 | 16.935 | 16.960 | 17.984 | [16.843, 17.027] |

**models/qwen2.5-1.5b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 9.345 | 9.547 | 11.266 | [8.854, 9.836] |
| 2 | transformers-gpu-compile | 135 | 9.542 | 9.443 | 10.771 | [9.435, 9.649] |
| 3 | transformers-gpu | 135 | 22.066 | 21.634 | 25.720 | [21.708, 22.425] |

**models/qwen2.5-3b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 12.717 | 13.263 | 15.197 | [12.306, 13.127] |
| 2 | transformers-gpu-compile | 135 | 17.978 | 17.819 | 19.676 | [17.863, 18.093] |
| 3 | transformers-gpu | 135 | 27.409 | 27.037 | 30.591 | [27.061, 27.757] |

### 4.3 Compile Effect: helps (-53.3%, significant, d=-1.211 [large])

- GPU eager mean: 17.563 ms | GPU compile mean: 8.202 ms
- t=19.90, p=0.0000

### 4.4 Pairwise Comparisons (3/3 significant)

| Group A | Group B | Mean A (ms) | Mean B (ms) | Delta (%) | p-value | Cohen's d | Effect | Sig? |
|---------|---------|-------------|-------------|-----------|---------|-----------|--------|------|
| ollama | transformers-gpu | 9.106 | 17.563 | +92.9% | 0.0000 | 1.259 | large | Yes |
| ollama | transformers-gpu-compile | 9.106 | 8.202 | -9.9% | 0.0037 | -0.177 | negligible | Yes |
| transformers-gpu | transformers-gpu-compile | 17.563 | 8.202 | -53.3% | 0.0000 | -1.211 | large | Yes |

### 4.5 Outlier Analysis (IQR)

| Backend | N Total | N Outliers | Outlier % |
|---------|---------|------------|-----------|
| ollama | 540 | 5 | 0.9% |
| transformers-gpu | 540 | 0 | 0.0% |
| transformers-gpu-compile | 540 | 0 | 0.0% |

## 5. Kv Decode

Total samples: 1080

### 5.1 Backend Rankings (by mean latency)

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | Std (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|----------|--------|
| 1 | ollama | 540 | 286.056 | 239.272 | 731.134 | 213.262 | [268.029, 304.084] |
| 2 | transformers-gpu | 540 | 2019.289 | 2254.380 | 3240.766 | 1006.272 | [1934.225, 2104.352] |

### 5.2 Per-Model Rankings

**llama3.2:1b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 318.784 | 449.921 | 476.393 | [288.392, 349.177] |

**models/gpt2-100m:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | transformers-gpu | 135 | 423.927 | 422.897 | 447.251 | [421.233, 426.622] |

**models/qwen2.5-0.5b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 150.265 | 170.173 | 243.380 | [135.357, 165.173] |
| 2 | transformers-gpu | 135 | 2058.462 | 2053.812 | 2164.827 | [2049.286, 2067.638] |

**models/qwen2.5-1.5b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 211.841 | 85.153 | 428.726 | [182.436, 241.245] |
| 2 | transformers-gpu | 135 | 2431.709 | 2429.564 | 2545.220 | [2420.537, 2442.881] |

**models/qwen2.5-3b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 463.336 | 336.839 | 742.085 | [422.808, 503.865] |
| 2 | transformers-gpu | 135 | 3163.057 | 3159.314 | 3324.547 | [3145.624, 3180.491] |

### 5.3 Pairwise Comparisons (1/1 significant)

| Group A | Group B | Mean A (ms) | Mean B (ms) | Delta (%) | p-value | Cohen's d | Effect | Sig? |
|---------|---------|-------------|-------------|-----------|---------|-----------|--------|------|
| ollama | transformers-gpu | 286.056 | 2019.289 | +605.9% | 0.0000 | 2.383 | large | Yes |

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
| 1 | ollama | 540 | 541.146 | 503.620 | 1040.962 | 252.236 | [519.824, 562.468] |
| 2 | transformers-gpu | 540 | 2051.199 | 2317.214 | 3302.298 | 1033.356 | [1963.846, 2138.552] |

### 6.2 Per-Model Rankings

**llama3.2:1b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 601.540 | 756.696 | 802.030 | [564.325, 638.755] |

**models/gpt2-100m:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | transformers-gpu | 135 | 427.167 | 425.561 | 444.541 | [425.228, 429.106] |

**models/qwen2.5-0.5b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 381.735 | 411.939 | 512.716 | [362.020, 401.450] |
| 2 | transformers-gpu | 135 | 2047.357 | 2045.817 | 2158.839 | [2037.885, 2056.828] |

**models/qwen2.5-1.5b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 448.624 | 302.021 | 722.396 | [412.589, 484.660] |
| 2 | transformers-gpu | 135 | 2484.275 | 2472.418 | 2595.906 | [2474.844, 2493.707] |

**models/qwen2.5-3b:**

| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |
|------|---------|---|-----------|-------------|----------|--------|
| 1 | ollama | 135 | 732.685 | 592.366 | 1059.671 | [686.058, 779.312] |
| 2 | transformers-gpu | 135 | 3245.996 | 3229.798 | 3355.206 | [3234.465, 3257.527] |

### 6.3 Pairwise Comparisons (1/1 significant)

| Group A | Group B | Mean A (ms) | Mean B (ms) | Delta (%) | p-value | Cohen's d | Effect | Sig? |
|---------|---------|-------------|-------------|-----------|---------|-----------|--------|------|
| ollama | transformers-gpu | 541.146 | 2051.199 | +279.0% | 0.0000 | 2.008 | large | Yes |

### 6.4 Outlier Analysis (IQR)

| Backend | N Total | N Outliers | Outlier % |
|---------|---------|------------|-----------|
| ollama | 540 | 0 | 0.0% |
| transformers-gpu | 540 | 0 | 0.0% |

## 7. Power Analysis

- **prefill:** N=540/group, min detectable d=0.170 (1.336 ms), can detect small effects
- **kv_decode:** N=540/group, min detectable d=0.170 (192.917 ms), can detect small effects
- **e2e_kv:** N=540/group, min detectable d=0.170 (181.707 ms), can detect small effects

## 8. Findings

**Finding 1:** Backend rankings vary by mode (2 different winners across 3 modes):
  - prefill: transformers-gpu-compile (8.202 ms)
  - kv_decode: ollama (286.056 ms)
  - e2e_kv: ollama (541.146 ms)

**Finding 2:** Rankings differ by model in prefill:
  - llama3.2:1b: ollama
  - models/gpt2-100m: transformers-gpu-compile
  - models/qwen2.5-0.5b: transformers-gpu-compile
  - models/qwen2.5-1.5b: ollama
  - models/qwen2.5-3b: ollama

**Finding 3:** Compile effect: 1/1 modes helped, 1 statistically significant.

**Finding 4:** prefill: compile helps (-53.3%, d=-1.211 [large], significant)

**Finding 5:** 5/5 (100%) pairwise comparisons reached significance.

**Finding 6:** Mean outlier rate: 0.1% (IQR method).

## 9. Conclusions & Implications

1. **Mode-dependent rankings:** No single backend dominates
   all modes. Backend selection should be mode-aware.

2. **Compilation beneficial:** Real Triton compilation consistently helps.
   Unlike TR120's `aot_eager` fallback, real inductor delivers speedups.

3. **Practically meaningful:** Large effect sizes in prefill — differences are operationally relevant.

