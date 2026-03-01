# TR108-TR116 Decision Whitepaper
## Executive guidance for language, architecture, runtime, and model selection

Project: Banterhearts LLM Performance Research
Date: 2025-12-28
Version: 1.0
Audience: Decision makers, engineering leads, ops leaders
Scope: TR108, TR109, TR110, TR111_v2, TR112_v2, TR113, TR114_v2, TR115_v2, TR116
Primary source: `PublishReady/reports/` (individual TR reports)

---

## Abstract

This whitepaper distills TR108-TR116 into deployment policy for multi-agent LLM inference on consumer-grade hardware. The program answers one central question:

Should we use Rust or Python for multi-agent LLM workloads on consumer hardware, and what architecture, runtime, and model choices maximize efficiency?

Outcome: Rust with dual Ollama instances, Tokio-default runtime, and Gemma 3 achieves 99.4% multi-agent parallel efficiency versus Python's structural ceiling of ~86%. The single highest-impact change is architectural (dual Ollama), not linguistic (Rust vs Python).

---

## Boundary conditions (do not skip)

This guidance is valid only under the measured boundary:

- NVIDIA RTX 4080 Laptop GPU (12 GB VRAM), Intel i9-13980HX, 32 GB DDR5-4800
- Windows 11 Pro
- Ollama inference backend (single and dual instance configurations)
- Gemma 3 4.3B Q4_K_M, Llama 3.1 8B instruct Q4_0, Qwen 2.5 7B
- 2-agent concurrent workloads (baseline-vs-chimera, chimera-homo, chimera-hetero)
- Measurement definitions: tok/s, TTFT, parallel efficiency, contention rate

If any of these change, re-run the core benchmark matrix and re-validate all findings.

---

## Executive summary: six decisions you can ship now

1. **Language:** Rust for production. 15.2% faster throughput, 67% less memory, 83% faster startup than Python.
2. **Architecture:** Dual Ollama mandatory for multi-agent. Contention drops from 63% to 0.74%; efficiency jumps from 82.2% to 99.4%.
3. **Runtime:** Tokio-default (`#[tokio::main]`). 98.72% mean efficiency, 1.21pp standard deviation. No custom configuration needed.
4. **Model:** Gemma 3 for scaling efficiency (99.2%). Llama 3.1 for reasoning-heavy tasks (96.5%).
5. **Python ceiling:** Structural event loop limit at ~86% multi-agent efficiency. Rust is mandatory for high-throughput concurrent workloads.
6. **Configuration transfer failure is systematic:** Single-inference optimal settings do not transfer to agent workflows, and agent-optimal settings do not transfer to multi-agent. Validate per deployment mode.

If you follow these rules, you avoid the four common deployment failures: wrong language at scale, single Ollama bottleneck, wrong runtime, transferred configs.

---

## Definitions (one-time)

- **TTFT:** Time to first token (ms). Measures cold-start and prompt processing latency.
- **tok/s:** Tokens per second. Primary throughput metric for decode-phase generation.
- **Parallel efficiency:** (concurrent throughput / sum of individual throughputs) x 100. 100% = zero overhead.
- **Contention rate:** Percentage of runs where concurrent agents degrade each other's throughput below baseline.
- **Dual Ollama:** Two independent Ollama server instances on separate ports, each serving one agent. Eliminates server-level request serialization.

---

## Decision matrix (one-glance policy)

| Condition | Language | Architecture | Runtime | Model |
|---|---|---|---|---|
| Multi-agent production (>95% eff required) | Rust | Dual Ollama | Tokio-default | Gemma 3 |
| Multi-agent reasoning-heavy | Rust | Dual Ollama | Tokio-default | Llama 3.1 |
| Single-agent production | Rust | Single Ollama | Tokio-default | Model-dependent |
| Prototyping / research | Python | Dual Ollama | asyncio | Any |
| Binary size constrained (<5 MB) | Rust | Dual Ollama | Smol-1KB | Gemma 3 |

---

## Key findings (decision-grade)

