# Measured regression gates (unreleased source)

`gate` applies a predeclared engineering policy to saved `bench --plan` receipts.
It executes no requests. Published 0.51.0 does not contain this command: install
the reviewed source checkout containing this feature.

Save this policy as `policy.json`, then supply the actual receipt from every
execution in its declared order. Never duplicate files to manufacture replicates.

```json
{
  "rules": {"completed_token_rate_tps": 0.05, "ttft_ms": 0.10},
  "expected_replicates": 2,
  "pairing": "ordered",
  "fixed_controls": {"backend": "ollama", "device": "cpu", "version": "0.35.1"},
  "baseline_treatment": {},
  "candidate_treatment": {},
  "require_cache_evidence": true
}
```

```bash
chimeraforge gate --baseline baseline-1.json --baseline baseline-2.json --candidate candidate-1.json --candidate candidate-2.json --policy policy.json --out gate.json --json
```

Each arm must contain exactly `expected_replicates` (1-16). All declared files
are consumed and validated, including extra files that cannot be paired. Every
metric rule on every ordered pair must pass; a faster pair cannot hide a slower
pair. Thresholds are maximum relative degradation in `[0,1)`: higher rates use
`(baseline-candidate)/baseline`, lower durations use
`(candidate-baseline)/baseline`. A zero baseline is inconclusive. These are
descriptive engineering statistics, not confidence intervals or independence
proofs.

| Rule | Value and timing basis |
|---|---|
| `completed_token_rate_tps` | Complete native output-token sum / client workload wall seconds, including scheduler and semaphore waits; preflight and metadata observations excluded. |
| `decode_tps` | Per-replicate arithmetic mean of recomputed sample rates. Ollama: all output tokens / server decode duration. Supported SSE adapters: output tokens minus the first / client first-to-last interval. |
| `ttft_ms` | Per-replicate arithmetic mean of native values. Ollama server prefill duration differs from SSE client first-content latency. |
| `request_duration_ms` | Per-replicate arithmetic mean. Ollama server total duration differs from SSE adapter client-call wall time, which excludes the client semaphore queue. |

Ollama and SSE bases cannot be pooled. An intentionally changed backend can use
the common token-sum/client-wall rule; vLLM and SGLang also share the supported
SSE timing bases. Negative native TTFT sentinels remain unavailable, never
improvements. Unknown values for unused rules do not automatically invalidate
other rules. Old receipts without the explicit elapsed-time basis cannot qualify
the client-wall rule. Plain `bench --model` results lack applied-request and
serving observations and remain inconclusive.

The loader verifies fingerprints, strict counts and finite native samples,
recalculates aggregates with shared benchmark helpers, and requires successful
coverage of every requested request. Persisted `binding`, `audit`, decision
labels, input quantization labels and client NVML readings are not gate evidence.
Actual prompt/output token lengths must be observed; character length and output
caps are not substitutes. Effective prompt SHA256, profile, concurrency,
configured arrival-rate parameter, output cap and additional options must agree,
as must observed length distributions. A shared Poisson parameter does not prove
the same actual arrival schedule.

`fixed_controls` and paired treatment maps name observed serving facts:
`backend`, `version`, `model`, `model_digest`, `quant`, `context_length`, `device`,
`tensor_parallel`, `pipeline_parallel`, `replicas`, `prefix_cache`,
`configuration_sha256`, `weight_version_label`, `execution_engine` or
`serving_data_parallel_size`. Physical `hardware.<field>` and normalized
`model_spec.<geometry-field>` conditions are also supported. Engine data
parallelism cannot attest a load-balanced fleet; hardware price/capture dates
are outside physical controls.

Required expectations must be observed before **and** after every execution.
Known within-run changes block qualification. Known cross-arm differences require
both treatment expectations; their keys cannot also be fixed controls. For
example, backend treatments are `{"backend":"vllm"}` and
`{"backend":"sglang"}` respectively. An intentional model-digest change also
needs paired expectations. Observed digests are unauthenticated metadata, not
actual weight-byte hashes.

Cache evidence is required by default: complete per-request cached-token counts
or observed disabled prefix caching before and after execution. Pinned Ollama
commonly omits both, yielding an honest inconclusive decision. Predeclaring
`require_cache_evidence:false` waives missing evidence only and retains prominent
unknown/uncontrolled cache scope. It cannot waive contradictory counters, known
cache changes or a required prefix-cache expectation. Known cross-arm cache
changes require paired cache treatments. No path assumes zero hits or cold runs.

```python
from chimeraforge import api

result = api.gate_benchmarks(
    ["baseline-1.json", "baseline-2.json"],
    ["candidate-1.json", "candidate-2.json"],
    policy=api.RegressionPolicy(
        rules={"completed_token_rate_tps": 0.05, "ttft_ms": 0.10},
        expected_replicates=2,
        fixed_controls={"device": "cpu", "backend": "ollama"},
    ),
)
result.save("gate.json")
print(result.to_dict()["outcome"])
```

`PlanBenchmark` objects and dictionaries are revalidated like file inputs. Reads
are bounded and held once: 8 MiB per receipt, 32 MiB total, 64 KiB policy. Strict
JSON, regular-file/link and duplicate-key checks apply. Decisions retain byte
identities, all pairs, native units and scoped blockers. Private option values,
prompts, completions, arbitrary metadata and provider diagnostics are not copied.
Atomic output refuses aliases of every input/policy, including hard links.
Duplicate execution payloads remain inconclusive when producer clocks change.
Integrity does not authenticate the source.

Exits: `0` conditional pass, `1` regression under a fully satisfied policy,
`2` malformed input/output failure, `3` inconclusive. Incomplete populations or
unavailable required evidence take precedence over arithmetic changes.
Unrequired unknown facts stay visible and limit a conditional pass. No decision
proves statistical confidence, independent cold execution, GPU/planner accuracy,
served weights or queue-inclusive SLO attainment.

Existing installed wheel/sdist acceptance exercises all four outcomes using
explicitly synthetic protocol fixtures. The existing hosted CPU endpoint makes
two actual installed benchmark executions and exercises missing-cache refusal;
shared-runner rates receive no performance qualification threshold. Hosted proof
remains pending publication.
