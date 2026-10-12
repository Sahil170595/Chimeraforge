# Isolated checkpoint acceptance seed (2026-10-09)

Source tested: `58fe7bbc2615c582eaf7fc991520898b9dfa62e3`.
The actual `python -I scripts/ci_checkpoint_identity.py --help` subprocess first
failed with `ModuleNotFoundError: ci_installed_acceptance`. Sibling acceptance
helpers are now imported only by the nonisolated parent `accept` function; the
seed does not restore `PYTHONPATH`, the current directory, or source imports.

- Red regression: 1 failed, 2.34s.
- Checkpoint and CI acceptance regressions: 65 passed, 11.63s.
- Full required suite: 3496 passed, 2 skipped, 14 warnings, 133.15s.
- Exact CI Ruff check: passed; format: 106 files already formatted.
- Configured mypy: no issues in 2 source files.

This is local source/subprocess evidence. Exact installed wheel/sdist acceptance
and hosted coverage/mutation qualification remain pending batch publication.
Earlier checkpoint receipts remain unchanged. No package/model/environment
copies or persistent task processes were created. Shared checkout and environment
remain PRESERVE under the existing owner and prior cleanup rejection.
