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
Absolute source paths retain their producer's Windows/POSIX flavor. A valid
foreign-platform receipt loads, but checking it reports the original input as
unavailable rather than coercing it into a local namesake.
Legacy checks still compare the current effective coefficient digest when no
external corpus was requested and inspect current expiry for an explicitly used
cloud. They distinguish these known observations from unverified original
sources, price history and replay geometry, and retain overall exit 1.

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

## Benchmark a saved candidate

```python
import asyncio
from chimeraforge.api import benchmark_plan

receipt = asyncio.run(benchmark_plan("plan.json", candidate_index=0,
    model="actual-served-id", prompt="The actual prompt", runs=5))
receipt.save("benchmark.json")
print(receipt.to_dict()["audit"])
```

```bash
chimeraforge bench --plan plan.json --candidate-index 0 --model actual-served-id \
  --prompt "The actual prompt" --runs 5 --base-url http://localhost:11434 \
  --output-dir results --json
```

This explicitly contacts a live serving endpoint. It validates and preserves the
saved artifact, binds its fingerprint/index/candidate identity, and reuses the
benchmark runner. The default adapter follows the selected backend; `--model`
can name an actual serving alias, but that label cannot verify the planned model.
Quant/context labels and sweeps are refused. The saved context is requested only
where an adapter supports it (Ollama `num_ctx`); other adapters require observed
server configuration. The saved decode length is sent as an output **cap**, and
the actual returned counts are recorded separately.

The receipt contains the prompt SHA256/character count, forwarded generation
options, applied single/batch/server profile, concurrency, server arrival rate,
requested/successful/failed counts and timing bases. Single concurrency is 1;
`--rate` applies only to server mode. A context window is not a prompt-token count.
Server token counts establish whether the actual workload matches the saved
prompt/output lengths. Repeating a prompt may warm caches; unavailable cache
counters/configuration remain unverified. Partial-run aggregates describe the
successful requests and cannot establish a passing SLO.

Observations before/after the workload are bounded and whitelisted. Ollama's
`/api/show` provides quant/architecture; `/api/ps` provides loaded digest, actual
context and CPU/GPU loaded bytes. Architecture maximum context is not active
context. Ollama family/version does not attest the underlying llama.cpp execution
version, TP/PP or GPU identity. vLLM's structured
`/server_info?config_format=json` can expose quant, context, TP/PP, data parallelism
and cache configuration; text representations are never evaluated. Engine data
parallel size is recorded separately with serving-engine scope ([vLLM's configuration
and external load balancing](https://github.com/vllm-project/vllm/blob/v0.30.0/vllm/config/parallel.py#L118-L153)): it does not
attest the total replica fleet behind an endpoint/load balancer. Replica count
remains unavailable unless an observation capability actually covers that
topology. Known engine-DP changes during a run remain configuration changes.
TGI's `/info`
exposes model identity/revision and router limits, not quant/TP/GPU configuration.
SGLang's resolved `/server_info` and current `/model_info` expose supported
configuration/identity fields; an operator weight-version label is not a digest.
Missing capabilities or refused metadata are unavailable, not supplied defaults.
Known configuration changes during a run are mismatches; a lazy-loaded unknown
pre-state remains unverified. Client NVML describes the benchmark client host.
Loaded GPU bytes or a GPU name do not establish full remote GPU geometry.

The native-unit audit keeps modeled values, actual measurements and a labeled
`raw_delta` even when equivalence cannot be established. That arithmetic is not
prediction accuracy. A `delta` is available only for a fully observed equivalent
single-stream base decode comparator; the saved base rate precedes batch/TP/PP
scaling. It does not qualify selected fleet capacity.

Saved LoRA adapters/rank/target and CPU offload modify that base rate, but the
runner does not apply or observe those scenarios; their comparator remains
unverified. Known SGLang weight-version label changes are mismatches, while
labels still do not establish immutable weights.

Queue-inclusive modeled p95
cannot be accepted from survivor-only adapter durations, which exclude the
client semaphore queue. Ollama server-prefill TTFT differs from client first-token
stream timing. Immutable planned weights remain unverified.

Exit 0 means requests completed without an observed binding mismatch; unavailable
evidence still remains explicitly unverified. Exit 1 means an observed mismatch,
partial execution or operational failure. Exit 2 means invalid saved input/options.
The saved receipt and JSON stdout agree. Endpoint URL credentials/query tokens
and raw private serving configuration are excluded from receipts. Fingerprints
detect edits, not authenticity. The hosted CPU acceptance executes the installed
saved-plan path and requires a truthful CPU-versus-GPU mismatch, useful native
measurements and unverified accuracy/SLO rather than a GPU performance claim.

Protocol references: [Ollama running models](https://docs.ollama.com/api/ps),
[Ollama generation](https://docs.ollama.com/api/generate),
[vLLM0.30.0 server info](https://github.com/vllm-project/vllm/blob/v0.30.0/vllm/entrypoints/serve/dev/server_info/api_router.py),
[TGI3.3.7 Info schema](https://github.com/huggingface/text-generation-inference/blob/v3.3.7/router/src/lib.rs),
[SGLang0.5.20 server/model info](https://github.com/sgl-project/sglang/blob/v0.5.20/python/sglang/srt/entrypoints/http_server.py).
