# Saved plans and the Python API

```python
from chimeraforge.api import PlanRequest, plan, load_plan, check_plan

record = plan(PlanRequest(model_size="3b", allow_network=False))
record.save("plan.json")
saved = load_plan("plan.json")
print(saved.candidate().provenance)
print(check_plan(saved).to_dict())
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

New schema-v2 snapshots include replay context version 1. The context binds the
full consumed `ModelSpec` for every target (including registry size-class targets),
raw and plannable GPU facts, target OS, parsed quality scores, corpus identity,
consumed cloud offers, engine-support/policy identities and quarantine contribution
IDs. Corpus identity covers coefficients; separate bindings cover the other
inputs. File receipts hash the bytes that were parsed and record absolute original
paths. No later reread is used to manufacture a consumption receipt. Strict
schema-v1 loading remains supported; missing v1 replay bindings are unverified.

`check_plan(saved)` accepts an artifact or a file path and returns a `PlanCheck`
with a defensive `to_dict()` copy. `chimeraforge check plan.json --json` exposes
the same report. Checks are offline regardless of the saved `allow_network`
option, preserve the artifact, and use the shared planner search. Saved full
geometry and OS remain the replay target; `auto` never probes the current host.
The unified-memory fraction and price multiplier are applied once. Current
canonical pricing is inspected separately and used for repricing unless the
request explicitly supplied its own hourly price. Original external corpus and
quality inputs must remain available at their bound paths; a namesake under a
different working directory does not verify them.

The report separates required components from informational evidence. Candidate
identities include model, quantization, backend, TP, PP, replica count, mode and
platform. Added/removed candidates, rank changes, feasibility transitions,
recommendation identities and modeled deltas retain native units and unknown
`null` values. A current local `resolution_view` observes metadata without
substituting it for saved geometry. Unavailable remote metadata or a registry
approximation is informational unverified; a changed resolved source or geometry
is actionable even when rounded predictions match. No metadata match proves
the identity of currently served weights or an immutable model revision.

Exit 0 means a completed comparison with required components unchanged; exit 1
means changed, expired or unverified required components (or a changed local
resolved identity/recommendation). Exit 2 means malformed input. Cloud snapshots
use the existing 90-day policy: day 90 is valid, day 91 is expired. Plans that did
not consume cloud prices do not inspect or expire them. GPU amortization and
coefficients have no invented expiry threshold. Performance remains informational
unverified: an unchanged modeled result is not a performance acceptance test.
Fingerprints detect edits, including context edits, but cannot authenticate a
snapshot or turn unsigned quarantine data into trusted measurements.
