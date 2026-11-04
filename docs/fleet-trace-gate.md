# Original-fleet regression gate

Available since **Chimeraforge 0.80.0**.
This gate consumes one complete [original-fleet trace](fleet-trace.md) per arm.
It does not execute requests or create independent replications.

```bash
chimeraforge gate --kind fleet-trace --baseline baseline-fleet.json \
  --candidate candidate-fleet.json --policy fleet-policy.json \
  --out decision.json --junit fleet-gate.xml --json
```

Declare the policy before collecting the executions. Each arm is one whole
execution, so `trace.expected_replicates` must be 1 regardless of endpoint N.
Repeat `--baseline` or `--candidate` is refused. Other gate kinds retain their
existing behavior; `--junit` is available only for `--kind fleet-trace`.

## Closed policy

The exact top-level fields are `trace`, `population`, `baseline`, `candidate`.
Unknown fields and missing commitments are refused. A policy can be a JSON file,
dictionary, or `api.FleetTraceGatePolicy`; no eligibility is inferred from the
most favorable receipts. These keys describe the schema; replace the placeholders
with declarations for the intended original saved plan, work and endpoint layout:

```json
{
  "trace": {
    "rules": {"latency_p95_ms": 0.05},
    "expected_replicates": 1,
    "pairing": "ordered",
    "fixed_controls": {"version": "YOUR-EXPECTED-VERSION"},
    "baseline_treatment": {},
    "candidate_treatment": {},
    "require_cache_evidence": true
  },
  "population": {
    "original_replicas": 3,
    "endpoint_ids": ["member-1", "member-2", "member-3"],
    "workload_sha256": "<canonical workload SHA256>",
    "ordered_descriptors_sha256": "<digest of ordered native request descriptors>",
    "routes_sha256": "<canonical ordered routes SHA256>",
    "minimum_requests_per_slot": 1,
    "controls": {
      "output_cap_tokens": 128,
      "concurrency": 3,
      "request_timeout_seconds": 300,
      "trace_timeout_seconds": 600,
      "cleanup_timeout_seconds": 2,
      "targets": {"latency_ms": 10000, "first_output_ms": null, "tpot_ms": null},
      "replica_scope": "declared_member",
      "declared_original_replicas": 3,
      "physical_independence": "unverified"
    }
  },
  "baseline": {
    "plan": {
      "fingerprint": "<original plan fingerprint>",
      "raw_sha256": "<held source SHA256, or explicit null for object origin>",
      "candidate_index": 0,
      "candidate_sha256": "<selected candidate digest>",
      "served_model": "YOUR-MODEL",
      "model_override": null
    },
    "backend": "vllm",
    "endpoints": [
      {"id": "member-1", "url": "https://first.example"},
      {"id": "member-2", "url": "https://second.example"},
      {"id": "member-3", "url": "https://third.example"}
    ]
  },
  "candidate": "<same closed arm object, with its own declared source and endpoints>"
}
```

`candidate` must be an object with exactly the same fields as `baseline`, not the
placeholder string above. Nullable `raw_sha256` and `model_override` are explicit
expectations, not wildcards. The complete original snapshot fingerprint, selected
candidate hash/index, alias and backend bind each arm separately. Endpoints are
canonical direct HTTP(S) URLs in the exact logical-ID order. Their URLs may differ
between arms when independently declared; the ID order and routed population may
not. `original_replicas` is 1..16. Every original member must meet the positive
declared minimum (default 1, maximum 1024); a valid zero-assigned trace is ineligible.

The exact common controls shown above, ordered descriptors, workload and routes
must match both arms. `trace` reuses the native [trace policy](trace-regression-gate.md)
rules and observed conditions. Rules are `goodput_rps`, `latency_p95_ms`,
`first_output_p95_ms`, `tpot_p95_ms`; fractional thresholds are finite in [0,1).

## Receiving, eligibility and arithmetic

