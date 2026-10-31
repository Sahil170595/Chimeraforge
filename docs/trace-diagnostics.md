# Trace diagnostics (unreleased 0.86.0)

Public installation remains **0.81.0**. The unreleased source adds descriptive
reports for one strict ordinary trace or one complete original-fleet trace.
Benchmark report defaults and output remain unchanged.

```python
from chimeraforge import api

artifact = api.render_trace_report(
    "fleet.json", kind="fleet-trace", format="html", title="Trace diagnostics"
)
artifact.save("fleet.html")
# artifact.content is the complete admitted text; kind/format are public fields.
```

```bash
chimeraforge report --kind fleet-trace --input fleet.json --format html --output fleet.html
chimeraforge report --kind trace --input trace.json --format markdown --output trace.md
chimeraforge report --kind fleet-trace --input fleet.json --format svg --output fleet.svg
```

The new modes require exactly one `--input` and reject benchmark selectors
`--results-dir`, `--results-files` and metadata-only `--json`. API defaults are
`kind="trace"`, `format="html"`, `title="Trace diagnostics"`; the existing CLI
format default remains Markdown. An explicit title is preserved even when it
equals the old benchmark default. HTML is static CSS plus inline SVG; SVG is
standalone; Markdown contains complete tables. No script or external asset is
embedded. Saved bytes and stdout are identical UTF-8 with LF line endings.
With `--output`, publication finishes before stdout. Exit 0 means an artifact was
produced, even for a native failed/incomplete/configuration-mismatch receipt.
Invalid, unsupported, unsafe or over-limit rendering exits 2, without normal
artifact stdout or a partial replacement.

## Inputs and native scope

`api.render_trace_report(source, *, kind="trace", format="html",
title="Trace diagnostics") -> api.TraceReport` accepts the matching native
`TraceReplay`/`FleetTraceReplay`, a native dictionary or a saved JSON path.
Strict native validation happens before presentation. Plan-trace and campaign
envelopes are rejected; no child is silently unwrapped. This is not a new gate,
comparison, JUnit exporter or performance assessment.

Ordinary receipts come from `api.replay_trace(...) -> api.TraceReplay`, the direct
`chimeraforge.bench.trace.replay(...)`, or `trace` without `--from-plan`:

```bash
# This measurement requires your already-running endpoint and private workload.
chimeraforge trace workload.json --model YOUR_SERVED_MODEL --backend vllm \
  --base-url http://127.0.0.1:8000 --out trace.json
chimeraforge report --kind trace --input trace.json --format html --output trace.html
```

`api.replay_plan_trace` and `trace --from-plan` instead produce a plan-trace
wrapper, which this renderer explicitly rejects. Use a native ordinary receipt
or the complete `api.replay_fleet_trace` result; no wrapper is silently unwrapped
and no plan/configuration outcome is inferred from an ordinary child.

All original request rows and all original fleet members remain, including
failed/partial/cancelled/not-started requests and zero-assigned/error members.
Generated row/member ordinals replace identities. A shared relative client clock
is retained. No clock means planned-only, with missing observations unavailable.
A zero-valued timing or token count remains zero. Native execution,
configuration, SLO and cleanup outcomes remain separate.

Scheduler lag is scheduled-to-arrival; client queue is arrival-to-start. The
client active interval is start-to-terminal, including transport, server queue
and potentially timeout/cancellation drain. It is **not server service time**.
Native scheduled-to-first-output includes client scheduling/queue, and is not
server prefill/TTFT. TPOT retains the native named per-request mean basis; it
is not every-token latency. No quantiles, intervals, pooling or causal attribution
are recomputed.

## Public projection and protection

Only generated ordinals, fixed native state labels, finite counts/timings/targets
and hashes enter the presentation. Raw identities, endpoint/model/version strings,
errors, serving observations, plan data, prompts, raw JSON and private paths are
excluded, including hidden markup. Explicit caller titles are intentionally
public, bounded to 200 characters/1024 UTF-8 bytes, single-line and control-free,
and escaped for each format. Treat a title's content as a deliberate disclosure.
Hashes bind the held file bytes or a native object snapshot as labeled; they do
not authenticate traffic, GPUs, weights, physical independence or file origin.

A saved input's held path is unioned with the native typed receipt's private
protected inputs. Delayed `.save()` and copy/replace keep those runtime guards
outside public dataclass fields and `asdict`. Dictionaries do not recover a
source filename from a hash. Saving refuses lexical/resolved/same-file aliases
of known inputs. Each file is written atomically; no filesystem race immunity
or multi-file transaction is claimed.

Native ordinary input 8 MiB and fleet input 32 MiB limits remain. Before an eager
native dictionary/typed copy, the supported finite ASCII JSON encoder counts the
native compact representation; saved paths use the bounded native reader once.
The existing strict receiver is then reused once. Each complete rendered format
has its own **8MiB** UTF-8 limit, including escaping, markup and final LF. Excess
refuses the whole artifact, without truncation or a hidden remainder. The bound
covers exported traversal/materialization, not earlier receipt construction,
HTTP work, one encoder scalar chunk, concurrent caller mutation, runtime or
browser heap.

## Qualification boundaries

[The regenerable source record](../validation/2026-10-31-trace-diagnostics/README.md)
uses synthetic native statuses/timings and actual source API/CLI processes.
Original/rebuilt installed distributions run the same consumer under all-loaded
module-origin guards. Hosted Ubuntu alone selects the pinned Playwright 1.64.1
nondefault `browser-ci` dependency group and Chromium headless shell. It opens
actual saved API/CLI HTML and SVG for both distributions, checks complete
population, geometry, null/zero/last-row and hostile-content behavior, plus separate
ordinary long-integer and wide Unicode title documents. It records
page HTTP(S) interception and console errors. The two allowlisted PNGs have
one-day retention for independent visual review. Browser execution and visual
acceptance are separate from source/XML checks; no local or embedded browser is
used for this feature's development. These fixtures do not qualify real engines,
GPU execution, traffic authenticity or performance.

Native browser API references: [context request routing](https://playwright.dev/python/docs/api/class-browsercontext#browser-context-route),
[screenshots](https://playwright.dev/python/docs/screenshots),
[headless-shell installation](https://playwright.dev/python/docs/browsers#chromium-headless-shell).
