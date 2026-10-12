# Serial trace campaigns

`trace-campaign` and async `api.replay_trace_campaign` execute one frozen workload
serially against an existing endpoint. This is the **unpublished 0.64.0
candidate**, requiring candidate source or wheel. The public install remains
`chimeraforge==0.61.0`; the preceding 0.62.0 streaming and 0.63.0 trace-gate
candidates retain their separate scopes. Campaigns do not launch servers,
download models, retry requests, warm up endpoints or promise cold runs.

Create the private workload using the [trace schema](trace-replay.md), then run:

```bash
chimeraforge trace-campaign workload.json --model llama3.2-3b --backend ollama --replicates 3 --campaign-timeout 1800 --concurrency 1 --request-timeout 300 --trace-timeout 600 --latency-slo 2000 --first-output-slo 500 --tpot-slo 50 --out campaign.json --json
```

`--base-url` selects the existing endpoint. The workload's prompts are sent
there; campaign receipts contain prompt hashes/descriptors, not prompts or
completions. Endpoint userinfo and query credentials are stripped from receipts.
Backend failures and cleanup diagnostics retain categorical stage/type evidence
without raw provider exception text or tracebacks.

## Frozen manifest and complete declared population

Before endpoint contact, preparation performs one bounded held workload read
and validates all client controls. Workloads contain 1–1024 requests per
replica; `--replicates` is an exact integer in 1–16, and the total declared
population cannot exceed 4096 requests. Request/trace/campaign budgets must be
finite positive seconds at most 3600. Campaign timeout defaults to 1800;
request timeout to 300; trace timeout to 600; replicas to 3; concurrency to 1.
Other trace limits and positive SLO validation remain unchanged. These request
population bounds **do not impose a serialization-byte ceiling on output**.

The manifest freezes the original raw/canonical workload hashes, ordered
descriptors, model/backend/sanitized endpoint, concurrency, timeouts, targets,
population and fixed stop-after-first-incomplete policy. Its fingerprint is
prepared before the campaign clock starts and before adapter construction.
This is a client-recorded declaration; it does not prove external
preregistration or authenticated preparation time.

Every replay uses the same frozen `TraceRequest` objects through the existing
typed-list route. Changing or deleting the original file between replicas cannot
change their requests. Each child therefore truthfully records `raw_sha256:null`;
the manifest separately retains the original file hash. Child canonical hashes
and ordered descriptors bind to the manifest. Child receipts and fingerprints
are retained unmodified; no receiving wrapper overwrites their provenance.

Every planned replica retains its index, manifest/workload reference, state,
actual start/end observations where started, and native receipt or categorical
failure evidence:

| State | Retained evidence |
|---|---|
| `completed` | Native exit 0, complete request population and completed adapter cleanup |
| `incomplete` | Full native failed/partial/cancelled/stopped receipt, including unstarted requests or cleanup failure |
| `failed` | Replay boundary supplied no accepted native receipt; fixed categorical error, receipt null |
| `not_started` | Declared manifest/workload reference and reason; no invented timestamps or native values |

After the first noncomplete replica, all remaining planned replicas stay
`not_started`. Execution is strictly serial with no retries/warmup and no
survivor-only aggregation. A native SLO breach or unknown target alone does not
make a completed execution incomplete. Native goodput/timing/SLO observations
remain in the child receipt without a campaign speed threshold.

## Deadlines, stopping and resource ownership

The whole campaign budget starts after manifest preparation. It covers
admission, preflight, metadata and scheduled replay. Each replica retains its
existing request and trace limits. Admission samples are checked against the
campaign deadline before recording a start or creating native replay work.

An owned replay task races an owned caller-event waiter and remaining budget
using `asyncio.wait`. Deadline/caller stop sets a **separate child stop event**;
the caller's Event is never mutated to impose the campaign deadline. The owned
waiter is cancelled/drained, then native replay is awaited cooperatively so its
full stopped receipt survives. No direct `wait_for`/`asyncio.timeout` cancellation
of replay is used to enforce the budget.

Drain is cooperative and may be unbounded for a hung adapter. This is not a
guaranteed wall-time return or proof of physical provider termination. Native
cleanup failures remain explicit. SIGINT in the CLI signals receipt-producing
stop; external async `Task.cancel()` propagates after cancelling/draining owned
tasks instead of returning a synthetic stopped receipt. Prior SIGINT handlers
are restored by the CLI.

Simultaneous native completion and caller stop preserves that completed receipt
and blocks any successor. If it was the final planned replica, all declared
executions completed: outcome/exit remain completed/0 while `stop_reason`
retains the observed control event. If successors remain, they are unstarted
and the population is incomplete/exit 1. The same distinction preserves a
completed final receipt drained after the budget expired; budget observations
do not rewrite completed native execution facts.

## API and output

```python
import asyncio
from chimeraforge import api

async def run():
    result = await api.replay_trace_campaign(
        "workload.json",
        model="llama3.2-3b",
        backend="ollama",
        replicates=3,
        campaign_timeout=1800,
        concurrency=1,
        request_timeout=300,
        trace_timeout=600,
        slos=api.TraceSLO(latency_ms=2000, first_output_ms=500, tpot_ms=50),
        stop_event=asyncio.Event(),
    )
    result.save("campaign.json")
    return result.to_dict()

receipt = asyncio.run(run())
```

The API also accepts `list[TraceRequest]` or `Path`. `TraceCampaign.to_dict()`
is defensive; `save()` writes atomically and protects the held workload path,
including hardlink aliases. Failed replacement preserves previous output.
CLI `--out` checks input aliases before any endpoint contact. JSON/prose modes
both retain full execution outcome; argument-parser errors use usage/error
output, while dispatched input/output failures use the selected mode.

| Exit | Meaning |
|---|---|
| `0` | Every declared replica completed native execution; SLO qualification is separate |
| `1` | Incomplete/stopped population, including categorical replay failure and unstarted successors |
| `2` | Invalid workload/options or output failure |

External preregistration/time authentication, independent cold/cache runs, GPU
geometry, served weights and physical provider termination remain unverified.
Serial order is not independence, cache reset or scientific qualification.

The existing hosted CPU consumer reuses its pinned Ollama endpoint/model/job
for a two-replica, one-request campaign and a missing-model campaign that does
no generation. It checks original/canonical manifest bindings, unchanged child
fingerprints, native counts/timing arithmetic and retained populations without
speed thresholds. Local mocks are source protocol fixtures; actual hosted
installed/native qualification remains a separate gate.
