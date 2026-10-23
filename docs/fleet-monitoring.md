# Passive declared-fleet monitoring

**Unreleased 0.76.0 candidate.** Use this source or its built wheel. Published
0.71.0 supplies the existing single-endpoint `monitor`, including monitoring an
endpoint selected from a multi-replica plan; it does not establish whole-fleet
coverage. `monitor-fleet` is separate and requires one explicit endpoint per
original saved replica. It never changes the selected candidate to one replica.

## Observe an existing deployment

Keep the original `fleet-plan.json` and candidate index used for the
[homogeneous Compose fleet](deployment.md). For example, an original native
three-replica candidate can be observed at three explicitly targeted endpoints:

```bash
chimeraforge monitor-fleet --from-plan fleet-plan.json --candidate-index "$FLEET_INDEX" \
  --endpoint replica-1=http://127.0.0.1:9001 \
  --endpoint replica-2=http://127.0.0.1:9002/metrics \
  --endpoint replica-3=http://127.0.0.1:9003/metrics \
  --ttft-slo 500 --interval 30 --windows 1 \
  --observation-seconds 60 --cleanup-seconds 2 --json \
  --prometheus fleet-monitor.prom
```

These are existing operator targets, not endpoints the command starts. The saved
candidate supplies the exact model label and vLLM/SGLang histogram contract.
Explicit `--ttft-slo`/`--tpot-slo` override saved millisecond targets; omitted
targets use the saved request and retain that source. At least one target is
required. SGLang ITL does not establish per-request TPOT. Native histogram bucket
bounds, missing data, resets, no traffic and unknown outcomes remain authoritative.
There is no inference, model download, active load or GPU probe.

```python
import asyncio
from chimeraforge import api

saved_path = "fleet-plan.json"
saved = api.load_plan(saved_path)
index = next(
    i for i, row in enumerate(saved.to_dict()["result"]["candidates"])
    if row["backend"] == "vllm" and row["quant"] == "FP16"
    and row["n_agents"] == 3 and row["tensor_parallel"] == 2
    and row["pipeline_parallel"] == 1 and row["offload_fraction"] == 0
)
request = api.FleetMonitorRequest(
    endpoints=(
        api.FleetEndpoint("replica-1", "http://127.0.0.1:9001"),
        api.FleetEndpoint("replica-2", "http://127.0.0.1:9002/metrics"),
        api.FleetEndpoint("replica-3", "http://127.0.0.1:9003/metrics"),
    ),
    ttft_slo=500,
    interval=30,
    windows=1,
)
report = asyncio.run(api.monitor_fleet(saved_path, request, candidate_index=index))
print(report.exit_code, report.to_dict()["declared_coverage"])
```

The asynchronous API accepts `PlanArtifact | str | Path`. `stop_event` may be an
`asyncio.Event`: setting it returns a retained partial report after cleanup;
pre-setting it contacts nothing. Direct cancellation of the caller task follows
normal async semantics: `CancelledError` is re-raised after owned cleanup, and no
partial report is returned. The CLI maps SIGINT to the stop event.

## Admission and shared budgets

Endpoint IDs use 1--64 ASCII letters/digits/`_.-`, beginning with a letter/digit.
IDs and normalized URLs must be distinct; population must equal the original
candidate's `n_agents`, from 1 through 16. URLs are bounded to 2,048 characters,
HTTP(S), without credentials, query strings, fragments or control/space bytes.
Roots and terminal `/metrics` routes, including proxy prefixes, are admitted.
Custom metrics paths and ambiguous repeated trailing-prefix slashes are refused.
HTTPX canonicalization catches host/scheme case, default-port, dot-segment and
IDNA aliases while preserving meaningful prefix/path bytes. Normalized distinct
URLs do not prove distinct servers or physical independence.

