# Observed finite load points

This is the unreleased 0.69.0 candidate. Published 0.66.0 does not include it.
The receiver assesses whole saved serial campaigns offline; it never generates
traffic, loads a model, replaces failures or interpolates between cells.

Save a closed declaration as `cases.json`. Replace the example commitments with
the exact ordered descriptors from your campaigns, excluding only arrivals:

```json
{
  "schema_version": 1,
  "kind": "chimeraforge.trace-envelope-cases",
  "model": "served-model",
  "backend": "ollama",
  "concurrency": 1,
  "expected_replicates": 3,
  "request_timeout_seconds": 300,
  "trace_timeout_seconds": 600,
  "campaign_timeout_seconds": 1800,
  "ordered_descriptors": [
    {"request_id": "first", "prompt_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "prompt_bytes": 8, "max_output_tokens": 16},
    {"request_id": "second", "prompt_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "prompt_bytes": 9, "max_output_tokens": 16}
  ],
  "cells": [
    {"name": "slow", "arrival_interval_seconds": 1},
    {"name": "fast", "arrival_interval_seconds": 0.5}
  ]
}
```

Each campaign must use the declared serving identity, concurrency, timeouts,
replica count and ordered commitments. Cell `i` schedules request `j` at
`float(j) * float(arrival_interval_seconds)`. Only four units of floating-point
roundoff are accepted when comparing observed offsets; native values are retained.
The last scheduled arrival must precede the trace timeout, and the reciprocal
nominal rate must be finite. At least two requests are required; intervals and
nonempty cell names must be unique. Names may contain Unicode and have at most
80 characters. The private workload digest is retained by each campaign; prompt
commitments alone cannot reconstruct or authenticate the original private text.

Save an explicit closed policy as `envelope-policy.json`:

```json
{
  "schema_version": 1,
  "kind": "chimeraforge.trace-envelope-policy",
  "targets": {"latency_ms": 2000, "first_output_ms": 500, "tpot_ms": 50},
  "fixed_controls": {"device": "cpu"},
  "require_cache_evidence": false
}
```

All three target keys are required, with positive finite values or `null`; at
least one must be active. Each supplied campaign must record exactly those
targets. Latency includes client queueing, first-output time uses the native
client basis, and TPOT is a per-request mean rather than individual-token latency.
Different known mean-timing bases cannot rank together when TPOT is active.
Fixed controls use the existing trace gate's supported observed facts. Required
unknown facts block the affected cell. Unrequired unknown facts remain explicitly
uncontrolled. Declaring an expectation does not prove it was applied.

```bash
chimeraforge trace-envelope --cases cases.json --policy envelope-policy.json --campaign slow=slow-campaign.json --campaign fast=fast-campaign.json --out envelope.json --json
```

```python
from chimeraforge import api

decision = api.assess_trace_envelope(
    "cases.json",
    {"slow": "slow-campaign.json", "fast": "fast-campaign.json"},
    policy="envelope-policy.json",
)
decision.save("envelope.json")
report = decision.to_dict()
print(report["highest_observed_passing"])
```

The result is defensive `RegressionGate`. The public API also accepts JSON
declarations and typed `TraceCampaign` objects. Every supplied native child passes
the strict campaign receiver. Missing mapping entries are retained as named
missing cells with every expected replica slot. Unknown names, duplicate CLI
assignments, unreadable or malformed supplied sources and case/campaign assignment
disagreements are invalid; they do not become missing measurements.
The CLI splits each assignment at the first `=`: cell names supplied this way
must exclude `=`, while paths may contain it. Use the Python API mapping for
declarations whose cell names contain `=`.

Each cell separately records execution state, observed pass/breach/unavailable,
eligibility blockers and every original replica. Every request in every replica
must satisfy every active target. Averaging successful replicas cannot qualify a
failed population. A cell also needs an observed native clock origin and positive
actual prompt/output token counts; completed requests with unavailable timing or
zero-length output cannot qualify a point. Known supported control/cache contradictions, changed actual
token lengths, differing active TPOT bases or duplicate execution payloads prevent
a ranked point across the envelope. Both before/after phases and all replicas are
compared: an unknown observation cannot hide a known conflict elsewhere.

`highest_observed_passing` names the eligible complete passing cell with the
largest `1 / arrival_interval_seconds`. This is a finite observed nominal cadence,
not a capacity bound or achieved throughput. A missing higher cell may leave a
lower observed point visible, while overall evidence remains incomplete. Lower
breaches are retained even if a higher cell passed; no monotonic curve is assumed.

| Exit | Meaning |
| --- | --- |
| 0 | Complete, compatible declared evidence; every cell passed conditionally |
| 1 | Complete, compatible evidence contains a known SLO breach |
| 2 | Malformed input, assignment or output |
| 3 | Incomplete or incompatible evidence; known breaches remain visible |

Inputs are held once: cases are bounded to 1 MiB, policy to 64 KiB, each campaign
to 16 MiB and all declared campaign occurrences to 32 MiB. Reusing a cached path
still charges each declared occurrence before cloning it. These are separate
input budgets, not a combined transport or output-size bound. At most 16 cells,
1–16 replicas per campaign and the native request limits apply; each campaign
contains at most 4096 request/replica slots. Output protects cases, policy, every
campaign source and private paths carried by typed campaigns, including aliases.

Evidence hashes catch unchanged normalized native payloads despite relabelled
IDs, timestamps, clock origins or signed zero. Schedule and relative timings
remain part of the measurement; consistently rescheduled and resealed copies
cannot be authenticated or excluded. Digests do not prove preregistration time,
private prompts, independent execution, physical hardware, served weights, cold
caches, deployment, planner calibration or scientific GO.
