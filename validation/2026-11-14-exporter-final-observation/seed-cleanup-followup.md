# Startup template cleanup follow-up

Renewed independent review found a third cleanup omission at `f1d3cc68` after
verifying both earlier repairs. The existing cancelled native startup template
still creates and closes three HTTP clients/backends and six pools. A controlled
real close callback completed and then raised for all three backends. Native
cleanup returned incomplete with three errors, all resources closed and no
endpoint tasks, but the newly constructed exporter initialized its private sticky
flag to false. A later genuine PASS therefore incorrectly qualified zero.

The real native SDK regression failed red while its completed-cleanup counterpart
passed. All fixture resources were physically closed/joined before the red
assertion. The [generated record](seed-cleanup-followup.json) preserves counts,
exact source identities and final consumer stdout hashes. The original
[701-test record](functional.json), [75-test repair record](cleanup-followup.json)
and their raw witnesses remain unchanged; overlapping counts are not added.

The production repair adds two lines: inspect the already-held template cleanup
before the constructor binds a socket, then initialize the same private sticky
flag before listener start. There is no extra template/source/monitor call, new
callback or default startup rejection. Completed cancelled templates remain
normal; their cancelled/unstarted observations never become qualifying evidence.
Previous returned-report and setup-exception cleanup repairs remain intact.

All six new SDK/default-selected CLI controls passed. The final source selection
passed **81 tests with no failures or skips**, including all 18 cleanup controls,
the previous 61 run controls and both existing source-consumer profiles. Those
consumers again exercised direct/mTLS SDK and actual OS CLI default/selected
runs. Default CLI retained two rows and process exit zero for both seed cleanup
states; the selected path safely failed with exit 1 for incomplete cleanup after
joins, and completed cleanup retained its positive qualification.

The controls retain exactly one seed report, all three real backend closes, closed
clients/six pools, no seed requests/tasks, clean actual worker completion, closed
listener/socket and controlled streams/transports closed once. The SDK checks no
after-close contacts. The private flag is checked before listener start; the
boundary still captures a later genuine PASS independently of cleanup failure.

Exact required Ruff/format paths passed for 290 files, and all five owned files
passed skip-import mypy. Native monitor/type sources are unchanged from the
previous repair, so its three proven baseline diagnostics were preserved without
repeating that scope. Canonical hosted typing remains required. Public cache,
Snapshot/readiness/body behavior, CLI command, native math/report schema, locked
dependencies and both earlier JSON records retain their exact prior blobs.

Public installation remains **0.101.0**; this is unreleased **0.106.0 source**.
Final independent review and exact-head hosted CI/CodeQL/clean installed artifact
acceptance remain gates. Controlled CPU protocols do not establish engine/GPU,
model, physical-independence, deployment, capacity or provider behavior.
