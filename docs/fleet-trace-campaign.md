# Whole-original-fleet trace campaigns

**Unreleased 0.84.0 source**, including the 0.82 and 0.83 candidates. Public
installation remains **0.81.0**. A campaign performs K serial executions of the
same saved original N-member fleet. K is not N: each execution retains every
original member, request, route, cap, arrival offset and one global concurrency
limit. There are no retries, warmups, N1 replans or survivor subsets.

## Produce one complete campaign

```python
from pathlib import Path
from chimeraforge import api

saved = api.load_plan(Path("fleet-plan.json"))
index = next(i for i, row in enumerate(saved.to_dict()["result"]["candidates"])
             if row["backend"] == "vllm" and row["n_agents"] == 3)
endpoints = tuple(api.FleetEndpoint(f"r{i}", f"http://127.0.0.1:{7999 + i}")
                  for i in range(1, 4))
report = await api.replay_fleet_trace_campaign(
    saved, Path("workload.json"), endpoints, Path("routes.json"),
    candidate_index=index, executions=2, concurrency=3, campaign_timeout=1800,
)
report.save(Path("candidate-campaign.json"))
received = api.load_fleet_trace_campaign(Path("candidate-campaign.json"))
assert received.exit_code == report.exit_code
```

`replay_fleet_trace_campaign(saved, requests, endpoints, routes, *, executions=3,
candidate_index=0, model=None, concurrency=1, request_timeout=300,
trace_timeout=600, cleanup_timeout=2, campaign_timeout=1800, stop_event=None,
connections=None)` prepares source/workload/routes/endpoints once and reuses the
native whole-fleet executor. Workload/route schemas and per-member connection
settings are the [original-fleet trace contract](fleet-trace.md).
Admission requires K1–16, M1–1024 and K×M≤4096, original N1–16, exactly N direct
endpoints, the entire ordered route population and saved candidate output caps.

```bash
chimeraforge trace-fleet-campaign workload.json --from-plan fleet-plan.json \
  --candidate-index 0 --routes routes.json --executions 2 \
  --endpoint r1=http://127.0.0.1:8000 --endpoint r2=http://127.0.0.1:8001 \
  --endpoint r3=http://127.0.0.1:8002 --concurrency 3 \
  --request-timeout 300 --trace-timeout 600 --cleanup-timeout 2 \
  --campaign-timeout 1800 --out candidate-campaign.json --json
```

The chosen index must actually be the saved N3 candidate for this example;
neither API nor CLI changes its N/TP/PP/model/context/batch. Runtime-only
`connections` snapshots an explicit per-ID HTTPS map once and forwards it for
every execution. CLI `--secure` and per-ID `--bearer-env ID=NAME`,
`--ca-bundle ID=PATH`, `--client-cert ID=PATH`, `--client-key ID=PATH` reuse the
typed monitoring boundary. Credentials and TLS input paths are not serialized.
Secure Ollama is refused before contact; it never silently becomes anonymous.

## Native outcomes and ownership

Every K slot is retained: completed, incomplete, failed or not_started.
Execution completeness, configuration and native SLO evidence are separate.
A complete child with known configuration mismatch has native exit1 and still
allows the next execution. A campaign exits0 when every execution completed and
there is no known configuration mismatch; otherwise1. Completion alone does not
prove an SLO, capacity or GPU claim. Admission/export failures use CLI2.

True execution incompleteness stops later admission. A native exception or the
unchanged native child **32 MiB** receipt guard can leave no returned child:
its slot retains a categorical error, null receipt and **unknown** execution
completion; later slots remain unstarted. No child receipt or native cleanup
fact is fabricated. Campaign cleanup counts joined coordinator children and
stop waiters; native resource closure is established only by returned children.

The campaign clock starts before synchronous preparation and includes admission,
probes, metadata, generation and cooperative drains. It is checked after
preparation and before every execution. A child completing after the campaign
deadline retains its actual complete native outcome while later starts stop.
Timeouts bound admission/signalling, not hard cooperative return or OS cleanup.
Repeated cancellation joins owned child/waiter tasks before propagating caller
cancellation. Each child retains the native fleet cleanup allowance and all
original member/row evidence. K serial executions do not establish independence,
cold conditions, physical member identity or statistical replication.

## Receive and gate every declared execution

