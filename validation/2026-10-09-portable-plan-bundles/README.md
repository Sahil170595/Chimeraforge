# Portable saved-plan inputs (2026-10-09)

Bundle source reviewed: `19e9a7811e52ee796ee3171d6141e63b3c53b6fd`.
Final source and test boundary: `78fd6b298bc4661ed5f87eda72f20f2d673970ed`.
The latter changes only the existing real HTTP MCP functional test's client
budget; production code is identical to the reviewed bundle source.

The behavioral tests create a plan using nondefault coefficient and quality
files, move the bundle, remove producer inputs, and check/replay the exact held
bytes through the shared planner. They cover strict membership, raw and parsed
bindings, constructed-object validation, interrupted staging, external links,
package-resource hardlinks, and captured source labels after a real Windows
junction replaces the receiving directory. Genuine released v1 and earlier v2
artifacts retain their original bytes and check statuses (`legacy-checks.json`).

TDD records retain the actual failures: 24 initial missing-surface cases; six
constructed-manifest cases; one SDK hardlink case; two source-label cases; 11
malformed corpus cases; and one excessive quality timestamp case. Each has a
corresponding implementation fix and focused green verification. Final focused
bundle/check/quality/acceptance validation: 177 passed, one skipped, 74.38s.

Required final local gate:

```text
python -m pytest tests/ -q --tb=short
3565 passed, 3 skipped, 14 warnings in 190.27s
```

The preceding full branch-coverage run at `19e9a781` was **failed**: 3564 passed,
three skipped, one MCP SDK client read timeout, 1140.14s. Its first four public
tool calls passed; the final `suggest` call exceeded the test client's three-second
budget. The functional test now allows the server's existing 30-second tool budget
plus a named five-second response margin. Other client defaults and dedicated
30-millisecond timeout/admission/control tests are unchanged. The full MCP file
then passed under branch coverage: 26 passed, 23.53s (`mcp-covered-green.log`).

The failed full run still produced usable **diagnostic coverage**, accepted by the
unchanged `scripts/check_coverage.py`: whole package 91.09% line / 84.89% branch;
bench metrics 99.07% / 90.00%; planner constants 100% / 100%. These measurements
are not a green full coverage run at the final head. No floors were changed.

Exact CI Ruff paths plus new tests passed; 111 files were already formatted.
Configured mypy passed for two source files. Existing actionlint passed.
The final logs record those actual outputs.

Installed acceptance is wired into existing jobs: an installed Linux wheel
produces a small bundle and deletes its producer inputs; the existing Ubuntu,
Windows and macOS wheel/rebuilt-sdist consumers verify/check unchanged plan bytes.
Default bundled coefficients are also exercised under the installed package.
Local source protocol tests do not establish that hosted or installed result.
Exact-head hosted full coverage and installed acceptance await batch publication.

Synthetic harness inputs are not retained here. Bundle integrity does not
authenticate its source, prove actual served checkpoint bytes, or qualify GPU
performance. All local task processes completed; no environment/model/container
copies were created. The shared checkout and existing environment remain
PRESERVE under the continuing builder, with the prior cleanup rejection in force.
