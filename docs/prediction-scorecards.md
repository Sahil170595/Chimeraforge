# Frozen prediction scorecards

This is an unpublished **0.66.0 candidate** feature; the published CLI is 0.61.0.
Use candidate source or wheels. `score` consumes saved plans and native benchmark
receipts offline, without generating traffic, replanning, refitting or replacing
the saved prediction with current coefficients.

## Declare the population and band

The policy has four required fields and no population or error-band defaults:

| Field | Requirement |
|---|---|
| `plan_fingerprint` | Exact fingerprint of the consumed saved plan |
| `candidate_indices` | Ordered 1-16 unique indices from that plan |
| `expected_receipts_per_index` | Exact matching canonical decimal index keys, each with 1-16 expected receipts |
| `relative_error_band` | Explicit finite nonnegative absolute relative-error band |

Create a policy for candidate 0 with one expected receipt and a chosen 20% band:

```python
import json
from chimeraforge.api import load_plan

saved = load_plan("plan.json")
policy = {
    "plan_fingerprint": saved.to_dict()["fingerprint"],
    "candidate_indices": [0],
    "expected_receipts_per_index": {"0": 1},
    "relative_error_band": 0.20,
}
with open("score-policy.json", "x", encoding="utf-8") as stream:
    json.dump(policy, stream, allow_nan=False)
```

The band and population are caller declarations. Their presence does not establish
external preregistration or authenticated timing. Empty received populations are
valid missing evidence, not a complete result.

```bash
chimeraforge score --plan plan.json --policy score-policy.json --benchmark plan-benchmark.json --out scorecard.json --json
# Supply each saved receipt separately; every one remains represented.
chimeraforge score --plan plan.json --policy score-policy.json --benchmark first.json --benchmark second.json --json
```

The saved plan can also be a verified portable plan-bundle directory. Ordinary
saved plans retain their frozen context declarations; bundles additionally verify
held coefficient/input bytes against producing bindings. Neither path reruns
the planner or reads replacement current coefficients to change predictions.

## Conditional eligibility

Only `base_decode_tps` is scored initially. Each native current `PlanBenchmark`
receipt must bind the original plan fingerprint, candidate index and existing
eight-field identity. The receiver records a new digest over the complete saved
candidate; it does not claim the producer originally recorded that digest.

The scorer recalculates the native sample population and stored aggregate, checks
count/duration arithmetic, and recomputes supported serving bindings from the
frozen candidate. A favorable producer `audit` or `binding` does not establish
eligibility. Malformed fingerprints, structures or native arithmetic are errors.
Valid evidence for another plan/index/identity remains a visible binding mismatch.

Conditional comparability requires:

- Complete native execution, single workload and concurrency one.
- Modeled TP/PP one, zero modeled LoRA adapters and zero modeled CPU offload.
- Full known, correctly typed matching model geometry, quantization, context and
  physical serving GPU facts, with compatible stable before/after engine/model
  controls. Boolean/integer equality cannot turn invalid types into known facts.
- Both native observations must report supported `device="gpu"`. Missing or
  unsupported stable device labels remain ineligible even with complete GPU
  metadata. This is a declared observation, not physical authentication.
- Every actual prompt/output token count matching the frozen modeled lengths.
  An output cap does not establish a returned length.
- Zero modeled prefix-cache hit rate and compatible known native cache evidence.
  Positive cached tokens contradict a reported disabled cache.
- Ollama `server-all-output/decode-duration` rate. Client stream intervals and
  whole-workload token rates cannot qualify a GPU decode prediction.

Optional underlying `execution_engine` observations are checked in both phases.
A supplied known contradiction or drift makes the row a binding mismatch; losing
or gaining an otherwise matching known observation leaves comparability unavailable.
Missing observations in both phases remain explicitly unverified and do not invent
an underlying-engine authentication requirement. Matching declarations also do not
authenticate the underlying execution engine.

Built-in observations do not supply full serving GPU geometry. Real hosted CPU
evidence remains received but ineligible, even with matching rates or client GPU
labels. A capability-shaped complete metadata fixture demonstrates conditional
arithmetic; it does not authenticate physical hardware or the measurement source.
Zero modeled modifiers do not attest that the live server actually applied none.
Live modifiers, immutable weights, independent execution and measurement truth
remain unverified; supported known contradictions make evidence ineligible.

For each eligible receipt, reconstruct every `1000 * output_tokens / eval_ms`
and use their arithmetic mean. The signed relative error is:

```text
(frozen_prediction - recalculated_measurement) / recalculated_measurement
```

Measurement must be positive and finite; prediction and derived error must be
finite. Positive error means overprediction, negative error means underprediction.
A row is within band exactly when `abs(error) <= relative_error_band`.

Fleet throughput, queue p95 latency, TTFT, TPOT and SLO predictions remain unscored
with explicit reasons. A base decode comparison cannot qualify the selected fleet.

## Retain every declared case

The scorecard retains missing, extra, mismatched, unavailable and duplicate evidence
alongside eligible rows. Missing declared observations and received-but-ineligible inputs
have different states. They never disappear into survivor averages. Worst scored
errors remain inspectable, and a comparable breach cannot be hidden by averaging.

Semantic duplicate groups are wholly ineligible with null error. Labels, paths,
timestamps and equivalent supported numeric spellings cannot manufacture a new
observation. This conservative content check does not authenticate shared execution
or independence. A separate unique comparable breach is still a breach.

| Exit | Outcome |
|---|---|
| 0 | `within_band`: every declared receipt is comparable and within the inclusive band, with complete population coverage |
| 1 | `breach`: at least one unique comparable receipt exceeds the band, even alongside missing or ineligible rows |
| 2 | Malformed/forged native structure or arithmetic, unsupported input, unsafe output, or I/O failure |
| 3 | `incomplete`: no comparable breach, but population coverage or comparability is incomplete |

Within-band results are conditional scorecards, not calibration GO, authenticated
hardware/weights, independent replication or scientific qualification. No outcome
modifies planner coefficients, corpus or contributions.

## Python API and outputs

```python
from chimeraforge.api import load_plan, PredictionScorePolicy, score_predictions

saved = load_plan("plan.json")
policy = PredictionScorePolicy(
    plan_fingerprint=saved.to_dict()["fingerprint"],
    candidate_indices=[0],
    expected_receipts_per_index={"0": 1},
    relative_error_band=0.20,
)
result = score_predictions("plan.json", ["plan-benchmark.json"], policy=policy)
result.save("scorecard.json")
print(result.exit_code)
```

`PredictionScorecard` provides defensive `to_dict()`, output validation, atomic
`save()` and `exit_code`. Its `chimeraforge.prediction-scorecard` receiving schema
contains plan/policy commitments, input digests, coverage, every row, worst scored
rows, unscored metrics, assurance/limits and its own fingerprint. Numeric metrics,
coded reasons/states and throughput provenance classes remain visible. Raw request
options, provider messages, producer audits/details, endpoints and paths are omitted.

Inputs are held and bounded: up to 16 declared indices, 1-16 expected receipts each
and 32 MiB total consumed plan/bundle/policy/receipt bytes. Native per-receipt
population and representation limits also apply. Atomic output protects every
consumed file/member and aliases; parser and output failures are categorical.
Original plans, bundles, policies and benchmark bytes are never rewritten.
