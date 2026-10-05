# Saved plans and the Python API

```python
from chimeraforge.api import PlanRequest, plan, load_plan

record = plan(PlanRequest(model_size="3b", allow_network=False))
record.save("plan.json")
saved = load_plan("plan.json")
print(saved.candidate().provenance)
```

The public boundary rejects mistyped, nonfinite and impossible options before
model resolution. `PlanError` represents invalid inputs and unavailable files or
models. `PlanRequest` accepts the shared planner's options, including workload,
hardware, quality, parallelism, cloud and session settings. `allow_network=False`
keeps model resolution offline. An empty candidate list means no feasible plan;
`candidate()` then raises `PlanError`.

The CLI also saves the effective inputs after workload-profile overrides:

```bash
chimeraforge plan --model-size 3b --no-network --json --save plan.json
```

Standard stdout remains the existing candidate array. A saved plan is a distinct
versioned document containing inputs, resolved model specifications, target OS,
candidate provenance, the fingerprint of the fitted corpus actually consumed by the search, timestamp
and producing package version. Heterogeneous fleets are currently refused with
`--save`; the artifact describes one homogeneous search. Nonfinite predictions
are JSON `null`, meaning unknown/unavailable.

The SHA256 fingerprint detects changes to the document. It is **not a signature**
and cannot establish authenticity: anyone can recompute it. Loading checks the
schema, types and fingerprint, and never replans or downloads a model. A snapshot
records the output; it does not guarantee a later recomputation will match moving
remote metadata, local measurement files or contribution records. The producing
version and provenance remain necessary when comparing records.

HF tokens are omitted and URL userinfo/query parameters are removed. Keep local
model identifiers and paths private when sharing a snapshot. The saved artifact
does not establish a calibrated prediction interval or a deployment drift verdict.
