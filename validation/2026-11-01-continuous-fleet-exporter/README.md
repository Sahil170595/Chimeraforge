# Continuous fixed-config exporter — source record

`functional.json` is a dated 0.91.0 editable-source aggregate from
`scripts/ci_fleet_exporter.py`. It hashes the actual current source inputs,
creates/saves/loads a genuine native N=3/TP=2 plan with a saved TPOT target, and
uses owned CPU protocol fixtures. The numerical histogram values are synthetic
fixture counters, not an inference measurement.

The run executes one anonymous API service, an actual OS CLI subprocess and a
separate API service with real TLS, bearer and mutual client authentication.
Each service proves five cached scrapes with zero additional backend requests.
The API cases also prove TTL unknown replacement and subsequent native polling;
all original three members remain present, with safe labels and joined worker /
listener ownership. A malformed final endpoint refuses before backend contact.
The genuine saved source bytes stay held. Clean CLI exit 0 is separate from
native qualification.

The native saved target is not removed to make the fixture pass. An initial
pre-publication aggregate failed correctly because its TTFT-only fixture lacked
the requested native `vllm:request_time_per_output_token_seconds` histogram.
The current controlled fixture provides that actual native family; existing
monitor semantics and the saved TPOT target are unchanged. The optional fixture
extension keeps prior default TLS fixture bytes unchanged.

Earlier source evidence retains the missing API/CLI RED, three ownership defects,
explicit path/direct-close cancellation controls, partial secure-map default
recreation and their qualified GREENs. Setup/caller errors are separate. One
inbound HTTP read error remains unexplained/unreproduced; a separate delegating
keepalive observer passed without establishing its cause. The current consumer
uses explicit finite five-connection limits and supported 0.5s client expiry for
its TTL check, below the listener's 1s keepalive, without retrying failed requests
or changing service timeouts. External recovery records preserve every adverse.

Regenerate to **fresh untracked outputs**, preserving this committed dated run:

```bash
python scripts/ci_fleet_exporter.py --checkout . \
  --record ./fleet-exporter-functional.local.json \
  --work-dir ./fleet-exporter-fixtures.local
```

Both paths must be new. The work directory retains owned protocol plans,
certificates and CLI logs for review; it is not a dependency environment. Archive
a new run under a fresh dated validation path if committing it.

This is local source/CPU protocol evidence. It does not execute a real inference
engine or GPU, establish SLO capacity, physical independence, private production
reachability, or qualify an installed wheel. Current full source/CI gates,
original/rebuilt installed artifacts and hosted acceptance have separate proofs.
The six installed consumer routes are wired in this candidate and qualify only
when actually executed against the corresponding artifact.
