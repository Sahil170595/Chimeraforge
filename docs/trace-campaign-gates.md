# Whole-campaign regression gates

This is the unreleased 0.67.0 candidate. The published 0.66.0 package does not
include this interface; use the candidate checkout until its release is cut.

Compare two saved serial campaigns without extracting successful replicas or
discarding unstarted ones. The operation is offline: it does not contact an
endpoint, resolve a model or execute replacement measurements.

```json
{
  "rules": {"goodput_rps": 0.05, "latency_p95_ms": 0.10},
  "expected_replicates": 3,
  "fixed_controls": {"device": "cpu"},
  "require_cache_evidence": true
}
```

Save that declaration as `campaign-policy.json` before examining the comparison.
Supply exactly one whole campaign per arm:

```bash
chimeraforge gate --kind trace-campaign --baseline baseline-campaign.json --candidate candidate-campaign.json --policy campaign-policy.json --out campaign-gate.json --json
```

```python
from chimeraforge import api

decision = api.gate_trace_campaigns(
    "baseline-campaign.json",
    "candidate-campaign.json",
    policy=api.TraceGatePolicy(
        rules={"latency_p95_ms": 0.10},
        expected_replicates=3,
        fixed_controls={"device": "cpu"},
    ),
)
decision.save("campaign-gate.json")
print(decision.to_dict()["outcome"])
```

The receiver validates the outer campaign, its frozen manifest and every retained
native child. Fingerprints, declared counts, unique ordered indices, workload
commitments, descriptors, applied controls and serial chronology must agree.
Observed native replay intervals must fit their enclosing campaign slots in the
producer's shared monotonic clock domain, allowing only floating-point roundoff.
Deleting a failed or unstarted slot and recomputing only the outer fingerprint
does not make an acceptable population. Native child raw-file hashes remain
`null`: the producer replayed frozen typed requests, while the manifest separately
commits the original workload file when one was supplied.

Every declared replica remains represented. An incomplete execution, missing
receipt, stopped population, unsupported required observation, changed workload
or actual token lengths, known control/cache contradiction, or copied execution
cannot yield a conditional pass. Semantic duplicate detection covers both arms
and every replica, including copies relabeled with timestamps or request IDs.
Fingerprints establish content consistency, not independent execution.
Equivalent real-valued spellings, including signed zero, cannot disguise a copy.

For paired native children, the existing trace gate recomputes queue-inclusive
metrics and preserves their timing bases. Goodput requires observed requested
targets; a zero baseline cannot establish a relative regression. Per-request mean
TPOT remains distinct from individual-token latency. A campaign whose executions
all completed can still contain SLO breaches. A final completed replica may also
coexist with a caller-stop or deadline observation when no replicas remain.

Exit codes are `0` conditional policy pass, `1` comparable regression, `2` malformed
input/output, and `3` inconclusive evidence. Incomplete evidence takes precedence
over an overall favorable or regression decision; known breach arithmetic is
retained for inspection. No survivor averaging or automatic retry repairs the
declared population.

Inputs are held once under byte limits, including a 32 MiB total campaign budget.
Producer request/replica limits do not guarantee that a serialized artifact fits
the receiver budget. Output protects both consumed campaigns, the policy and
private workload paths carried by typed campaign objects, including aliases.

The decision does not authenticate preregistration time, original private prompts,
physical hosts, GPU geometry, served weights, cold caches or independent runs. It
does not validate a planner coefficient, fleet deployment or scientific GO.
