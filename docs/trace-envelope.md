# Observed finite load points

Available since **Chimeraforge 0.69.0**.
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
zero-length output cannot qualify a point. Known supported control/cache
contradictions, changed actual
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

## Whole-fleet campaigns

Since 0.101.0, the explicit fleet mode receives saved native
`trace-fleet-campaign` receipts and an independent original plan/candidate.
It holds all inputs offline and reuses strict native campaign receiving,
per-request SLO qualification, member conditions/cache checks and normalized
whole-execution evidence hashes.

```bash
chimeraforge trace-envelope --fleet --plan original-plan.json \
  --candidate-index "$FLEET_INDEX" --cases fleet-cases.json \
  --policy fleet-policy.json --campaign slow=slow-fleet.json \
  --campaign fast=fast-fleet.json --out fleet-envelope.json --json
```

```python
decision = api.assess_fleet_trace_envelope(
    "original-plan.json", "fleet-cases.json",
    {"slow": "slow-fleet.json", "fast": "fast-fleet.json"},
    policy="fleet-policy.json", candidate_index=fleet_index,
)
```

Fleet cases are a distinct closed schema 1 object. Its exact keys are
`schema_version`, `kind`, `model`, `model_override`, `backend`, `concurrency`,
`expected_executions`, `original_replicas`, `request_timeout_seconds`,
`trace_timeout_seconds`, `cleanup_timeout_seconds`, `campaign_timeout_seconds`,
`ordered_descriptors`, `endpoints`, `routes` and `cells`.

Use `kind="chimeraforge.fleet-trace-envelope-cases"`. The schedule and descriptor
fields follow the serial declaration above. Replace `expected_replicates` with
`expected_executions` for K. Set `original_replicas` to the selected candidate's N.
`model_override` is null when the original campaign used its candidate model,
otherwise it is the exact independently retained override. `model` is the native
served identity after the native Ollama prefix handling. Copy no intent from an
untrusted received campaign.

`endpoints` is the complete ordered native list of exact `{"id", "url"}` objects.
`routes` is the complete canonical ordered list of `{"request_id", "endpoint_id"}`
objects, one for each declared descriptor. IDs/URLs, routing, request order,
prompt or chat commitments, temperature, caps, N, K, concurrency and all timeout
controls remain fixed across cells. Only each declared uniform arrival interval
varies. A native chat descriptor keeps its complete ordered message commitments,
mode and profile. The source remains private and unauthenticated.

Fleet policy is a separate closed schema 1 object with the same five keys as the
serial policy, using `kind="chimeraforge.fleet-trace-envelope-policy"`. Its
`targets` must equal the original saved plan's native SLO targets. Each member's
fixed observed controls are checked before/after and across every execution and
cell. Missing required facts, changed known facts, contradictory caches, changed
ordered actual lengths/cache counts and incompatible active TPOT bases block
eligibility. Unrequired unknown controls remain uncontrolled.

K counts complete global executions. N counts original declared endpoints.
With M scheduled requests, each cell retains K*M global rows and K*N member
views that refer to those rows. For K=2, N=3 and M=6, this is 12 global rows per
cell. Nominal global offered rate is `1 / arrival_interval_seconds`. It is
independent of N and K and describes only the declared cadence.

Each cell retains every execution/member/request, including not-started, failed,
missing, incomplete and zero-assigned members. Native metrics remain known or
unknown as recorded. There are no pooled percentile or synthetic capacity values.
Cell outcomes are `observed_pass`, `breach` or `unknown`. Eligibility requires
complete known native request evidence and the full original member population.
Zero-assigned members block eligibility. Empty or missing evidence cannot pass.

Overall priority is inconclusive/exit 3, then observed breach/exit 1, then
conditional pass/exit 0. Invalid declarations, source selection, controls or
native receiving use exit 2. Known breaches remain visible under exit 3. A local
passing point can remain descriptive with a missing grid cell. Global
compatibility or duplicate-execution blockers disqualify all points. The highest
observed point selects only an eligible declared cell, with no extrapolation.

The distinct `chimeraforge.fleet-trace-envelope-assessment` schema 1 output uses
cell, execution, member and row ordinals. It omits model/endpoint/operator names,
private paths, prompts, messages, native diagnostic bodies and raw metadata
values. Inputs retain exact held-byte hashes and fingerprints. File plan hashes
must match the producer's original source-byte basis. Typed artifacts use their
defensive snapshot basis with no original-file hash. The complete snapshot and
candidate identity are checked in either case. Embedded child hashes describe
their serialized representation, rather than alleged original child files.

The original plan is bounded to 8 MiB, cases to 1 MiB, policy to 64 KiB, each
campaign to 16 MiB and logical campaign occurrences to 32 MiB total. All files
are held once and repeated occurrences are charged. Native link/regular-file
guards apply. Every consumed path, including protected paths from typed inputs,
participates in output alias protection. The complete portable JSON document
must fit 8 MiB before a result is returned, printed or atomically saved. Overflow
refuses the whole document. These byte profiles do not bound total heap usage.

Evidence hashes detect identical normalized native executions under changed
dates, IDs, paths or clock origins. Arrivals and relative timings stay in the
measurement, so consistently rescheduled/resealed copies remain unauthenticated.
The installed consumer uses CPU protocol fixtures for native campaign generation
and verifies that offline API/CLI receiving adds zero backend contacts. This does
not establish inference performance, independent physical devices or capacity.
