# Original-fleet gate functional controls

Regenerate the aggregate using the current source CLI/API/JUnit, without traffic,
models, GPUs or containers:

```bash
uv run --no-sync python scripts/ci_fleet_trace_gate.py --record validation/2026-10-25-fleet-trace-gate/functional.json
```

The helper creates a genuine unchanged native N3/TP2/PP1 candidate and explicitly
synthetic metadata, timing and ownership evidence. It exercises conditional 0,
regression 1 and inconclusive 3 through both public API and actual CLI, validates
JSON/JUnit consistency and checks input/output aliases refuse 2 without clobbering.
The aggregate contains current source hashes and measured control outcomes; it does
not claim that synthetic metadata describes running hardware or inference.

`python -m pytest tests/test_fleet_trace_gate.py tests/test_trace_gate.py
tests/test_fleet_trace_lifecycle.py tests/test_ci_acceptance.py` covers semantic-copy
relabeling, equivalent supported reals, original population/source commitments,
partial/zero-member evidence, cache/binding drift, strict threshold equality,
zero-baseline arithmetic, held-byte budgets and guarded JUnit/JSON outputs.

The same synthetic consumer runs inside existing installed wheel and rebuilt-sdist
acceptance on all three hosted OS profiles. The existing pinned CPU job additionally
feeds its unchanged actual .79 API/CLI original-fleet receipts into gate API/CLI and
JUnit as adverse evidence (3). It reuses the existing assets/store/daemons and makes
no additional inference requests. CPU/GPU binding mismatch and unknown cache facts
remain visible. Exact-head hosted logs establish those separate outcomes; this
local aggregate does not assert that the hosted jobs passed or prove independence,
scientific replication, native GPU execution or prediction accuracy.