- **Rust single-agent advantage is real:** +15.2% throughput (114.54 vs 99.34 tok/s), +46% consistency (2.6% vs 4.8% CV), 58% faster TTFT cold start. Evidence: TR112_v2, 111 runs.
- **Dual Ollama is the single highest-impact change:** Transforms multi-agent from 82.2% efficiency / 63% contention (TR113, single Ollama) to 99.4% efficiency / 0.74% contention (TR114_v2, dual Ollama). This is an architectural fix, not a code fix.
- **Tokio-default wins on consistency, not peak:** All four working runtimes hit ~100% peak (99.87-99.99%), but Tokio-default has the tightest distribution (1.21pp sigma vs 4.03pp for localset, 4.87pp for smol). Async-std is unusable (50% serialization). Evidence: TR115_v2, 150 runs.
- **Gemma 3 is the efficiency champion:** 99.2% chimera-homo efficiency in Rust, 97.3% overall multi-agent mean. Llama 3.1 close behind at 96.5%. Qwen 2.5 trails at 90.0% with heavier coordination overhead. Evidence: TR116, 60 runs.
- **Python cannot exceed ~86% multi-agent efficiency:** Best Python result across all models is 83.8% (Llama 3.1). This is a structural event loop ceiling, not a tuning gap. Rust achieves +12-17pp higher efficiency for every model tested.
- **Config transfer failure is systematic:** TR108 optimal (GPU=999, CTX=4096) fails for agent workflows (TR109 optimal: GPU=60-80, CTX=512-1024). Agent-optimal fails for multi-agent (TR110/TR114_v2 optimal: GPU=80, CTX=512-2048). Each deployment mode requires independent validation.

---

## Operational recommendations (policy statements)

### Language selection

- **Policy:** Default to Rust for all production workloads.
- **Policy:** Permit Python only for prototyping, research, and development-velocity-critical paths.
- **Gate:** If multi-agent efficiency >90% is required, Rust is mandatory.

### Architecture

- **Policy:** Always deploy dual Ollama instances for multi-agent workloads.
- **Policy:** Monitor contention rate; alert if contention exceeds 1% of runs.
- **Policy:** Single Ollama is acceptable only for single-agent deployments.

### Runtime

- **Policy:** Use `#[tokio::main]` with no custom thread pool configuration.
- **Policy:** Never use async-std (50% serialization failure).
- **Policy:** Smol-1KB is acceptable only when binary size is the binding constraint (<5 MB).

### Model selection

- **Policy:** Default to Gemma 3 (4.3B Q4_K_M) for multi-agent efficiency.
- **Policy:** Use Llama 3.1 8B for reasoning-heavy tasks where quality outweighs throughput.
- **Policy:** Avoid Qwen 2.5 for multi-agent workloads (90% Rust, 77.6% Python; 7-13pp below alternatives).

### Configuration

- **Policy:** Multi-agent baseline: GPU=80, CTX=512-2048, TEMP=0.6-0.8.
- **Policy:** Never transfer single-inference configs to agent or multi-agent workloads.
- **Policy:** Validate every configuration change with a minimum 5-run benchmark.

---

## Economic impact (what changes your spend)

Memory and resource efficiency:

- **Memory:** Rust uses 65-90 MB vs Python's 300-350 MB (67% reduction). Enables 3x concurrent capacity per host.
- **Throughput:** 15.2% higher single-agent tok/s reduces cost per token proportionally.
- **Startup:** 0.2s vs 1.5s (83% faster). Enables rapid scaling and serverless-compatible cold starts.

Infrastructure savings:

- **Dual Ollama at 99.4% efficiency:** 2 instances serve the work of 2 agents with <1% overhead.
- **Python at 86% ceiling:** Requires ~15% more wall time, translating to 15% more compute cost.
- **Instance reduction:** At scale, Rust + dual Ollama requires 2 instances where Python requires 4 for equivalent throughput. 50% infrastructure cost reduction.

Annual savings estimate:

- **Small scale (10K req/month):** ~$1,440/year (memory + throughput savings)
- **Medium scale (100K req/month):** ~$3,040/year (50% instance reduction)
- **Large scale (1M req/month):** ~$7,680/year (compounding throughput + instance savings)
- **Break-even on Rust migration:** 12.7-20 months depending on development overhead ($3-5K estimated)
- **5-year TCO:** 26% lower with Rust + dual Ollama stack

---

## Implementation plan (30-day view)

Days 1-7: reproduce and validate

