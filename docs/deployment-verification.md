# Verify offline deployment declarations

This feature is available since **Chimeraforge 0.75.0**.

`deploy-verify` compares an existing generated **JSON Compose object** and required
companion bytes with what the current installed renderer produces from an original,
independently supplied saved plan and complete render intent. It reuses
`export_deployment`, including its checkpoint/quant/KV/platform/native fidelity
refusals and original multi-replica population. It never copies a fleet into a
one-agent candidate or reconstructs expected options from the file being checked.

## Single-replica CLI

First create a saved plan and supported export using [the deployment example](deployment.md).
Keep the selected index, explicit image and any model/device/port options separately
from the generated file. Then use the exact original intent:

```bash
chimeraforge deploy-verify --plan plan.json --candidate-index "$CANDIDATE_INDEX" \
  --config deployment/compose.yaml --image vllm/vllm-openai:v0.30.0 --json
```

The extension does not select a parser: this file must contain generated JSON,
even when named `.yaml`. Arbitrary YAML is outside scope. The image is required;
use your independently chosen explicit non-latest tag or digest. No registry/image
inspection occurs. If the original export used `--model`, repeat it. For a singular
layout, repeat each `--gpu-device` and the original `--host-port`; omitting them
requests the renderer's defaults rather than adopting actual file contents.

## Original multi-replica CLI and API

