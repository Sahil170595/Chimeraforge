# Queried inventory and saved baseline arithmetic

Chimeraforge 0.92.0 adds optional selected-batch memory preflight. Batch-one
behavior remains the default.

Available since **Chimeraforge 0.77.0**. This operation checks an inventory view and
saved arithmetic. Every report has `deployment_ready: null`.

```bash
# One saved replica, in its original TP x PP declaration order:
chimeraforge inventory-check --plan saved.json --gpu-device 7 --gpu-device 3 --json

# A saved N=3, TP=2, PP=1 candidate requires all six selectors:
chimeraforge inventory-check --plan fleet.json --candidate-index 0 \
  --replica-devices 7,3 --replica-devices 9,2 --replica-devices 8,4 --json
```

Choose the original candidate index; the operation never reduces its replica
population or replans. A single replica requires repeated `--gpu-device`;
multiple replicas require one ordered `--replica-devices` group per replica.
There are no port, image, model or hardware overrides. Canonical ordinals or full
GPU UUIDs must be globally disjoint in one namespace, exactly as native deployment
selection requires. Those declarations do not establish independent physical GPUs.

```python
import asyncio
from chimeraforge import api

report = asyncio.run(api.check_inventory(
    "fleet.json", candidate_index=0,
    replica_gpu_devices=[["7", "3"], ["9", "2"], ["8", "4"]], timeout=10,
))
print(report.exit_code, report.to_dict())
```

`saved` is a `PlanArtifact` or original saved-plan JSON path. Input bytes are held
once; object inputs are copied through native validation. The fingerprint detects
edits, not authenticity. No producer dependency, model, driver configuration or
output file is written. The CLI writes JSON or complete per-slot text to stdout.

## What is compared

The saved candidate's `vram_gb` is the native per-GPU modeled **batch-one GiB**
quantity, rounded to two decimals. Its separately saved `effective_batch` is
reported without multiplying it into this baseline. For saved `r`, the interval is
`[max(0, r - 0.005), r + 0.005] GiB`. Exact bounded integer/rational arithmetic is
independent of the caller's Decimal precision, rounding and traps.

Each observed free-MiB value is divided by 1024. At least the upper bound passes
that arithmetic check; below the lower bound is a known shortfall; overlap is
unknown. The interval bounds serialization rounding only, not model error.
Reported total is compared separately and never fills unavailable free. No memory
values are summed. Offload-clamped, unavailable or unsupported saved baselines
remain unknown without reconstruction or native contact.

## Opt-in selected-batch memory (since 0.92.0)

```bash
# Produce/save the plan with this 0.87 source first; keep its selected B/context:
chimeraforge inventory-check --plan single.json --candidate-index 0 \
  --gpu-device 7 --gpu-device 3 --memory-basis selected-batch --json
```

```python
report = asyncio.run(api.check_inventory(
    "single.json", candidate_index=0, gpu_devices=["7", "3"],
    memory_basis="selected-batch",
))
```

Use the held saved B1 interval as a fixed intercept and add
`(saved_effective_batch - 1) * per_sequence_increment_gib` to both bounds. For
supported dense MHA/GQA and whole KV-head TP partitions at PP=1, the increment is
`layers * (KV_heads / TP) * head_dimension * 2 * saved_context * KV_element_bytes / 2^30`.
It uses the saved context, KV quantization and original degrees, without resolving
today's model, reloading the coefficient corpus, refitting or replanning. The
increment covers full saved context for each active sequence. Idle sessions,
prefix pools, workspace and runtime peaks remain unassessed. It models resident
components, not peak demand or an allocation guarantee.

For the archived Qwen2.5-1.5B geometry (28 layers, two KV heads, head dimension 128),
context 8192, two-byte KV, TP=2, PP=1 and saved B=8 add exactly **784 MiB per device**
over B1. The configuration was captured on 2026-09-05 from an upstream `main` URL;
it is not a resolved Hub revision. The native test producer declares
`params_b=1.5`, not a weight or physical-memory measurement. At context 8193 the
increment is `0.1093883514404296875 GiB` per sequence. Comparisons retain that exact
fraction instead of rounding it into the inventory input's six-decimal domain.

Newly produced candidates may carry a closed versioned calculator declaration
under `provenance.vram.memory_formula`. It binds actual native formula use, saved
B1, B, context, actual KV element size, TP/PP, full saved model facts and emitted
architecture. This is structural compatibility and input provenance, **not code
or producer authentication**. A plan fingerprint detects edits; it authenticates
neither the declaration nor the producer. The existing policy digest is not a
calculator identity. Older saved plans without the declaration remain valid for
default B1 checks and return selected-batch unknown without querying inventory.
The native `check`/study prediction-provenance view excludes only this inventory
annotation, with an explicit detail. Numerical predictions, all other provenance
anchors and existing tool/checkpoint/resolution guards remain assessed; the
selected-batch inventory operation validates its own declaration separately.

