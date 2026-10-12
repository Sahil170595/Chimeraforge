# Measured regression-gate local validation - 2026-10-09

Exact implementation tested/reviewed: `a6f3f72c0f0e2b1f429c0b86173bced3cb351771`,
tree `4ecaeccb2810e1fcebcc704dbaa65bcf9f65f769`, on
`codex/measured-regression-gate`, based on accepted trace replay
`acb3fe3c8476a5e664d90b0c01288a5d983b974e`. The final metadata commit changes
no production code, scripts, tests or workflows.

- Full required `pytest tests/ -q`: **3,798 passed, 3 skipped**, 14 warnings,
  103.79s (`pytest-final.log`); 3,801 collected cases. No live backend required.
- Final gate and existing installed-consumer source regressions with branch
  coverage: **114 passed**, 1 warning, 14.37s (`focused.log`). Gate modules:
  367/392 lines (93.62%), 173/196 branches (88.27%), 91.84% combined.
  This is focused coverage, not the hosted global coverage gate.
- Exact CI Ruff check/format paths pass (121 files), existing mypy paths pass
  (2 files), actionlint exits0 (`lint.log`). Five feature files parse with
  Python3.10 grammar, and public API type annotations resolve. Grammar parsing
  is not actual Python3.10 execution evidence (`coverage-summary.json`).
- Root and independent reviewer rechecked the exact implementation, including
  cache evidence, strict finite JSON, canonical duplicate detection and native
  TTFT aliases. Prior-head full passes and actual red findings are recorded
  separately in `red-summary.json`; none is final-head qualification.

Source protocol fixtures exercise every declared receipt/pair/rule, exact
replicate population, raw-sample aggregate recomputation, observed conditions
before/after, intentional treatments, native metric bases, complete request
coverage, cache absence versus known contradictions, unknown counters bounded
by observed prompt capacity, atomic output/input aliases and defensive JSON.
They are synthetic protocol evidence, not measured performance. Raw private
prompts, completions, option values and arbitrary provider metadata are not
included in this evidence directory or gate receipts.

The existing installed wheel/sdist consumer now runs the public CLI for all
four outcomes using clearly labeled synthetic protocol fixtures. The existing
CPU serving consumer adds one fresh three-request saved-plan benchmark to the
already-owned pinned Ollama0.35.1/Smol endpoint. Together with its prior actual
benchmark this exercises native arithmetic and required-cache refusal, without
a shared-runner speed threshold. **Actual installed wheel/sdist/CPU and unchanged
global coverage floors remain pending exact hosted qualification after batch
publication.** No local model execution, new dependency/environment copies,
containers, worktrees or CI jobs were created.

The native wall-rate denominator is captured before post-run metadata and
excludes preflight/metadata. Ollama server decode/prefill/total durations remain
separate from SSE client decode/first-content/call bases. Missing actual prompt
length, cache evidence or requested metric cannot pass. An explicit cache
absence waiver never waives known changes or disabled-cache contradictions;
unknown counters remain unknown. Duplicate identities exclude irrelevant
labels while retaining validated execution facts, without claiming fraud or
independent executions.

All task-owned test sessions have closed. Shared checkout/environment remain
PRESERVE due the prior cleanup rejection and parent-owned publication; no
deletion is retried. Gate decisions are conditional engineering comparisons,
not confidence intervals, independent cold-run proof, served-file authentication,
GPU/planner accuracy or queue-inclusive SLO qualification.
