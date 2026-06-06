# TR126: Docker/Linux + Triton Validation

**Research Question:** Do Windows inference results hold on Linux? Does real Triton compilation change backend rankings?

**Why this matters:** TR120 discovered that `torch.compile` on Windows falls back to `aot_eager` (no Triton). All compilation results in TR117-TR122 are under this fallback. Real Inductor+Triton compilation on Linux may change everything.

**Hardware:** RTX 4080 Laptop (12 GB VRAM) — same GPU, Docker Linux environment.

---

## Phases

### Phase 1: Docker Environment Validation (~50 runs)
- Verify GPU passthrough, CUDA, Triton availability
- Confirm identical model weights and deterministic output across platforms
- **Gate:** Phase 2-3 do not proceed until Phase 1 passes

### Phase 2: Compile Paradox Replication (~300 runs)
- Rerun TR120 controlled experiments with **real Triton** (not aot_eager)
- 5 scenarios x 30 reps x 2 backends (eager/compile) x 3 modes (prefill/kv_decode/e2e_kv)
- Ablations: padded shapes, dynamic=True
- **Key question:** Does compile still help prefill and hurt decode with real Triton?

### Phase 3: Backend Matrix Rerun (~630 runs)
- Focused subset of TR117 Tier-3 matrix under Linux
- 3 backends (transformers-gpu, transformers-gpu-compile, ollama) x 2 models x 5 scenarios x 7 reps x 3 modes
- **Key question:** Does Triton change gpu-compile's ranking position?

### Phase 4: Python Ceiling Test (Deferred)
- Python multi-agent with uvloop on Linux
- Does the 86% asyncio efficiency ceiling lift?
- Designed separately after Phase 1-3 complete

---

## Quick Start

```bash
# Build Docker image
docker build -t tr126 -f research/tr126/Dockerfile .

# Phase 1: Environment validation
docker run --rm --gpus all -v "${PWD}:/workspace" -w /workspace \
  tr126 python research/tr126/phase1/run.py

# Phase 2: Compile paradox
docker run --rm --gpus all -v "${PWD}:/workspace" -w /workspace \
  tr126 python research/tr126/phase2/run.py

# Phase 3: Backend matrix
docker run --rm --gpus all -v "${PWD}:/workspace" -w /workspace \
  tr126 python research/tr126/phase3/run.py
```

---

## Dependencies

- TR120 Windows results: `research/tr120/results/` (cross-platform comparison baseline)
- TR117 Windows results: `results/tr117_tier3/` (backend ranking baseline)
- Local model: `models/tiny-gpt2` (mounted into container)
- Ollama models: `gemma3:270m` (pulled inside container for Phase 3)

---

## Update / Resolution (2026-06-05): compiled-decode crash fixed upstream

Phase 2's `reduce-overhead` / cudagraph runs surfaced a hard crash on compiled
autoregressive decode ("accessing tensor output of CUDAGraphs that has been
overwritten by a subsequent run"; PyTorch #175557). Earlier write-ups concluded
this was architectural and not patchable from PyTorch internals. That conclusion
is now SUPERSEDED:

- The earlier "architectural, not patchable" claim was based on a "never free"
  prototype (disabling the dealloc free path + assertion), which still crashed.
  The correct fix is the opposite: preserve/clone the cudagraph-pool-aliased
  inputs BEFORE dealloc frees them. PyTorch #184102 (jansel,
  `_preserve_inputs_that_alias_current_path`, Fixes #175557) does this.
- We validated #184102 on a REAL gpt2 decode (`mode="reduce-overhead"`,
  `past_key_values` fed back, 128 tokens) on Docker / RTX 4080 Laptop across two
  torch builds (NGC 2.10.0a0 and pip nightly 2.12.0.dev20260408). Baseline
  crashes at the first decode step; with #184102 all 128 tokens complete and
  cudagraphs stay active. Also held across 7 synthetic feedback topologies.
  So compiled decode with a growing cache CAN work on a patched PyTorch.
- One coverage gap found (synthetic, source-verified): when a compiled function
  splits into multiple cudagraph partitions and a top-level input consumed only
  by a LATER partition is fed back from the pool, #184102 still crashes, because
  `_preserve` only clones the current partition's inputs while dealloc frees the
  whole path. Reproduces on torch 2.10 and 2.12 nightly. The split was forced
  synthetically via a DeviceCopy boundary; no real model has been shown to hit
  this, so the practical blast radius is unproven / likely small. Reported
  upstream; vmoens' alternative #176295 raises a clear error for this case.
- Status: #184102 is under active maintainer review (eellison: likely opt-in due
  to copy cost; needs to interact with cached outputs), NOT merged. The
  assertion-cleanup PR #175562 DID land in main (squash `be90a1495310`,
  2026-06-04).

Artifacts: validation gist
https://gist.github.com/Sahil170595/062d40cb18e2b2e27e99c1efbfa3ccdb and the
endorsement comment on #184102
https://github.com/pytorch/pytorch/pull/184102#issuecomment-4635948508 .
