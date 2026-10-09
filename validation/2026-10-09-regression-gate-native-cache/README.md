# Native-cache acceptance correction - 2026-10-09

Implementation tested/reviewed: `c4f03125378e539775cc804f753ffedb98b074ce`,
tree `e3bfc400f2c4af1a9f0fa943067d9cb850e611e6`, based on
`7053dab6dacc2703431385c36c46c880be13271a`. Final metadata changes no
production code, acceptance scripts, tests or workflows.

- Required related source checks: **149 passed**, one warning, 7.38s
  (`focused.log`), covering the installed-consumer source harness, regression
  gate and existing native decode adapter. This includes 27 new protocol cases.
- Collection only: **3,828 test cases** (`collection.log`). Collection does
  not establish that all those cases passed. No full suite was repeated for
  this consumer-only correction; the prior 3,798-pass/3-skip local record and
  old7053 hosted 3,800-pass/1-skip coverage record remain historical evidence.
- Exact CI Ruff check/format paths pass (120 files), configured mypy paths pass
  (two files), actionlint exits0 (`lint.log`). Production package, adapters,
  gate, workflows, dependencies and all prior validation blobs are unchanged.
- Root and independent reviewer rechecked exactc4. Native known counts,
  unknown counters, disabled-cache contradictions, residual prompt capacities,
  workload changes, before/after conditions, both metric directions, input
  byte associations and every accepted outcome have source-protocol coverage.

Actual [hosted CPU job113904380451](https://github.com/Sahil170595/Chimeraforge/actions/runs/37955012465/job/113904380451)
failed because the consumer required both cache states to be `unknown`, after
the gate's exit3 check had passed. The pinned API supports nullable native
cached counts: [metrics](https://github.com/ollama/ollama/blob/v0.35.1/api/types.go#L515-L523)
and [total prompt-count mapping](https://github.com/ollama/ollama/blob/v0.35.1/llm/llama_server.go#L1488-L1500).
Total prompt counts already include cached tokens. Initial failure retained no
final benchmark/gate aggregate JSON; its exact counter populations and full
blocking reasons are **not inferred** from server log messages.

The correction retains the original CPU/Ollama/version policy and required
cache evidence. It derives native cache/workload/condition facts and the
token-sum/client-wall plus server-prefill arithmetic before accepting native
exit0,1 or3. Operational exit2 is still refused. A regression is an observed
result, not a shared-runner speed failure. No invented prefix-cache expectation,
zero-hit/cold inference or performance qualification is introduced. Before
assertions the consumer prints only numerical population and reported cache/
blocker evidence, visibly marked validation pending; final summaries contain
verified fields. Prompts, completions, private options and warnings are excluded.

**As of exactc4, corrected installed/hosted qualification is pending parent
publication.** Local fixtures exercise the actual gate CLI and unchanged native
receipt parsing, but synthetic benchmark generation is not model inference or
installed acceptance. The red summaries retain hashes of actual failing outputs
without duplicating raw provider logs or private artifacts. All owned test
processes closed; no new dependencies, environments, models, containers or
worktrees were created. Shared resources remain PRESERVE due the prior cleanup
rejection and parent-owned publication; no deletion is retried.
