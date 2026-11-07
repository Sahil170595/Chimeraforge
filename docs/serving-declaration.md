# Operator-authored serving declarations

**Since 0.92.0.** This workflow
declares concrete serving settings without running an optimizer, resolving a model,
loading a coefficient corpus or claiming that the configuration can serve traffic.

## Declare, save and receive

```python
from chimeraforge import api

intent = api.declare_serving(api.ServingRequest(
    model="Qwen/Qwen2.5-1.5B-Instruct",
    revision="00112233445566778899aabbccddeeff00112233",  # example operator claim
    backend="vllm", image="vllm/vllm-openai:v0.30.0",
    replicas=3, tensor_parallel=2, pipeline_parallel=2,
    context_length=8192, batch_size=8,
))
intent.save("operator.serving.json")
held = api.load_serving_declaration("operator.serving.json")
quote = api.quote_serving(held, cloud="aws", instance="p5.48xlarge", region="us-east-1")
```

`ServingRequest` also exposes `dtype="FP16"`, `kv_quant="fp16"`,
`prefix_caching=False` and optional `max_num_batched_tokens`. The closed profile
supports online Linux CUDA vLLM/SGLang with FP16/BF16 weights and fp16/q8 KV.
SGLang BF16 with requested fp16 KV refuses: its implicit cache dtype does not
establish FP16. The explicit chunked-prefill token budget is vLLM-only, aligned to
the native tile boundary and at least the declared batch. q4, offload, LoRA,
other backends/platforms and unknown settings are unsupported.

Replicas are 1..16, each TP/PP degree is positive and TP*PP is at most 64.
Context and batch are 1..1,048,576. These are serialization/argv bounds, not model
or engine limits. The model is an explicit namespace/repository and the revision
is a lowercase 40-hex **operator claim**, without Hub resolution/authentication.
An explicit non-latest image tag remains mutable. A sha256 digest identifies
content, but neither image availability nor flag/model/platform compatibility
is checked. `image_compatibility` remains null.

The closed versioned JSON artifact is at most 64 KiB. File input is held once;
typed input is admitted before copying/encoding, then schema and fingerprint are
revalidated. Unknown keys, fabricated feasibility claims, nonfinite values,
foreign profiles and inconsistent fingerprints refuse. The fingerprint detects
edits; it is not a signature. Save requires a new ordinary file. All throughput,
latency, quality, memory, feasibility, capacity, token-cost and readiness claims
remain null. This artifact is not a `PlanArtifact`; native `plan`/`check_plan`
cannot use it as optimizer feasibility evidence.

## Quote whole instances, without assigning hosts

`quote_serving` takes either a declaration or its saved path. Omit all billing
arguments for an explicit unknown quote. Otherwise supply **all three** of
`cloud`, exact `instance` and exact `region`. AWS/Azure selection admits exactly
one matching bundled offer; missing, ambiguous, unpriced and group-too-large
offers retain unknown costs instead of using per-GPU or zero-price fallbacks.

The existing native arithmetic fits `floor(instance_GPUs / (TP*PP))` complete
groups per instance, then bills `ceil(N / groups)` whole instances. N=3, TP=2,
PP=2 has 12 logical slots; on the bundled 8-GPU p5.48xlarge offer it bills two
whole instances, 16 GPUs, with four idle billed GPUs. It does not split one group
across instances. Monthly arithmetic uses the existing 720-hour convention.

Every estimated quote carries the selected offer's specification/price sources,
region, the bundled snapshot date (currently 2026-10-01), actual age, stale flag
(age greater than 90 days), and a canonical whole-snapshot object digest. This is
dated list-price arithmetic, not a live offer, invoice, placement or availability
check. Quotes do not assign replica/device identities to hosts or predict
throughput, token cost, quality, feasibility or deployment readiness.

## Export and verify the same concrete intent

`api.export_serving_declaration(intent, *, format, ...)` returns the existing
`DeploymentExport` with `.content`, `.notes` and `.to_dict()`.
Formats are `launch`, `compose` and `kubernetes`. The same native argv and
configuration projection feeds `api.verify_serving_declaration(intent, config,
*, format="compose", ...)`, whose `.to_dict()` reports `declaration_sha256`,
config/expected hashes and bounded changes. No plan fingerprint/candidate index
is invented. Match exits 0, known config drift 5 and invalid input 1 (native CLI
usage errors remain 2). A match means configuration equality, not engine startup.

For multi-replica launch/Compose, provide one ordered disjoint device group of
TP*PP IDs and one distinct host port per replica:

```python
layout = {
    "replica_gpu_devices": [["0", "1", "2", "3"], ["4", "5", "6", "7"],
                            ["8", "9", "10", "11"]],
    "replica_host_ports": [9001, 9002, 9003],
}
exported = api.export_serving_declaration(held, format="compose", **layout)
with open("operator.serving.compose.json", "x", encoding="utf-8", newline="\n") as output:
    output.write(exported.content)
assert api.verify_serving_declaration(
    held, "operator.serving.compose.json", format="compose", **layout
).exit_code == 0
```

These IDs share **one declared host namespace**. The example needs twelve
distinct device IDs on that host; it does not place the quote's two 8-GPU
instances, and cannot be copied unchanged onto each one. Launch returns separate
entrypoints and environments, not a distributed fleet launcher. Singular
`gpu_devices`/`host_port` apply only to a single replica. Missing multi-replica
bindings, aliases, overlapping groups, repeated ports and mixed singular/fleet
options refuse.

Kubernetes uses `KubernetesOptions(namespace=..., name_prefix=...,
node_selector=...)` and logical GPU requests/limits, not physical device or host
port bindings. N=3 produces three Deployments and three Services (six objects),
each Deployment requesting TP*PP=4 GPUs. This does not establish scheduling,
network topology or distributed runtime support. Outputs and received configs
are bounded by the existing 2 MiB native config limit; source/output aliases and
overwrites refuse. The independent original declaration remains the authority
for comparison; editing both artifacts is not attestation.

## CLI

See the [complete `serving` command examples](../README.md).
`serving declare` requires `--model --revision --backend --image --out`, with
`--replicas --tp --pp --context --batch --dtype --kv-quant --prefix-caching` and
optional `--max-num-batched-tokens`. `serving quote` requires `--declaration` and
optionally the complete `--cloud --instance --region` target. `serving export`
requires `--declaration --out`, and `serving verify` requires
`--declaration --config`; both accept `--format launch|compose|kubernetes`,
`--gpu-device --host-port`, repeated `--replica-devices --replica-port`, or
Kubernetes `--namespace --name-prefix --node-selector`. All four support `--json`.

## Fixed reference and proof boundaries

The declared argv profile is based on the existing native projection and static
official [vLLM v0.30.0 argument definitions](https://github.com/vllm-project/vllm/blob/v0.30.0/vllm/engine/arg_utils.py)
(Git blob `b420e84f542b0679d746eb22ffc6ff728d6397f1`) and
[SGLang v0.5.20 definitions](https://github.com/sgl-project/sglang/blob/v0.5.20/python/sglang/srt/server_args.py)
(Git blob `d79bb75d7a32844ed9d4d08a4b1aedeee632542d`). Static definitions support
intended flag spelling, not full parser/cross-field/model/image compatibility.
No engine/image/model download or runtime was executed for this feature's source
controls. The native producer, actual CLI, quote and config receivers execute;
original/rebuilt installed acceptance remains a separate hosted qualification.
