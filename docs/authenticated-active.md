# Authenticated active benchmarks and traces

This complete feature is an **unreleased 0.82.0 source candidate**. Public
installation remains Chimeraforge 0.81.0. The candidate extends the existing
runtime-only `api.MonitorConnection` boundary to active native vLLM/SGLang paths;
it does not start an engine, fetch weights or validate physical hardware.

## CLI

```bash
chimeraforge bench --model organization/model --backend vllm \
  --base-url https://inference.example --secure --bearer-env CF_API_TOKEN \
  --ca-bundle trust.pem --client-cert client.pem --client-key client-key.pem \
  --runs 3 --output-dir results --json
chimeraforge trace workload.json --model organization/model --backend sglang \
  --base-url https://inference.example --secure --bearer-env CF_API_TOKEN \
  --ca-bundle trust.pem --out trace.json --json
chimeraforge bench --plan plan.json --candidate-index 0 \
  --model organization/model --base-url https://inference.example \
  --secure --bearer-env CF_API_TOKEN --ca-bundle trust.pem --json
chimeraforge trace workload.json --from-plan plan.json --candidate-index 0 \
  --model organization/model --base-url https://inference.example \
  --secure --bearer-env CF_API_TOKEN --ca-bundle trust.pem --out bound-trace.json --json
```

The environment variable is named explicitly; there is no literal bearer-token
argument. Any secure option opts into HTTPS, and `--secure` alone selects verified
anonymous HTTPS. Client certificate and key are a pair. Encrypted keys are refused
without an interactive password prompt. These settings also flow through existing
benchmark quantization/context sweeps; their unapplied-option warnings remain.
Saved traces retain the selected original backend and native wrapper resolution.

## Python

```python
import asyncio
from pathlib import Path
from chimeraforge import api
from chimeraforge.bench.runner import run_benchmark, save_results

connection = api.MonitorConnection.from_env(
    "https://inference.example", bearer_env="CF_API_TOKEN", ca_bundle="trust.pem"
)
rows = [api.TraceRequest("one", "Explain batching briefly.", 4, 0)]

async def measure():
    ordinary = await run_benchmark(
        "organization/model", "vllm", base_url="https://inference.example",
        runs=1, options={"max_tokens": 4}, connection=connection,
    )
    save_results([ordinary], Path("results"), connection=connection)
    trace = await api.replay_trace(
        rows, model="organization/model", backend="vllm",
        base_url="https://inference.example", connection=connection,
    )
    trace.save("trace.json")
    bound = await api.benchmark_plan(
        "plan.json", candidate_index=0, model="organization/model",
        base_url="https://inference.example", runs=1, connection=connection,
    )
    bound.save("benchmark.json")
    bound_trace = await api.replay_plan_trace(
        "plan.json", rows, candidate_index=0, model="organization/model",
        base_url="https://inference.example", connection=connection,
    )
    bound_trace.save("bound-trace.json")

asyncio.run(measure())
```

`connection: MonitorConnection | None = None` is keyword-only on these async
entry points and `save_results`. The ordinary runner does not autosave. A direct
ordinary writer caller must pass the same runtime connection to protect its TLS
inputs; `BenchmarkResult` cannot recover that state from its unchanged dataclass
or `result_to_dict`. The CLI forwards it automatically. The existing saved-plan
cap, context, original-candidate and model-admission rules still apply.

## Admission, trust and output ownership

Only the exact registered native vLLM and SGLang adapter classes admit a secure
connection. Ollama, TGI, plugins and replaced registry classes are refused before
discovery/construction/contact. Explicit HTTPS origin admission applies even to
anonymous and client-certificate-only secure requests; native origin-bound auth
covers preflight, metadata and generation. Redirects are not followed. Explicit
trust bypasses opted HTTPX proxy/CA environment discovery and implicit TLS key
logging without mutating the process environment. This is not a universal claim
about every OS or third-party environment variable.

The connection privately retains supplied TLS path identities and the effective
default certifi CA input. Explicit CA bytes are bounded before loading; OpenSSL
rereads client certificate/key paths, so admission is not an atomic file snapshot.
Private runtime guard state stays outside `to_dict` data, saved settings, native
fingerprints and public report schemas. The plain benchmark result/dataclass
schema is unchanged.

Known trace destinations are checked against workload, saved source and effective
TLS inputs before contact and again at save. Benchmark output-directory intent
is admitted early; a timestamp/fingerprint filename is checked only once it is
known immediately before writing. Resolved-path and existing-file identity checks
include hardlinks. These checks do not promise a filesystem-race-proof transaction,
immutable inputs or rollback of another write. Secure output failures are
categorical and suppress native exception chains that could expose input paths.

## Logging, closure and evidence limits

Secure benchmark, trace, standalone monitor, fleet monitor and original-fleet
trace owners categorize the standard HTTPX/httpcore message, argument, exception
and stack fields **before** delegating to an existing LogRecordFactory. Native
child logger names are included. A context-local setting preserves unrelated and
nested/concurrent anonymous records. Delegation captures the prior factory
immutably; the helper restores only a factory slot it still owns. It does not
control later caller factory replacements, post-factory `extra` fields, custom
SDK bypasses, unrelated loggers or unowned background tasks.

Owned secure backend close tasks are joined through repeated cancellation before
the logging scope exits; caller cancellation still propagates. Secure ordinary
and saved traces reuse the existing managed generation/task population to prevent
legacy Python 3.10 wait-for cancellation from detaching a held generation child.
The controlled extracted-executor proof uses the actual installed 3.10 standard
library; full public TLS behavior is separately exercised by hosted Python profiles.
Cleanup is
cooperative and may extend a deadline when a backend refuses to close. Native
execution, configuration, unavailable binding facts and SLO outcomes remain
separate. Software fixture timings are not engine, model, GPU, capacity,
independence or performance qualification. See the
[regenerable source protocol record](../validation/2026-10-30-authenticated-active/README.md).
