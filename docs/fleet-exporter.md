# Continuous fleet exporter (since 0.92.0)

`api.serve_fleet_exporter` and `monitor-fleet-exporter` expose the latest bounded
native fleet observation through a loopback Prometheus endpoint. Install the
`exporter` extra for this workflow. Its reference stack is Starlette 1.7.0 and
Uvicorn 0.54.0, declared directly in that extra; no Prometheus client is needed.

```bash
python -m pip install "chimeraforge[exporter]==0.96.0"
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

In 0.99.0 (unreleased), GET or HEAD `/readyz` exposes a small cached-readiness
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
