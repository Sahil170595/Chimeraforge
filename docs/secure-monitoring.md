# Runtime HTTPS and authenticated monitoring

Unreleased 0.82.0 source adds [authenticated active benchmarks and traces](authenticated-active.md)
with runtime-only `connection` settings and matching CLI secure flags. Public
installation remains 0.81.0; existing anonymous defaults and native metrics remain.

Available since **Chimeraforge 0.78.0**. These runtime-only settings
apply to existing `monitor`, saved-plan monitoring and `monitor-fleet`; no new
command, traffic generator or serving process is created.

## CLI

Provision a bearer in an explicitly named environment variable through your
secret manager or shell. Its value is never a CLI argument:

```bash
chimeraforge monitor --backend vllm --url https://inference.example:8000 \
  --model YOUR_SERVED_MODEL --ttft-slo 500 --interval 30 --json \
  --bearer-env INFERENCE_TOKEN --ca-bundle /private/ca.pem

chimeraforge monitor --from-plan plan.json --candidate-index 0 \
  --backend sglang --url https://inference.example:30000 --model YOUR_SERVED_MODEL \
  --interval 30 --json --secure \
  --client-cert /private/client.pem --client-key /private/client-key.pem
```

`--secure` alone uses explicit certifi roots and no bearer. Any of `--bearer-env`,
`--ca-bundle`, `--client-cert` or `--client-key` also opts into secure mode.
A supplied PEM CA bundle **replaces** default roots. Client certificate and key
must be supplied together; encrypted keys are refused without prompting. There
is no passphrase option or plaintext-token option.

Fleet options are repeatable `ID=VALUE` declarations, split at the first `=`:

```bash
chimeraforge monitor-fleet --from-plan fleet-plan.json --candidate-index 0 \
  --endpoint a=https://a.example:8000 --endpoint b=https://b.example:8000 \
  --endpoint c=https://c.example:8000 --secure --ttft-slo 500 --json \
  --bearer-env a=TOKEN_A --bearer-env b=TOKEN_B \
  --ca-bundle a=/private/ca-a.pem --client-cert c=/private/c.pem \
  --client-key c=/private/c-key.pem
```

Use exactly one direct endpoint per original saved replica. Unknown IDs,
duplicate per-ID settings or incomplete key pairs refuse before any contact.
Omitted settings select secure anonymous certifi trust for that ID; another
replica's bearer or client certificate is never copied implicitly. Explicitly
assigning the same credential to multiple origins is an operator decision.

## Python

```python
import asyncio
from chimeraforge import api
from chimeraforge.monitor import MonitorRequest, run_monitor
from chimeraforge.monitor_connection import MonitorConnection

connection = MonitorConnection.from_env(
    "https://inference.example:8000", bearer_env="INFERENCE_TOKEN",
    ca_bundle="/private/ca.pem",
)
request = MonitorRequest("vllm", "https://inference.example:8000", "YOUR_SERVED_MODEL",
                         ttft_slo=500, interval=30)
report = run_monitor(request, connection=connection)
bound = api.monitor_plan("plan.json", request, candidate_index=0, connection=connection)

fleet_request = api.FleetMonitorRequest((
    api.FleetEndpoint("a", "https://a.example:8000"),
    api.FleetEndpoint("b", "https://b.example:8000"),
    api.FleetEndpoint("c", "https://c.example:8000"),
), ttft_slo=500)
fleet = asyncio.run(api.monitor_fleet("fleet-plan.json", fleet_request, connections={}))
```

`MonitorConnection(endpoint_url, *, bearer_token=None, ca_bundle=None,
client_cert=None, client_key=None)` accepts a programmatically supplied bearer;
`from_env` reads only the named variable, once. Tokens are bounded to 8,192 ASCII
bytes and admitted as bearer syntax. The opaque, non-dataclass connection has a
redacted representation and privately owns its prepared TLS context. It is
runtime-only: do not put it in persisted requests, plans or application settings
serialized with `asdict`. Requests/reports/bindings/Prometheus never store these
settings. This is not protection from arbitrary same-process introspection or
an operating-system secrecy guarantee for certificate paths in argv.

`connection=None` and fleet `connections=None` preserve anonymous defaults.
**An explicit fleet mapping, including `{}`, requires HTTPS for ALL original
slots.** Values must be `MonitorConnection` instances bound to that endpoint's
scheme, HTTPX-normalized host and effective port; host aliases are not equated.
All settings and native requests are admitted before tasks, budgets or contact.

## Trust, failures and lifecycle

Secure metrics and every before/after metadata request use the same verified
peer/hostname policy and origin guard, including anonymous and mTLS-only modes.
TLS reaches both actual fleet transport pools. Redirects are not followed, and
there is no insecure fallback. HTTPS validates the configured peer under the
selected CA policy; it does not establish GPU/process independence, served
weights, saved-plan authenticity or physical capacity.

Opted clients disable HTTPX proxy and CA environment discovery and avoid implicit
`SSLKEYLOGFILE` handling; process environment is unchanged. This does not promise
independence from all OS/OpenSSL settings. A supplied CA is read as bounded held
PEM data. Explicit CA/cert/key files must be regular, readable and non-linked,
at most 1 MiB. Client cert/key checks are **preflight**: OpenSSL rereads their
paths, so no atomic held-key snapshot, hostile-race immunity or hard parser-time
bound is claimed. Contexts load once, without automatic credential renewal.

Both CLI commands refuse a `--prometheus` destination that aliases any explicit
CA, certificate, key or saved-plan input before constructing connections or
contacting endpoints. This uses native resolved-path/file-identity admission;
it is not a hostile-filesystem atomicity guarantee. The direct textfile writer
API still writes to the destination its caller explicitly owns.

Admission failures raise categorical `MonitorConnectionError` (`ValueError`) or
CLI exit1. Secure standalone metrics failures remain exit1; saved unavailable
identity remains4; full fleet retains its native mismatch5/breach3/unknown4
priority. TLS/auth failures cannot be converted into successful missing metadata.
Native SLOs, whole slot population, request/body/deadline accounting and cleanup
remain separate facts. Fleet retains shielded owned async cleanup; endpoint
metadata retains its existing bounded cooperative cleanup. These are not hard
kernel/DNS deadlines or secret-zeroization guarantees.

The [functional validation record](../validation/2026-10-25-secure-monitoring/README.md)
is regenerated from real owned CPU HTTPS fixtures. It covers both native route
contracts and CLI/API transport behavior, not actual vLLM/SGLang inference,
GPU latency, customer authentication or a production deployment.
