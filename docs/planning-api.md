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
the same report. Checks default to offline regardless of the saved `allow_network`
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
is actionable even when rounded predictions match. Hub checkpoint metadata can
bind a resolved immutable revision, as described below; it cannot prove the
identity of currently served weight bytes.

Exit 0 means a completed comparison with required components unchanged; exit 1
means changed, expired or unverified required components (or a changed local
resolved identity/recommendation). Exit 2 means malformed input. Cloud snapshots
use the existing 90-day policy: day 90 is valid, day 91 is expired. Plans that did
not consume cloud prices do not inspect or expire them. GPU amortization and
coefficients have no invented expiry threshold. Performance remains informational
unverified: an unchanged modeled result is not a performance acceptance test.
Fingerprints detect edits, including context edits, but cannot authenticate a
snapshot or turn unsigned quarantine data into trusted measurements.

## Checkpoint identity

This is an unreleased source feature, beyond PyPI 0.51.0 and the README's older
review-stack install pin. Install this feature's checkout with `pip install .`.

```python
from chimeraforge.api import PlanRequest, plan, check_plan
from chimeraforge.deploy import export_deployment

repo = "HuggingFaceTB/SmolLM2-135M-Instruct"
commit = "12fd25f77366fa6b3b4b768ec3050bf629380bac"
saved = plan(PlanRequest(models=[repo], model_revisions={repo: commit},
    platform="linux", hardware="RTX 4080 12GB", request_rate=0.01,
    quality_target=0, budget=100000))
saved.save("checkpoint-plan.json")
print(saved.spec(repo).checkpoint)
print(check_plan(saved).to_dict()["checkpoint_view"])  # offline
print(check_plan(saved, allow_network=True).to_dict()["checkpoint_view"])

# Choose an actual supported row; rank zero may be a different backend/quant.
index = next(i for i, row in enumerate(saved.to_dict()["result"]["candidates"])
    if row["backend"] == "vllm" and row["quant"] == "FP16"
    and row["n_agents"] == row["tensor_parallel"] == row["pipeline_parallel"] == 1
    and row["offload_fraction"] == 0)
config = export_deployment(saved, format="compose", candidate_index=index,
    image="vllm/vllm-openai:v0.30.0")
print(config.content)  # includes --revision with the resolved commit
```

`resolve_spec(repo, hf_revision=ref)` accepts a commit, branch or tag. The CLI
uses `plan --revision REF` with one `--model`, or repeated `--revision MODEL=REF`
for selected HF models. All online HF metadata resolution, including the default
`main` route, first obtains one commit from Hub model metadata and reads config
only at that commit. An explicit revision unavailable offline fails rather than
substituting registry geometry or another cached revision. Manual overrides,
registry geometry and Ollama metadata carry no fabricated Hub identity.

`ModelSpec.checkpoint` is a versioned receipt for the requested ref, resolved
commit, observation time, SHA256 of consumed config bytes, optional declared Git
blob identity, safetensors parameter total and whitelisted declared weight-file
sizes/Git/LFS hashes. Its metadata digest covers normalized declarations, not
downloaded weights. No weight files are downloaded for resolution. The config's
declared Git blob, when available, is checked against the consumed bytes.
Credentials and arbitrary Hub card metadata are not retained. The receipt is
unsigned and cannot authenticate the producer or Hub response.

`checkpoint_view` separates `pinned_metadata`, `requested_ref` and
`served_weights`. Offline checks may compare the producing cache's pinned
metadata; a cached branch/tag does not establish its current target. Explicit
`check --network` / `check_plan(..., allow_network=True)` inspects the pinned
commit and current requested ref, without substituting either into replay or
mutating the artifact/cache. A known metadata/ref change is actionable exit 1;
optional unavailable Hub observation alone does not fail an otherwise complete
offline comparison. Capture time alone is not an identity change. Actual
downloaded weights, served weights and tokenizer bytes remain unverified.

Existing v1/v2 snapshots load with their original bytes/fingerprint and unknown
checkpoint identity. Newly observed identity cannot contradict an unknown
original. Mixed or malformed new revision bindings are refused, including a
declared explicit revision with no corresponding checkpoint receipt. Serving
exports preserve the resolved commit for vLLM/TGI/SGLang's native `--revision`
option; their same-repository default tokenizer follows that revision. Different
tokenizer overrides are outside this contract. Ollama cannot represent this HF
pin and refuses conversion. Legacy unpinned HF export remains available with an
explicit warning to replan online for a bound checkpoint.

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
Partial matching geometry remains unverified; only known contradictions are
mismatches. Newly observed dimensions cannot contradict unspecified saved
dimensions. Hardware cost and source dates are excluded from physical geometry.
Documented dense/standard absence is normalized separately from unknown
dimensions; introduced MoE/MLA structure remains a disagreement.

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

## Passively monitor a saved candidate

