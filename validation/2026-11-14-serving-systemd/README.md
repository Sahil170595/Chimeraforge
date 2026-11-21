# Declared systemd unit source qualification

This aggregate record describes **unreleased 0.104.0 source**, independently
branched from released main `a688af5a604aea0e77d5600b94cb0a1bf8043c0e`. Public
installation remains **0.101.0**. No other open feature is required. Raw plans,
declarations, units and logs are retained only as local qualification witnesses;
this directory contains aggregate results and source identities.

Four initial native API/actual OS CLI tests failed because the new format and
executable controls were absent. The first expanded attempts exposed test
expectation errors: two CLI drift checks expected an invented `state` field
instead of the existing `category`/`count` schema, and one SGLang check assumed
vLLM's KV dtype. The native schema and pinned SGLang `fp8_e5m2` mapping were read
and retained; production argv was not changed to satisfy those assertions.
An initial Ruff long-string diagnostic was fixed with equivalent adjacent
literal strings. The final selected run passed **877 tests**, with **6 unavailable
checks skipped** and six existing deprecation warnings. Runs are not added.

The new systemd module passed all **34** cases. It executes actual OS CLI export,
match, categorical `/unit` drift and invalid receiving for both vLLM and SGLang.
Controls retain revision, TP/PP, dtype, KV/cache/chunked-prefill settings, native
loopback ports and the SGLang interpreter/`-m` structure. They refuse absent or
non-POSIX executables, nonuniform/missing/extra devices, N>1, host-port overrides,
replica matrices/ports and Kubernetes controls. Other formats refuse executable
overrides. Source/config aliases, exclusive output, malformed UTF-8/NUL/empty
units and independently supplied executable/device/revision drift are covered.
Forbidden plan/engine operations are trapped; the executable is never run.

Before implementation, twelve old plan-systemd cases were captured using held
original plans across vLLM/SGLang/Ollama, implicit/explicit device selection and
escaped executables/model identifiers. Six old declaration configs were captured
across both backends and launch/Compose/Kubernetes. On final candidate 0.104.0,
every captured unit/config byte and old companion hash matched exactly. The
shared unit renderer changes neither old plan comments nor argv/env ordering.
New units have a declaration fingerprint comment and use no fabricated plan.

The existing installed consumer now exercises both new backends through native
SDK and actual OS CLI paths, including source preservation, independent intent,
drift and invalid handling. Its source run passed; installed distributions remain
hosted qualification. No image/model is fetched, no unit is installed/started,
and no engine/GPU/performance, allocation, feasibility or SLO proof is claimed.

Local Windows could not create three existing symlink fixtures and has no
`systemd-analyze` for the old unit case or the two new declared-backend cases.
These six skips are explicit unavailability, not passing evidence. Both new
parser cases are in the existing required Ubuntu test file. With
`CHIMERAFORGE_DEPLOY_ACCEPTANCE=1`, a missing tool fails. The parser uses
`/usr/bin/true` fixtures without starting a service; no new job or upload exists.

Exact workflow Ruff/format paths passed. Seven owned deployment/serving files
passed skip-import mypy. The existing canonical silent-import steps remain
required hosted gates; known incompatible Python 3.13 NumPy-stub and unrelated
ambient-audit scopes were not repeated or silenced. Offline lock validation and
all **130 exact universal-lock version pairs** passed both advisory layers. This
does not qualify the borrowed ambient installation as clean. Five added Markdown
links and current systemd/executable CLI help passed. Archives, historical
validation and original declaration/verification receivers remain unchanged.

`functional.json` is generated from actual pytest XML, held parity receipts and
current raw source hashes/Git blob identifiers. Reproduce its selected paths with
`python -m pytest -q -p no:cacheprovider <paths> --junitxml=<temporary XML>`.
Full hosted pytest, canonical typing, clean installed audit, CodeQL, installed
wheel/sdist consumers and required native Ubuntu parsing remain final-head gates.