- Re-run TR112_v2 single-agent benchmarks on your hardware (Rust vs Python, 18 configs each).
- Confirm Rust throughput advantage and consistency characteristics match within 10% of reported values.

Days 8-14: deploy dual Ollama and benchmark multi-agent

- Stand up dual Ollama instances on separate ports.
- Run TR114_v2 multi-agent matrix (baseline-vs-chimera, chimera-homo, chimera-hetero).
- Validate >95% parallel efficiency and <1% contention rate.

Days 15-21: select runtime and model

- Run TR115_v2 runtime comparison (Tokio-default vs smol-1KB minimum) with 30 runs each.
- Run TR116 cross-model comparison (Gemma 3, Llama 3.1, Qwen 2.5) with 10 runs each.
- Confirm Tokio-default consistency and Gemma 3 efficiency leadership.

Days 22-30: enforce policies and monitor

- Ship language, architecture, runtime, and model policies from the operational recommendations above.
- Deploy contention monitoring with <1% alert threshold.
- Document invalidation triggers in change management.
- Set re-run-required gates on hardware, OS, Ollama, model, and toolchain changes.

---

## Risks, limitations, invalidation triggers

Limitations:

- Single hardware baseline (RTX 4080 Laptop). Not portable across GPU classes without re-run.
- Windows 11 only. Linux/macOS may exhibit different async runtime characteristics.
- 2-agent concurrency limit. Scaling to 3+ agents is unmeasured.
- Shadow pricing (estimated $/token), not actual cloud TCO.
- Quality not measured in multi-agent mode. Pair efficiency decisions with quality evaluation.
- All models tested at Q4 quantization. Different quantization levels may shift rankings.

Invalidates guidance:

- Hardware change (different GPU, CPU, or memory tier)
- OS change (Linux, macOS, or major Windows update)
- Ollama version upgrade (inference scheduling may change)
- Model update (new quantization, architecture revision, or fine-tune)
- Rust toolchain major version change (async runtime behavior may shift)
- Agent count change (3+ agents introduces new contention dynamics)

---

## Evidence anchors (audit-ready)

- Rust vs Python single-agent throughput: TR112_v2, 111 runs, 37 configs (`PublishReady/reports/Technical_Report_112_v2.md`)
- Single Ollama multi-agent contention: TR113, 19 configs, 63% contention rate (`PublishReady/reports/Technical_Report_113.md`)
- Dual Ollama multi-agent efficiency: TR114_v2, 135 runs, 27 configs, 99.4% peak (`PublishReady/reports/Technical_Report_114_v2.md`)
- Runtime ranking and consistency: TR115_v2, 150 runs, 5 runtimes (`PublishReady/reports/Technical_Report_115_v2.md`)
- Cross-model multi-agent validation: TR116, 60 runs, 3 models x 2 runtimes (`PublishReady/reports/Technical_Report_116.md`)
- Python efficiency ceiling: TR116, Python never exceeds 86% across all models (`PublishReady/reports/Technical_Report_116.md`)
- Config transfer failure: TR108 vs TR109 optimization inversion (`PublishReady/reports/Technical_Report_108.md`, `PublishReady/reports/Technical_Report_109.md`)

---

## References

- TR108: `PublishReady/reports/Technical_Report_108.md` (Ollama model benchmarking, 158 configs)
- TR109: `PublishReady/reports/Technical_Report_109.md` (Python agent workflow optimization)
- TR110: `PublishReady/reports/Technical_Report_110.md` (Python multi-agent, 150 runs)
- TR111_v2: `PublishReady/reports/Technical_Report_111_v2.md` (Rust single-agent, 57 runs)
- TR112_v2: `PublishReady/reports/Technical_Report_112_v2.md` (Rust vs Python comparison, 111 runs)
- TR113: `PublishReady/reports/Technical_Report_113.md` (Rust multi-agent, single Ollama)
- TR114_v2: `PublishReady/reports/Technical_Report_114_v2.md` (Rust multi-agent, dual Ollama, 135 runs)
- TR115_v2: `PublishReady/reports/Technical_Report_115_v2.md` (Rust runtime deep dive, 150 runs)
- TR116: `PublishReady/reports/Technical_Report_116.md` (Cross-model multi-agent, 60 runs)
