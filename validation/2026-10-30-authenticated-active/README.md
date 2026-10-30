# Authenticated active protocol observations (2026-10-30)

This source record exercises the unreleased 0.82.0 CLI/API with owned CPU HTTPS
protocol servers. It is not installed-wheel, real-engine, model, GPU, capacity,
performance or customer qualification. Hosted installed profiles separately run
the same consumer against original and rebuilt-sdist wheels under the existing
site-packages origin guard. The committed installed consumer also checks every
loaded `chimeraforge` module before/after same-process acceptance, requiring origins
inside the actual installed package and outside the checkout. It records actual
loaded counts without forcing optional modules; the local full151-module import
sweep is separate evidence.

Regenerate from this source checkout and its locked development environment:

```bash
uv sync --locked --all-extras
uv run --no-sync python scripts/ci_secure_active.py --record validation/2026-10-30-authenticated-active/functional.json
```

The generator runs actual public API calls and isolated CLI module subprocesses.
It retains aggregate roles/counts, actual source/workload hashes and current
consumer/runtime hashes, never bearer values, key bytes, raw prompts or outputs.
Forty positive invocations cover both adapters, ordinary/saved benchmarks and
traces, bearer with/without client certificates, plus anonymous and client-only
HTTPS traces. The 24 adverse invocations retain failed CA/hostname/token/client,
redirect and malformed-SSE outcomes; redirects contact no second origin. Nine
late receipt-save refusals preserve all TLS inputs. These calls are controlled
protocol tests, not independent scientific replications.

The source tests additionally exercise named-environment CLI admission, encrypted
and malformed keys without prompts, poisoned proxy/CA/keylog settings, backend
identity/type/origin refusal before contact, known output and hardlink aliases,
effective default CA protection, original saved-input preservation, native sweep
warnings and workers, pre-factory SDK diagnostics, nested/concurrent anonymous
scopes, factory chaining, repeated cancellation and close-error priority. The
historical causal REDs and final local/hosted receipts are retained by the delivery
run; regeneration verifies current behavior and does not replay historical source
mutations. No source-test count is represented as a regeneration result here.

`source_sha256`/`workload_sha256` bind the inputs created in that run. Plan creation
includes a timestamp, so regeneration need not reproduce identical plan bytes or
hashes; neither hashes nor endpoint URLs authenticate inputs or physical servers.
Private runtime settings remain outside serialized measurement schemas. Output
checks are not filesystem transactions or universal path-secrecy guarantees; see
[the complete runtime and ownership limits](../../docs/authenticated-active.md).
