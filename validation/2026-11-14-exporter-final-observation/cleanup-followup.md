# Native cleanup follow-up

Independent review found two ownership gaps in initial local commit `25964a52`.
The [initial record](functional.json), its 701-test count and raw witnesses are
preserved. This separate [generated record](cleanup-followup.json) identifies the
changed source and its own validation. Public installation remains 0.101.0;
0.106.0 is an unreleased source candidate.

This record preserves the first cleanup repair at `f1d3cc68`. Renewed review then
demonstrated the startup-template omission recorded in the separate
[seed cleanup follow-up](seed-cleanup-followup.md); the 75-test record remains
unchanged.

The first red regression used the real native monitor and real listener. A first
poll passed; a second poll stalled until stop. The finite boundary captured PASS,
then actual controlled transport closes completed and raised. Native cleanup
returned incomplete with three close errors, but the exporter discarded that
normal-return report after stop. Joined flags and a successful worker therefore
allowed a false qualified zero. A separate allowance-exceeded case reproduced
the same false PASS. Both failed red; completed cancelled cleanup passed.

The second red regression caused an actual transient native backend-construction
failure. Both created backends and all three HTTP clients closed; two backend
close callbacks then raised. Native cleanup recorded incomplete with two close
errors and all six pools closed, but ordinary `FleetMonitorError` lost that fact.
A later real PASS incorrectly restored qualified zero. That regression failed
red while the same setup failure with completed cleanup recovered correctly.

The repair retains a private sticky exporter cleanup-failure boolean before any
stop-related publication discard. The existing exact `FleetMonitorError` also
carries a private typed boolean only when setup failed after known incomplete
cleanup; its public type, message and arguments remain unchanged. Ordinary
completed-cleanup unavailability remains native unknown/recoverable. Neither
repair changes the boundary observation, retries monitoring, adds a request or
changes native cleanup arithmetic/report schema. The sticky fact participates
only in post-join finite qualification; default startup and CLI behavior remain.

The affected broader suite passed **227 tests** with no skips. A subsequent local
typing correction made exception narrowing explicit before the same exact native
type and boolean checks. On that final runtime source, **75 tests passed** with no
skips: 12 cleanup regressions, the previous 61 run controls and both existing
source-consumer profiles. These overlapping totals are not added to one another
or to the original 701. The final consumers exercised direct/mTLS SDK runs and
actual OS CLI default/selected paths. Default output stayed two rows with process
exit zero; selected output qualified all three original replicas after closed.

Cleanup controls require safe SDK failure and selected CLI exit 1 after complete
joins despite captured PASS, including a later successful native poll. A native
cancelled shutdown with completed cleanup remains successful. The tests retain
actual worker completion, closed sockets, dead listener threads, every controlled
transport/stream closed once, no after-close contacts, safe exception text and
the original exception type/arguments. Existing genuine worker/listener failures,
cancellation, raw-clock/TTL and atomic population controls remain included.

Exact required Ruff/format paths passed for 290 files. The five owned exporter
files passed skip-import mypy. Expanding that local scope to native monitor files
showed three Any-return diagnostics; the supported mypy `--shadow-file` boundary
reproduced the same three at unchanged initial source. An earlier copied-package
attempt added missing-stub diagnostics and remains preserved as an invalid
comparison. No cast, ignore, dependency change or environment workaround was
introduced. Canonical hosted typing remains required.

The initial seven-case cache parity remains applicable to the unchanged exact
cache source, public snapshot type, CLI command and installed-consumer helper.
The new adverse default CLI controls additionally retain its two-row/exit-zero
contract during native cleanup failure. Archives, dependencies, jobs, uploads and
the previous four feature refs remain unchanged. Renewed independent review and
full final-head hosted CI/CodeQL/installed artifacts remain publication gates.