```python
from chimeraforge.api import monitor_plan
from chimeraforge.monitor import MonitorRequest

report = monitor_plan("plan.json", MonitorRequest(
    backend="vllm", url="http://localhost:8000", model="org/served-model",
    interval=30, windows=2, timeout=10,
), candidate_index=0)
print(report.to_dict(), report.exit_code)
```

The synchronous API fills a copy of missing targets from the saved request and
preserves both artifact and input request. Standalone `run_monitor` still requires
at least one explicit target. The plan binding records fingerprint, producing
tool version, exact candidate identity and each target's source. Required model
and backend identity is observed across each histogram window; known configuration
disagreements are separate from native SLO breaches and missing evidence.
Metadata uses the same supported serving observation/binding seam as benchmarking,
without executing a workload. An entire metadata observation is bounded by the
monitor timeout, followed when cancelled by a cooperative cleanup budget of
`min(timeout, 1 second)`. Receipts distinguish completed cleanup from incomplete
transport closure; arbitrary cancellation-ignoring transports are not covered by
the timing guarantee. Metric/reset/window semantics stay those
of the [monitoring guide](monitoring.md).

`report.outcome` remains the native histogram policy outcome. Plan mode exit codes
are 5 for known identity/configuration disagreement, 3 for valid SLO breach, 4 for
unknown required identity/SLO or incomplete observation, and 0 for an observed
model/backend match plus native SLO pass. Exit 0 retains explicit unavailable GPU,
fleet, workload and immutable-weight limits; it does not certify deployment or
planner accuracy. CLI operational/input/output errors exit 1. Target override
attribution and separate Prometheus binding gauges are included in the guide.

## MCP transport configuration

The same five planner tools are available through default stdio or the SDK-native
Streamable HTTP endpoint (`chimeraforge mcp --transport streamable-http`). For
Python embedding, pass the frozen operator settings explicitly:

```python
from chimeraforge.mcp_server import build_server
from chimeraforge.mcp_transport import MCPHTTPSettings

build_server(http_settings=MCPHTTPSettings(port=8766)).run("streamable-http")
```

HTTP is loopback-only and offline by default. Its raw-argument guard rejects
caller-controlled local paths, URLs/Ollama endpoints, and `allow_network` before
the SDK injects defaults. Operator `allow_network=True` permits Hugging Face model
resolution and discovery; catalog data remains server-owned. Initialization
instructions expose the effective policy. Stdio retains its existing tool knobs.
HTTP discovery accepts an integer `hf_limit` from 1 to 16, bounding resolver fanout
before worker/network admission even when the operator enables network access.

`MCPHTTPSettings` owns native body/session/idle limits and fixed worker admission.
Timed-out/cancelled calls retain capacity until their synchronous job completes;
there is no unbounded executor submission queue. Protocol controls remain on the
event loop. Lifespan shutdown stops admission and drains owned workers, rather
than claiming Python can preempt a hung synchronous operation. Ordinary clients
should use the supported SDK `streamable_http_client` and `ClientSession`.

## Review and replay quarantined contributions

```python
from chimeraforge.api import review_contribution, replay_contribution

review = review_contribution("unsigned.contribution.json", decision="retain",
                             reason="Keep for a controlled comparison")
review.save("review.json")
replay = await replay_contribution("unsigned.contribution.json", prompt="Explain KV caching.",
                                   output_tokens=128, runs=3, base_url="http://localhost:11434")
replay.save("replay.json")
```

Both return a defensive `ContributionReceipt` with `to_dict()`, atomic `save()`
and `exit_code`. A full quarantine id can replace the path. Contribution schema,
verification, import, trust and planner-selection semantics are unchanged.
Disposition is an unsigned reviewer statement, not a signer attestation; retain
and reject require a reason and never mutate quarantine. The full source content
id, canonical envelope digest, flags and unsigned attestation travel with receipts.

Live replay reuses the actual runner's applied prompt hash/options/profile,
counts, before/after typed metadata and per-request native timings. Explicit
model/backend/workload overrides preserve known disagreement with declared
labels. The output-token option is a cap, distinct from observed token counts.
Server workloads require an explicit positive finite arrival rate; concurrency
and request counts are validated before contact. Operational preflight/all-failed
receipts preserve intent, successful/failed/not-started counts and a safe error
class/reason. Cancellation propagates through the runner's existing lifecycle.

Legacy v1 lacks original prompt, token-count, configuration, immutable-weight,
timing-basis and remote-hardware bindings. `replay_equivalence` and metric
comparability remain unverified, with native arithmetic `raw_delta` separate from
the unavailable qualified `delta`. CPU or known different GPU observations are
ineligible to qualify the declared GPU measurement; label agreement alone does
not verify either run. Exit 0 denotes completed operation only, 1 known mismatch
or failed/partial replay, and new CLI commands use 2 for malformed input/options
or output errors. Receipt output guards refuse source/contribution overwrites and
quarantine writes before execution. URL credentials/query values are redacted.