| Control | Default | Admission limit |
|---|---:|---:|
| `interval` / `--interval` | 30 seconds | positive, at most 600 seconds |
| `windows` / `--windows` | 1 per endpoint | total N x windows at most 256 |
| `timeout` / `--timeout` | 10 seconds | positive, at most 600 seconds |
| `observation_seconds` / `--observation-seconds` | 60 seconds | positive, at most 600 seconds |
| `cleanup_seconds` / `--cleanup-seconds` | 2 seconds | positive, at most 10 seconds |
| `concurrency` / `--concurrency` | 4 HTTP exchanges | 1--16 |
| `max_requests` / `--max-requests` | 256 attempts | 1--2,048 |
| `max_body_bytes` / `--max-body-bytes` | 8 MiB accepted body | 1--32 MiB |

All numeric controls must be finite; booleans are not integers. Saved model
identifiers are bounded to 4,096 characters. Plan admission reuses bounded
held-byte/node/depth parsing. Invalid shape, population, unsupported backend or
overlimit work refuses before contact. A low positive quota or short deadline is
valid and can return partial/error/unstarted coverage rather than a pass.

Attempts are charged immediately before transport contact, after semaphore
admission. Failed and fallback requests count, including every native metadata
route. A charged in-flight attempt need not reach the server before cancellation.
The semaphore covers stream consumption and closure. Accepted body chunks share
one fleet budget; each metrics response is limited to 2 MiB and each metadata
response to 1 MiB. Identity encoding is requested, and encoded responses are
refused before decoded expansion. These are accepted-body limits, not a bound on
discarded/in-flight chunks or transport buffers. Native optional-metadata error
handling cannot turn a response-contract or global-budget violation into a pass.
Using exactly the final quota can pass when all work completed; an attempted
overrun terminates further work.

One observation deadline covers semaphore waiting, intervals, metrics and all
metadata requests. Adjacent windows reuse their shared metrics/metadata boundary;
window duration uses actual metrics-completion monotonic timestamps. Metadata
brackets remain approximate. Cleanup has a separate, shared allowance: owned
workers are cancelled and joined, clients/streams/pools are closed, and closure
overrun remains a non-pass fact even when resources close later. These are
cooperative deadlines, not universal kernel/DNS/cancellation-resistant hard-return
guarantees. No HTTP worker threads are abandoned.

## Results and limits

All declared slots remain in caller order, with `complete`, `error`, `cancelled`
or `unstarted` state, native completed windows, and admitted metadata observations.
Partial prefixes are retained. Each observation is checked independently against
the original saved facts; a known early identity/configuration mismatch or SLO
breach survives a later unavailable response, error or cancellation. Genuine
before/after brackets are separate from independent observation evidence; no
complete window is fabricated from a lone snapshot. The existing endpoint monitor
also retains a known BEFORE configuration contradiction when AFTER is unavailable.
Unknown-only configuration and engine DP=1 remain compatible with an original
multi-replica candidate; engine DP does not attest full endpoint replica topology.

| Exit | Meaning |
|---:|---|
| 0 | All declared slots complete; native SLOs pass, required identities match, no known config mismatch, no budget violation and cleanup completed |
| 5 | Known required-identity or saved-configuration mismatch, even if later work failed |
| 3 | Known native SLO breach without a binding mismatch, including retained earlier breach |
| 4 | Unknown, missing identity, partial/error/cancelled coverage or incomplete cleanup/budget termination |
| 1 | Invalid/unsupported/unavailable request, plan or output |
| 2 | Native CLI usage/syntax error |

Configuration stays `unverified` when partially unavailable; this is separate
from required model/backend identity and native SLOs. No pooled percentiles or
capacity claim is made. Declared URL coverage does not authenticate processes,
physical GPUs/topology, model weights or the saved plan's source.

Prometheus output uses per-replica labels and one HELP/TYPE per family, plus a
separate all-declared-endpoint qualification gauge. Output aliases of the saved
plan are refused before network contact using the existing native protection.
Textfile output is atomically replaced; this does not imply atomic observations,
atomic source/output snapshots or source authentication.
