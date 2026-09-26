# Technical Report 147: The Third-Party Validation Audit
## How wrong the planner's first-principles predictions are, graded against published benchmarks

| Field | Value |
|-------|-------|
| **TR Number** | 147 |
| **Project** | ChimeraForge |
| **Date** | 2026-09-25 |
| **Version** | 1.0 |
| **Status** | Complete |
| **Pre-registration commit** | `ac1a3d3` (matrices, bands and source list committed before the audit first ran) |
| **Combined fingerprint** | `1db6b1fe4827d5aa` (per-GPU fingerprints in `corpora/SCORECARD.md`) |
| **Raw data** | `corpora/` -- matrices, sourced measurements, exclusions, per-GPU audits, `scorecard.json` |
| **Regenerate** | `python scripts/build_validation_corpus.py --write --audit` |
| **Evidence class** | `third-party-measured` only (no own-rig cells in this edition) |

---

## Abstract

`chimeraforge validate` shipped in 0.22.0 and had never been run against a real measurement. This report runs it. Ground truth is 103 cells read from 8 published third-party benchmark sources, of which 42 survive seven pre-registered inclusion rules and become audit cells on 17 GPUs. Every prediction scored here is a **roofline estimate**. No audited model is in the planner's measured corpus, so this tests the first-principles path, which is the one making an out-of-sample claim.

On the 15 fully specified decode cells, the planner is inside a +-25% band **13%** of the time, with a median absolute error of **35.9%** and a GMFE of **1.63x**. The headline bias (-26.8%) averages two populations whose errors have **opposite signs**, which makes it misleading on its own:

- **On HBM datacenter parts, decode is over-predicted by a median of +57.8%.** The planner is optimistic, up to +206% on a B200.
- **On GDDR consumer cards, decode is under-predicted by a median of -35.9%.** The planner is pessimistic.

TTFT, derived from prefill throughput, shows the same split with the signs reversed: +148% on GDDR (predicted slower), -66% on HBM (predicted faster).

The operational conclusion is that a roofline decode estimate on an HBM part should be read as an upper bound, not an expectation. This report publishes the errors; it does not change the model.

---

## 1. Method

### 1.1 Sources, enumerated before extraction

Sources were listed before any value was read, and every source consulted is published, including those that yielded nothing and why (`scripts/validation_sources.json`, repeated in every matrix so it is fingerprinted). Eight sources were used:

- llama.cpp's CUDA, ROCm and Vulkan performance scoreboards (GitHub discussions 15013, 15021, 10879);
- XiongjieDai/GPU-Benchmarks-on-LLM-Inference at a fixed commit;
- Argonne's LLM-Inference-Bench raw CSV at a fixed commit;
- an SGLang maintainer's `bench_latency` results (sgl-project/sglang#1008);
- AMD's ROCm performance-results page;
- DatabaseMart's Ollama benchmark pages.

Eleven more were consulted and not used, each with its reason. They include LocalScore (each figure averages eight different test shapes), the vLLM HUD (HTTP 403), and NVIDIA's NIM page (it does not name the engine behind its figures).

Every cell carries its URL (a permalink to the comment, or a file at a commit), a verbatim quote, and a capture date. The quotes were checked by script against the fetched artifacts. Three were re-checked independently against the live source before commit: an XiongjieDai README row, the SGLang issue body, and an Argonne CSV row. All three matched exactly. No source authored by this project is used; the loader refuses one.

### 1.2 Inclusion rules

These were fixed before any error was computed, applied by code, and every exclusion is published with its rule (`corpora/exclusions.json`, 36 cells).

