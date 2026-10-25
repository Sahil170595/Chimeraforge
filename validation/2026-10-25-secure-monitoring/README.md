# Secure monitoring protocol validation

Regenerate the aggregate record from the current source with the locked all-extras
environment (certificate generation uses the existing `sign` extra):

```bash
uv run --no-sync python scripts/ci_secure_monitor.py --record validation/2026-10-25-secure-monitoring/functional.json
```

The same consumer is called by installed acceptance after its existing
site-packages origin guard, for the original wheel and rebuilt sdist on Linux,
Windows and macOS. Its 12 positive controls cover both native metadata route
contracts, bearer/private CA with and without mTLS, and standalone/saved/full
three-replica CLI/API. Before/after authorized metadata routes are counted
explicitly. Subprocess stdin is closed; encrypted client keys refuse without
contact. Poisoned child proxy/CA/keylog settings are checked by owned sentinels.
The record contains aggregate observations and source hashes, never fixture keys.
Eight additional installed/source CLI/API controls refuse wrong server trust,
wrong bearer or absent required client certificates. TLS failures reach zero
HTTP handlers; wrong bearers reach only unauthorized handlers. Both owned
listeners use non-daemon handlers and native blocking close before thread join.

Run the source security and lifecycle negative controls with:

```bash
uv run --no-sync python -m pytest tests/test_monitor_connection.py tests/test_secure_monitor.py tests/test_ci_acceptance.py tests/test_repo_conventions.py tests/test_monitor_slo.py tests/test_plan_monitor.py tests/test_fleet_monitor.py tests/test_fleet_monitor_transport.py
```

Those controls cover real bad CA/hostname/client certificates, missing/wrong
bearer and metadata-only denial, per-origin separation, redirects, full-map
admission, private diagnostics, explicit empty secure mappings, native known
failure priorities, stop/deadline/repeated cancellation and owned closure.
Protocol fixtures run on CPU and do not execute a real vLLM/SGLang engine or
qualify physical identity, GPU performance, saved-plan authenticity or capacity.
Local source validation and installed hosted acceptance remain separate evidence.
