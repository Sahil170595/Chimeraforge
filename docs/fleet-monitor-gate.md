# Whole-original-fleet passive SLO acceptance

**Unreleased 0.83.0 source**, including the 0.82 active-connection candidate.
Public installation remains **0.81.0**. This workflow generates no inference
traffic. It evaluates saved native histogram assessments, not raw scrapes or a
new percentile estimate. P95 bucket bounds are **not confidence intervals**.

## Produce and receive

`api.monitor_fleet(saved, request, *, candidate_index=0, stop_event=None,
connections=None)` returns the entire typed `FleetMonitorReport`, retaining
native priority: mismatch5, known SLO breach3, incomplete/unknown4, otherwise0.
Schema2 preserves all original ordered slots, windows, observations and full
bindings. Its new `effective_controls` version1 records canonical endpoints,
requested windows/interval/timeout/concurrency, observation/cleanup allowances,
HTTP request/body limits and resolved targets with their source labels. Runtime
connections, tokens, environment names, TLS paths and guards are not serialized.

```python
from pathlib import Path
from chimeraforge import api

saved = api.load_plan(Path("fleet-plan.json"))
index = next(i for i, row in enumerate(saved.to_dict()["result"]["candidates"])
             if row["backend"] == "vllm" and row["n_agents"] == 3)
request = api.FleetMonitorRequest(
    tuple(api.FleetEndpoint(f"r{i}", f"http://127.0.0.1:{7999 + i}/metrics")
          for i in range(1, 4)), interval=1, windows=2, ttft_slo=500,
)
report = await api.monitor_fleet(saved, request, candidate_index=index)
report.save(Path("candidate-monitor.json"))
received = api.load_fleet_monitor(
    Path("candidate-monitor.json"), saved, candidate_index=index
)
assert received.exit_code == report.exit_code
```

The receiver holds the independently supplied original plan and validates source
fingerprint/selection, original N, model/backend, canonical unique IDs/URLs, native
metric contracts, finite assessments, prefix counts, complete bindings, budgets,
cleanup and derived native outcomes. A partial final window may lack after
metadata. Declared producer versions are retained in pure binding reconstruction.
Recognizable in-limit schema1 remains loadable; its missing requested controls
stay unavailable. Durations/prefix counts never fill them in.

`json_bytes()`, `to_dict()` and `save()` admit the **complete** exact escaped,
indented UTF-8 JSON plus LF against **8 MiB**, refusing without truncation. The
encoder traverses shallow allowlisted public fields before recursive copies;
admitted bytes are reused at file/stdout sinks. This bounds exported traversal
and materialization, not prior native construction, scalar encoder allocation,
total heap, HTTP buffers or runtime. Native HTTP/body limits are separate.
An in-limit compact legacy file can load fully while its pretty export refuses.
Loaded typed inputs compare current public state with freshly decoded held bytes
before reuse; nested mutation cannot use a stale snapshot. Native root slots stay
a Python tuple; native nested list/dict conventions remain unchanged.

`monitor-fleet --out receipt.json --json --prometheus metrics.prom` preflights JSON
before either file. Oversize emits only a bounded export-error diagnostic, not a
normal monitor receipt, writes neither sink and exits5/3 for known native
mismatch/breach, otherwise4. Text/Prometheus-only paths use typed native state.
Output guards cover actually held plans and runtime TLS inputs, including
effective default trust, and recheck before writing.

## Declare and evaluate the policy

`api.FleetMonitorGatePolicy(original_replicas, endpoint_ids, windows, metrics,
baseline, candidate, schema_version=1)` is closed. Each arm has exactly `plan`
(`fingerprint`, `candidate_index`) and `controls` (the full effective-controls
schema). Ordered IDs/windows agree with the common population. Each requested
`ttft`/`tpot` has exactly `minimum_samples`, a positive integer. Every requested
target needs a rule. Targets **and source labels are committed per arm**.
Declare intent from actual plans/endpoints/requests before observation; the
policy is not authenticated preregistration. The regenerable native consumer
below constructs complete policy objects and exercises both public entrypoints.

```python
decision = api.gate_fleet_monitors(
    baseline_receipt, candidate_receipt,
    baseline_plan=Path("baseline-plan.json"),
    candidate_plan=Path("candidate-plan.json"),
    policy=Path("fleet-monitor-policy.json"),
)
api.write_fleet_monitor_gate(
    decision, out=Path("decision.json"), junit=Path("decision.xml")
)
```

```bash
chimeraforge gate --kind fleet-monitor --baseline baseline-monitor.json --candidate candidate-monitor.json --baseline-plan baseline-plan.json --candidate-plan candidate-plan.json --policy fleet-monitor-policy.json --out decision.json --junit decision.xml --json
```

Both arms need complete original population, requested controls/windows, matched
required identity, no known configuration contradiction, determinate requested
metrics meeting minimum samples, coherent metadata brackets and completed native
observation/cleanup. Configuration **unverified** is normal and permitted.
Equivalent window payloads remain ineligible after endpoint/label or equivalent
real spelling changes; a digest does not authenticate independent traffic.

- **3 inconclusive:** any incomplete, legacy, unavailable, mismatched, copied or
  cancelled evidence takes precedence over a known candidate breach.
- **1 breach:** eligible candidate native evidence breaches a requested SLO.
- **0 conditional pass:** eligible candidate meets every requested SLO.
- **2 error:** malformed/unsafe/unavailable/over-limit input or output. An
  error-only export diagnostic cannot produce a normal gate/JUnit artifact.

Baseline breaches remain supporting evidence, not candidate failures. Native
upper <= target passes; lower >= target breaches; straddling/unavailable bounds
remain unknown. A null infinite upper can still establish breach from its lower
bound. SGLang ITL never substitutes for TPOT. No relative fractions, pooling,
averaged P95, causal improvement or confidence interval is computed.

JUnit contains population and every declared arm/member/requested-window/
required-metric case, including missing prefixes and unmatched actual members.
Cells are the union of policy declarations and each actual member's requested
windows (observed windows only for legacy), not a cross-product of unrelated IDs
and window counts. Extra actual windows for common IDs remain visible.
Inconclusive decisions produce errors; eligible candidate breaches failures.
Baseline cases identify their supporting role. Known native adverse outcomes
remain visible. The gate projection retains hashes, source/producer controls and
outcomes, every original member/window/metric, and binding/bracket states.
Repeated raw metadata stays in the validated hashed monitor inputs.

Exact JSON and escaped JUnit are bounded before either per-file atomic write.
Outputs cannot alias held reports, original plans, policy, inherited runtime
inputs or each other, including native file identity. This is not a two-file
transaction: a later filesystem error can leave the earlier output.

Receipts contain declared URLs and private model/plan intent; treat them like
source plans. Consistency does not attest raw histogram/reset/series selection,
fresh traffic, cache/workload distribution, source authenticity, physical
processes/GPUs, weights, actual closure, engines, capacity or scientific results.
See the [actual regeneration command and aggregate protocol observations](../validation/2026-10-30-fleet-monitor-gate/README.md).
