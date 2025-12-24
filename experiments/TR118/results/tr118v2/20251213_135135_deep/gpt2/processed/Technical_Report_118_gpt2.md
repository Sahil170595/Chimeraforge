# Technical Report 118: ONNX Runtime + TensorRT Deep Dive


**Version:** 1.0
**Date:** 2025-12-13
**Status:** Draft (auto-generated from artifacts)
**Git SHA:** `f73684a2d4d8a87c52032f18dcff57dc3c9584f6`

## Abstract

TR118 deep-dives ONNX Runtime and TensorRT for local-first LLM inference, closing the TR117 gap where ONNX/TRT runs were fully degraded.
We report performance, degraded-rate, and accuracy (perplexity) gates, using artifact-driven reproducibility (JSONL + CSV + manifests).

## Executive Summary

### Key Findings

- Reliability: 360 run-level records across prefill, generate; degraded-rate = 27.8% (100/360)
- Accuracy: perplexity gate not fully satisfied (see `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2\20251213_135135_deep\gpt2\processed\perplexity_results.csv`)
- prefill: best mean latency = tensorrt-fp16 (4.13 ms), vs baseline transformers-gpu-compile (19 ms, -78.27%)
- generate: best mean latency = onnxruntime-gpu (37.2 ms), vs baseline transformers-gpu-compile (101 ms, -63.05%)
- Note: PyTorch `transformers-gpu-compile` uses `torch.compile(..., backend="cudagraphs", dynamic=False)` on Windows (no Triton).

### Honest Limitations

- `generate` mode is an uncached greedy loop (`use_cache=False`) and is not representative of KV-cached decoding throughput.
- `models/tiny-gpt2` in this repo is a toy/untrained model; perplexity is expected to be near-uniform (~vocab) and accuracy deltas mainly reflect numerical consistency.
- Single model (gpt2/124M) and single machine; results may not generalize to larger models (see TR121).
- Latency excludes end-to-end serving overhead (tokenization, networking, batching policies).

## Introduction

- TR117 established a cross-backend baseline and identified ONNX/TRT infrastructure failures.
- TR118 focuses on making ONNX export + TRT engine builds real and measurable, with explicit degraded reasons and accuracy gates.

## Methodology

### Metrics
- Latency (ms), throughput (tok/s), degraded rate.
- Generation mode (if enabled) uses an uncached greedy loop (repeated full forward passes).

### Accuracy Gate
- Perplexity on WikiText-2 vs PyTorch baseline with per-precision thresholds.

### Statistical Analysis
- 95% confidence intervals + t-tests + Cohen's d via TR117 helpers.

## Experimental Design

- Config: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2\20251213_135135_deep\gpt2\processed\config_generated_tr118v2_gpt2.yaml`
- Prompt config: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr117\configs\matrix_tier3.yaml`
- Modes: prefill, generate
- Backends: transformers-gpu-compile, onnxruntime-cpu, onnxruntime-gpu, tensorrt-fp32, tensorrt-fp16, tensorrt-int8
- Scenarios: single_micro, single_short, single_medium, single_long, batch_short, batch_medium
- Repetitions: 5

**Artifacts root:** `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2\20251213_135135_deep\gpt2`

### Run Manifest

