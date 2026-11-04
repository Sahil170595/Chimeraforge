# 0.82 release dependency correction (2026-10-31)

The previous source advertised Python 3.10 and selected filelock 3.20.3 on that
interpreter. The [current Unix advisory](https://github.com/advisories/GHSA-69hj-f68j-2879)
and [Windows advisory](https://github.com/advisories/GHSA-8mx5-7m5m-r77g) include
that version. [The patched filelock release](https://pypi.org/project/filelock/4.2.1/)
requires Python 3.11 or later. The former claim that older Python used unaffected
APIs was unsupported. This candidate requires Python 3.11+, selects unmarked
`filelock>=4.2.1,<5`, and aligns the current docs, classifier, tooling and matrix.

The previous marker-evaluated requirements audit could omit a locked version for
another interpreter. The CF-owned helper now unions installed external pairs with
every versioned PyPI registry pair in `uv.lock`, preserving duplicate versions.
It partitions exact pins into the minimum number of batches with one version per
name, then invokes the supported strict pip-audit CLI on every batch. Unknown
lock schemas/sources/versions and any unavailable lookup or finding fail closed.
No advisory engine, dependency suppression or cross-repository import is added.

The initial regression run had **2 failures and 1 pass**: the old Python floor and
absent whole-lock helper failed, while the native marker control demonstrated the
old platform-selected omission. A subsequent first focused run passed 20 tests;
its XML and tool stdout were retained, without a separate raw stdout file.
The first complete scope passed 392 tests before the new helper's typed lane
reported two input-annotation errors. The validating boundary now accepts object
inputs and narrows them with its existing string checks; runtime logic did not
change. The corrected run passed all 18 static commands and the fresh advisory
checks. Its recorder-only style failure (two overlong strings) was then corrected
with affected style checks, carrying the unchanged passing runtime/advisory logs.
The final scoped execution is recorded separately below. These are software and
policy controls, not a local exploit reproduction or a compromise-free claim.

`summary.json` records the current whole-lock graph, exact advisory inventory,
scoped test results and current source hashes. It also verifies that application
Git content, pre-existing tests and the complete published 0.81 changelog tail
remain unchanged from `f31761fb13f223e356aab1e4e7b0502a736dc6d8`. Old validation
records are immutable. Earlier feature full/native results remain historical;
this correction does not claim a new local full suite or installed-wheel run.
Fresh hosted validation and tagged artifact/publication verification are separate.

Regenerate after the scoped runner has saved its actual command/log receipt:

```bash
python validation/2026-10-31-release082-security/regenerate.py --gates /path/to/cf-082-release-final-scoped-gates.json
```

The helper uses the current environment and native registry advisory service.
Results are dated observations, not a prediction about future advisories.

The frozen A source review found seven current-facing guides still describing
0.82 as unreleased or 0.81 as current. B corrects only those availability statements
and this evidence record. Its application, auditor, tests, metadata and lock are
held A; the 392 tests, 18 static commands and 126 advisory lookups remain A-executed
carryforward. B runs affected documentation, recorder style and diff checks and
regenerates current hashes. A's exact raw files, manifest/index and record remain
in named external recovery evidence; older committed validation is unchanged.
