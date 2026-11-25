# Continuous fleet exporter (since 0.92.0)

Chimeraforge 0.106.0 adds the optional
[finite final-observation requirement](#finite-final-observation-since-01060).

`api.serve_fleet_exporter` and `monitor-fleet-exporter` expose the latest bounded
native fleet observation through a loopback Prometheus endpoint. Install the
`exporter` extra for this workflow. Its reference stack is Starlette 1.7.0 and
Uvicorn 0.54.0, declared directly in that extra; no Prometheus client is needed.

```bash
python -m pip install "chimeraforge[exporter]==0.111.0"
chimeraforge monitor-fleet-exporter --from-plan fleet-plan.json \
  --candidate-index "$FLEET_INDEX" \
  --endpoint replica-a=http://127.0.0.1:8101/metrics \
  --endpoint replica-b=http://127.0.0.1:8102/metrics \
  --endpoint replica-c=http://127.0.0.1:8103/metrics \
  --interval 1 --observation-seconds 15 --ttft-slo 500 \
  --listen-host 127.0.0.1 --listen-port 9400 \
  --poll-seconds 15 --stale-after-seconds 60
```

Select an actual saved candidate with **N=3** for this three-endpoint example.
The service never changes the original N, optimizes, probes GPUs or sends
generation requests. Each cycle invokes the existing passive monitor with one
finite two-scrape window and the same admitted controls. Polls are sequential;
`poll_seconds` is the pause **after** a completed poll, not a fixed-rate schedule.
Each poll retains native shared concurrency, request, accepted-body and elapsed
observation budgets, metadata prefixes and owned cleanup. Resets are detectable
within the observed window; resets in idle gaps are not necessarily detectable.

## Python ownership

```python
from chimeraforge import api

request = api.FleetMonitorRequest(
    endpoints=(
        api.FleetEndpoint("a", "http://127.0.0.1:8101/metrics"),
        api.FleetEndpoint("b", "http://127.0.0.1:8102/metrics"),
        api.FleetEndpoint("c", "http://127.0.0.1:8103/metrics"),
    ),
    windows=1, interval=1, observation_seconds=15, ttft_slo=500,
)
config = api.FleetExporterConfig(port=9400, poll_seconds=15, stale_after_seconds=60)
async with api.serve_fleet_exporter("fleet-plan.json", request,
                                  candidate_index=FLEET_INDEX, config=config) as service:
    print(service.metrics_url)
    snapshot = service.snapshot()  # frozen view; body is immutable bytes
    # Keep this context alive for the desired service lifetime.
```

The complete plan, normalized endpoint tuple and explicit connection mapping are
held at startup. Later plan-file or caller-mapping mutations do not alter polls.
Opted-secure partial maps are completed once with native `MonitorConnection`
defaults; their SSL contexts and per-origin credentials are held. With
`connections=None`, existing anonymous mixed HTTP/HTTPS semantics remain; HTTPX
may recreate its own default CA context on later polls. Fixed configuration does
not mean every SDK default file is snapshotted.

All native offline admission runs before a loopback socket is bound; bind failure
causes no backend requests. One non-daemon listener thread owns one ASGI event
loop and one poll task. Context exit or direct `await service.aclose()` signals,
stops and joins those resources, including cancellation/startup failures and
repeated close. Cleanup is cooperative with joins, not a hard wall-clock bound.
The caller owns the service context; it must not abandon it.

CLI Ctrl+C/SIGTERM requests clean shutdown. `--run-seconds 30` explicitly opts into
a finite diagnostic run; the default runs continuously. Ready and closed JSON
lines describe listener ownership. Clean process exit **0 is not fleet
qualification**; use the native qualification gauges or snapshot native exit code.
Invalid/unavailable service setup exits 1; native Typer usage errors remain 2.

## Finite final observation (since 0.106.0)

The API and flag reuse one existing
service context without adding a backend request, source reload, monitoring retry,
HTTP readiness probe or Prometheus parse at the qualification boundary:

```python
result = await api.run_fleet_exporter(
    "fleet-plan.json", request, candidate_index=FLEET_INDEX, config=config,
    policy=api.FleetExporterRunPolicy(run_seconds=30, require_final_observation=True),
)
print(result.to_dict())
```

For the CLI, add `--run-seconds 30 --require-final-observation` to the continuous
example. The flag without a finite duration is invalid before service work.
Duration starts after the existing context is ready, as in the old finite CLI.
The exact policy type, exact boolean and finite numeric duration `0 < seconds <=
86400` are admitted before optional service imports or resources; booleans as
durations, enormous integers, NaN and infinity are refused.

At the finite timeout, capture one immutable cache entry **before** shutdown
publishes stopped. A private fact in that same entry binds the actual native
report and every ordered original slot to the already held plan, selected
candidate, endpoint IDs/URLs, backend/model, tool metadata and admitted controls.
The expected population comes from original admission, not the seed template or
the latest observed row count. No raw fresh report is retained in the entry.
Initial, unavailable and stopped templates are not real observations.

Qualification requires an observation committed to the cache by the monotonic
cutoff, including time spent assembling its output. A publication committed
after the cutoff retains its observed native code and yields qualification exit 4.
Eligible entries use age at the cutoff. Qualification also requires exact original
coverage and `0 <= raw monotonic age < stale_after_seconds`. Equality at the TTL,
clock regression or non-finite age cannot pass. The existing public snapshot's
age clamping, fields, Prometheus bytes and readiness contract are unchanged.
Fresh readiness 200 alone never qualifies a fleet.

The final result is produced **after** the existing shielded shutdown closes and
joins the listener/worker. Joined flags alone are insufficient: listener failure,
a failed or cancelled worker task, or unsuccessful cleanup yields a safe SDK
`FleetExporterError` and CLI exit `1`. A genuine late failure overrides an earlier
captured PASS. Native cleanup failures remain sticky even when an in-flight poll
finishes after stop or a later poll succeeds. This includes resources owned by
the initial cancelled template; a completed template cleanup remains normal.
Ordinary poll/setup unavailability
with completed cleanup retains native unknown/recovery behavior. Cancellation
propagates only after owned cleanup and never
returns a qualified zero. Optional typed `stop_event` requests a clean early SDK
stop; that boundary remains unqualified even if the last native report passed.

| Selected qualification outcome | Exit |
|---|---|
| Fresh, complete, fully bound native `0`, timeout reached and clean joins | `0` |
| Fresh, complete, bound native SLO breach | `3` |
| Initial/stale/unavailable/partial/foreign evidence, native unknown, invalid clock or early stop | `4` |
| Fresh, complete, bound native identity/configuration mismatch | `5` |
| Invalid configuration, startup or shutdown failure | `1` |

`FleetExporterRunResult` is frozen and emits a closed schema-1 receipt with finite
duration, boundary/state, sequence/age, expected/observed counts, population-bound
status, native observed code, qualification code and cleanup flags. It includes
no backend URL, model, original ID, exception text or raw observation body.
The original observed code remains separate when freshness or binding makes
qualification unknown.

With an exact `False` policy, the new SDK returns clean-close `0` with
`qualification_requested=False` and `qualification_met=None`; this is not a
qualified PASS. Existing continuous/finite CLI behavior keeps its ready and
closed rows and `process_exit_is_qualification=False`. Only the selected flag
sets that field true and appends a separate qualification receipt after closed.
CLI signal handlers are restored on every path. Original request budgets and
source/connection admission remain unchanged. These are passive client
observations, without engine/GPU, physical-independence, capacity or deployment
proof.

## Freshness and metric meaning

Scrapes read only an immutable cached byte snapshot and monotonic age. They do
not call a backend, open outbound pools, format a native report or reread a plan.
The native formatter runs at publication. Every original member remains present.
Labels use `replica-1` through `replica-N` and fixed model `configured`; original
operator IDs, model names, endpoints and credentials are excluded from metrics.
Opaque plan fingerprints retain their native meaning, without authentication.

`FleetExporterSnapshot` contains `body`, `state`, `age_seconds`, `sequence`,
`native_exit_code`, `original_replicas` and `published_unix_seconds`. State
`fresh` describes cache age, **not** PASS: a fresh native mismatch, reset,
unavailable or failed window replaces prior values immediately. Poll exceptions
publish an unavailable all-N view; shutdown publishes stopped. Initial age is
unknown. Once TTL expires, snapshot and HTTP choose a prebuilt all-N unknown view
even if the worker is stalled. Prior numeric p95/sample series are absent, never
fabricated zero. Stale native exit is 4. A previous PASS is never the current view
after a new failure or expiry.

All samples, p95 bounds, outcomes and exporter metadata are **gauges**. Publication
sequence counts cache publications, not traffic. Do not sum window samples into
a cumulative request counter or pool percentiles. Local publication wall time is
diagnostic, not signed freshness, server identity, capacity or SLO proof.

## Cache readiness

Since 0.99.0, GET or HEAD `/readyz` exposes a small cached-readiness
response. The Python service has a read-only `readiness_url` property.
The CLI ready/closed records and `metrics_url` keep their existing shapes.

```bash
curl --fail http://127.0.0.1:9400/readyz
```

The response has `schema_version: 1`,
`kind: "chimeraforge.fleet-exporter-readiness"`, `ready`, `state`,
`age_seconds`, `sequence` and `native_exit_code`. It returns 200 exactly when
snapshot state is `fresh`, including fresh native breach, mismatch or unknown
evidence. Initial, stale, unavailable and stopped cache states return 503.
Initial age is null. Sequence and native exit come from that same snapshot.

This endpoint performs no upstream poll and uses the existing monotonic
expiry. It exposes no model/endpoint/operator labels, paths or native bodies.
Responses use `Cache-Control: no-store` and a complete 1 KiB JSON limit;
an oversized response is refused with an empty 503. HEAD sends the same
status and headers with an empty body. The same method, raw-path, query,
header and request-body admission applies to both endpoints. Normal native
concurrency backpressure can also return 503.

Readiness describes whether cached observation is fresh. Fleet qualification
continues to use the separately reported native exit and metric outcomes.
After the listener closes the URL is no longer served.

## HTTP and outbound settings

Only numeric `127.0.0.1` or `::1` listens are admitted. GET/HEAD `/metrics` and,
in 0.99.0, `/readyz` support requests without a query or request body. Other
methods and paths refuse. HTTP runs on the
installed supported ASGI stack with configured concurrency/backlog (2–64),
one-second keepalive, bounded header/path admission and a complete 1 MiB metric
snapshot cap. These bounds do not claim a process heap or kernel-buffer limit.
There is no inbound authentication: trusted local processes can read the endpoint.
Do not forward it to an untrusted network. Scrape concurrency may receive native
503 backpressure without triggering backend work.

Existing `--secure`, `--bearer-env ID=ENV`, `--ca-bundle ID=PATH`,
`--client-cert ID=PATH` and `--client-key ID=PATH` apply to outbound native
monitoring. Explicit settings require native HTTPS/origin admission for every
member; credentials never cross origins or enter cached metrics. See
[secure monitoring](secure-monitoring.md). Observations remain unauthenticated
claims about served model/configuration and declared endpoints, not independent
machines, running weights or physical GPU ownership.

## Evidence

The source aggregate and regeneration command are in
[the dated validation record](../validation/2026-11-01-continuous-fleet-exporter/README.md).
It exercises actual native producers, CPU protocol fixtures, TLS/auth/mTLS,
loopback scrapes and OS CLI lifecycle. Controlled fixtures are not real inference
engines or performance evidence. Original/rebuilt installed qualification and
current hosted checks are separate from local source execution.