| Rule | Excludes | Cells |
|---|---|---|
| 1 | More than one GPU (the audit predicts tensor-parallel 1) | 3 |
| 2 | Batch other than 1 | 3 |
| 3 | No stated metric definition | 5 |
| 4 | GPU variant differs from the planner entry (PCIe cells against SXM entries) | 16 |
| 5 | Vulkan backend (the planner's GGUF path is CUDA/ROCm llama.cpp) | 4 |
| 6 | Non-default engine configuration (SGLang torch.compile) | 1 |
| 7 | Superseded duplicate of a better-specified or more recent source | 4 |

Rule 4 is the largest, and the reason is concrete. The planner's H100 80GB entry is the SXM part at 3352 GB/s, and a PCIe H100 has substantially less. Scoring a PCIe measurement against it would have charged the planner for a bandwidth error that belongs to the matching, not the model.

### 1.3 Metric definitions

Every measured number states which quantity it is, and only planner-comparable quantities are scored:

- llama-bench `tg` is batch-1 decode with no prompt in context, scored against the planner's single-stream decode rate.
- llama-bench `pp512` is prefill throughput. It becomes TTFT at the cell's own 512-token prompt (`512 / pp512`). A prefill figure measured at any other length is refused, not converted.
- Argonne's vLLM rows are single-request end-to-end latency. They are scored against the planner's own service time, `ttft + output_tokens / decode_rate`.

### 1.4 Bands

The bands were registered with the matrices: throughput +-25%, TTFT +-50%, end-to-end latency +-25%. They are set from the corpus's own spread. One author's H100 SXM5 decode moved +13% between two llama.cpp builds, and flash attention moves decode 0-10%, so a band much tighter than that would fail a perfect model.

### 1.5 Underspecified cells

A source that omits its engine build or serving flags is marked `underspecified`. Its cells are published with their errors and kept out of every headline row. That covers 26 of the 42 cells. The whole XiongjieDai README (no llama.cpp commit) and the whole Argonne CSV (no vLLM version) fall here.

---

## 2. Results

All figures are from `corpora/scorecard.json` and `corpora/SCORECARD.md`, which lists every scored cell, worst first.

### 2.1 Headline: fully specified third-party cells, roofline estimates

| Metric | n | In-band | Median abs | GMFE | Bias (median signed) | Worst |
|---|---|---|---|---|---|---|
| Decode throughput | 15 | 13% | 35.9% | 1.63x | -26.8% | +206.3% (B200) |
| TTFT | 14 | 14% | 135.4% | 2.68x | +135.4% | +183.9% (RTX 3080) |

The sign convention differs by metric. A positive error on a rate means optimistic; a positive error on a latency means the planner predicted it slower than measured.

### 2.2 The split that the headline hides

| Memory | Metric | n | In-band | Median abs | GMFE | Bias |
|---|---|---|---|---|---|---|
| HBM | Decode | 6 | 17% | 57.8% | 1.77x | **+57.8%** |
| HBM | TTFT | 5 | 20% | 65.5% | 3.21x | -65.5% |
| GDDR | Decode | 9 | 11% | 35.9% | 1.54x | **-35.9%** |
| GDDR | TTFT | 9 | 11% | 148.3% | 2.43x | +148.3% |

**HBM decode.** llama.cpp's measured batch-1 decode for Llama 2 7B Q4_0 falls between 200 and 308 tok/s on every HBM part audited: A100 80GB 200.1, MI300X 232.9, H100 303.1, B200 297.7, H200 307.8. Across those parts the planner's roofline predicts 242 to 912 tok/s, because it scales linearly with memory bandwidth. The measured figures do not scale: a B200 has roughly 2.3x an H100's bandwidth and decodes at about the same rate. A bandwidth-only roofline cannot represent a ceiling that is not set by bandwidth. This report does not diagnose what sets it; candidates include per-token kernel launch and host overheads, which a bandwidth model omits by construction, but that is a hypothesis this audit does not test. The one fully specified non-llama.cpp HBM cell, SGLang on H100 for Llama 3 8B FP16, is also optimistic, at +29%.

**GDDR decode.** On consumer cards the same roofline is too **low** by 18-47%. The planner's roofline takes a single memory-bandwidth-utilisation constant (`MBU_DEFAULT = 0.65`) calibrated on one datapoint from the reference laptop GPU. These results are consistent with desktop GDDR cards sustaining a higher fraction than that under llama.cpp, but the audit measures the error, not its cause.

**TTFT.** Prefill is modelled as compute at a single MFU constant, bounded below by the weight-read time. On fully specified GDDR cards the prediction is 2.3x to 2.8x slower than llama-bench's `pp512` implies; on HBM parts it is 1.8x to 6.3x faster. The one GDDR exception is a T4 at -36.8%, which its author noted may read low because it was run on Kaggle.

### 2.3 Underspecified evidence (published, not in the headline)

- **vLLM single-request end-to-end latency** (Argonne; 14 cells on A100 40GB, H100 and MI300X): every cell is predicted faster than measured, from -12.9% to -78.5%, median -31.4% over the 14 cells listed in `SCORECARD.md`. The MI300X 8B cells are the worst, and the source's own MI300X series is erratic across lengths, which the extraction notes record.
- **XiongjieDai llama.cpp cells** repeat the headline's direction: under-predicted on GDDR, over-predicted on A100 80GB. One cell is the exception: Llama 3 70B Q4_K_M on an A100 80GB is within 6.1%.

### 2.4 What was refused and skipped

One cell is skipped, and the skip is itself a finding. Llama 3 8B F16 on an RTX 4080 16GB is refused by the planner's VRAM gate (16.7 GB needed against 16 GB), yet the source ran it and reports 40.58 tok/s. The source does not say whether layers were offloaded to the CPU. That is plausible for a model that exceeds the card, and it is why the cell is recorded rather than scored.

---

## 3. Limits of this evidence

- **Engine coverage is narrow.** 27 of 42 audit cells are llama.cpp. The HBM finding is therefore mostly a finding about llama.cpp on HBM parts. Datacenter engines are thinly represented: one SGLang cell, plus 14 underspecified vLLM cells.
- **llama-bench is not Ollama.** It measures llama.cpp directly, without Ollama's HTTP and scheduling layer, and its decode test has no prompt in context.
- **No own-rig cells.** This edition grades the planner only against other people's hardware, drivers and builds. An own-rig class is designed in and reported separately when it exists.
- **Small n.** 15 and 14 fully specified cells are enough to see a sign split of this size, not to fit a correction to it. No correction is fitted here.

---

## 4. Reproduction

- `python scripts/build_validation_corpus.py --check` confirms that the committed corpus is exactly the builder's output from the extraction record.
- `python scripts/build_validation_corpus.py --audit` re-runs the audit offline against the bundled planner corpus.
- `tests/test_validation_corpus.py` checks that the published scorecard re-derives from the committed per-GPU audit JSON alone, with no planner, network or GPU, and that it is current against today's planner.
- `tests/test_accuracy.py::TestThirdPartyAuditDoesNotWiden` pins the headline error bands, so a change that widens them fails.