Selected mode requires whole-head TP division with TP no greater than KV-head
count and PP=1. TP greater than KV heads is unknown: the saved spec does not
establish query-head replication semantics. PP>1, MLA, recurrent or hybrid state,
sliding-window facts (including an unknown interleave), approximate geometry,
offload and LoRA controls remain unknown before inventory contact. Missing,
foreign or inconsistent declarations, geometry or controls are also unknown.
Refusal paths use held facts and never resolve current model metadata. Admitted
geometry integers are 1..1,000,000; saved B/context are 1..2^31-1. A selected upper
bound above 10^9 GiB is unsupported. These are arithmetic admission limits, not
claims that such configurations are realizable.

Selected reports use schema 2 and frozen `SelectedBatchBaseline`: nested original
`saved_batch1`, saved B/context/KV/TP/PP, per-sequence increment, selected lower/upper
bounds, status and categorical reason. Numeric evidence is complete canonical
decimal strings or null. `interval_scope` is serialization precision only; no
uncertainty distribution is inferred. Comparisons explicitly say
`at_least_selected_batch_estimate` or `below_selected_batch_estimate`. A B1 pass can
become a selected-batch shortfall without being mislabeled as below B1. Every
original ordered N x TP x PP slot remains; values are never pooled. The CLI shows
both references and makes unsupported bounds unavailable. The default retains
schema 1 and its old labels/captions. `deployment_ready` is always null.

## Query and source bounds

One owned process requests:

```text
nvidia-smi --query-gpu=index,uuid,name,memory.total,memory.free,driver_version,mig.mode.current --format=csv,noheader,nounits
```

There is no retry, alternate query, NVML fallback or engine contact. An installed
driver that cannot provide the requested interface produces unknown evidence.
The timeout defaults to 10 seconds and is at most 60. Evidence buffers admit stdout
up to 1 MiB, stderr up to 16 KiB, rows up to 1024, fields up to 256 characters, and fixed-point
numeric tokens at 32 characters/six fractional digits/10^12 MiB. Exponents,
nonfinite values and contradictory free/total are refused. These bounds limit
consumed data, not every OS/pipe buffer or a universal kernel return deadline.
After terminating an over-limit child, cleanup discards remaining pipe data in
bounded 16 KiB chunks; those discarded bytes are not admitted evidence and are
not included in the evidence-buffer caps. The child and pipe readers are
closed/joined before return or cancellation.

Strict seven-field UTF-8 CSV, canonical IDs and a unique ordinal/UUID map are
required. Malformed, duplicate, truncated or failed output invalidates the entire
observation. No useful-looking subset can establish selector absence. A successful
query is one view collected over an interval, not an atomic host/CUDA snapshot.

## Outcomes and report types

Both memory modes retain the native exit priorities below. A logical invalid
`memory_basis` raises `InventoryCheckError`; the CLI names the two allowed values.

| Exit | Meaning |
| --- | --- |
| 0 | Complete requested mapping and reported-free arithmetic pass against the chosen B1 or selected-batch reference |
| 5 | Complete valid view establishes a missing requested selector or free-memory shortfall |
| 4 | Unsupported valid candidate/basis, unavailable memory, overlap, invalid observation or cleanup uncertainty |
| 1 | Malformed source, candidate selection, options or selector declaration; refused before contact |
| 2 | Native Typer usage error |

Known negatives on a complete view take precedence over other valid unknowns.
Invalid observations stay unknown, including when a partial row set looks missing.
Every returned `InventoryCheck` preserves all original ordered `InventorySlot`
entries; unresolved evidence is null with a reason. `InventoryBaseline`,
`InventoryObservation` and `InventoryDevice` are frozen typed dataclasses exported
through `api`. Numeric JSON evidence is a canonical decimal string or null.

MIG `Enabled`, `Disabled` and `N/A` have identical arithmetic treatment, with their
raw values retained. None establishes partition topology, bare metal or independent
memory pools. Names are diagnostic; no hardware-compatibility registry is inferred.
CUDA visibility, physical identity, engine compatibility, allocation and runtime
peak remain unassessed, even on exit 0. Reported free memory is neither a reservation
nor a deployment-readiness result.

NVIDIA documents [unsupported query information and shared MIG memory](https://docs.nvidia.com/deploy/nvidia-smi/index.html).
Its [guest-VM example](https://docs.nvidia.com/ai-enterprise/release-8/latest/infra-software/vgpu/licensing.html)
combines a full GPU UUID with MIG N/A and VGPU mode. Neither a UUID nor N/A proves
physical independence. Controlled subprocess fixtures qualify parser, arithmetic
and ownership behavior; hosted CPU unavailability is not GPU qualification.
