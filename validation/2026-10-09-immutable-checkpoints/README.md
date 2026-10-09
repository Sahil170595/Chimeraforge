# Immutable checkpoint validation

Feature baseline: `62de7bad34d1a7c5479efef81a9bdd8c490ce00e`.
Source scope: unreleased `codex/immutable-checkpoints`; no version bump or publication.

The initial behavioral run failed 25 cases and passed one (`red-tests.log`).
The two independently demonstrated legacy defects have retained red receipts:
v1 explicit-revision consistency and malformed metadata (`adversarial-red.log`),
then unknown original identity enrichment (`compatibility-red.log`). Final focused
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
