# TR118 Fixed for GPT-2 124M

**Date:** 2025-12-12  
**Status:** Ready for re-run with correct model

---

## What Was Wrong

**Model Mix-Up:**
- **Used:** `sshleifer/tiny-gpt2` (102,714 params = 0.103M, test fixture)
- **Claimed:** "tiny-gpt2 (124M params)"
- **Size:** 0.39MB (FP32) vs expected 474.7MB (1,217x smaller)

**Why Results Were Invalid:**
1. Model is 1,210x smaller than claimed
2. Perplexity = 50,285 (random/untrained weights)
3. All backends show "identical" accuracy (no signal to preserve)
4. Performance dominated by framework overhead, not compute
5. ONNX/TRT artifact sizes impossibly small (1-5MB vs expected 240-475MB)

---

## What Was Fixed

### ✅ Configuration Files (7 files)
- `configs/matrix_postdoc.yaml` → model: `gpt2`, cache: `gpt2_wikitext2_test_512x8x128.calib`
- `configs/baseline.yaml` → model: `gpt2`, cache: `gpt2_wikitext2_test_256x8x128.calib`
- `configs/smoke.yaml` → model: `gpt2`
- `configs/sweep_base.yaml` → model: `gpt2`

### ✅ Python Scripts (3 files)
- `export_to_onnx.py` → example updated to `gpt2`
- `build_trt_engines.py` → all references to `gpt2`
- `generate_report.py` → model reference updated

### ✅ Model Downloaded
```
Model: gpt2 (HuggingFace)
Parameters: 124,439,808 (124.4M) ✅
FP32 size: 474.7 MB ✅
FP16 size: 237.4 MB ✅
Location: ~/.cache/huggingface/hub/models--gpt2
```

### ✅ Report Marked Invalid
- Added **CRITICAL WARNING** at top of TR118 report
- Updated all parameter counts (0.103M actual vs 124.4M claimed)
- Explained all anomalous results (perplexity=50K, identical quantization, etc.)
- Marked conclusions as forensic/invalid

---

## Expected Results Tomorrow

### ONNX Export (~10-15s)
- **File:** `artifacts/onnx/gpt2.onnx`
- **Size:** ~475MB (graph) + possible external data
- **Validation:** Should pass `onnx.checker.check_model()`

### TensorRT Builds (~90s total)
- **FP32:** ~240-475MB, ~20-30s build
- **FP16:** ~120-240MB, ~40-50s build
- **INT8:** ~120-240MB, ~25-35s build + WikiText-2 calibration

### Benchmark (180 runs, ~15-20 min)
- 6 backends × 6 scenarios × 5 reps = 180 samples
- Prefill latency: expect 10-100ms range (not 2-6ms)
- Throughput: expect 100-5000 tok/s (not 5K-15K tok/s)

### Perplexity (~60s)
- **Baseline (PyTorch):** ~30-40 (not 50,285)
- **ONNX Runtime:** ~30-40 (delta < 0.1%)
- **TRT FP32:** ~30-40 (delta < 0.1%)
- **TRT FP16:** ~30-40 (delta < 0.5%)
- **TRT INT8:** ~30-45 (delta < 2.0%, measurable degradation)

### Key Differences
| Metric | Old (0.103M) | New (124.4M) | Change |
|--------|--------------|--------------|--------|
| ONNX size | 1.86MB | ~475MB | 255x |
| TRT FP16 size | 4.2MB | ~240MB | 57x |
| Perplexity | 50,285 | ~35 | Real signal |
| Latency | 2-6ms | 10-100ms | Compute-bound |
| INT8 accuracy | Identical | Degraded | Real quantization |

---

## How to Run Tomorrow

```bash
# Full production run (matrix_postdoc config)
cd scripts/tr118
python run_experiment.py --config configs/matrix_postdoc.yaml --device cuda

# Expected duration: ~20-25 minutes
# - ONNX export: ~15s
# - TRT builds: ~90s
# - Benchmarks: ~15-18 min (180 runs)
# - Perplexity: ~60s
# - Analysis: ~5s
```

**Output:**
- Raw results: `results/raw/bench_prefill_<ts>.jsonl`
- Processed: `results/processed/latency_summary.csv`
- Perplexity: `results/processed/perplexity_results.json`
- Report: `../../reports/generated/Technical_Report_118.md` (auto-generated)

**What to watch for:**
1. ✅ ONNX export size ~475MB (not 1.86MB)
2. ✅ TRT FP16 size ~240MB (not 4.2MB)
3. ✅ Perplexity ~30-40 (not 50,285)
4. ✅ INT8 perplexity slightly worse than FP16 (not identical)
5. ✅ Latencies 10-100ms range (not 2-6ms)

---

## Sanity Checks After Run

```bash
# 1. Check ONNX size
ls -lh artifacts/onnx/gpt2.onnx
# Should be ~475MB, not 1.86MB

# 2. Check TRT engine sizes
ls -lh artifacts/tensorrt/*.plan
# Should be 120-475MB each, not 4-5MB

# 3. Check perplexity
cat results/processed/perplexity_results.json | grep perplexity
# Should be ~30-40, not 50,285

# 4. Check INT8 accuracy
# INT8 perplexity should be slightly higher than FP16 (measurable degradation)
```

---

## Files Changed

**Configs:**
- `scripts/tr118/configs/matrix_postdoc.yaml`
- `scripts/tr118/configs/baseline.yaml`
- `scripts/tr118/configs/smoke.yaml`
- `scripts/tr118/configs/sweep_base.yaml`

**Scripts:**
- `scripts/tr118/export_to_onnx.py`
- `scripts/tr118/build_trt_engines.py`
- `scripts/tr118/generate_report.py`

**Reports:**
- `reports/generated/Technical_Report_118.md` (marked invalid, ready for rewrite)

---

## Commit Message (After Successful Run)

```
fix(tr118): Use correct GPT-2 124M model instead of 0.103M test fixture

Previous TR118 data accidentally used sshleifer/tiny-gpt2 (0.103M params,
test fixture) instead of gpt2 (124.4M params, production model).

Changes:
- All configs now point to "gpt2" (124.4M params)
- INT8 calibration cache paths updated
- Model downloaded and cached locally
- Previous report marked INVALID with forensic preservation

Expected artifact sizes with correct model:
- ONNX: ~475MB (was 1.86MB)
- TRT FP16: ~240MB (was 4.2MB)
- Perplexity: ~35 (was 50,285)

Ready for proper TR118 run.
```

---

**Status:** ✅ All code fixed, model downloaded, ready for re-run tomorrow.

