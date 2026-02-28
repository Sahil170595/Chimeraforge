# TR117-TR122 Decision Whitepaper (Revised Draft v1.1)
## Executive guidance for deployment leaders

Project: Banterhearts LLM Performance Research
Date: 2025-12-26
Version: 1.1 (editorial tightening)
Audience: Decision makers, product leaders, ops leaders
Scope: TR117, TR118_v2.2, TR119v1, TR120, TR121v1, TR122
Primary source: `PublishReady/reports/Technical_Report_Conclusive_117-122.md`

---

## Abstract

This whitepaper distills TR117-TR122 into deployment policy for local-first LLM inference on a fixed hardware baseline. The program answers one central question:

How do we convert performance measurements into safe operational policy without false attribution or false precision?

Outcome: a reusable decision method. Tokens/sec drives cost and capacity only when the measurement boundary is explicit, inference phases are separated (prefill vs decode), and instrumentation limits are respected. No universal scaling claims are made; results are bound to the measured stack.

---

## Boundary conditions (do not skip)

This guidance is valid only under the measured boundary:

- Fixed hardware class (same GPU/CPU/memory tier)
- Same inference stack (driver/runtime/compiler versions)
- Same measurement definitions (phase split + end-to-end boundaries)
- Same instrumentation cadence (notably energy sampling)

If any of these change, re-run the core scenario matrix and re-validate artifacts.

---

## Executive summary: five decisions you can ship now

1. Default backend (decode-heavy): `onnxruntime-gpu`
2. Route by workload shape: batch-heavy prefill can invert winners
3. Compile policy: compile prefill only, and only with compiler-real evidence + stable shapes
4. Warmup policy: cold-start is a separate regime -> warm pools + pre-routing warmups
5. Energy reporting policy: per-event energy requires valid sampling coverage; otherwise label as `no_data`

If you follow these rules, you avoid the common deployment failures: wrong backend, wrong phase, wrong attribution, false precision.

---

## Definitions (one-time)

- Prefill: prompt ingestion / KV cache construction
- Decode: token generation loop reusing KV (often the dominant time at moderate+ generation lengths)
- Cold-start: first-run / post-idle behavior where caches/allocations/compilation/warm kernels are not resident
- Steady-state: warmed execution with stable caches and runtime state

---

## Decision matrix (one-glance policy)

| Condition (workload shape) | Operational classification | Default backend | Compile policy | Warmup policy |
| --- | --- | --- | --- | --- |
| gen_tokens >= 64 or decode_fraction > 0.9 | Decode-heavy | onnxruntime-gpu | Keep decode eager unless a measured decode win exists in your stack | Maintain warm pools; pre-warm per model tier |
| batch > 1 and gen_tokens minimal | Prefill-heavy | Route by measured prefill winner (can invert) | Compile prefill only if stable shapes + compiler-real evidence | Warmup the prefill path for expected batch shapes |
| Mixed / uncertain | Default-safe | onnxruntime-gpu (unless your matrix contradicts) | No compile by default | Track cold-start separately; do not average into steady-state |

---

## Key findings (decision-grade)

- Decode dominates end-to-end at gen >= 64; prefill-only logic is unsafe for capacity planning.
- Backend labels are not evidence; label-only compile claims were false in TR117 and corrected via TR120 attribution audit.
- Throughput drives cost under typical shadow pricing; energy is secondary unless you are power-constrained or energy-priced.
- Scaling is regime-dependent; small-model GPU latency can be dominated by overhead and depth effects.
- 100ms polling cannot attribute sub-100ms events; short prefill energy frequently becomes no_data without sufficient samples.

---

## Operational recommendations (policy statements)

### Backend selection

- Policy: Default to `onnxruntime-gpu` for decode-heavy traffic.
- Policy: Maintain a measured scenario matrix; route prefill-heavy cases by actual prefill winner.

### Compile

