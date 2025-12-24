# Technical Report 120: The "Compile Paradox" (Root-Cause Audit)
## Why a "-compile" backend can win the mean while losing the median (and what is actually happening)

**Project:** Banterhearts LLM Performance Research  
**Date:** 2025-12-21  
**Author:** Research Team  
**Report Type:** Artifact-backed root-cause audit + controlled reproduction  
**Primary Data Sources:** TR117 Tier-3 `results/tr117_tier3/metrics.csv` + TR120 controlled runner artifacts  
**Related Work:** [TR117](Technical_Report_117.md) (baseline benchmark + paradox discovery), [TR118_v2.2](Technical_Report_118_v2.2.md) (measurement rigor), [TR119v1](Technical_Report_119v1.md) (token economics)

---

## Executive Summary

TR117 surfaced an apparent contradiction:

> The "-compile" backend looks better on mean latency, while the non-compile backend looks better on median latency.

This report makes the situation definitive.

Claim status (to prevent misreads):

| Claim | Evidence base | Status |
| --- | --- | --- |
| TR117 `transformers-gpu-compile` is a torch.compile claim | TR117 tier3 artifacts + repo code audit | **Not compiler-real** (label-only; no `torch.compile()` call path) |
| Compilation can create p50 wins + heavy tails under shape churn | TR120 controlled runner (Inductor+Triton) | **Compiler-real** (artifact-backed) |
| "Compile helps decode" generalizes to KV-cached serving | TR120 controlled runner | **Not supported here** (compiled KV decode regresses in this run set) |

### Publish-grade conclusions

1. **TR117's "compile paradox" is real in the artifacts, but misattributed.** In this repo, `transformers-gpu-compile` does not call `torch.compile()`, so TR117's label-level distribution difference is not compiler evidence.
2. **When `torch.compile(backend="inductor")` is actually enabled (Inductor+Triton), prefill becomes extremely fast at p50 but can develop a very heavy tail.** The tail corresponds to compilation churn driven by shape instability (variable prompt lengths).
3. **A padding/bucketing fix collapses the compiled tail.** When prompts are padded to stable shapes within scenarios (attention-masked), compiled prefill p99 drops from multi-millisecond to sub-millisecond and the compiled distribution becomes tightly bounded.
4. **KV-cached decode is a different regime.** Even with stable prefill shapes, KV-cached decode introduces inherent shape growth (the KV cache length increases each token). In this run set, Inductor improves prefill but regresses KV decode, making end-to-end worse unless you split modes or adopt a shape-polymorphic strategy.

### What to ship (production)

If you want to ship compile safely:

1. **Do not rely on backend labels.** Wire compilation explicitly and record compile metadata.
2. **Treat prefill and decode as separate optimization targets.** In this run set, compiling prefill is strongly beneficial, while compiling KV-cached decode is not.
3. **Stabilize shapes** (padding/bucketing) or use a dynamic strategy designed for shape polymorphism; otherwise compilation churn will create tails.
4. **Gate compile availability** on Triton (Windows/Python combos can advertise `torch.compile` but cannot run Inductor on GPU).

### Artifacts referenced in this report

TR120 includes a controlled runner that makes compilation explicit and observable:

- Runner: `scripts/tr120/run_root_cause.py`
- Inductor+Triton artifact set (Docker): `scripts/tr120/results/tr120_root_cause_triton/20251221_173112`
- Inductor+Triton (padded shapes + KV decode; cudagraph trees disabled): `scripts/tr120/results/tr120_root_cause_triton/20251221_182658`
- Inductor+Triton (prefill-only; CUDA-event timing + compiler evidence): `scripts/tr120/results/tr120_root_cause_triton/20251221_191009`
- Windows-host fallback artifact set (no Triton): `scripts/tr120/results/tr120_root_cause/20251221_113136`

Environment behavior summary:

- On the Windows host (Python 3.13): Inductor GPU compile fails (Triton missing) and the runner falls back to `aot_eager` (explicitly recorded).
- In Triton Docker (Linux): Inductor runs successfully; tail behavior depends on shape stability.

### Root cause (definitive)

The "compile paradox" as stated in TR117 is a **misattribution**:

- It is a real distributional artifact in the TR117 dataset,
- but it is **not caused by torch.compile** in this codebase, because torch.compile was not invoked for that backend label.
- The paradox is real as a *distributional observation*, but TR117 cannot be used to infer compiler causality.
- The mean/median flip is explained by a cold-start skew: extreme outliers appear as the first sample in some TR117
  `latencies_ms` arrays under `transformers-gpu`; dropping the first sample per run-file removes the mean advantage
  of the `*-compile` label (Section 4.4).

Separately, the controlled TR120 runner shows why a naive "enable compile" strategy is unsafe unless you control shapes:

- on Windows host: the default GPU compiler backend is not supported (missing Triton).
- in Inductor+Triton: variable input lengths trigger repeated recompilations (and can hit the default `recompile_limit`), which is an explicit mechanism for distribution shifts and median/tail anomalies.

### Production decision (what to ship)

- Do not ship a "-compile" backend as a default unless you can prove it actually compiles and the compiler backend is supported on your runtime.
- This repo now gates "compile backends" on Triton availability (see `banterhearts/runtime/capabilities.py`).

---

## Table of Contents

