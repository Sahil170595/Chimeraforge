# TR120: Compile Paradox Investigation (with KV-Cache Decode Subtask)

**Status:** In progress (TR120.A distribution analysis + report complete; profiler pending)  
**Target:** Week of 2025-12-23  
**Primary Depends On:** TR117 (Tier-3 benchmark artifacts)  
**Secondary Depends On:** TR118/TR119 (optional; shared inference/cost infrastructure)

## Summary

TR120 answers a production-critical question discovered in TR117:

> Why does `torch.compile()` improve mean latency but degrade median latency for GPU inference, and what should we ship in production?

Important correction (root-cause audit):

- In this repository, the TR117 backend label `transformers-gpu-compile` did **not** invoke `torch.compile()`. TR120 therefore includes an explicit, controlled runner to make compiler behavior observable and artifact-backed.

TR120 also bundles a closely related decode-validation subtask:

> Validate decode performance under KV-cache generation (`use_cache=True`) to ensure conclusions transfer to real serving decode.

## Subtasks (TR120.A / TR120.B)

### TR120.A - Compile paradox investigation (primary)

**Research question:** Why does `torch.compile()` improve mean latency but degrade median latency? Can we mitigate it?

**Scope:**

- Distribution-first analysis (p50/p90/p95/p99, not just means)
- Profiler trace analysis (`torch.profiler`, Nsight Systems) for compiled vs eager
- Kernel-level breakdown: where compile helps vs hurts
- Hypothesis testing: warmup effects, kernel launch overhead, cache effects, graph breaks
- Production strategies:
  - hybrid compile policy (compile for batch > 2, eager for single)
  - adaptive routing (profile-guided selection by shape)

### TR120.B - KV-cached decode study (subtask)

**Research question:** How do backend rankings change when generate uses KV-cache (`use_cache=True`) rather than uncached recompute?

**Why it is part of TR120:** TR117/TR119 use an uncached decode loop as a stress test; production decode is KV-cached. This subtask prevents a common reviewer/production critique ("you measured the wrong decode regime").

**Scope:**

- Re-run decode benchmarks with KV-cache enabled (at minimum for PyTorch eager vs `torch.compile()`)
- Measure TTFT, decode tok/s, and stability across shapes
- Compare to uncached results and quantify the delta
- Determine whether the compile paradox persists in KV-cached decode

## Key gaps from TR117 (what TR120 fixes)

- Compile paradox observed, not explained
- No profiler evidence (root cause unverified)
- No production routing strategy tested
- Decode regime mismatch: uncached stress test vs KV-cached production decode

## Expected deliverables

1. Root cause analysis with profiler evidence (TR120.A)
2. Production decision rule (eager vs compile vs hybrid) by workload shape (TR120.A)
3. KV-cached decode validation and whether it changes the recommendation (TR120.B)
4. Publish-ready technical report with explicit methodology and artifacts

## Repository layout

- `scripts/tr120/configs/` - experiment configs (added as TR120 execution begins)
- `scripts/tr120/results/` - TR120 artifacts (processed tables + plots + traces)
- `PublishReady/reports/Technical_Report_120.md` - definitive TR120 report (publish-ready)

## Quick start

Label-only analysis (TR117 artifacts):

```bash
python scripts/tr120/analyze_compile_paradox.py --metrics-csv results/tr117_tier3/metrics.csv --out-dir scripts/tr120/results/tr120_compile_paradox
```

Controlled reproduction (explicit eager vs compile):

- Windows host (no Triton): runs, but Inductor GPU compile will fall back (recorded in artifacts).
- Inductor+Triton (recommended): run in the Triton Docker image:

```bash
docker run --rm --gpus all -v "${PWD}:/workspace" -w /workspace nvcr.io/nvidia/tritonserver:25.08-trtllm-python-py3 \
  python3 scripts/tr120/run_root_cause.py --config scripts/tr120/configs/root_cause.yaml --out-root scripts/tr120/results/tr120_root_cause_triton
```

Configs:

- `scripts/tr120/configs/root_cause.yaml`: baseline variable-length run (prefill + kv_decode + e2e_kv).
- `scripts/tr120/configs/root_cause_padded.yaml`: padded-shape ablation (prefill only; fastest to run).
- `scripts/tr120/configs/root_cause_padded_kv.yaml`: padded-shape ablation including KV decode + end-to-end.
- `scripts/tr120/configs/root_cause_dynamic.yaml`: `dynamic=True` ablation (prefill only).
- `scripts/tr120/configs/root_cause_prefill_only.yaml`: prefill-only timing validation (also records CUDA-event timing and compiler evidence).

Notes on artifacts:

- Controlled runs write per-mode `metrics.csv`; when CUDA events are available, `cuda_event_ms` is recorded alongside wall-clock `latency_ms`.
- Compiler evidence is summarized in `compiler_evidence.json` at the run root (compact `torch._dynamo.explain(...)` fields).

## Timeline

- Week 1: Distribution analysis + profiler setup + trace collection
- Week 2: Kernel analysis + hypothesis testing
- Week 3: Hybrid strategy implementation + KV-cache decode study
- Week 4: Report writing + reproducibility hardening

**Start date:** TBD
