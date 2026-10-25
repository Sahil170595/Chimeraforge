# Queried inventory and saved baseline arithmetic

**Unreleased 0.77.0 source candidate.** The public installation is 0.76.0 and
does not include `inventory-check`. This operation checks an inventory view and
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

| Exit | Meaning |
| --- | --- |
| 0 | Complete requested mapping and reported-free versus saved-B1 arithmetic pass |
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
