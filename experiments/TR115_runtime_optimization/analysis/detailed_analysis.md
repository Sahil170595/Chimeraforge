# TR115 Detailed Analysis

## Per-Runtime Analysis

### tokio-default

**Peak Efficiency**: 99.9% (chimera_homo_gpu100_ctx512 / run_1)
**Mean Efficiency**: 98.7% ± 1.2pp (30 runs)
**Peak Speedup**: 1.998x
**Mean Speedup**: 1.974x ± 0.024x
**Efficiency Range**: 94.8% - 99.9%

**Top 3 Configurations**:

1. chimera_homo_gpu100_ctx512 / run_1 -- 99.888% (1.998x)
2. baseline_vs_chimera_gpu80_ctx512 / run_3 -- 99.876% (1.998x)
3. chimera_homo_gpu80_ctx2048 / run_4 -- 99.850% (1.997x)

### tokio-localset

**Peak Efficiency**: 99.99% (chimera_hetero_gpu80-100_ctx512-1024 / run_4)
**Mean Efficiency**: 97.9% ± 4.0pp
**Peak Speedup**: 2.000x
**Mean Speedup**: 1.959x ± 0.079x
**Efficiency Range**: 81.0% - 99.99%

**Top 3 Configurations**:

1. chimera_hetero_gpu80-100_ctx512-1024 / run_4 -- 99.990% (2.000x)
2. chimera_homo_gpu100_ctx512 / run_3 -- 99.982% (2.000x)
3. chimera_homo_gpu80_ctx1024 / run_1 -- 99.948% (1.999x)

### async-std

**Peak Efficiency**: 50.0% (chimera_homo_gpu100_ctx512 / run_1)
**Mean Efficiency**: 50.0% ± 0.0pp
**Peak Speedup**: 1.000x
**Mean Speedup**: 1.000x ± 0.00003x
**Efficiency Range**: 49.99% - 50.00%

**Top 3 Configurations**:

1. chimera_homo_gpu100_ctx512 / run_1 -- 49.999% (1.000x)
2. chimera_homo_gpu100_ctx512 / run_4 -- 49.999% (1.000x)
3. chimera_homo_gpu100_ctx512 / run_3 -- 49.999% (1.000x)

### smol

**Peak Efficiency**: 99.87% (baseline_vs_chimera_gpu80_ctx512 / run_1)
**Mean Efficiency**: 97.7% ± 4.8pp
**Peak Speedup**: 1.997x
**Mean Speedup**: 1.954x ± 0.096x
**Efficiency Range**: 72.8% - 99.9%

**Top 3 Configurations**:

1. baseline_vs_chimera_gpu80_ctx512 / run_1 -- 99.867% (1.997x)
2. chimera_homo_gpu80_ctx2048 / run_4 -- 99.794% (1.996x)
3. chimera_hetero_gpu80-100_ctx512-1024 / run_1 -- 99.689% (1.994x)

### smol-1kb

**Peak Efficiency**: 99.94% (baseline_vs_chimera_gpu80_ctx512 / run_2)
**Mean Efficiency**: 98.6% ± 1.3pp
**Peak Speedup**: 1.999x
**Mean Speedup**: 1.972x ± 0.026x
**Efficiency Range**: 94.98% - 99.94%

**Top 3 Configurations**:

1. baseline_vs_chimera_gpu80_ctx512 / run_2 -- 99.940% (1.999x)
2. chimera_homo_gpu80_ctx1024 / run_3 -- 99.921% (1.998x)
3. chimera_homo_gpu80_ctx1024 / run_2 -- 99.896% (1.998x)