- Manifest: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2\20251213_135135_deep\gpt2\processed\experiment_manifest_1765652089.json`
- Duration (s): 481.27777218818665

## Environment

- OS: Windows-11-10.0.26200-SP0
- Python: 3.13.1 (tags/v3.13.1:0671451, Dec  3 2024, 19:06:28) [MSC v.1942 64 bit (AMD64)]
- GPU: NVIDIA GeForce RTX 4080 Laptop GPU (12282 MB, CC 8.9)
- ONNXRuntime providers: TensorrtExecutionProvider, CUDAExecutionProvider, CPUExecutionProvider
- Key packages: torch=2.8.0+cu128, transformers=4.57.0, onnxruntime=1.23.2, tensorrt=10.12.0.36

## Sanity Checks

### Model / ONNX Artifacts

| Field | Value |
| --- | --- |
| model | gpt2 |
| onnx_path | C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\artifacts\tr118v2\gpt2\onnx\gpt2.onnx |
| onnx_sha256 | N/A |
| onnx_file_size_mb | 622.4 |
| external_data | False |
| external_total_mb | 0 |
| total_artifact_mb | 622.4 |
| initializer_numel_est | 163037184 |
| initializer_bytes_est_mb | 621.9 |
| weight_files_total_mb | N/A |

### TensorRT Engine Inspection

| Precision | Plan_MB | Layers | InspectorType | INT8_in_JSON | INT8_tensors | OutputDTypes | CalibSource | CalibCacheHit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fp32 | 778.7 | 901 | dict | False | False | Float=780, Int64=248 | N/A | N/A |
| fp16 | 312.4 | 137 | dict | False | False | Float=1, Half=112, Int64=48 | N/A | N/A |
| int8 | 781 | 1025 | dict | False | False | Float=930, Int64=249 | dataset | False |

### Perplexity Correctness

| Field | Value |
| --- | --- |
| baseline_ppl | 58.34 |
| baseline_mean_nll | 4.066 |
| baseline_token_count | 72531 |
| ln_vocab | 10.82 |
| expected_uniform_ppl | 5.026e+04 |
| ref_loss_mean_nll | 4.138 |
| ref_loss_ppl | 62.7 |

### Logit Diffs vs PyTorch (Last Token)

| Backend | mean_abs | max_abs | providers_used | error |
| --- | --- | --- | --- | --- |
| onnxruntime-cpu | 4.125e-05 | 0.0002136 | ['CPUExecutionProvider'] | N/A |
| onnxruntime-gpu | 0.02025 | 0.05012 | ['CUDAExecutionProvider', 'CPUExecutionProvider'] | N/A |
| tensorrt-fp32 | 0.02825 | 0.05691 | N/A | N/A |
| tensorrt-fp16 | N/A | N/A | N/A | RuntimeError: set_input_shape_failed:input_ids:1x128 |
| tensorrt-int8 | 0.006077 | 0.03185 | N/A | N/A |

### Sanity Warnings

- TensorRT INT8 engine inspector does not report INT8 coverage; treat INT8 claims as unverified (likely FP16/FP32 fallback).

## Results

### Mode: `prefill`

#### Overall Backend Summary (Run-Level)

| Backend | n_ok | n_total | degraded_rate | lat_mean_ms | lat_ci95 | thr_mean_tok_s | thr_ci95 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| tensorrt-fp16 | 20 | 30 | 0.3333 | 4.13 | [3.416, 4.845] | 3851 | [3464, 4238] |
| tensorrt-int8 | 30 | 30 | 0 | 4.624 | [3.535, 5.714] | 6284 | [5667, 6902] |
| tensorrt-fp32 | 30 | 30 | 0 | 5.866 | [4.842, 6.891] | 4711 | [4006, 5417] |
| onnxruntime-gpu | 30 | 30 | 0 | 10.37 | [6.505, 14.23] | 3927 | [3222, 4631] |
| onnxruntime-cpu | 30 | 30 | 0 | 18.83 | [16.11, 21.54] | 1434 | [1211, 1656] |
| transformers-gpu-compile | 30 | 30 | 0 | 19.01 | [11.59, 26.42] | 2121 | [1520, 2722] |

#### Resource Summary (Run-Level)

| Backend | n_ok | gpu_power_mean_w | gpu_mem_peak_mb | gpu_temp_peak_c | cpu_mem_peak_mb |
| --- | --- | --- | --- | --- | --- |
| onnxruntime-cpu | 30 | 13.89 | 5507 | 43 | 3050 |
| onnxruntime-gpu | 30 | 23.63 | 5517 | 44.07 | 3210 |
| tensorrt-fp16 | 20 | 16.08 | 6829 | 43 | 3278 |
| tensorrt-fp32 | 30 | 16.83 | 6530 | 43 | 3277 |
| tensorrt-int8 | 30 | 23.04 | 7806 | 42.9 | 3291 |
| transformers-gpu-compile | 30 | 14.31 | 4203 | 43 | 3176 |

- Summary CSV: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2\20251213_135135_deep\gpt2\processed\latency_summary_prefill.csv`

