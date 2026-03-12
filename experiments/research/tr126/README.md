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
