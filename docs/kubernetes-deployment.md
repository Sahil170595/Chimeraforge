# Kubernetes declarations and independent verification

This is an **unreleased 0.81.0 source feature**. Public installation remains
0.76.0; install this candidate source to use these options.

Export the original online Linux CUDA vLLM or SGLang candidate as one JSON
`v1 List`. It contains one `replicas: 1` Deployment and one ClusterIP Service
for **every original member**, in member order. No cluster calls occur in the
exporter or verifier.

```bash
# Select a supported candidate from your saved plan, rather than assuming rank 0.
export CANDIDATE_INDEX=0
chimeraforge deploy --plan plan.json --candidate-index "$CANDIDATE_INDEX" \
  --format kubernetes --image vllm/vllm-openai:v0.30.0 \
  --namespace default --name-prefix inference \
  --node-selector operator.example/accelerator=declared --out inference.json

# Supply desired intent independently; never recover it from inference.json.
chimeraforge deploy-verify --plan plan.json --candidate-index "$CANDIDATE_INDEX" \
  --format kubernetes --config inference.json \
  --image vllm/vllm-openai:v0.30.0 --namespace default --name-prefix inference \
  --node-selector operator.example/accelerator=declared --json
```

Use a matching explicit non-`latest` tag or digest for the selected backend.
These example image strings declare intent; the exporter does not check their
existence or compatibility. The target namespace must already exist before any
operator-initiated application. Export and verification do not create it.

```python
from pathlib import Path
from chimeraforge import api
from chimeraforge.deploy import export_deployment

saved = api.load_plan("plan.json")
index = 0  # Independently select a supported saved candidate.
options = api.KubernetesOptions(
    namespace="default", name_prefix="inference",
    node_selector={"operator.example/accelerator": "declared"},
)
declaration = export_deployment(
    saved, format="kubernetes", candidate_index=index,
    image="vllm/vllm-openai:v0.30.0", kubernetes=options,
)
with Path("inference.json").open("x", encoding="utf-8", newline="") as stream:
    stream.write(declaration.content)
checked = api.verify_deployment(
    saved, "inference.json", format="kubernetes", candidate_index=index,
    image="vllm/vllm-openai:v0.30.0", kubernetes=options,
)
assert checked.exit_code == 0
```

`KubernetesOptions` is typed declaration intent, without cluster credentials.
Defaults are namespace `default`, a prefix derived from the source fingerprint
and selection, and the mandatory `kubernetes.io/os=linux` selector. Caller label
maps are defensively copied. Names are conservative alpha-start DNS labels,
at most 63 characters; an explicit prefix is at most 40. At most 16 final node
selector pairs are allowed, **including** Linux. Qualified label keys and values
are validated; an operator cannot override the OS selector away from Linux.

Every member has disjoint logical selectors and a corresponding Service. These
names persist as declarations, not process/GPU identities. Deployments use
`Recreate`; replacement Pods can still be different processes. Original N, TP,
PP, context, effective batch, supported quantization/KV/cache controls and pinned
checkpoint revision stay intact. Every Pod requests and limits `nvidia.com/gpu`
to TP times PP; desired total is N times TP times PP. This is a scheduler request,
not observed devices, plugin availability, fit, independence or capacity.

The native engine listens on `0.0.0.0`, with port 8000 for vLLM or 30000 for
SGLang. `/dev/shm` uses a memory `emptyDir` with declared `sizeLimit: 1Gi`, not a
memory reservation or fit prediction. No router, autoscaler, NodePort,
LoadBalancer, host network/port/path, privileged container, credential environment
or pull-secret registry is generated. Operator-supplied namespace, selectors,
image and source model paths may be private; treat the manifest like its plan.

Kubernetes command and argument arrays perform dollar expansion despite using
no shell. The renderer reuses the raw native engine vector and encodes each
literal `$` once as `$$`. Thus `$(TOKEN)` becomes `$$(TOKEN)` and an original
`$$(TOKEN)` becomes `$$$$(TOKEN)`. Other quotes, Unicode and whitespace remain
JSON string content. This follows the
[pinned native expansion implementation](https://github.com/kubernetes/kubernetes/blob/v1.37.0/third_party/forked/golang/expansion/expand.go).
Server dry-run admission does not execute this kubelet expansion.

All N, including N1, require the native online Linux CUDA vLLM/SGLang fidelity
contract. Unsupported platforms/backends, offline mode, unknown/nonzero offload,
LoRA, recurrent ambiguity and unsupported quantization/cache/chunk controls are
refused. Host GPU IDs, replica device groups, host/replica ports and executable
overrides are refused for this format. Existing Compose and other format
defaults and bytes retain their behavior.

The encoded command plus args has at most 128 tokens, 4096 UTF-8 bytes per token
and 64 KiB total. These bounds apply **after** dollar encoding. Final output
is at most 2 MiB UTF-8, at most 32 objects (N at most 16), and uses the existing
100,000-node/depth-64 JSON admission bounds.

Verification compares the held manifest to a fresh render from independently
supplied source/selection/image/model/namespace/prefix/selectors. It admits only
bounded JSON Lists of Deployment and Service resources, with no YAML parser,
interpolation or Kubernetes client. Added or missing members, unknown object
keys and changed declared values produce redacted differences. Unsupported
kinds/versions, duplicate JSON keys, nonfinite values, bounds failures and input
aliases are invalid. Exit codes stay 0 match, 5 admitted drift, 1 invalid;
native Typer usage errors stay 2. Output values/unknown keys are not reflected
in difference diagnostics. Existing default Compose report shape is unchanged.

The hosted `kubernetes-admission` job installs the built wheel outside checkout
and uses checksum-pinned kind 0.33.0, kubectl 1.37.1 and a digest-pinned Kubernetes
1.37.0 node. Its offline checkpoint metadata fixture produces genuine native
N1/N3 plans for both backends; no weights are downloaded. It submits every
generated object using server-side strict dry-run, checks returned fields and
defaulting, rejects unequal GPU request/limit and an unknown field, and proves
API-valid image/model/selector drift still returns native verification 5.

Only an owned named cluster, private kubeconfig/context and ordinary bridge are
used. Preexisting cluster names and duplicate `kind` networks are refused. An
existing single network is preserved by ID; a newly created network is labelled
and removed only by exact ID after ownership and emptiness checks. Partial
creation still triggers named deletion, process-group reaping and cleanup
evidence. Normal kind system infrastructure is allowed. Feature Deployments,
Services and Pods must remain absent after dry-run.

This gate qualifies **API admission only**. As the
[native dry-run contract](https://kubernetes.io/docs/reference/using-api/api-concepts/#dry-run)
explains, requests are not persisted. It establishes no inference image pull,
model access, executed argv, scheduling, driver/plugin, GPU allocation, TP/PP
runtime topology, SLO, readiness or independent capacity. Installed CLI/API
controls and regenerable source evidence are documented in
[the validation record](../validation/2026-10-25-kubernetes-export/README.md).