After producing the actual native three-replica plan/export in
[the fleet example](deployment.md#homogeneous-compose-replicas), verify its full
independently retained layout:

```bash
chimeraforge deploy-verify --plan fleet-plan.json --candidate-index "$FLEET_INDEX" \
  --config fleet/compose.json --model org/manual-fleet --image example/engine:1 \
  --replica-devices 7,3 --replica-port 9001 \
  --replica-devices 9,2 --replica-port 9002 \
  --replica-devices 8,4 --replica-port 9003 --json
```

The illustrative model/image are assumptions from that example, not provisioned
weights or a qualified engine. For real use, retain the selected resolved checkpoint
and matching image. The same direct module API supports all four Compose backends
within their original exporter restrictions:

```python
from chimeraforge.api import load_plan
from chimeraforge.deployment_verify import verify_deployment

original = load_plan("fleet-plan.json")
index = next(i for i, row in enumerate(original.to_dict()["result"]["candidates"])
    if row["backend"] == "vllm" and row["quant"] == "FP16" and row["n_agents"] == 3
    and row["tensor_parallel"] == 2 and row["pipeline_parallel"] == 1
    and row["offload_fraction"] == 0)
result = verify_deployment(
    "fleet-plan.json", "fleet/compose.json",
    image="example/engine:1", model="org/manual-fleet", candidate_index=index,
    replica_gpu_devices=[["7", "3"], ["9", "2"], ["8", "4"]],
    replica_host_ports=[9001, 9002, 9003],
)
print(result.status, result.exit_code)
print(result.to_dict())
```

Here `index` is the original selected candidate index, equivalent to `FLEET_INDEX`.
The exact signature is:

```python
verify_deployment(
    saved: PlanArtifact | str | Path,
    config_path: str | Path,
    *,
    image: str,
    model: str | None = None,
    candidate_index: int = 0,
    gpu_devices: list[str] | None = None,
    host_port: int | None = None,
    replica_gpu_devices: list[list[str]] | None = None,
    replica_host_ports: list[int] | None = None,
) -> DeploymentVerification
```

The direct `chimeraforge.deployment_verify` API is also exposed by the lazy `chimeraforge.api`
re-export. `DeploymentVerification`, `DeploymentChange` and `DeploymentCompanion`
are frozen typed results; change/companion collections are tuples. Invalid inputs
raise `DeploymentVerificationError` with sanitized public diagnostics. The function
does not save a receipt or change the source/config/companions. It has no
executable, output-path or write option. Exporter `output_path` only affects
unpersisted provisioning instructions, which are intentionally not compared.

## Outcomes and comparisons

| Exit | Meaning |
| --- | --- |
| 0 | All admitted JSON and required companion bytes match current-renderer intent |
| 5 | Admitted JSON differs, or a required sibling Modelfile is missing/different |
| 1 | Invalid/unsupported intent; malformed, unsafe, unavailable or overlimit input |
| 2 | Native CLI syntax/usage error before verifier invocation |

Object key order and JSON whitespace are irrelevant. Scalar types are exact:
`true`, `1` and `1.0` differ. Arrays remain ordered, including commands and requested
GPU IDs. JSON is compared **before Compose interpolation**: doubled `$$` generated
by the renderer remains literal. Nothing expands variables, unescapes dollars,
reads `.env`, invokes Docker or contacts a provider. Only persisted configuration
and declared companion bytes participate; notes/provisioning instructions do not.

For an expected Ollama export, only `config.parent / "Modelfile"` is inspected.
Actual mount paths, extra services, environment keys or filenames never direct
filesystem reads. The companion comparison is byte exact, including CRLF versus LF.
A genuinely absent required sibling is drift; unsafe links, unreadable files and
other I/O failures are invalid. A missing top-level config is invalid. Extra files
are ignored; directories are not scanned. Drift does not assert that the modified
JSON would satisfy Compose's schema or run successfully.

## Admission, receipts and proof limits

Every input uses lexical absolute paths followed by native bounded regular-file
guards. Symlinks/reparse points and hardlinks are refused; source/config/required
companion aliases are rejected by path and native file identity. Source and actual
file buffers are held once and hashed; expected assets come only from the renderer.
This does not claim an atomic cross-file filesystem snapshot.

Both actual and expected JSON are fully admitted as UTF-8 objects with unique keys
and finite numbers **before** the diagnostic cap. The limits are:

| Bound | Value |
| --- | --- |
| Saved plan file or serialized object snapshot | 8 MiB |
| Each actual/expected Compose JSON asset | 2 MiB |
| Each actual/expected required Modelfile | 64 KiB |
| Cumulative held source + actual/expected asset buffers | 12.125 MiB |
| Nodes per admitted JSON tree, counting repeated references and object keys | 100,000 |
| JSON nesting depth (root depth zero) | 64 |
| Integer bit length | 4,096 |
| Image, explicit/derived model identity and input-path text | 4,096 characters |
| Diagnostic records | 64, plus complete bounded change count/truncation flag |

The held-byte budget is not a total process-memory ceiling. Direct `PlanArtifact`
data is admitted before copying/serialization, so cycles or repeated shared subtrees
cannot bypass traversal bounds. Native layout limits still apply: at most 16 replicas,
64 GPUs per replica, canonical IDs up to 40 characters and distinct valid host ports.
The full 16-by-64 declared layout fits the verifier's admission bounds; this is not
a claim that the planner or physical hardware can realize every such shape.

Receipts name `renderer_version`. `source_kind="file_bytes"` means `plan_sha256`
hashes the exact held saved-file bytes. `source_kind="artifact_snapshot"` means it
hashes the bounded serialized `PlanArtifact` snapshot; that is not an original-file
hash. Config and expected-config hashes identify their respective original byte
buffers and may differ even when object semantics match. Companion digests retain
the exact byte basis. Digests do not authenticate a producer.

Changes expose only paths from the fixed expected renderer structure, category
and counts. Extra unknown key names and actual/expected values are omitted; public
native/parser exception causes are suppressed. The total counts scalar/type/missing
changes, extra keys and array-length differences; capped detail never skips admission
of the remaining actual input.

A match means consistency with this current renderer and supplied intent. It does
not establish source authenticity, image/registry state, running model/weights,
GPU existence/model/order/topology, engine startup, serving capacity or performance.

## Kubernetes intent (unreleased 0.81.0)

Use explicit `format="kubernetes"` (CLI `--format kubernetes`) with independently supplied `KubernetesOptions`, image, selection and optional model intent. Default `format="compose"` and its report shape stay unchanged. The bounded receiver admits Deployment/Service JSON Lists and redacts drift values; it never infers desired intent from actual configuration. See [full examples, source/alias bounds and hosted API-admission limits](kubernetes-deployment.md).
