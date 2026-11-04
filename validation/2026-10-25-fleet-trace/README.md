# Original-fleet trace functional controls

Regenerate the aggregate from the current source and owned CPU HTTP/HTTPS/mTLS
protocol fixtures, without models, GPUs or containers:

```bash
uv run --no-sync python scripts/ci_fleet_trace.py --record validation/2026-10-25-fleet-trace/functional.json
```

The helper creates an original native N3/TP2/PP1 saved plan, then exercises actual
CLI/API behavior for vLLM/SGLang protocol fixtures: complete, mTLS+bearer,
short-token mismatch and whole-preflight refusal. Each invocation keeps six
ordered rows and all three declared slots. The fixture has one owned listener
with three paths, not three independent inference servers. The aggregate records
source hashes, actual exit/contact counts, input preservation and fixture closure.
It is source protocol evidence, not installed-distribution or GPU qualification.

`python -m pytest tests/test_fleet_trace.py tests/test_fleet_trace_lifecycle.py
tests/test_fleet_trace_ownership.py tests/test_fleet_trace_cli.py` verifies strict
receiving mutations, shared admission/concurrency, cancellation, final cleanup
allowance and input-alias controls without rewriting production source.

The same protocol consumer is called by existing wheel and rebuilt-sdist
acceptance on all three hosted OS profiles. The existing hosted CPU job separately
reuses its one pinned Ollama/model download/import and initialized writable store
for three owned native daemon groups. It runs six original rows through the new
API and the same six through the new CLI (two protocol invocations, not scientific
replications), retaining CPU/GPU mismatches and unavailable offload diagnostics.
The native model's original default cap16 is retained; every replay row must
generate a positive count within its explicitly requested cap4. Client interval
occupancy is derived from actual row start/terminal timestamps and must stay
within globalC3, separately from the declared concurrency control.
Those hosted outcomes must be read from their exact-head completed job logs;
the local aggregate does not assert that they passed.