#### Baseline Comparisons (Overall)

| baseline | candidate | metric | mean_a | mean_b | pct_change | p_value | cohens_d | significant |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| transformers-gpu-compile | onnxruntime-cpu | latency_ms | 19.01 | 18.83 | -0.9392 | 0.9633 | -0.01194 | False |
| transformers-gpu-compile | onnxruntime-gpu | latency_ms | 19.01 | 10.37 | -45.46 | 0.03887 | -0.5457 | True |
| transformers-gpu-compile | tensorrt-fp16 | latency_ms | 19.01 | 4.13 | -78.27 | 0.001667 | -0.9618 | True |
| transformers-gpu-compile | tensorrt-fp32 | latency_ms | 19.01 | 5.866 | -69.13 | 0.0006814 | -0.9269 | True |
| transformers-gpu-compile | tensorrt-int8 | latency_ms | 19.01 | 4.624 | -75.67 | 0.0002331 | -1.013 | True |

#### Figures

![mean_latency_prefill](../plots/mean_latency_prefill.png)

![mean_throughput_tok_s_prefill](../plots/mean_throughput_tok_s_prefill.png)

![degraded_rate_prefill](../plots/degraded_rate_prefill.png)


### Mode: `generate`

#### Overall Backend Summary (Run-Level)

| Backend | n_ok | n_total | degraded_rate | lat_mean_ms | lat_ci95 | thr_mean_tok_s | thr_ci95 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| onnxruntime-gpu | 30 | 30 | 0 | 37.19 | [31.65, 42.73] | 438.3 | [334.2, 542.5] |
| transformers-gpu-compile | 30 | 30 | 0 | 100.6 | [90.7, 110.6] | 156.8 | [123.2, 190.5] |
| onnxruntime-cpu | 30 | 30 | 0 | 189.9 | [156.8, 223] | 76.87 | [67.92, 85.83] |
| tensorrt-fp16 | 0 | 30 | 1 | N/A | N/A | N/A | N/A |
| tensorrt-fp32 | 0 | 30 | 1 | N/A | N/A | N/A | N/A |
| tensorrt-int8 | 0 | 30 | 1 | N/A | N/A | N/A | N/A |

#### TTFT Summary (Run-Level)

| Backend | n_ok | ttft_mean_ms | ttft_ci95 | ttft_median_ms |
| --- | --- | --- | --- | --- |
| onnxruntime-gpu | 30 | 5.083 | [3.528, 6.638] | 3.982 |
| transformers-gpu-compile | 30 | 12.69 | [11.29, 14.09] | 13.21 |
| onnxruntime-cpu | 30 | 23.52 | [19.4, 27.63] | 17.77 |

#### Resource Summary (Run-Level)

| Backend | n_ok | gpu_power_mean_w | gpu_mem_peak_mb | gpu_temp_peak_c | cpu_mem_peak_mb |
| --- | --- | --- | --- | --- | --- |
| onnxruntime-cpu | 30 | 12.23 | 5822 | 44.47 | 2117 |
| onnxruntime-gpu | 30 | 46.76 | 5832 | 50.27 | 2332 |
| transformers-gpu-compile | 30 | 29.38 | 4520 | 44.93 | 2097 |

