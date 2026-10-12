# Frozen-context sensitivity (2026-10-09)

Source tested and independently reviewed: `620a0ecbb1827aec30eccc3050eeebecb1bd7008`.
Base: accepted portable-plan source `03db82f198ad4e8edd7852d42d96dd28f31e6d7a`.

The public Python and CLI study use the existing shared planner. Behavioral tests
compare an explicit case with an ordinary plan, retain an infeasible zero-budget
case, and check native monthly-token deltas. Full saved MoE/hybrid model geometry,
auto-resolved unified memory and producer paths are preserved. Each study consumes
current engine support, applicable cloud prices, grid/date observations and
quarantined contributions once. Tests alter source files and loader-owned records
after capture and require later cases to keep the captured facts. Policy or GPU
registry changes abort. Output aliases cannot overwrite receiving inputs or
applicable native producer files. Foreign producer paths retain their own flavor.

TDD retained: 24 initial missing-surface failures (`initial-red.log`), then a
selected-configuration failure (`config-red.log`). The latter ensures a context
or batch switch remains visible when the eight candidate identity fields match.
Review exposed four writer-dispatch failures for original corpus/quality paths
and their hardlink aliases (`producer-output-red.log`). The corrected guard
rejects those before dispatch; a foreign-path collision fixture stays distinct
from native source identity. Study/bundle focused validation then passed 120
tests with one skipped in 59.84s. The earlier affected shared-surface run passed
560 tests with one skipped in 81.87s, before the configuration addition.

Required full local gate at the exact source head:

```text
python -m pytest tests/ -q --tb=short
3627 passed, 3 skipped, 14 warnings in 181.97s
```

Exact-head focused branch coverage:

```text
python -m pytest tests/test_plan_study.py -q --cov=chimeraforge.plan_study --cov-branch
59 passed in 80.38s
plan_study.py: 183/192 statements (95.31%); 62/68 branches (91.18%)
```

That is coverage of the new study module, not a full package coverage run.
Package and critical-module floors remain unchanged; exact hosted full coverage
is pending batch publication. Exact CI Ruff paths plus the new tests passed,
115 files were already formatted, configured mypy passed for two source files,
and existing actionlint passed. The small logs record actual outputs.

Prior source `b9d4a973` passed its full suite (3622 passed, three skipped,
191.97s) and new-module coverage (54 passed, 95.16% line / 90.32% branch).
Those logs remain prior-head evidence; the corrected source has the final gates
above. Independent review reproduced the original producer-path defect and
confirmed the corrected public API refuses before any writer is called.

The existing installed wheel/rebuilt-sdist consumer now runs actual public CLI
and Python studies over a saved plan and a relocated bundle, checks byte identity,
native deltas and retained negative outcomes, and rejects output overwrite. Its
origin guard remains active. A local source protocol fixture exercises those
commands with the origin guard explicitly patched; it is source wiring evidence.
Real installed and cross-host results await the existing hosted jobs.

These are modeled sensitivity results. Source authentication, actual served
checkpoint bytes and performance remain unverified; there are no measured GPU
claims or confidence bounds. No harness payloads, model weights or large plans
are retained here. All local task processes completed and no environment, model
or container copies were created. The shared checkout/environment remain PRESERVE
under the continuing builder because prior cleanup rejection remains in force.
