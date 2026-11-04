# Synthetic inventory contract evidence

From this checkout with its locked development environment, regenerate
`functional.json` using the existing installed-consumer protocol helper:

```bash
uv run --no-sync python scripts/ci_inventory_check.py --record validation/2026-10-25-inventory-check/functional.json
```

The generator creates an offline native N=3/TP=2/PP=1 saved plan, checks every
ordered slot through CLI and API using owned Python subprocess protocol fixtures,
and removes its temporary plan directory. It explicitly suppresses the native
absence query even inside CI. It records actual 0/4/5 controls, current source
hashes, unchanged plan bytes and unassessed limits. Timestamp/fingerprint may
change; GPU execution and installed-distribution acceptance are not established.
Actual wheel/rebuilt-sdist acceptance separately uses the same helper under the
existing installed-origin guard, including hosted CPU native unavailability.

Verify the broader focused contracts with:

```bash
uv run --no-sync pytest tests/test_inventory_check.py tests/test_inventory_process.py tests/test_deploy.py tests/test_deploy_fleets.py tests/test_fleet_monitor_transport.py tests/test_ci_acceptance.py::test_installed_placement_source_protocol_uses_actual_native_two_gpu_plan -q
```

At the 2026-10-25 source checkpoint, that command's equivalent approved-environment
invocation passed **170 tests**. This is a historical observation, not a regenerated
constant in `functional.json`; use the command to obtain current counts. It covers
hostile Decimal settings, native CSV quoting, diagnostic-only total memory,
bounded process ownership and unchanged original deployment behavior.

The deterministic fleet-deadline regression also passed with the original runtime.
A controlled negative run removed only the final elapsed-deadline guard and failed
its required exit-4 assertion with actual exit 0. The original production file was
restored byte-for-byte (SHA256
`5d02f3e74750ee7848d51ba3abc066ff9bff2490551522c59824e3f4d71b5dfe`).
That RED is historical TDD evidence; regeneration does not mutate production source
or replay the mutant. The focused command verifies the retained positive regression.
