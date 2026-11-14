# Trace-envelope JUnit: source qualification

This aggregate record describes **unreleased 0.102.0 source** based directly on
released main `a688af5a604aea0e77d5600b94cb0a1bf8043c0e`. Public installation
remains **0.101.0**. No release, merge or installed-distribution qualification is
claimed here. `functional.json` is generated from the actual local pytest XML
and source files; raw receipts, private fixtures and test logs are not bundled.

Three initial API/CLI tests failed solely because `api.write_trace_envelope` and
`trace-envelope --junit` were absent. Those same tests passed after implementation.
An intermediate expanded attempt had 23 passes and one test-helper ImportError;
the corrected test executes a controlled native mixed fleet campaign instead of
transplanting serialized execution slots. The final selected local suite passed
**1,041 tests**, including all **28** new output controls. A further adverse
shape test first failed because an already-incomplete fleet member bypassed
blocker-list validation; unconditional shape admission then closed that gap.
An initial Ruff fixture-import alias diagnostic was corrected before the final
gates. Overlapping earlier runs are not added to the final total.

Ordinary synthetic native campaigns exercise passing, breached, missing-clock,
missing-higher and required/unrequired unknown-control evidence. Actual native
whole-fleet controlled protocols exercise K=2, N=3 and M=6. A complete passing
execution remains passing beside a breached sibling; required uncertainty then
retains the known failure and adds errors. Complete lower cells stay passing
when a higher cell is missing. Fleet compatibility facts available only in cell
blockers conservatively affect that cell's execution cases. XML never infers
native SLO pass from process exit alone or repeats assessment.

The existing source consumer calls the actual OS CLI and controlled CPU HTTPS
protocols, checks original input bytes, closed ordinal cases, privacy and full
native JSON population. It is also used by the existing hosted installed wheel
and sdist consumers; their final-head results remain pending. There are no new
jobs, uploads, browser/GPU/model runs, performance or physical-independence claims.

A valid 16-cell by 16-execution assessment produces 273 complete cases exceeding
the real 64 KiB XML limit. Refusal preserves both pre-existing sentinels. A
test-local enlarged cap confirms the complete population without truncation.
Other controls check fingerprints, type/kind/shape admission, declared and
consumed inputs, hard-link/mutual aliases, single assessment and individually
atomic files. A second-file failure intentionally leaves the first complete
file: publication is not a two-file transaction. The no-JUnit CLI retains its
existing save path and native stdout/exits.

The exact current workflow Ruff check/format paths passed. The existing seven-file
envelope mypy cohort passed with the new renderer included. `uv lock --check
--offline --no-cache` passed without dependency changes. All 130 universal-lock
package/version pairs passed both existing native advisory lookup layers; this
lock-only lookup does not qualify the borrowed environment as a clean install.
Five added local Markdown links resolve; no existing heading was renamed.

Two local canonical mypy invocations (base and inherited fleet cohort) stopped
before source checking because Python 3.13's correctly locked NumPy 2.5.3 stubs
use PEP 695 while mypy targets Python 3.11. Hosted lint uses Python 3.12 and its
separate locked NumPy 2.4.6. No dependency repin or checker ignore was added.
The native audit helper also inventoried unrelated global packages exposed by
the borrowed system-site-packages environment and failed on a private package
absent from PyPI plus stale global pip/tornado advisories. No global package was
changed. These failed scopes remain adverse evidence, distinct from the passing
owned typing and lock-only audit. Canonical hosted typing, clean installed audit,
the full pytest matrix, CodeQL and installed-distribution checks remain required.

Reproduce the selected test paths listed in `functional.json` with
`python -m pytest -q -p no:cacheprovider <paths> --junitxml=<temporary XML>`.
Run the exact lint/typing commands from `.github/workflows/ci.yml` and the native
audit helper in a clean locked environment. Source hashes describe raw local
bytes, with Git blob identifiers also recorded for newline-normalized review.