- Policy: Compile prefill only.
- Policy gate: Enable compile only if you have compiler-real evidence (runtime proof, not labels) and stable shapes.
- Policy: Keep decode eager unless you can demonstrate a decode win in your stack without shifting tail latency risk.

### Warmup / cold-start

- Policy: Treat cold-start as its own regime and track it as an SLO dimension.
- Policy: Use warm pools for large models and phase-specific warmups aligned to routing paths.

### Energy reporting

- Policy gate: Report per-event energy only when there are >= 2 in-window samples; otherwise label as no_data.
- Policy: Report energy for macro windows (batch/regime) when event attribution is below sampling resolution.

---

## Economic impact (what changes your spend)

Tokens/sec is the budget lever:

- seconds_per_1M = 1e6 / tokens_per_s
- usd_per_1M = (seconds_per_1M / 3600) * usd_per_hour

Implications:

- Backend choice is multiplicative: cheapest generate path can be ~3x cheaper than the most expensive GPU alternative within this boundary.
- Model tiering becomes mandatory at scale: ~7B can be ~3x cheaper than ~20B at fixed decode length in this regime.
- Capacity numbers are lower bounds: apply burst factors from real traffic distributions (p95/p99 mix, concurrency, long-tail prompts).

---

## Implementation plan (30-day view)

Days 1-7: reproduce + validate

- Re-run the core scenario matrix on your hardware + workload mix.
- Validate artifacts to TR118 standard; capture manifests.

Days 8-14: translate into planning numbers

- Recompute cost per token and capacity with your own pricing inputs.
- If compiling: verify compiler-real evidence and identify stable shapes.

Days 15-30: enforce policies

- Ship routing + compile policies based on phase splits.
- Roll out warmup + cold-start monitoring; set SLO alarms and dashboards.
- Add re-run required triggers to change management.

---

## Risks, limitations, invalidation triggers

Limitations

- Single hardware baseline; not portable across hardware classes without re-run.
- $/token values are planning proxies (shadow prices), not exact TCO.
- Quality is not measured here; pair cost decisions with quality evaluation.
- Energy attribution is valid only when sampling coverage supports it.

Invalidates guidance

- Driver/compiler/runtime/model upgrades without rerun
- Workload mix shifts (prompt/gen/batch) without reweighting
- Instrumentation cadence changes or energy pipeline changes

---

## Evidence anchors (audit-ready)

- Cost per 1M tokens + scenario inversions: `scripts/tr119/results/tr119_matrix/processed/cost_energy_summary.json`
- Decode dominance at gen_tokens = 64: `scripts/tr121/results/tr121_decode_sweep/20251224_002955/gen_64/metrics.csv`
- Compile attribution audit: `scripts/tr120/results/tr120_compile_paradox/processed/summary_overall.csv`
- Warmup ratio distribution: `scripts/tr121/results/20251223_230615/analysis/warmup_effect.csv`
- Energy gating outcomes: `scripts/tr122/results/20251225_190043/generation_events.jsonl`

---

## References

- Conclusive report: `PublishReady/reports/Technical_Report_Conclusive_117-122.md`
- TR117: `PublishReady/reports/Technical_Report_117.md`
- TR118_v2.2: `PublishReady/reports/Technical_Report_118_v2.2.md`
- TR119v1: `PublishReady/reports/Technical_Report_119v1.md`
- TR120: `PublishReady/reports/Technical_Report_120.md`
- TR121v1: `PublishReady/reports/Technical_Report_121v1.md`
- TR122: `PublishReady/reports/Technical_Report_122.md`

---

## Optional upgrades (if you want it to feel board-ready)

- Add a 1-page Decision Card at the front (matrix + three gates + rerun triggers).
- Add a single diagram: traffic -> classify -> route backend -> warmup regime -> measure and audit.
- Add a Change Control clause: any upgrade triggers rerun of Scenario Set S0-S3.