Schema1 commits a full saved-plan snapshot, selection, original N, K, M, K×M,
ordered request descriptors, direct endpoints, routes and effective controls.
All accepted full native child records remain embedded unchanged. The bounded
receiver holds the outer JSON once, validates the complete manifest and every
nonnull child, binds native clocks to serial slots and refuses unsafe, nonfinite,
duplicate-key, inconsistent, missing or unknown fields. Missing native receipts
remain null. Fingerprints and source hashes are integrity commitments, not
authenticated source inputs or external preregistration. An embedded child's
serialized hash describes that representation, not an original child file.

Prepare a complete [native fleet policy](fleet-trace-gate.md) independently of
the measured outcomes. The campaign policy adds explicit K and campaign budget:

```python
import json
from pathlib import Path
from chimeraforge import api

native_policy = json.loads(Path("fleet-policy.json").read_text(encoding="utf-8"))
policy = {"schema_version": 1, "expected_executions": 2,
          "campaign_timeout_seconds": 1800, "fleet": native_policy}
decision = api.gate_fleet_trace_campaigns(
    Path("baseline-campaign.json"), Path("candidate-campaign.json"), policy=policy
)
api.write_fleet_trace_campaign_gate(decision, out=Path("decision.json"),
                                   junit=Path("decision.xml"))
```

The typed policy is `FleetTraceCampaignGatePolicy(fleet, expected_executions,
campaign_timeout_seconds, schema_version=1)`. Its native inner
`fleet.trace.expected_replicates` stays **1**; outer K does not become inner
replicate count. The native per-execution source/member/cache/control rules,
full-row/common-horizon arithmetic and thresholds are reused unchanged. No
pooling, averaging p95, best-run selection or new percentile calculation occurs.
All 2K child payloads are checked for semantic copies, including within an arm;
different labels/hashes do not authenticate independent traffic.

```bash
chimeraforge gate --kind fleet-trace-campaign --baseline baseline-campaign.json \
  --candidate candidate-campaign.json --policy campaign-policy.json \
  --out decision.json --junit decision.xml --json
```

Malformed input is error2. Missing/ineligible/incomplete/mismatched/copied
evidence yields inconclusive3 before any known regression1; eligible conditional
pass is0. Known arithmetic is retained under blockers. JUnit contains one campaign
population case plus a fleet-population case and every required metric for each
declared or actual execution, including null/missing slots. Inconclusive decisions
use errors for all cases; eligible regressions use failures. All original input
member outcomes remain in the evidence projection without repeating raw metadata.

## Complete byte profile and protected publication

Campaign input raw bytes **and** canonical ASCII-escaped indent2 JSON plus LF
must fit **16 MiB**; the logical pair charges both arms against **32 MiB** even
when one file is physically held once. Policy has a separate **64 KiB** limit.
New schema1 has no legacy compact-size exception. Native child 32 MiB admission
is unchanged, and no claim says every possible child×K fits the outer profile.

The typed API retains complete accepted child data and outcomes if outer export
later refuses. `json_bytes()`, `to_dict()` and `save()` refuse without truncation.
The public encoder uses `JSONEncoder.iterencode` over explicit public data and
reuses exact admitted bytes at stdout/file sinks, including Windows. A streamed
sorted/compact/ASCII/finite hash matches the native canonical digest on this
closed family; global native hashing is unchanged. These bounds cover exported
traversal/buffers, not prior native construction, total heap, HTTP work or one
escaped scalar chunk allocated by the SDK. Generic caller `asdict` is outside
the export bound; private runtime guard attributes stay outside dataclass fields,
and copies/`dataclasses.replace` retain them.

Known source/workload/routes and runtime TLS inputs are protected against output
aliases before contact where the destination is known, and again before save.
Loaded files protect actually held inputs; private TLS paths cannot be recovered
from serialized data. JSON and escaped JUnit are fully admitted before either
requested file is written; output destinations are also protected from each
other. Existing atomic replacement is **per file**, not a pair transaction:
a later filesystem failure may leave an earlier file. Export/admission failure
writes no normal receipt or requested sink and uses a bounded categorical error.
Receipts contain saved plan intent and endpoint URLs and may be private.

The [regenerable protocol record](../validation/2026-10-30-fleet-trace-campaign/README.md)
separates owned CPU HTTPS software fixtures from synthetic matching gate cases.
The hosted native canary reuses three owned pinned Ollama members for API and CLI
K2 campaigns, retaining real CPU-versus-modeled-GPU mismatch and gate3. Neither
qualification is a real vLLM/SGLang deployment, GPU, SLO or performance proof.