The strict original-fleet receiver rederives source selection, headers, routes,
slots, counts, bindings, timing and SLO facts before comparison. Both declared
receipts together must fit **32 MiB**, plus a separate **64 KiB** policy. A cached
same-path input is read once and charged twice. Each original-fleet receipt retains
its existing portable 32 MiB writer admission and nested native 8 MiB projection
limit. File SHA/size describe held outer bytes; object SHA/size describe the
serialized defensive snapshot, not original source bytes.

Required backend/model identity is checked before and after on every member.
Known binding contradictions, failed/incomplete execution or cleanup, inactive
members, required missing/drifting conditions, cache contradictions/required
unknowns and changed undeclared cache counts block eligibility. Unrequired unknown
facts remain visible as uncontrolled. Cache treatments require paired explicit
expectations; an empty member never supplies cache or token evidence.

A valid receipt with a different original population remains inconclusive (3),
not malformed. `inputs.baseline.slots` and `inputs.candidate.slots` each retain
every original member's state, error, row indices, before/after facts, bindings
and SLOs. Paired comparisons do not replace or drop unmatched arm evidence.

All rows share the native global denominator and common horizon. Percentiles use
native full-population linear interpolation, never averaged member percentiles.
Incomplete rows forbid survivor metrics. Goodput consumes saved SLOs; TPOT basis
homogeneity is checked whenever TPOT is consumed, including TPOT-qualified goodput.
Higher-is-better fraction is `(baseline-candidate)/baseline`; lower-is-better is
`(candidate-baseline)/baseline`. Baseline must be positive and bases compatible.
A breach requires **strictly greater** than the threshold; equality passes.

An evidence fingerprint detects complete semantic copies despite request/member
labels, URLs, declaration order, equivalent supported real spellings or signed
zero. It retains original N, all rows and the sorted member multiset, including
membership and supported before/after facts. Matching copies are inconclusive;
different fingerprints do not authenticate independent executions or true inputs.

| Exit | Meaning |
|---|---|
| 0 | Conditional comparison passed all required evidence and declared thresholds |
| 1 | Eligible comparison has a known global metric regression |
| 2 | Malformed, unsafe, over-limit input/output or operational output failure |
| 3 | Any required evidence blocker, even when known arithmetic breaches are retained |

Producer execution, configuration, SLO and cleanup remain separate in the decision.
The existing native CPU-versus-modeled-GPU canary therefore yields gate 3, preserving
its completed rows and known mismatch rather than forcing a GPU pass.

## Python API and output ownership

```python
from chimeraforge import api

decision = api.gate_fleet_traces(
    "baseline-fleet.json", "candidate-fleet.json", policy="fleet-policy.json"
)
api.write_fleet_trace_gate(decision, out="decision.json", junit="fleet-gate.xml")
print(decision.to_dict()["outcome"])
```

`gate_fleet_traces` is synchronous and accepts a `FleetTraceReplay`, dictionary or
file per arm. The writer takes one defensive finalized decision and materializes
both bounded projections before writing. JSON is capped at 32 MiB, escaped JUnit
at 64 KiB. Every destination is checked against all actually held input/policy and
typed inherited paths, and against the other output, by resolved path/file identity.
Unread original source or TLS paths are not inferred from report strings.

JUnit contains one population case plus each declared global metric. Inconclusive
means errors for every case, regression means metric failures, and pass means no
failures/errors. Known arithmetic stays in metric properties under inconclusive;
JUnit omits raw plan intent, endpoint URLs and private metadata. Each output uses a
native atomic replacement; this is **not a two-file transaction**. A later file
failure can leave the earlier output written and returns 2, without rollback.

The full decision includes saved-plan commitments and declared endpoint URLs and
may carry private model identifiers or plan intent. Treat it like its source plan
when sharing. Runtime connection credentials remain omitted. Neither hashes,
metadata, distinct URLs nor this gate authenticate weights, physical independence,
GPU execution, cold runs, capacity or scientific significance.

The [regenerable functional record](../validation/2026-10-25-fleet-trace-gate/README.md)
separates synthetic source controls from exact-head installed and native acceptance.
