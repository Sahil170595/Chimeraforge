# TR126 Phase 4: Python Ceiling Test (Deferred)

**Goal:** Test Python multi-agent with `uvloop` on Linux to determine if the 86% asyncio efficiency ceiling (TR117-MA) lifts.

**Baseline:** TR114v2 showed 98.28% efficiency with Rust (Tokio work-stealing). Python peaked at ~86% due to asyncio event loop saturation.

## Why Deferred

Phase 4 requires:
1. Multi-agent orchestration infrastructure (Python + Rust) working inside Docker
2. Multiple Ollama instances on separate ports (11434-11441)
3. uvloop integration and testing
4. Baseline reproduction of TR114v2 Rust results

This is a separate engineering effort that should not block Phases 1-3 (the compile/Triton validation).

## Planned Design

When implemented:
- Agent counts: 2, 4 (with uvloop on Linux vs stock asyncio)
- Model: gemma3:270m (small enough for multiple agents)
- Metrics: per-agent throughput, efficiency ratio, contention rate
- Compare: Linux+uvloop vs Windows+asyncio (from TR117-MA data)

## Dependencies

- TR114v2 Rust orchestration code
- TR117-MA Python multi-agent baseline data
- Working Docker GPU passthrough (validated in Phase 1)
