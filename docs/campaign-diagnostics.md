# Whole-campaign diagnostics

**Since 0.92.0.**
Render one complete native serial or original-fleet campaign as HTML, SVG or
Markdown. Every declared execution stays visible, including failed, incomplete
and not-started slots. Native child observations and missing receipts remain
distinct. Rendering is offline and does not run an optimizer or backend.

```python
from chimeraforge import api

report = api.render_trace_report(
    "campaign.json", kind="trace-campaign", format="html",
    title="Whole campaign diagnostics",
)
report.save("campaign.html")

fleet = api.render_trace_report(
    "fleet-campaign.json", kind="fleet-trace-campaign", format="svg",
)
fleet.save("fleet-campaign.svg")
```

```bash
chimeraforge report --kind trace-campaign --input campaign.json --format html --output campaign.html
chimeraforge report --kind fleet-trace-campaign --input fleet-campaign.json --format svg --output fleet-campaign.svg
chimeraforge report --kind trace-campaign --input campaign.json --format markdown
```

These extend the existing `report` command and `render_trace_report` API. The
ordinary `trace`, `fleet-trace` and benchmark defaults remain compatible. Trace
modes require exactly one `--input`, with no benchmark selectors or `--json`.
Successful CLI stdout and the saved artifact have the same UTF-8/LF bytes.
Invalid input/output produces a categorical exit 2 error with no partial document.

The returned `TraceReport` still serializes only `content`, `kind`, and `format`.
Source-protection guards are runtime-only and survive ordinary copy, deepcopy and
dataclass replacement. `save` preserves source/guarded paths and aliases.

## Complete populations and native facts

The existing strict campaign loaders validate one held snapshot and all embedded
native receipts before rendering. Panels retain all K ordered executions, each
original fleet N and all requested rows, including zero-assigned members. Serial
campaigns declare endpoint work, not a fleet N=1 or distinct machines. Chat
descriptors introduced by 0.89 remain admitted without exposing message text.

Returned children reuse the existing closed trace presentation: native execution
counts, per-request state/timing/token/SLO/basis, known goodput, bindings and
cleanup remain native facts. No percentile or regression-gate math is rebuilt.
Panel scales and native client clocks stay separate; campaign-relative start/end
offsets describe the outer campaign. No pooled latency, mean, percentile,
goodput, concurrency or favorable-execution selection is introduced.

If a native child is absent, the validated manifest still supplies declared
request ordinals and planned member routing. All original members and rows are
shown, but observed counts, times, tokens, cleanup and member states remain
**unavailable**. A declared member with no routed rows is not an observed
zero-load success. Known native zero remains zero. Native campaign completion
and exit status are not a regression-gate verdict or deployment proof.

Source SHA256/fingerprint/size describe the held file or object representation.
Child hashes and sizes explicitly describe the **embedded serialized child**,
not alleged original child-file bytes. Fingerprints are consistency identifiers,
not producer authentication. No source labels are reopened.

## Privacy, representations and limits

The public projection excludes model/endpoint names, URLs, request IDs, prompts,
chat history, completions, diagnostics, credentials and private absolute paths.
Caller titles are intentionally public text and are validated/escaped; HTML/SVG
has no scripts, remote assets, links, telemetry or application network behavior.

Both native campaign input profiles remain 16 MiB. K is at most 16, original fleet N
at most 16, and K times requests per execution at most 4,096. The separate complete
exported-report cap remains 8 MiB for every format. A valid input may exceed that
presentation cap and is refused without truncation, a partial target or partial
stdout. These bound admitted representations, not total process heap.

SVG retains one complete canvas, measured from actual wrapped native panel
layouts. Each panel has distinct title IDs/references and all original rows;
public Unicode titles reuse the native conservative title wrapping policy.
There is no viewport-only export, hidden last execution or shortened population.

The evidence is descriptive client software evidence. It does not authenticate
served files, GPU execution, physical independence, cold/cache independence,
customer traffic, performance/SLO capacity, human truth or scientific conclusions.
The aggregate producer and existing installed/hosted browser consumers are
documented in the [dated validation record](../validation/2026-11-01-whole-campaign-diagnostics/README.md).
