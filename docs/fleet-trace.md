# Original-fleet scheduled trace

Unreleased **0.79.0 source candidate**. Public installation remains 0.76.0.
`trace-fleet` and async `api.replay_fleet_trace` replay a held private workload
against every declared member of one original saved homogeneous candidate.
They do not export, resize or replace that candidate, route production traffic,
or establish deployment readiness.

```python
import asyncio
from chimeraforge import api

report = asyncio.run(api.replay_fleet_trace(
    "saved-n3.json", "requests.json",
    (api.FleetEndpoint("a", "http://host-a:8000"),
     api.FleetEndpoint("b", "http://host-b:8000"),
     api.FleetEndpoint("c", "http://host-c:8000")),
    "routes.json", candidate_index=0, concurrency=3,
    request_timeout=30, trace_timeout=60, cleanup_timeout=2,
))
report.save("fleet-trace.json")
received = api.load_fleet_trace("fleet-trace.json")
assert received.to_dict() == report.to_dict()
```

The example requires a native N3 candidate. Exactly N direct HTTP(S) base URLs
are required, with unique bounded IDs and distinct normalized URLs. Userinfo,
query strings, fragments and port zero are refused. Direct base paths are kept;
this active endpoint admission does not rewrite a passive `/metrics` URL.
Ollama, vLLM and SGLang use their existing native adapters. The native
`llama.cpp` planner wrapper maps to Ollama without editing the saved backend.

The workload is the existing native JSON list:

```json
[
  {"request_id":"r1","prompt":"Private prompt one","max_output_tokens":4,"arrival_offset_s":0},
  {"request_id":"r2","prompt":"Private prompt two","max_output_tokens":4,"arrival_offset_s":0}
]
```

Every output cap must equal the selected candidate's original
`decode_tokens_per_req`. Prompts go to the selected endpoints and are replaced
by native descriptors/hashes in receipts. A separate closed route list assigns
every request exactly once; route list order is canonicalized to original
workload order:

```json
[
  {"request_id":"r1","endpoint_id":"a"},
  {"request_id":"r2","endpoint_id":"b"}
]
```

The third member `c` stays declared and observed even when assigned no requests.
Its token and latency evidence is unavailable. Requested SLOs are unavailable
for an empty member; absent targets remain `not_requested`. Empty populations
cannot provide a vacuous token match or observed SLO pass.

```bash
chimeraforge trace-fleet requests.json --from-plan saved-n3.json \
  --endpoint a=http://host-a:8000 --endpoint b=http://host-b:8000 \
  --endpoint c=http://host-c:8000 --routes routes.json --concurrency 3 \
  --request-timeout 30 --trace-timeout 60 --cleanup-timeout 2 \
  --out fleet-trace.json --json
```

There is no backend or SLO override. `--model` supplies an explicit served alias;
original model geometry, N, TP/PP, batch, context and saved targets remain held.
`--out` is checked against actual saved-plan/bundle members, workload, routes,
and every explicit CA/certificate/key input, including file-identity aliases,
before constructing connections or contacting endpoints.

## One population and explicit ownership

All members must finish required health/model preflight and before-metadata
bracketing before any generation. A required preflight failure prevents all
generation and keeps the full request and member populations visible. Optional
metadata can remain unavailable. Preflight/metadata fanout is separately bounded;
the scheduled replay timeout starts after the before barrier.

Generation uses the existing native executor: one origin, arrival schedule,
global concurrency semaphore, task population and replay deadline. A request
timeout retains its semaphore lease until its owned generation child stops.
There are no retries, reassignment or per-member C-sized executors.

One final cooperative cleanup deadline is captured before final cancellations
or drains. Every client close is attempted, including after allowance expiry,
before unbounded cooperative joining of remaining work. Direct task cancellation
is rethrown after owned closure; repeated cancellation does not abandon cleanup.
SIGINT uses the existing graceful stop event and returns retained partial facts.
Python/native close operations can overrun the allowance; this is reported as
incomplete cleanup, without a hard OS deadline or whole-HTTP-byte guarantee.
Native streaming/metadata limits apply only on their existing paths.

## Secure per-member connections

The runtime-only `.78` `MonitorConnection` is reused for vLLM/SGLang generation,
preflight and both metadata brackets. `connections=None` preserves anonymous
legacy behavior. An explicit mapping, including `{}`, requires verified HTTPS
for every endpoint. Credentials are scoped per declared ID; there is no implicit
broadcast. Opted-secure Ollama is refused before contact because that native
constructor is not qualified for these settings.

CLI `--secure`, `--bearer-env ID=ENV_NAME`, `--ca-bundle ID=PEM_PATH`,
`--client-cert ID=PEM_PATH` and `--client-key ID=PEM_PATH` follow the
[secure monitoring](secure-monitoring.md) trust and privacy boundary. Pass tokens
through named environment variables, never token arguments. Runtime connection
objects, secrets, environment names and TLS paths stay outside persisted plans,
reports and typed route/request descriptors.

## Receiving and interpretation

The distinct `chimeraforge.fleet-trace` envelope contains the full validated saved
plan snapshot, one global native trace with `endpoint_id`, original ordered
route coverage, per-slot row indices, member metadata and derived bindings.
Member views reference global rows; they are not duplicated independent runs.
Goodput uses the same common global horizon and denominators. No per-member p95
average or new latency estimator is introduced.

`api.load_fleet_trace` accepts a receipt object, dictionary or bounded JSON path.
It rejects unknown fields, duplicate JSON keys, malformed native rows, missing
members/routes, contradictory derived counts/indices and impossible post-origin
ownership. It projects only the declared endpoint extension into the unchanged
strict native reader, then rederives saved bindings, native headers, targets,
slot references, native timing and common-horizon arithmetic. The named report
limit is 32 MiB, including the existing pretty writer, trailing newline and a
portable CRLF newline upper bound. Save admission runs before native replacement;
routes are capped at 1 MiB and native workloads at 1,024 requests.
Raw source/workload/route hashes cannot be authenticated without original bytes.
Fingerprints establish internal integrity, not origin authentication.

The receipt contains the full saved plan snapshot and declared endpoint URLs.
It can carry original model identifiers, local paths or other private plan intent;
treat it like the source plan when sharing. Runtime connection credentials,
environment names and TLS input paths remain omitted, but the whole snapshot is
not guaranteed path-free or safe for public disclosure.

Serving metadata uses closed `declared_member` replica scope: compare one
declared member with observed replicas=1 while retaining original candidate N.
Serving data parallelism remains a separate field. Distinct URLs, model names,
metadata and source hashes do not authenticate processes, GPUs, immutable
weights, physical independence or capacity.

| Exit | Meaning |
|---|---|
| 0 | Complete execution/cleanup without a known configuration or token mismatch |
| 1 | Incomplete execution, failed preflight/cleanup, or known binding mismatch |
| 2 | CLI admission/operational refusal; API admission raises `PlanError` or inherited `MonitorConnectionError` |

Native SLOs remain separately reported: execution exit 0 can accompany an unknown
configuration or breached/unavailable target. The real hosted CPU canary retains
the native CPU-versus-modeled-GPU mismatch rather than relabeling it a GPU pass.

The regenerable [functional record](../validation/2026-10-25-fleet-trace/README.md)
describes controlled protocol observations. Hosted wheel/rebuilt-sdist acceptance
and the pinned three-daemon CPU canary are separate qualification gates. Protocol
fixtures do not execute vLLM/SGLang engines; CPU integration establishes neither
GPU performance nor prediction accuracy.