1. [Context](#1-context)
2. [Datasets & Semantics](#2-datasets--semantics)
3. [Backend Label Audit (TR117)](#3-backend-label-audit-tr117)
4. [TR117 Results (Label-Only Distribution)](#4-tr117-results-label-only-distribution)
5. [TR120 Controlled Reproduction (Explicit Compile Attempt)](#5-tr120-controlled-reproduction-explicit-compile-attempt)
6. [Interpretation (What Could Cause TR117's Shape)](#6-interpretation-what-could-cause-tr117s-shape)
7. [Production Guidance](#7-production-guidance)
8. [TR120.B: KV-Cached Decode (Subtask)](#8-tr120b-kv-cached-decode-subtask)
9. [Limitations & Next Steps](#9-limitations--next-steps)
10. [Reproducibility & Artifacts](#10-reproducibility--artifacts)
11. [Appendix A: Key Tables](#appendix-a-key-tables)
12. [Appendix B: Figures](#appendix-b-figures)
13. [Appendix C: Configs](#appendix-c-configs-source-of-truth-for-runs)
14. [Appendix D: Glossary](#appendix-d-glossary)

---

## 1. Context

If you optimize for mean latency, rare outliers can dominate your conclusion.
If you optimize for median latency, the "typical call" dominates.

Those statements are always true. The publishable question is:

> What mechanism caused the TR117 Tier-3 "-compile" label to differ distributionally from the non-compile label, and can we attribute it to torch.compile?

TR120 answers that by separating:

- **TR117 label-only evidence** (what the artifacts show), from
- **TR120 controlled evidence** (what explicit compilation does on this environment).

### 1.1 Why this matters (production, not benchmarking)

The "mean vs median" distinction is not academic. It maps directly to production risk:

- **Median latency** approximates the "typical request" experience and the steady-state throughput you can plan around.
- **Tail latency (p95/p99/max)** controls your SLOs, timeout rates, and incident surface area.
- **Mean latency** is often a proxy for "aggregate compute-hours per request", but in heavy-tail settings it can be dominated by rare events that your users *still* experience as stalls/timeouts.

When a change improves mean but hurts median (or vice versa), there are only a few real explanations:

1. You changed the distribution shape (e.g., fewer extreme outliers but slightly slower typical calls), or
2. You changed the workload mix, measurement boundary, or attribution (a harness issue), or
3. You introduced a bimodal system (e.g., fast path + slow path such as compilation, cache misses, or fallback execution).

TR120's goal is to pin which of those is actually happening.

### 1.2 Research evolution (why TR120 exists)

TR120 is a "make it real" report in the same lineage as TR118/TR119:

- **TR117** surfaced the paradox inside a broader Tier-3 backend matrix.
- **TR118_v2.2** established the standard that *claims must be artifact-backed and attribution-correct*.
- **TR119v1** translated throughput into decision-grade economics (where tails still matter operationally).
- **TR120 (this report)** performs the missing step for compiler claims: it audits attribution and then reproduces compiler behavior under a controlled harness.

### 1.3 Research questions (decision-grade)

This report answers:

1. **Attribution:** Did TR117's `transformers-gpu-compile` label actually run `torch.compile()` in this repo?
2. **Mechanism (prefill):** If we enable Inductor+Triton for real, does compilation create a fast path + slow path distribution that can flip mean/median?
3. **Mitigation:** Do stable shapes (padding/bucketing) or shape-polymorphic compilation (`dynamic=True`) reduce compiler-induced tails?
4. **Decode transfer:** Do conclusions hold for **KV-cached decode**, which is the production decode regime (not uncached recompute)?

### 1.4 How to read this report

Use TR120 in three passes:

1. **Section 3 (label audit)** establishes what is and is not a valid compiler claim in TR117.
2. **Section 4 (TR117 results)** shows the paradox is real at the distribution level and isolates which outliers drive it.
3. **Section 5+ (controlled reproduction)** shows what real compilation does, which mitigations work, and what the production decision should be.

---

## 2. Datasets & Semantics

### 2.1 TR117 Tier-3 dataset (label-only)

Source of truth:

- `results/tr117_tier3/metrics.csv`

Row semantics:

- Each row is one prompt-measurement (rowified from run artifacts; see `scripts/tr117/analyze_tr117.py`).

Important measurement caveat:

- TR117 measures end-to-end latency at the `InferenceService.generate(...)` call boundary. This includes any model/pipeline caching behavior, runtime initialization effects, and other non-kernel work in the timed region.

### 2.2 TR120 controlled runner dataset (explicit)

Source of truth:

- `scripts/tr120/run_root_cause.py`
- Referenced artifact sets:
  - Inductor+Triton (Docker): `scripts/tr120/results/tr120_root_cause_triton/20251221_173112/`
  - Windows fallback (no Triton): `scripts/tr120/results/tr120_root_cause/20251221_113136/`

Runner semantics:

- Loads the HF model once (no per-call model load).
- Pre-tokenizes prompts (removes tokenizer variance from timed regions).
- Measures three explicit modes:
  - `prefill` (single forward pass with `use_cache=True`)
  - `kv_decode` (decode loop only, using KV cache; excludes prefill)
  - `e2e_kv` (prefill + KV decode total)
- Attempts `torch.compile(backend="inductor")` and records any fallback in each run artifact under `compile`.

### 2.3 Modes (what is measured, and what is not)

TR120 uses three modes because "compile helped" can mean three different things depending on where the time is:

**Prefill (`prefill`)**

- Runs one forward pass over the prompt context with `use_cache=True`.
- Records latency for the forward pass only.
- This approximates "time-to-first-token" kernel work, but it is not full serving TTFT because tokenization and framework overheads are intentionally excluded.

**KV decode (`kv_decode`)**

- Runs a deterministic greedy decode loop for `max_new_tokens` steps.
- Uses `use_cache=True` and feeds `past_key_values` between steps.
- Records the decode-loop latency only (prefill is executed to obtain `past_key_values`, but is excluded from the reported latency).

**End-to-end KV (`e2e_kv`)**

- Runs prefill + KV decode and records the combined latency.
- This is the closest "serving-like" metric in TR120, while still remaining kernel-focused and reproducible.

What TR120 does not measure:

- Uncached decode (recompute) behavior (that is a stress test regime used elsewhere).
- Full serving overheads (queueing, tokenization, RPC, batching policy, scheduler effects).

### 2.4 Metrics and aggregation (reviewer-proof definitions)

Per prompt-measurement we record:

- `latency_ms`: elapsed time for the mode's timed region.
- `tokens`: tokens processed in that timed region:
  - `prefill`: number of non-padding prompt tokens (sum of `attention_mask`)
  - `kv_decode`: number of generated tokens (`max_new_tokens` in these runs)
  - `e2e_kv`: prompt tokens + generated tokens
- `tokens_per_s = tokens / (latency_ms / 1000)`

Important padding note:

- In padded runs, `tokens` remains "semantic tokens" (non-padding) for interpretability, while actual compute increases by design.
  As a result, `tokens_per_s` is not an apples-to-apples throughput comparison between padded and non-padded runs; padding is treated
  as a tail-risk mitigation strategy, not a throughput-fairness strategy.

Distribution statistics:

- `p50` (median), `p95`, `p99` are computed over the per-measurement latencies.
- In controlled runs, each backend/mode summary has `n~270` measurements:
  - 5 scenarios, with 2 prompts per scenario except `stress_single` (1 prompt), and 30 repetitions.

Important: TR120 is intentionally distribution-first. We do not treat a mean as a sufficient summary when the underlying mechanism can produce multimodal behavior (fast path vs compile/recompile/fallback path).

### 2.5 What counts as "compiled" (and how we prove it)

TR120 does not accept "backend label says compile" as evidence.

A run is considered *compiler-real* only if the artifacts show:

1. `compile.backend == "inductor"` in the run metadata, and
2. `compile.dynamo_counters_after_compile` is present (a successful compile-stage counter snapshot), and
3. The run did not record a fallback (e.g., `fallback_from` / `fallback_error`).

This matters because on some platforms `hasattr(torch, "compile")` is true, but the intended GPU backend is unavailable (e.g., missing Triton wheels). TR120 records those fallbacks explicitly so the report cannot accidentally claim Inductor behavior when it is not occurring.

### 2.6 Environment split (Windows host vs Triton Docker)

TR120 uses two environments for a reason:

- **Windows host:** representative of the local-first dev environment, but Inductor+Triton GPU compilation is not available for this Python/OS combo in the tested stack (falls back; recorded).
- **Triton Docker (Linux):** provides a known-good Inductor+Triton toolchain so we can collect definitive compiler evidence.

---

## 3. Backend Label Audit (TR117)

The TR117 Tier-3 backend labels include `transformers-gpu-compile`. In this repo, that label does not imply torch.compile execution.

Evidence:

- `banterhearts/api/inference/service.py` executes Hugging Face `transformers.pipeline(...)` for any backend starting with `transformers` and does not call `torch.compile()` based on the backend name.
- `git blame` shows that behavior existed prior to the TR117 Tier-3 artifact timestamp.

Additional corroboration:

- A repository-wide search for `torch.compile(` (outside of TR120's controlled runner) does not show a `transformers-*-compile` code path that actually wraps the model/module.
- The inference service contains an explicit comment (near the transformers backend dispatch) that compile integration is model-specific and not currently wired into the generic Hugging Face path.

Interpretation (why this happened):

- The TR117 benchmark matrix treated backend names as labels in the measurement harness.
- A label called `transformers-gpu-compile` therefore created a *measurement category*, but did not create a *compiled execution path*.

This is a subtle but common failure mode in performance research: the benchmark taxonomy becomes disconnected from the actual runtime behavior.

Definitive conclusion:

- TR117's reported `transformers-gpu` vs `transformers-gpu-compile` differences are **not attributable to torch.compile** in this codebase.
- Any "compile paradox" explanation must therefore focus on **artifact/harness behavior**, not on compiler internals, unless and until compilation is explicitly wired into the inference backend.

---

## 4. TR117 Results (Label-Only Distribution)

This section reports what the TR117 Tier-3 artifacts say, while keeping the attribution correct (label-only).

Comparison: `transformers-gpu` vs `transformers-gpu-compile`, filtered to:

- `status == "ok"`
- `model == "models/tiny-gpt2"`

Overall summary across scenarios and quantization labels (n=273 rows per label):

| Label | Mean (ms) | Median (ms) | p99 (ms) | Max (ms) |
| --- | --- | --- | --- | --- |
| `transformers-gpu` | 404.05 | **322.68** | 931.48 | **3325.81** |
| `transformers-gpu-compile` | **389.22** | 328.69 | **631.16** | 681.76 |

What this means (and what it does not mean):

- It does mean: the recorded Tier-3 dataset has a heavier tail under the non-compile label.
- It does not mean: torch.compile reduced tail latency, because torch.compile was not invoked for that label in this codebase.

### 4.1 The paradox is driven by a small number of extreme outliers

The mean difference is small (~15ms) relative to the overall scale, but the max difference is enormous:

- `transformers-gpu` max: **3325.81 ms**
- `transformers-gpu-compile` max: **681.76 ms**

Those outliers dominate the mean while barely affecting the median. Concretely, the largest outlier in the dataset is:

| Backend label | Scenario | Quantization | Latency (ms) | Tokens | Tok/s | Artifact |
| --- | --- | --- | --- | --- | --- | --- |
| `transformers-gpu` | `single_micro` | `fp32` | **3325.81** | 38 | 11.43 | `results/tr117_tier3/runs/single_micro/transformers-gpu/fp32/models_tiny-gpt2/run_1765143078658.json` |

By contrast, the worst `transformers-gpu-compile` outliers are an order of magnitude smaller (sub-700ms), and are concentrated in `single_long` / `single_micro` rather than in multi-second spikes.

### 4.2 Scenario-level view (where the tail lives)

Per-scenario medians are broadly comparable, but max latency is not:

| Scenario | `transformers-gpu` median (ms) | `transformers-gpu` max (ms) | `transformers-gpu-compile` median (ms) | `transformers-gpu-compile` max (ms) |
| --- | --- | --- | --- | --- |
| `single_micro` | 594.88 | **3325.81** | 573.41 | 622.38 |
| `dual_medium` | 292.90 | 1061.90 | 287.20 | 522.33 |
| `dual_short` | 285.38 | 1042.76 | 288.31 | 393.29 |
| `single_long` | 339.88 | 701.04 | 370.70 | **681.76** |
| `stress_single` | 565.60 | 612.76 | 566.82 | 612.65 |
| `single_medium` | 315.74 | 441.36 | 324.32 | 551.18 |
| `single_short` | 323.52 | 413.06 | 324.53 | 518.57 |

Interpretation:

- The TR117 "compile paradox" is not a uniform shift in typical latency; it is a **tail phenomenon** that appears concentrated in a few scenarios, especially `single_micro` and the `dual_*` scenarios.
- This is consistent with a harness/system effect (initialization, caching, run ordering) rather than a systematic compiler effect.

### 4.3 Trimmed-mean sensitivity (how fragile the mean ranking is)

If we recompute means while dropping only the largest outliers, the story changes:

| Label | Mean (ms) | Mean excluding max (ms) | Mean excluding top 5 (ms) | Median (ms) |
| --- | --- | --- | --- | --- |
| `transformers-gpu` | 404.05 | 393.31 | **385.40** | **322.68** |
| `transformers-gpu-compile` | **389.22** | 388.15 | 384.38 | 328.69 |

This is the core reason "mean vs median" can flip:

- If a small number of rare events dominate one label but not the other, the mean ranking is *fragile*.
- The median ranking remains stable because it reflects the typical call.

### 4.4 Cold-start signal (artifact-backed; explains the mean)

TR117 Tier-3 stores repeated measurements inside each `run_*.json` file as an ordered array `latencies_ms`.
In the worst outlier file, the multi-second spike is the first element of that array:

- `results/tr117_tier3/runs/single_micro/transformers-gpu/fp32/models_tiny-gpt2/run_1765143078658.json`
  - `latencies_ms[0] = 3325.81 ms`
  - subsequent samples in the same file are ~590-620ms

This "first sample is sometimes a cold-start" pattern is not a one-off. We analyze it directly from the run JSON
arrays (not from aggregated CSVs) and recompute overall distributions after dropping the first element of every
run-file array (one element per `{scenario, backend, quantization}` artifact).

Artifacts:

- `scripts/tr120/results/tr120_compile_paradox/processed/cold_start_effect_overall.csv`
- `scripts/tr120/results/tr120_compile_paradox/processed/cold_start_by_file.csv`

Overall effect (models/tiny-gpt2; status=ok):

| Label | Mean (ms) | Median (ms) | p99 (ms) | Max (ms) | Mean excluding first sample per run-file (ms) |
| --- | --- | --- | --- | --- | --- |
| `transformers-gpu` | 404.05 | 322.68 | 931.48 | 3325.81 | 386.75 |
| `transformers-gpu-compile` | 389.22 | 328.69 | 631.16 | 681.76 | 388.29 |

Reviewer-proof asymmetry (cold-start skew frequency):

- In TR117, `transformers-gpu` has cold-start skew in **3/21 run files (14.3%)** where the first sample is
  >3x the median of the remaining samples in that file.
- In TR117, `transformers-gpu-compile` has **0/21** such files.

Why the skew is asymmetric (and what we can and cannot claim):

- We do not attribute this asymmetry to backend behavior; the TR117 `*-compile` label is not compiler-real (Section 3).
- The most likely explanation is run ordering / cache warming / initialization variance inside the TR117 timed boundary.
  TR117 did not enforce randomized backend order or explicit warmup exclusion at the row level, so it is expected that
  first-call spikes can attach unevenly to a label depending on harness order and system state.

Decision-grade interpretation:

- The TR117 mean advantage for the `*-compile` label (which is not actually compiled in this repo) is explained
  by a small number of extreme cold-start samples under `transformers-gpu`.
- After excluding the first sample in each run-file array, the mean delta essentially disappears (and slightly
  reverses): the apparent "compile mean win" is not a stable backend property.
- Because TR117's timed region includes initialization/caching work inside `InferenceService.generate(...)`, first-call
  spikes are expected unless the harness explicitly separates warmup from measurement (the TR120 controlled runner does).

### 4.5 What we can conclude from TR117 alone

From TR117 alone we can say:

- The dataset contains a heavy tail under the `transformers-gpu` label for this model.
- That heavy tail is large enough to flip the mean ranking.

We cannot say:

- That compilation caused the difference (it was not invoked).
- That the TR117 dataset reveals Inductor/Triton behavior (it does not).

---

## 5. TR120 Controlled Reproduction (Explicit Compile Attempt)

This section answers the "ok, but what happens if we actually compile?" question, using explicit artifacts.

### 5.1 Inductor+Triton (Docker): compile is real, and recompiles are measurable

This run executes inside `nvcr.io/nvidia/tritonserver:25.08-trtllm-python-py3` (Linux) with GPU enabled (`--gpus all`).

#### Controlled-run configuration (what was held constant)

The controlled runner exists to remove confounds that make compiler claims non-definitive:

- Model is loaded once (no per-measurement weight load).
- Prompts are tokenized once (tokenizer variance removed from timed region).
- CUDA synchronization is used around timed regions to avoid async timing artifacts.
- Both "eager" and "compiled" backends share the same model weights and tokenizer.

Config inputs for the referenced Inductor run:

- Config: `scripts/tr120/configs/root_cause.yaml`
- Scenarios: `single_micro`, `single_short`, `single_medium`, `single_long`, `stress_single`
- Repetitions: 30 (plus 3 warmups)
- Decode length: `max_new_tokens=64`
- Compile: `torch.compile(mode="reduce-overhead", backend="inductor", dynamic=False)`

Environment (from manifest):

- Torch: `2.8.0a0+5228986c39.nv25.05`
- CUDA: `12.9`, cuDNN: `91001`
- GPU: `NVIDIA GeForce RTX 4080 Laptop GPU` (CC 8.9)

Artifact set:

- `scripts/tr120/results/tr120_root_cause_triton/20251221_173112/manifest.json`

The run artifacts confirm real Inductor compilation:

- Example run artifact:
  - `scripts/tr120/results/tr120_root_cause_triton/20251221_173112/prefill/runs/stress_single/transformers-gpu-compile/fp32/run_1766338305841.json`
- Compile metadata includes `backend: "inductor"` and `dynamo_counters_after_compile.stats.unique_graphs: 1`.

#### Prefill results (single forward pass)

From `scripts/tr120/results/tr120_root_cause_triton/20251221_173112/prefill/analysis/processed/summary.json`:

| Backend | Mean (ms) | Median (ms) | p95 (ms) | p99 (ms) | Max (ms) |
| --- | --- | --- | --- | --- | --- |
| eager (`transformers-gpu`) | 1.74 | 1.74 | 2.15 | 3.05 | 4.09 |
| compile (Inductor; `transformers-gpu-compile`) | **0.52** | **0.19** | 2.70 | 5.21 | 9.39 |

Interpretation:

- Inductor makes prefill dramatically faster for the typical call (median), but introduces a much heavier tail in this configuration.
- That tail is not "mystery noise"; it correlates with recompilation activity.

#### Timing validity cross-check (CUDA events; addresses the "0.19ms is noise" critique)

Prefill medians around ~0.2ms for tiny-gpt2 can trigger a reasonable reviewer concern:
"Are you mostly measuring Python + synchronize overhead?"

To harden this claim, we reran a prefill-only controlled run with both:

- wall-clock timing (with `torch.cuda.synchronize()` boundaries), and
- CUDA-event timing (GPU-only elapsed for the forward pass)

Artifact set:

- `scripts/tr120/results/tr120_root_cause_triton/20251221_191009`

From `scripts/tr120/results/tr120_root_cause_triton/20251221_191009/prefill/metrics.csv` (status=ok; n=270 per backend):

| Backend | Wall median (ms) | CUDA-event median (ms) | Wall p99 (ms) | CUDA-event p99 (ms) |
| --- | --- | --- | --- | --- |
| eager (`transformers-gpu`) | 1.9611 | 1.6914 | 3.4330 | 2.8825 |
| compile (Inductor; `transformers-gpu-compile`) | 0.2406 | 0.1814 | 0.6324 | 0.4390 |

Interpretation:

- CUDA-event timing is lower than wall-clock (kernel launch + host overhead do not appear in the CUDA event window),
  but the compiled-vs-eager delta remains visible in GPU-only time.
- The sub-millisecond compiled prefill p50 is therefore not a wall-clock artifact; the speedup exists on-GPU.
- These absolute numbers are tiny-gpt2-specific (small model, short sequences); the point of this cross-check is timing
  validity and directionality, not that "all prefill is sub-millisecond" on larger models.

#### Compiler evidence beyond `unique_graphs` (why we claim compilation is real)

`unique_graphs` is a useful proxy for "how many specialized graphs did we end up compiling," but it is not, by itself,
a full explanation of compiler behavior.

The controlled runner therefore also records a compact `torch._dynamo.explain(...)` summary for representative calls:

- `scripts/tr120/results/tr120_root_cause_triton/20251221_191009/compiler_evidence.json`
  - `prefill_explain.graph_count = 1`, `graph_break_count = 0`, `break_reasons_count = 0`
  - `prefill_explain.out_guards_count = 463`

How to read this with the counters:

- The explain snapshot shows that for a fixed representative shape, Dynamo captures a single graph without graph breaks.
- The per-run counters still show shape pressure over the full run set (multiple `unique_graphs` can arise as guards fail
  for different input shapes across scenarios).

#### Recompilation evidence (artifact-backed)

The runner writes per-mode Dynamo counters:

- `scripts/tr120/results/tr120_root_cause_triton/20251221_173112/prefill/dynamo_counters.json`

Key fields (prefill mode):

- `dynamo_counters.stats.unique_graphs: 7`
- `dynamo_counters.frames.total: 8`

This is the concrete mechanism: **variable prompt lengths cause multiple compiled graphs**, which creates compilation churn and tail events.

### 5.1.1 Ablation: padded shapes (per-scenario max length)

We re-run the same prefill mode, but pad prompts to a stable shape within each scenario (and pass `attention_mask` so padding does not change semantics):

- Config: `scripts/tr120/configs/root_cause_padded_kv.yaml` (runs all modes; prefill results shown here)
- Artifact set: `scripts/tr120/results/tr120_root_cause_triton/20251221_182658`

Prefill summary (padded run):

| Backend | Mean (ms) | Median (ms) | p95 (ms) | p99 (ms) | Max (ms) |
| --- | --- | --- | --- | --- | --- |
| eager (`transformers-gpu`) | 2.33 | 2.23 | 3.07 | 3.82 | 6.24 |
| compile (Inductor; `transformers-gpu-compile`) | **0.20** | **0.19** | **0.31** | **0.38** | **0.45** |

Interpretation nuance:

- Eager becomes slower in the padded run because it is doing more work (it now processes padded tokens). Padding is semantics-preserving here because `attention_mask` is passed, but it is not compute-free.
- The key signal is the compiled distribution: padding collapses the compiled tail by stabilizing shapes, while keeping typical compiled latency extremely low.
- Padded runs are a tail-risk mitigation experiment, not a throughput fairness comparison: `tokens` remains "semantic tokens"
  (non-padding) for interpretability, while the actual compute intentionally increases due to padding.

Compilation churn (prefill mode):

- Variable-length run (`20251221_173112`): `unique_graphs: 7`
- Padded run (`20251221_182658`): `unique_graphs: 5`

Interpretation:

- Padded shapes materially reduce tail events for compiled prefill (p99 drops from ~5ms+ down to sub-millisecond range).
- Unique-graph count drops, consistent with the hypothesis that shape instability is a primary driver of compile churn and tail inflation.
- `unique_graphs` can remain >1 even when the tail collapses because each scenario has a different padded max length; padding
  eliminates within-scenario recompilation churn, not the existence of multiple scenario-shaped graphs.

### 5.1.2 Ablation: `dynamic=True` (shape-polymorphic compile)

As an alternative to padding, we run Inductor with dynamic shape support enabled:

- Config: `scripts/tr120/configs/root_cause_dynamic.yaml`
- Artifact set: `scripts/tr120/results/tr120_root_cause_triton/20251221_181045`

Prefill summary (dynamic compile run):

| Backend | Mean (ms) | Median (ms) | p95 (ms) | p99 (ms) | Max (ms) |
| --- | --- | --- | --- | --- | --- |
| eager (`transformers-gpu`) | 2.03 | 1.99 | 2.80 | 3.33 | 5.36 |
| compile (Inductor dynamic; `transformers-gpu-compile`) | **0.65** | **0.78** | **0.96** | **1.21** | **1.59** |

Compilation churn:

- Dynamic run (`20251221_181045`): `unique_graphs: 2` (from `prefill/dynamo_counters.json`)

Interpretation:

- `dynamic=True` materially reduces compilation churn and tail inflation without requiring padding.
- It is slower than the padded compile path at p50, but significantly more stable than the variable-shape compile run.

#### 5.1.3 Prefill ablation summary (one table, decision-relevant)

All three Inductor configurations improve the typical compiled prefill latency dramatically versus eager. The differences are in *tail risk* and *operational constraints*:

| Prefill strategy | Artifact run | Compiled median (ms) | Compiled p99 (ms) | `unique_graphs` | Operational note |
| --- | --- | --- | --- | --- | --- |
| Variable-length inputs | `20251221_173112` | **0.19** | **5.21** | 7 | Fast p50, unsafe tail due to recompiles |
| Padded per-scenario shapes | `20251221_182658` | **0.19** | **0.38** | 5 | Tail collapsed; eager path slows due to extra compute |
| `dynamic=True` (no padding) | `20251221_181045` | **0.78** | **1.21** | 2 | Fewer graphs; slower p50 than padded |

Key takeaway:

- If you only change one thing before shipping compile for prefill, change **shape stability** (padding/bucketing). It is the highest-leverage tail fix in this run set.

### 5.2 Windows host (no Triton): inductor GPU compile is not supported here

On the Windows host (Python 3.13), `torch.compile(backend="inductor")` fails due to missing Triton wheels; the runner falls back to `aot_eager`.

Why this matters:

- If your production environment resembles the Windows host stack, "turn on compile" can silently become "run eager with extra wrapper overhead" unless you record fallbacks.
- This is exactly why TR120 requires compiler-real evidence (Section 2.5) and why the repo gates compile-capable backends on Triton availability.

How TR120 records it:

- Each run artifact contains a `compile` block that captures the requested backend (`inductor`) and the actual backend used (fallback), plus the error message that triggered the fallback.

Concrete evidence:

- Example run artifact with fallback metadata:
  - `scripts/tr120/results/tr120_root_cause/20251221_113136/e2e_kv/runs/stress_single/transformers-gpu-compile/fp32/run_1766334864085.json`

### 5.3 Controlled results: KV-cached decode (Inductor run)

From the Inductor artifact set (`scripts/tr120/results/tr120_root_cause_triton/20251221_173112`) with variable-length prompts:

**KV decode-only (64 tokens, `use_cache=True`):**

| Backend | Mean (ms) | Median (ms) | p95 (ms) | p99 (ms) | Max (ms) |
| --- | --- | --- | --- | --- | --- |
| eager (`transformers-gpu`) | **95.10** | **93.99** | 105.32 | 119.81 | 122.55 |
| compile (Inductor; `transformers-gpu-compile`) | 104.90 | 103.09 | 115.61 | 133.47 | 167.87 |

**End-to-end (prefill + KV decode):**

| Backend | Mean (ms) | Median (ms) | p95 (ms) | p99 (ms) | Max (ms) |
| --- | --- | --- | --- | --- | --- |
| eager (`transformers-gpu`) | **98.64** | **96.23** | 113.20 | 136.18 | 153.85 |
| compile (Inductor; `transformers-gpu-compile`) | 108.58 | 105.64 | 131.66 | 149.09 | 165.27 |

Interpretation:

- Inductor helps prefill strongly, but it hurts KV-cached decode in this configuration.
- A single global "compile on GPU" decision is therefore unsafe unless you split modes or control shapes.

#### 5.3.1 Padded shapes + KV decode (and the cudagraph-trees hazard)

This run uses per-scenario padding (attention-masked) and explicitly disables Inductor's cudagraph trees (via `disable_cudagraphs: true`, which disables `config.triton.cudagraph_trees` in the runner). This matters because autoregressive KV decode feeds `past_key_values` across iterations, which can interact poorly with cudagraph output reuse.

Artifact set:

- `scripts/tr120/results/tr120_root_cause_triton/20251221_182658`

**KV decode-only (64 tokens, `use_cache=True`):**

| Backend | Mean (ms) | Median (ms) | p95 (ms) | p99 (ms) | Max (ms) |
| --- | --- | --- | --- | --- | --- |
| eager (`transformers-gpu`) | **99.39** | **97.54** | 111.06 | 132.75 | 154.11 |
| compile (Inductor; `transformers-gpu-compile`) | 106.69 | 105.40 | 116.87 | **132.44** | **151.44** |

**End-to-end (prefill + KV decode):**

| Backend | Mean (ms) | Median (ms) | p95 (ms) | p99 (ms) | Max (ms) |
| --- | --- | --- | --- | --- | --- |
| eager (`transformers-gpu`) | **101.22** | **98.32** | 121.86 | 142.79 | 164.69 |
| compile (Inductor; `transformers-gpu-compile`) | 107.04 | 105.53 | **118.83** | **141.53** | **157.65** |

Two key points:

1. Padding fixes the prefill tail, but it cannot remove decode's inherent shape growth (KV length increases each token).
2. In this run set, compiled decode remains slower at p50/p90 even when tails are similar; end-to-end is still worse because decode dominates request time at `max_new_tokens=64`.

#### 5.3.2 Why KV-cached decode is harder to "just compile"

Before blaming "compile" generically, note that several concrete mechanisms can cause the observed decode regression:

- graph breaks/recompiles driven by `past_key_values` shape growth (guard churn / `recompile_limit` pressure)
- loss of decode-optimized attention kernels under compilation (kernel-path selection changes)
- extra synchronizations, copies, or layout conversions introduced by graph capture boundaries
- CUDA graph capture hazards (cudagraph trees) in iterative decode loops (mitigated in TR120 via explicit disabling)

This report treats these as falsifiable hypotheses; the next step is a `torch.profiler` trace diff that shows which
kernel paths and graph-break/recompile events change between eager and compiled decode (Section 8.2 / 9.2).

KV-cached decode violates two assumptions that make compilation "easy":

1. **State changes every step:** `past_key_values` grows every token, so the effective tensor shapes change monotonically within a single request.
2. **The hot path is different:** decode is typically dominated by attention + MLP for batch=1 with cache reads/writes, and optimized kernels (FlashAttention, paged attention) often matter more than generic fusion.

Practical implication:

- A compile strategy that is excellent for prefill can be neutral or negative for decode, especially if it triggers recompiles, hits `recompile_limit`, or prevents the use of specialized kernels.

Decode sanity check (what the artifacts say):

- Variable-length run (`20251221_173112`): compiled decode is slower at p50/p95/p99 and has a worse max.
- Padded run (`20251221_182658`): compiled decode is still slower at median/mean, even though the extreme tail is similar.

This is why TR120 recommends treating prefill and decode as separate optimization targets (Section 7).

### 5.4 Dynamo recompilation pressure (why stability can degrade)

During the controlled runs, `torch._dynamo` emitted critical diagnostics consistent with shape-driven churn:

- Variable-length prefill run (`20251221_173112`) emitted `torch._dynamo hit config.recompile_limit (8)` due to `input_ids` size mismatch (variable prompt lengths).
- Padded+decode run (`20251221_182658`) emitted `torch._dynamo hit config.recompile_limit (8)` due to `past_key_values[...]` size mismatch (KV length growth).

Artifact-backed churn evidence:

- Variable-length prefill (`20251221_173112`): `unique_graphs: 7`, `frames.total: 8` in `scripts/tr120/results/tr120_root_cause_triton/20251221_173112/prefill/dynamo_counters.json`
- Padded KV decode (`20251221_182658`): `unique_graphs: 2`, `unimplemented["recompile_limit reached"]: 1` in `scripts/tr120/results/tr120_root_cause_triton/20251221_182658/kv_decode/dynamo_counters.json`

This is consistent with a real mechanism that can produce distribution differences when compilation is enabled:

- variable prompt lengths imply variable `input_ids` sequence lengths
- naive compilation specializes on shapes, causing multiple compiled graphs and recompilations
- once `recompile_limit` is hit, compilation can degrade to a less optimized path

KV-cached decode adds a second, unavoidable source of shape pressure:

- `past_key_values` grows by one token per step. A compiler must either (a) generate multiple specialized graphs, (b) use shape-polymorphic compilation, or (c) eventually hit `recompile_limit` and degrade to a fallback path.

This is the compiler-shaped mechanism behind median/tail anomalies: **shape instability induces compilation churn**.

---

## 6. Interpretation (What Could Cause TR117's Shape)

Because TR117 "-compile" did not actually invoke torch.compile in this repository, the correct interpretation space is "harness behavior," not "compiler behavior."

Plausible contributors to the TR117 label-only distribution difference:

1. **Run ordering and caching:** if one label tends to run after another, it can benefit from warmed caches (filesystem cache, CUDA context, allocator state).
2. **End-to-end variance:** TR117 measures at the `InferenceService.generate` call boundary, which includes non-kernel work and is sensitive to background system activity.
3. **Heavy-tail initialization effects:** large outliers can occur from first-time initialization (lazy module loads, CUDA initialization, allocator growth). If those outliers are unevenly distributed across label segments, the mean can flip while the median stays similar.

The controlled TR120 runner removes most of these confounds by design (single model load; pre-tokenized prompts; explicit sync).

### 6.1 TR117 cold-start skew (artifact-backed; why the label means differ)

With attribution corrected (Section 3), the remaining question is:
"Why does the TR117 `transformers-gpu-compile` label look better on mean?"

The dataset itself contains the answer: the largest outliers for `transformers-gpu` appear as the first element of
some TR117 `latencies_ms` arrays (Section 4.4). When we drop the first element of every run-file array and recompute
the overall mean, the apparent mean advantage of the `*-compile` label disappears.

Concrete result (models/tiny-gpt2; status=ok):

- Mean delta (compile - eager): `389.22 - 404.05 = -14.83 ms`
- Mean delta after excluding first sample per run-file: `388.29 - 386.75 = +1.54 ms`

Interpretation:

- The TR117 mean/median flip is driven by cold-start samples that are unevenly present under the `transformers-gpu`
  label, not by any compilation mechanism (none existed in this code path).
- The remaining question is not "is compile better," but "why are some first samples cold-start within the timed
  boundary?" (likely one-time initialization inside `InferenceService.generate(...)`, allocator growth, CUDA context
  init, cuDNN autotune, or run ordering/caching effects).

If you want to attribute the cold-start to a specific subsystem, the highest ROI follow-up is still to rerun TR117 with
explicit first-N tagging and randomized backend/scenario order. TR120's controlled runner already demonstrates how to
build that kind of "confound-resistant" harness.

### 6.2 Why TR120 still studies real compilation

Even though TR117 is a misattribution, a careful reviewer will ask:

> "Fine, but if I actually enable Inductor, could it create the same kind of mean/median disagreement?"

The answer is yes, and TR120 demonstrates the precise mechanism:

- shape instability -> multiple graphs -> recompiles/fallback -> tail events (Section 5.1 / 5.4).

This matters because it means the TR117 paradox is not a one-off: it is the same *shape of failure* you can get if you "enable compile" without controlling shapes and state boundaries.

---

## 7. Production Guidance

### 7.1 What not to do

- Do not publish or ship a "torch.compile performance claim" based on TR117 Tier-3 `transformers-gpu-compile` label differences in this repo; it is not a compiler claim here.

### 7.2 What to do (safe default)

1. Gate "-compile" backend selection on verified support for the intended compiler backend.
   - This repo now gates compile backends on Triton availability (see `banterhearts/runtime/capabilities.py`).
2. If you want to ship compilation, wire it explicitly into the inference backend and warm it up outside the timed region.
3. Treat KV-cache transitions (`past_key_values`) as a first-class shape/state boundary in your compile strategy (or expect recompilations and latency variance).

### 7.3 The production decision rule (make it impossible to misunderstand)

Use this as the "break-glass" decision logic:

1. **If you cannot prove compilation is real (Inductor backend recorded):** do not ship a `*-compile` backend label. Fix instrumentation first.
2. **If you can stabilize prefill shapes (padding/bucketing):** compiling prefill can be worth it (large p50 win, tail can be controlled).
3. **If your workload is decode-dominant (most serving):** do not assume the prefill win matters. In these runs, compiled KV decode is slower, so end-to-end gets worse unless you split modes.
4. **If you need one backend choice today:** choose eager for correctness and predictability; enable compile only behind a flag and validate tails under your real traffic mix.

### 7.4 Recommended deployment pattern (what to actually ship)

Given the controlled artifacts in this report, the safest high-performance pattern is:

- **Compile prefill only** (or only for a narrow, stable set of prompt shapes).
- **Keep KV-cached decode eager** (or use a decode-optimized backend/kernels rather than generic Inductor).

This can be implemented as:

1. Implement prefill as a compiled function (e.g., `prefill_step(input_ids, attention_mask)`), warmed on a fixed set of shapes.
2. A decode loop that remains eager and uses optimized attention kernels where available.
3. A routing policy that falls back to eager if compilation shows churn (`unique_graphs` grows unexpectedly, `recompile_limit reached`, or any fallback metadata is present).

### 7.5 Instrumentation checklist (minimum for publishability)

If you publish or ship compilation results, record at minimum:

- compile backend (`inductor` vs fallback), compile mode, and whether `dynamic=True`
- compile-stage counters (`dynamo_counters_after_compile`)
- per-mode counters (`unique_graphs`, `recompile_limit reached`)
- distribution stats (median + p95/p99), not just means

TR120's controlled runner is structured to emit these artifacts by default.

---

## 8. TR120.B: KV-Cached Decode (Subtask)

TR120.B exists to prevent a predictable critique:

> "Your conclusions do not transfer to real decode, because real decode is KV-cached."

This report includes KV-cached decode explicitly in the controlled harness (`kv_decode` and `e2e_kv` modes), because the production decision depends on which phase dominates.

### 8.1 What TR120.B establishes in this repo

1. **Decode is not a simple extension of prefill.** In both the variable-length Inductor run (`20251221_173112`) and the padded run (`20251221_182658`), KV-cached decode is slower under Inductor at typical latencies (median/mean).
2. **End-to-end is decode-dominant at `max_new_tokens=64`.** A large prefill win does not automatically improve request latency when decode dominates.
3. **Decode introduces unavoidable shape pressure.** `past_key_values` grows every step; even after padding prompt shapes, the compiler is still exposed to a moving-shape state boundary (Section 5.4).
4. **CUDAGraph output reuse can be a real hazard in decode loops.** TR120 disables Inductor cudagraph trees for the padded+decode run to avoid overwrite hazards and make the results reproducible.

### 8.2 What remains to make decode "definitive" (frontier-grade)

TR120.B is still incomplete as a full decode study because it has not yet been integrated into the broader experimentation pipeline (TR117-style matrix + plots + report narrative), and because decode behavior is sensitive to model size and kernel availability.

Publish-grade next steps:

1. **Decode kernel attribution:** run `torch.profiler` for eager vs compiled decode to identify whether regressions come from:
   - graph breaks / recompiles,
   - loss of specialized attention kernels,
   - extra memory copies / synchronizations,
   - or fusion/autotune differences.
2. **Decode-length sweep:** repeat `max_new_tokens` across a range (e.g., 8/32/128/512) to show where the crossover occurs, if any.
3. **Model-size sweep:** repeat on a larger model where attention/MLP kernels and memory pressure differ qualitatively.
4. **Strategy sweep:** compare compile strategies specifically for decode:
   - `dynamic=True` vs `False`
   - compile modes (`default`, `reduce-overhead`, `max-autotune`)
   - eager+FlashAttention vs compiled without it (if applicable)

The TR120 controlled runner already provides the scaffold for this; the missing work is running the sweep and integrating the conclusions into the main pipeline.

---

## 9. Limitations & Next Steps

### 9.1 Limitations (explicit)

1. TR117 label-only results are not attributable to torch.compile in this repo.
2. Inductor+Triton compilation is not available on the Windows host Python stack used for development; TR120 therefore relies on a GPU-enabled Linux Docker environment for definitive compiler evidence.
3. The controlled runs use a small model (`models/tiny-gpt2`) on one GPU; larger models and different kernel stacks (FlashAttention, paged attention) can change decode behavior materially.
4. This report is distribution- and artifact-definitive, but not yet profiler-definitive: it does not include `torch.profiler`/Nsight traces that pinpoint which kernels or graph breaks cause the decode regression.
5. Compile strategy space is not exhausted: only a small set of compile modes (`reduce-overhead`, `dynamic` ablation for prefill) are explored here.

### 9.2 Next steps (to become "compiler-definitive")

1. Add profiler evidence:
   - `torch.profiler` traces for prefill vs KV decode, eager vs compiled
   - explicit graph-break/recompile accounting around `past_key_values`
2. Expand decode to a real study (TR120.B completion):
   - decode-length sweep (`max_new_tokens`), context-length sweep, and model-size sweep
   - compile strategy sweep for decode (`dynamic`, compile modes, kernel availability)
3. If the goal is to make TR117's pipeline "compiler-real":
   - implement true `torch.compile` wiring for `transformers-*-compile`
   - add warmup and model caching so the benchmark measures inference rather than repeated initialization
4. Integrate TR120 into the main experimentation pipeline:
   - add a TR120 entry in the experiments roadmap/status
   - ensure plots, summaries, and report generation are part of the standard workflow

---

## 10. Reproducibility & Artifacts

### 10.1 Re-run TR117 label-only analysis

```bash
python scripts/tr120/analyze_compile_paradox.py --metrics-csv results/tr117_tier3/metrics.csv --out-dir scripts/tr120/results/tr120_compile_paradox
```

### 10.2 Run the controlled reproduction (Windows host; fallback recorded)

```bash
python scripts/tr120/run_root_cause.py --config scripts/tr120/configs/root_cause.yaml
```

### 10.3 Run Inductor+Triton (Docker; compiler-real)

Run inside the Triton Docker image (Linux users can run directly without Docker if Triton is installed):

```bash
docker run --rm --gpus all -v "${PWD}:/workspace" -w /workspace nvcr.io/nvidia/tritonserver:25.08-trtllm-python-py3 \
  python3 scripts/tr120/run_root_cause.py --config scripts/tr120/configs/root_cause.yaml --out-root scripts/tr120/results/tr120_root_cause_triton
```

Additional ablation configs used in this report:

- Padded prefill-only: `scripts/tr120/configs/root_cause_padded.yaml`
- Padded prefill + KV decode: `scripts/tr120/configs/root_cause_padded_kv.yaml`
- Dynamic prefill-only: `scripts/tr120/configs/root_cause_dynamic.yaml`
- Prefill-only (timing validation): `scripts/tr120/configs/root_cause_prefill_only.yaml`

### 10.4 Analyze a run (all modes)

Replace `<RUN_ID>` with the printed folder under `scripts/tr120/results/tr120_root_cause_triton/` (or `scripts/tr120/results/tr120_root_cause/` for Windows-host runs):

```bash
python scripts/tr120/analyze_compile_paradox.py --metrics-csv scripts/tr120/results/tr120_root_cause_triton/<RUN_ID>/prefill/metrics.csv --out-dir scripts/tr120/results/tr120_root_cause_triton/<RUN_ID>/prefill/analysis
python scripts/tr120/analyze_compile_paradox.py --metrics-csv scripts/tr120/results/tr120_root_cause_triton/<RUN_ID>/kv_decode/metrics.csv --out-dir scripts/tr120/results/tr120_root_cause_triton/<RUN_ID>/kv_decode/analysis
python scripts/tr120/analyze_compile_paradox.py --metrics-csv scripts/tr120/results/tr120_root_cause_triton/<RUN_ID>/e2e_kv/metrics.csv --out-dir scripts/tr120/results/tr120_root_cause_triton/<RUN_ID>/e2e_kv/analysis
```

### 10.5 Key artifacts referenced by this report

- TR117 dataset:
  - `results/tr117_tier3/metrics.csv`
- TR117 label-only analysis artifacts:
  - `scripts/tr120/results/tr120_compile_paradox/processed/summary_overall.csv`
  - `scripts/tr120/results/tr120_compile_paradox/processed/cold_start_effect_overall.csv`
  - `scripts/tr120/results/tr120_compile_paradox/processed/cold_start_by_file.csv`
  - `scripts/tr120/results/tr120_compile_paradox/plots/cdf_latency_overall.png`
- TR120 controlled runs referenced:
  - Variable-length Inductor+Triton (Docker):
    - `scripts/tr120/results/tr120_root_cause_triton/20251221_173112/manifest.json`
    - `scripts/tr120/results/tr120_root_cause_triton/20251221_173112/prefill/dynamo_counters.json`
  - Padded shapes + KV decode (Inductor+Triton; Docker):
    - `scripts/tr120/results/tr120_root_cause_triton/20251221_182658/manifest.json`
    - `scripts/tr120/results/tr120_root_cause_triton/20251221_182658/prefill/analysis/processed/summary.json`
    - `scripts/tr120/results/tr120_root_cause_triton/20251221_182658/kv_decode/analysis/processed/summary.json`
    - `scripts/tr120/results/tr120_root_cause_triton/20251221_182658/kv_decode/dynamo_counters.json`
  - Prefill-only timing validation (Inductor+Triton; Docker):
    - `scripts/tr120/results/tr120_root_cause_triton/20251221_191009/manifest.json`
    - `scripts/tr120/results/tr120_root_cause_triton/20251221_191009/prefill/metrics.csv` (includes `cuda_event_ms`)
    - `scripts/tr120/results/tr120_root_cause_triton/20251221_191009/prefill/dynamo_counters.json`
    - `scripts/tr120/results/tr120_root_cause_triton/20251221_191009/compiler_evidence.json`
  - Dynamic shapes ablation (Inductor+Triton; Docker):
    - `scripts/tr120/results/tr120_root_cause_triton/20251221_181045/prefill/dynamo_counters.json`
  - Windows host fallback (no Triton):
    - `scripts/tr120/results/tr120_root_cause/20251221_113136/manifest.json`
    - `scripts/tr120/results/tr120_root_cause/20251221_113136/e2e_kv/analysis/processed/summary_overall.csv`
    - `scripts/tr120/results/tr120_root_cause/20251221_113136/e2e_kv/analysis/plots/cdf_latency_overall.png`

---

## Appendix A: Key Tables

### A.1 TR117 label-only "paradox" summary (do not attribute to torch.compile)

| Label | Mean (ms) | Median (ms) | p99 (ms) | Max (ms) |
| --- | --- | --- | --- | --- |
| `transformers-gpu` | 404.05 | **322.68** | 931.48 | **3325.81** |
| `transformers-gpu-compile` | **389.22** | 328.69 | **631.16** | 681.76 |

### A.2 TR117 scenario-level tail map (max dominates the mean)

| Scenario | `transformers-gpu` median (ms) | `transformers-gpu` max (ms) | `transformers-gpu-compile` median (ms) | `transformers-gpu-compile` max (ms) |
| --- | --- | --- | --- | --- |
| `single_micro` | 594.88 | **3325.81** | 573.41 | 622.38 |
| `dual_medium` | 292.90 | 1061.90 | 287.20 | 522.33 |
| `dual_short` | 285.38 | 1042.76 | 288.31 | 393.29 |
| `single_long` | 339.88 | 701.04 | 370.70 | **681.76** |
| `stress_single` | 565.60 | 612.76 | 566.82 | 612.65 |
| `single_medium` | 315.74 | 441.36 | 324.32 | 551.18 |
| `single_short` | 323.52 | 413.06 | 324.53 | 518.57 |

### A.3 TR120 controlled runs (Inductor+Triton) summary

Variable-length Inductor run: `scripts/tr120/results/tr120_root_cause_triton/20251221_173112`

**Prefill**

| Backend | Mean (ms) | Median (ms) | p95 (ms) | p99 (ms) | Max (ms) |
| --- | --- | --- | --- | --- | --- |
| eager (`transformers-gpu`) | 1.74 | 1.74 | 2.15 | 3.05 | 4.09 |
| compile (Inductor) | **0.52** | **0.19** | 2.70 | 5.21 | 9.39 |

**KV decode**

| Backend | Mean (ms) | Median (ms) | p95 (ms) | p99 (ms) | Max (ms) |
| --- | --- | --- | --- | --- | --- |
| eager (`transformers-gpu`) | **95.10** | **93.99** | 105.32 | 119.81 | 122.55 |
| compile (Inductor) | 104.90 | 103.09 | 115.61 | 133.47 | 167.87 |

Padded+decode Inductor run (cudagraph trees disabled): `scripts/tr120/results/tr120_root_cause_triton/20251221_182658`

**Prefill**

| Backend | Mean (ms) | Median (ms) | p95 (ms) | p99 (ms) | Max (ms) |
| --- | --- | --- | --- | --- | --- |
| eager (`transformers-gpu`) | 2.33 | 2.23 | 3.07 | 3.82 | 6.24 |
| compile (Inductor) | **0.20** | **0.19** | **0.31** | **0.38** | **0.45** |

**KV decode**

| Backend | Mean (ms) | Median (ms) | p95 (ms) | p99 (ms) | Max (ms) |
| --- | --- | --- | --- | --- | --- |
| eager (`transformers-gpu`) | **99.39** | **97.54** | 111.06 | 132.75 | 154.11 |
| compile (Inductor) | 106.69 | 105.40 | 116.87 | **132.44** | **151.44** |

### A.4 TR120 controlled run (Windows host; explicit fallback recorded)

Run: `scripts/tr120/results/tr120_root_cause/20251221_113136`

| Mode | Backend | Mean (ms) | Median (ms) |
| --- | --- | --- | --- |
| `prefill` | eager | **2.49** | **1.98** |
| `prefill` | "compile" (fallback `aot_eager`) | 3.90 | 3.78 |
| `e2e_kv` | eager | **109.67** | **99.08** |
| `e2e_kv` | "compile" (fallback `aot_eager`) | 134.93 | 110.92 |

---

## Appendix B: Figures

Plots are generated artifacts. Paths are relative to this report.

### B.1 TR117 label-only distribution (not a compiler claim)

![tr117_label_only_cdf](../../scripts/tr120/results/tr120_compile_paradox/plots/cdf_latency_overall.png)

![tr117_label_only_quantiles](../../scripts/tr120/results/tr120_compile_paradox/plots/quantiles_overall.png)

### B.2 TR120 controlled run distribution (Inductor+Triton; Docker)

![tr120_triton_prefill_cdf](../../scripts/tr120/results/tr120_root_cause_triton/20251221_173112/prefill/analysis/plots/cdf_latency_overall.png)

![tr120_triton_e2e_cdf](../../scripts/tr120/results/tr120_root_cause_triton/20251221_173112/e2e_kv/analysis/plots/cdf_latency_overall.png)

![tr120_triton_kv_decode_cdf](../../scripts/tr120/results/tr120_root_cause_triton/20251221_173112/kv_decode/analysis/plots/cdf_latency_overall.png)

### B.3 TR120 controlled run distribution (Inductor+Triton; padded prefill ablation)

![tr120_triton_padded_prefill_cdf](../../scripts/tr120/results/tr120_root_cause_triton/20251221_182658/prefill/analysis/plots/cdf_latency_overall.png)

![tr120_triton_padded_kv_decode_cdf](../../scripts/tr120/results/tr120_root_cause_triton/20251221_182658/kv_decode/analysis/plots/cdf_latency_overall.png)

![tr120_triton_padded_e2e_cdf](../../scripts/tr120/results/tr120_root_cause_triton/20251221_182658/e2e_kv/analysis/plots/cdf_latency_overall.png)

### B.4 TR120 controlled run distribution (Inductor+Triton; dynamic prefill ablation)

![tr120_triton_dynamic_prefill_cdf](../../scripts/tr120/results/tr120_root_cause_triton/20251221_181045/prefill/analysis/plots/cdf_latency_overall.png)

### B.5 TR120 controlled run distribution (Windows host fallback; no Triton)

![tr120_windows_fallback_e2e_cdf](../../scripts/tr120/results/tr120_root_cause/20251221_113136/e2e_kv/analysis/plots/cdf_latency_overall.png)

---

## Appendix C: Configs (source of truth for runs)

Configs referenced directly in this report:

- Baseline variable-length (all modes): `scripts/tr120/configs/root_cause.yaml`
- Padded prefill-only: `scripts/tr120/configs/root_cause_padded.yaml`
- Padded prefill + KV decode (all modes): `scripts/tr120/configs/root_cause_padded_kv.yaml`
- Dynamic prefill-only: `scripts/tr120/configs/root_cause_dynamic.yaml`

Key knobs (how to interpret configs):

- `max_new_tokens`: decode length for `kv_decode` and `e2e_kv`
- `tokenization.pad_to_max_length`: enables per-scenario padding for stable shapes
- `torch_compile.dynamic`: enables shape-polymorphic compilation (not a guarantee of "no recompiles")
- `torch_compile.disable_cudagraphs`: disables Inductor cudagraph trees in the runner to avoid decode-loop overwrite hazards

---

## Appendix D: Glossary

- **Compile paradox:** A distribution-level result where a "compiled" label looks better on one aggregate (often mean) but worse on another (often median), typically because of tail behavior or a bimodal fast/slow path.
- **Eager:** Standard PyTorch execution without `torch.compile`.
- **Inductor:** PyTorch's default compilation backend for `torch.compile` that lowers graphs into optimized kernels (often via Triton on GPU).
- **Triton:** A compiler/runtime for custom GPU kernels used by Inductor; its availability can determine whether GPU compilation is possible.
- **Graph break:** A point where the compiler cannot capture a full graph, forcing a fall back to eager or multiple graphs.
- **`unique_graphs`:** Dynamo counter approximating how many distinct graphs were compiled; higher values often indicate shape instability and potential recompilation churn.
- **`recompile_limit`:** A Dynamo safeguard; after too many recompilations, the system can stop compiling and fall back to less-optimized paths.
- **Prefill:** Prompt-processing phase (forward pass over the context).
- **KV-cached decode:** Token-by-token generation using `past_key_values` so each step reuses prior attention keys/values rather than recomputing the full prefix.
- **CUDAGraph trees:** An Inductor CUDA-graph capture mechanism that can speed stable loops but can create output reuse hazards if tensors are accessed after being overwritten by subsequent replays.
