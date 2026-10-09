# Request-trace local validation - 2026-10-09

Source boundary on `codex/trace-replay`, based on accepted sensitivity head
`d9f0f017c28011d0106381d2b2ba113779547677`. No publication or hosted proof yet.

- Focused real source CLI/API, Ollama HTTPX streaming protocol, cancellation,
  complete-population, privacy, timing arithmetic and existing backend/convention
  regressions: **360 passed**, 6 warnings, 6.27s. Synthetic adapter/protocol fixtures
  are not installed package, live CPU inference or GPU performance evidence.
- Focused trace modules: 249/263 lines and explicit branch metrics in
  `coverage-summary.json`; global coverage floors remain unchanged and pending
  exact hosted qualification after branch publication.
- Exact CI Ruff check/format paths pass (117 files), existing mypy paths pass
  (2 files), actionlint exits 0, four new files parse with Python 3.10 grammar.
  Syntax compatibility is not an actual Python 3.10 execution claim.
- Full required plain pytest is pending at this immutable source boundary; its
  actual terminal result will be added before final local handback.

`red-summary.txt` preserves hashes/counts of actual retained failure logs,
including missing API/CLI, streamed first-frame coalescing, no-origin false rate,
Windows clock resolution and shortened installed-oracle population. `lint.log`
records actual CPython 3.12.13 Windows clocks: GetTickCount64 monotonic resolution
0.015625s versus QueryPerformanceCounter perf_counter resolution 0.0000001s.
The implementation uses the existing high-resolution clock primitive and
rechecks absolute arrivals/deadline after event-loop timer wakeups.

The existing installed CPU consumer is extended with three varied prompt/cap/
arrival requests against its already owned pinned Ollama 0.35.1/Smol endpoint.
It recomputes timing/native-count/SLO arithmetic and keeps real positive horizon,
ordered timestamp and exact population guards, without a speed threshold.
That actual installed wheel/sdist/CPU evidence remains pending hosted execution.
No local models, dependency/environment copies, containers or new CI jobs exist.
Shared worktree/environment remain PRESERVE due the prior cleanup rejection;
no deletion is retried. All local test processes completed before this commit.

Primary API references checked: [Python performance counter](https://docs.python.org/3.12/library/time.html#time.perf_counter),
[Ollama generate](https://docs.ollama.com/api/generate), and
[pinned Ollama response types](https://github.com/ollama/ollama/blob/v0.35.1/api/types.go).
Native prefill remains server prefill; actual streamed first output is separate.
