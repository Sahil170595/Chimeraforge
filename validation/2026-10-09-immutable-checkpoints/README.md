# Immutable checkpoint validation

Feature baseline: `62de7bad34d1a7c5479efef81a9bdd8c490ce00e`.
Source scope: unreleased `codex/immutable-checkpoints`; no version bump or publication.

The initial behavioral run failed 25 cases and passed one (`red-tests.log`).
The two independently demonstrated legacy defects have retained red receipts:
v1 explicit-revision consistency and malformed metadata (`adversarial-red.log`),
then unknown original identity enrichment (`compatibility-red.log`). Initial focused
coverage of checkpoint/API/recheck/resolver/deploy/launch/REST/acceptance behavior
passed **247 tests in 21.37 seconds** (`focused.log`).

The unchanged CI lint/format paths, plus the new checkpoint tests, passed:

```text
python -m ruff check src/chimeraforge scripts/ci_*.py scripts/check_coverage.py tests/test_ci_*.py tests/test_planner_properties.py tests/test_checkpoint_identity.py
python -m ruff format --check src/chimeraforge scripts/ci_*.py scripts/check_coverage.py tests/test_ci_*.py tests/test_planner_properties.py tests/test_checkpoint_identity.py
python -m mypy
```

Ruff checked/formatted 107 files; mypy passed its existing two configured files.
Local interpreter: existing CPython 3.12 environment; no new dependencies,
environments, model downloads or serving engines.

`legacy-compatibility.json` records byte/fingerprint preservation for a genuine
fresh-PyPI 0.51.0 v1 artifact and the frozen reviewed-source v2 artifact. Their
native exits are respectively 1 (missing legacy replay bindings) and 0.

`anonymous-hub.json` is an actual anonymous metadata/config observation at the
declared Smol checkpoint. Config bytes are hashed and checked against its declared
Git blob. Weight-file LFS hashes remain declarations; no weights were downloaded.
This was source execution, not installed-package or inference qualification.

The existing hosted installed wheel/sdist consumer now exercises the isolated
public CLI save/check/export loop with a protocol fixture. The existing hosted
Linux CPU consumer adds real anonymous pinned metadata/config and explicit network
recheck, with no extra weight download. Those exact-head hosted results are pending
publication; local protocol tests are not substituted for them. Full-suite results
are recorded in the final validation follow-up after the immutable code commit.

The first immutable code head `6f5900fb14c1208dd9cf75f112991e8f32ecf5f4`
completed the full suite with **1 failed, 3486 passed, 2 skipped** in 126.02s.
The existing MCP shared-surface parity test found the missing revision argument;
it was retained unchanged. Independent review also demonstrated fleet probes
switching the explicit checkpoint A to a different `main` checkpoint B.
`surface-red.log` records five meaningful regressions before fixes: invalid-map
MCP rejection, public SDK schema/execution and actual distinct-checkpoint fleet
selection. The fix exposes/forwards the map through MCP, retains checkpoint
receipts and selected refs through resolve/plan, and forwards the map into all
fleet probes. The installed MCP consumer also checks the cached pin through a
real SDK stdio conversation. The original full result is prior-head evidence,
not a success claim for the final feature.

The corrected source head **`77eb15dc264a2dbe4c11e7067377762e072a4f59`** passed
**3495 tests, with 2 skips and 14 warnings, in 108.50 seconds**
(`full-pytest.log`; exit 0). Its focused MCP/fleet/checkpoint/acceptance surface
passed **145 tests in 12.42 seconds** (`surface-green.log`). Exact lint/format and
configured type checks passed (`lint-type.log`, 108 files / 2 typed files).
The SDK protocol test initially assumed structured tuple output; inspection of
installed MCP 1.30.0 confirmed that generic-dict tools return one JSON TextContent
block through FastMCP's public method. The test uses that exact interface, and
the separate real stdio ClientSession test checks the protocol result.

This final commit adds validation metadata only; the tested package, scripts,
tests and functional docs remain byte-identical to the corrected source head.
Hosted global coverage, critical-module ratchets, mutation sentinels and actual
installed wheel/sdist/CPU consumers remain pending the authorized batch push.
Their existing thresholds and guards are unchanged. No local coverage result,
GPU performance qualification or server-loaded checkpoint proof is claimed.