- Summary CSV: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2\20251213_135135_deep\gpt2\processed\latency_summary_generate.csv`

#### Baseline Comparisons (Overall)

| baseline | candidate | metric | mean_a | mean_b | pct_change | p_value | cohens_d | significant |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| transformers-gpu-compile | onnxruntime-cpu | latency_ms | 100.6 | 189.9 | 88.69 | 2.037e-06 | 1.363 | True |
| transformers-gpu-compile | onnxruntime-gpu | latency_ms | 100.6 | 37.19 | -63.05 | 1.886e-16 | -2.945 | True |

#### Figures

![mean_latency_generate](../plots/mean_latency_generate.png)

![mean_throughput_tok_s_generate](../plots/mean_throughput_tok_s_generate.png)

![degraded_rate_generate](../plots/degraded_rate_generate.png)

### Accuracy (Perplexity Gate)

- Results CSV: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2\20251213_135135_deep\gpt2\processed\perplexity_results.csv`
- Diagnostics JSON: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2\20251213_135135_deep\gpt2\processed\perplexity_results.json`

| Backend | PPL | delta_frac | Threshold | Pass | Error |
| --- | --- | --- | --- | --- | --- |
| transformers-gpu-compile | 58.34 | 0 | nan | True | nan |
| onnxruntime-cpu | 58.34 | -1.354e-05 | 0.001 | True | nan |
| onnxruntime-gpu | 58.35 | 0.0001874 | 0.001 | True | nan |
| tensorrt-fp32 | 58.35 | 3.047e-05 | 0.001 | True | nan |
| tensorrt-fp16 | nan | nan | nan | False | set_input_shape_failed:input_ids:4x128 |
| tensorrt-int8 | 58.34 | 1.494e-05 | 0.02 | True | nan |

### Export Overhead (ONNX)

| Field | Value |
| --- | --- |
| onnx_path | C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\artifacts\tr118v2\gpt2\onnx\gpt2.onnx |
| export_time_s | N/A |
| file_size_mb | 622.4 |
| opset_version | 17 |
| dynamic_axes | True |
| trt_friendly_inputs | True |
| reused | True |
| valid | N/A |
| onnx_sha256 | N/A |

### TensorRT Build Overhead

- Build metadata: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2\20251213_135135_deep\gpt2\processed\trt_build_metadata_1765652089.json`

| Precision | Plan | Built | Reused | Build s | Size MB | Dynamic | Profiles | Error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fp32 | gpt2_fp32.plan | True | False | 66.8 | 778.7 | True | 5 | N/A |
| fp16 | gpt2_fp16.plan | False | True | N/A | 312.4 | True | 5 | N/A |
| int8 | gpt2_int8.plan | True | False | 153 | 781 | True | 5 | N/A |

## Discussion

### Interpretation
- This run demonstrates that ONNX export + TensorRT engine builds can be made reliable on a single Windows + CUDA workstation.
- For this tiny model and short prompts, ORT-CPU can win on latency due to reduced GPU launch/dispatch overhead; larger models should re-test (TR121).
- TensorRT build cost is non-trivial; treat it as an offline step that must be amortized for production value.

### Limitations / Threats to Validity
- See `Executive Summary: Honest Limitations` for the primary caveats.

## Conclusions

TR118 provides an artifact-driven pipeline for measuring ONNX Runtime and TensorRT locally, including degraded-rate accounting, build/export metadata, and perplexity gates.

## Recommendations

- If you need portability/simplicity: start with ONNX Runtime (CPU or CUDA EP).
- If you can prebuild engines and need maximum GPU throughput: TensorRT (FP16/INT8 as permitted by accuracy gates).
- Keep PyTorch as the reference baseline; on Windows prefer `torch.compile(..., backend="cudagraphs", dynamic=False)` for stability.

## Reproducibility

Run the full pipeline:

```bash
python scripts/tr118/run_experiment.py --config C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2\20251213_135135_deep\gpt2\processed\config_generated_tr118v2_gpt2.yaml --device cuda
```

Generate this report from artifacts:

```bash
python scripts/tr118/generate_report.py --config C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2\20251213_135135_deep\gpt2\processed\config_generated_tr118v2_gpt2.yaml --manifest C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2\20251213_135135_deep\gpt2\processed\experiment_manifest_1765652089.json
```

## Appendix

- Artifacts root: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2\20251213_135135_deep\gpt2`
- Processed dir: `C:\Users\sahil\OneDrive\Documents\GitHub\Banterhearts\scripts\tr118\results\tr118v2\20251213_135135_deep\gpt2\processed`
