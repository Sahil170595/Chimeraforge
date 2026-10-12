# Request-trace local validation - 2026-10-09

Exact implementation tested/reviewed: `b7b4841cd128bfbef850bdb059bfe6b10333c7c9`,
tree `27f7e57ade6785a9d117cc4f87a1ed64be454b69`, on `codex/trace-replay`,
based on accepted sensitivity `d9f0f017c28011d0106381d2b2ba113779547677`.
The final metadata commit does not change production/scripts/tests/workflows.

- Full required `pytest tests/ -q`: **3,698 passed, 3 skipped**, 14 warnings,
  220.04s (`pytest-final.log`); 3,701 collected cases. No live backend required.
- Focused trace, existing backend/runner/decode and repository conventions with
  branch coverage: **376 passed**, 6 warnings, 8.12s (`focused.log`). Trace
  modules: 279/295 lines, 83/92 branches; per-module and existing Ollama adapter
  metrics appear in `coverage-summary.json`. This is focused, not global coverage.
- Exact CI Ruff check/format paths pass (117 files), existing mypy paths pass
  (2 files), actionlint exits0, six changed/new files parse with Python3.10
  grammar. Syntax compatibility is not actual Python3.10 execution evidence.
- Root and independent auditor rechecked the exact implementation and corrected
  graceful stop, active callback, complete-frame and fragmented-frame fairness
  boundaries. Raw prior-head full results and actual failure hashes/counts are
  preserved in `red-summary.txt`; those results are not final-head qualification.

The real source API/CLI and HTTPX0.28.1 native MockTransport fixtures test timing,
privacy, complete populations, partial/failed/cancelled/unstarted outcomes,
output aliases, streamed first content, native final counts, byte limits, EOF,
graceful setup/metadata stop, external cancellation and stable receipt fingerprints.
They are **source protocol fixtures**, not installed packages or model inference.

The Windows CPython3.12.13 diagnostic identified GetTickCount64 monotonic resolution
0.015625s versus QueryPerformanceCounter perf_counter resolution0.0000001s.
The implementation uses the existing high-resolution performance clock and
rechecks absolute scheduled arrivals/deadline after timer wakeups. The two small
native diagnostics separately record real HTTPX streaming cancellation using
actual clocks. Windows timers can wake early; those timings are not serving
benchmarks. Fragment byte count is computed from the exact synthetic chunks.

Repeated-tail-copy starvation and no-newline fragmented starvation were reproduced
before fixing linear scanning plus independent32frame/32chunk/64KiB cooperative
checkpoints. A transitional controlled-clock test had a mismatched real sleeper;
its synthetic sleeper now follows the same injected clock. The actual timed
native diagnostics remain separate. No tokens are inferred from frames/chunks.

Existing installed CPU acceptance is extended with three varied prompt/cap/arrival
requests on its already owned pinned Ollama0.35.1/Smol endpoint. The consumer
recomputes native/timing/SLO arithmetic, exact population and original/receipt byte
associations, retaining real positive horizon/ordered timestamp guards without a
speed threshold. **Actual installed wheel/sdist/CPU and unchanged global coverage
floors remain pending exact hosted qualification after batch publication.**
No local models, dependency/environment copies, containers or new CI jobs exist.
All owned test sessions have closed. Shared checkout/environment remain PRESERVE
due the prior cleanup rejection; no deletion is retried.

Primary references checked: [Python performance counter](https://docs.python.org/3.12/library/time.html#time.perf_counter),
[HTTPX streaming](https://www.python-httpx.org/async/#streaming-responses),
[Ollama generate](https://docs.ollama.com/api/generate), and
[pinned response types](https://github.com/ollama/ollama/blob/v0.35.1/api/types.go).
Native prefill stays separate from actual client first output. No GPU qualification,
served-file authentication, every-token SLO or independent cold-run claim is made.
