# Queue-inclusive trace regression gates

`gate --kind trace` and `api.gate_traces` apply a predeclared conditional
engineering policy to saved `trace` receipts. They execute no model requests.
This is an **unpublished 0.63.0 candidate**, requiring candidate source or wheel.
The public installation remains `chimeraforge==0.61.0`; 0.62.0 is the preceding
native streaming trace candidate. `gate` without `--kind` selects the existing
[benchmark gate](regression-gate.md).

Save `trace-policy.json` before collecting the compared executions:

```json
{
  "rules": {"goodput_rps": 0.05, "latency_p95_ms": 0.10},
  "expected_replicates": 2,
  "pairing": "ordered",
  "fixed_controls": {"backend": "ollama", "device": "cpu"},
  "baseline_treatment": {},
  "candidate_treatment": {},
  "require_cache_evidence": true
}
```

```bash
chimeraforge gate --kind trace --baseline baseline-1.json --baseline baseline-2.json --candidate candidate-1.json --candidate candidate-2.json --policy trace-policy.json --out trace-gate.json --json
```

Each arm declares 1–16 receipts in execution order. Every receipt is validated
and retained, including extra unpaired executions. Both arms must contain
exactly `expected_replicates`. All rules on all pairs must pass; a fast pair
cannot hide a slow or incomplete pair. Nonempty rules contain finite maximum
fractional degradation in `[0,1)`. Unknown fields/conditions are malformed.

| Rule | Full-population value | Direction |
|---|---|---|
| `goodput_rps` | Requests passing every requested target / `max(drained elapsed,last planned arrival)` seconds | Higher |
| `latency_p95_ms` | Scheduled arrival to terminal, including scheduler/semaphore queue | Lower |
| `first_output_p95_ms` | Scheduled arrival to visible first output, including queue | Lower |
| `tpot_p95_ms` | p95 of each request's explicitly named **mean** TPOT | Lower |

p95 uses linear interpolation at `k=(n-1)*0.95` over the entire request population.
Unknown rows are never filtered; missing required metrics remain inconclusive.
Empty populations are malformed, never summarized as zero. Higher metrics use
`(baseline-candidate)/baseline`; lower metrics use
`(candidate-baseline)/baseline`. **Any zero metric baseline is inconclusive**
because the fractional comparison is undefined. Candidate zero goodput against
a positive baseline is a regression. Confidence intervals are not computed.

## Validated observations and comparison conditions

Each trace retains 1–1024 ordered requests. The loader verifies its fingerprint,
strict integer populations, finite nonnegative observations, applied schedule,
relative arrival/start/first/terminal chronology, native count/interval arithmetic,
output-cap states, execution counts, SLO states and goodput. Arithmetic comparisons
allow serialization roundoff only; counts, identities and expectations remain strict.

Elapsed is a fingerprint-bound **observed primitive measured after draining
tasks**. Terminals cannot exceed it; elapsed is not physically re-proven from
rows. Cooperative cancellation/cleanup can extend past a requested timeout.
The horizon preserves the last planned arrival even when execution stops early.
Clock origin `0` is valid; missing origin is unavailable evidence.

Pairs require the same workload commitment, ordered request descriptors,
schedule, output caps, concurrency, timeouts, targets and known actual prompt/
output token lengths. Hash commitments do not re-prove private prompt contents.
Caps do not substitute for observed lengths. A consistently recorded exceeded
cap is valid but ineligible; a summary contradicting native counts is malformed.

Fixed controls and paired treatment maps use supported observed facts from the
[benchmark policy contract](regression-gate.md): engine/version/model, digests
and quantization labels, device, context/parallelism/replica settings, prefix
cache, configuration/weight labels, hardware and model geometry. Required
expectations must be observed before **and** after every execution. Known
within-run changes block qualification. Known cross-arm changes require paired
treatment expectations; treatment/fixed keys cannot overlap. Unrequired unknown
facts remain visible as uncontrolled evidence.

Default cache evidence requires complete observed counts or the existing
observed-disabled prefix-cache alternative. `require_cache_evidence:false`
waives absence only. Known cached-token drift is checked at matched request
positions: a reordered multiset cannot hide a change. Contradictions and known
drift remain blockers despite the opt-out; intentional changes require different
paired `prefix_cache` treatment expectations. Missing counts never become zero;
no policy claims a cold run.

Ollama server decode means and supported adapter client means cannot be pooled.
Mean bases must match when consumed by a TPOT rule **or a TPOT target used in
joint goodput**. First-output/latency use queue-inclusive client bases; TPOT
remains a mean per request, never every-token latency. Saved rows lack original
wire IDs, arrival coverage and coalescing: arithmetic cannot re-prove the original
EOS/native-wire observations.

## API, receipt protections and outcomes

```python
from chimeraforge import api

decision = api.gate_traces(
    ["baseline-1.json", "baseline-2.json"],
    ["candidate-1.json", "candidate-2.json"],
    policy=api.TraceGatePolicy(
        rules={"goodput_rps": 0.05, "latency_p95_ms": 0.10},
        expected_replicates=2,
        fixed_controls={"device": "cpu"},
    ),
)
decision.save("trace-gate.json")
print(decision.to_dict()["outcome"])
```

Inputs may be paths, dictionaries or defensive `TraceReplay` snapshots. All are
revalidated. Reads hold bounded bytes once: 8 MiB per receipt, 32 MiB for the
declared population (every repeated occurrence is charged), 64 KiB policy.
Repeated identical file paths use the same held input rather than a second read.
Strict JSON rejects duplicates/nonfinite numbers; guarded regular-file reads
reject links. Decisions retain byte identities, execution counts, paired metrics,
blockers and all unpaired producer outcomes. Private prompts/completions,
arbitrary provider payloads/options and endpoint URLs are not copied. Atomic
saves protect all consumed inputs/policies, including hardlink aliases; failed
replacement leaves prior output intact.

Duplicate-execution digests include semantic prompt descriptors, relative
measurements, controls and supported observations. They ignore created/tool/
endpoint labels, fingerprints, clock origins and cosmetic request IDs. Relabeling
IDs and resealing their workload hash cannot manufacture an independent replicate.
Full IDs/workload hashes still bind paired comparison. Digest diversity does not
prove physical independence.

| Exit | Outcome |
|---|---|
| `0` | Conditional pass: all rules and required comparison conditions passed |
| `1` | Regression under otherwise complete, eligible evidence |
| `2` | Malformed input/options or output failure |
| `3` | Inconclusive: incomplete population, unknown evidence, copied execution or mismatched conditions |

Valid failed, partial, cancelled, unstarted, stopped, missing-origin and global
after-probe/cleanup-failure receipts remain retained **inconclusive** inputs.
Incomplete evidence takes precedence over arithmetic changes. Errors rejected
by CLI argument parsing use usage/error output; dispatched failures use the
selected JSON/prose mode.

Existing installed wheel/sdist consumers contain an explicitly synthetic CLI
oracle for all four exits and enforce installed package origin. The existing
hosted CPU trace slot consumes its one real receipt twice and expects copied
execution refusal, adding no model run or shared-runner speed threshold. Local
source protocol checks do not qualify installed artifacts or real GPU serving.
Physical/source/served-file authentication, independent cold executions and GPU
geometry remain unverified. No safety, quality or scientific GO claim is made.
