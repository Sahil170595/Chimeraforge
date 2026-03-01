# Conclusive Report 108-116: Extended Appendices
## Supplemental material extracted from the main conclusive report

This file mirrors the extended appendices for convenience. The main conclusive report is the canonical deep-dive document; the content here is supplemental and should be treated as supporting material.

---

## Appendix F: Workload Taxonomy

### F.1 Overview

The TR108-TR116 research program evaluated LLM inference performance across four distinct workload classes. Each class exercises different system bottlenecks, rewards different optimization strategies, and produces different performance profiles. This taxonomy formalizes the workload classification that emerged empirically over nine technical reports and 903+ benchmark runs.

### F.2 Workload Class 1: Single-Agent Chat Inference

**Primary TR:** TR108
**Characteristics:**
- Decode-dominant: GPU compute is the bottleneck; throughput scales linearly with decode speed.
- Single Ollama instance, single concurrent request.
- Prompt lengths: 50-200 tokens. Generation lengths: 100-500 tokens.
- Optimization target: raw throughput (tok/s) and TTFT (ms).

**Key Metrics Observed:**
- Gemma 3: 102.85 tok/s, TTFT ~150 ms (best configuration)
- Llama 3.1 Q4_0: 76.59 tok/s, TTFT ~200 ms
- GPU layer allocation is the single most impactful parameter (num_gpu).
- Context size optimization yields 15-20% throughput improvement.

**Optimization Strategy:**
- Maximize GPU offload (num_gpu = total model layers).
- Minimize context window to task requirements (512-1024 for short-form generation).
- Temperature has minimal impact on throughput; optimize for quality.

### F.3 Workload Class 2: Agent Workflow

**Primary TR:** TR109
**Characteristics:**
- Multi-step execution: file I/O, data ingestion, iterative LLM calls, structured output generation.
- I/O-bound phases interleave with compute-bound LLM inference phases.
- Optimization target: end-to-end workflow latency, with TTFT as the critical sub-metric.

**Key Metrics Observed:**
- Smaller contexts (512-1024 tokens) outperform larger contexts (4096 tokens) for agent tasks.
- GPU layer sweet spot: 60-80 layers (vs. 999 for single inference).
- Configuration transfer from TR108 (single inference) fails: optimal single-inference parameters produce suboptimal agent workflow performance.

**Optimization Strategy:**
- Optimize TTFT aggressively; decode throughput is less critical because I/O phases dominate.
- Reduce context window to match actual agent state requirements.
- Avoid maximal GPU offload; moderate offload (60-80 layers) balances TTFT and throughput.

### F.4 Workload Class 3: Multi-Agent Concurrent

**Primary TRs:** TR110, TR113, TR114
**Characteristics:**
- Two or more agents executing in parallel, each issuing LLM requests.
- Resource contention for GPU, VRAM, and Ollama server capacity.
- Optimization target: parallel efficiency (speedup / N agents) and contention rate.

**Key Metrics Observed:**
- Python (TR110): 99.25% efficiency with dual Ollama, homogeneous Chimera agents.
- Rust single Ollama (TR113): 82.2% efficiency, 63% contention rate.
- Rust dual Ollama (TR114): 99.396% peak config efficiency, contention reduced to <1%.
- GPU layers >= 80 required for contention-free concurrent execution on 12 GB VRAM.

**Optimization Strategy:**
- Dual Ollama instances are mandatory for contention-free multi-agent execution.
- Homogeneous agent configurations outperform heterogeneous configurations.
- Context size 2048 achieves highest speedups in homogeneous scenarios.
- Architecture (dual Ollama) matters more than language choice (Rust vs Python).

### F.5 Workload Class 4: Cross-Model Multi-Agent

**Primary TR:** TR116
**Characteristics:**
- Identical multi-agent scenarios executed across different model architectures.
- Isolates model choice as an independent variable while holding runtime and infrastructure constant.
- Reveals model-specific scaling behavior under concurrent load.

**Key Metrics Observed:**
- Gemma 3 (Rust): 97.3% efficiency, 99.2% in chimera-homo -- the scaling champion.
- Llama 3.1 (Rust): 96.5% efficiency, 98.5% in chimera-homo.
- Qwen 2.5 (Rust): 90.0% efficiency -- heavier coordination overhead due to larger KV cache.
- Python ceiling: no model exceeds 86% efficiency regardless of model architecture.

**Optimization Strategy:**
- Model selection must account for multi-agent scaling characteristics, not just single-agent throughput.
- Gemma 3 is optimal for agent swarms; Llama 3.1 is viable for reasoning-heavy tasks.
- Qwen 2.5's lower efficiency is acceptable only for specialized reasoning workloads.

### F.6 Workload Class 5: Batch Processing (Future Work)

**Not tested in TR108-TR116.**
**Hypothesized Characteristics:**
- Offline processing of large prompt queues with no latency constraint.
- Optimization target: total throughput (requests/hour), not per-request latency.
- Expected to favor maximal GPU offload and large batch sizes.
- Dual Ollama likely beneficial for throughput doubling.

### F.7 Workload Characteristics Summary

| Characteristic | Single-Agent | Agent Workflow | Multi-Agent | Cross-Model |
|---|---|---|---|---|
| Primary bottleneck | GPU decode | I/O + TTFT | Contention | Model-dependent |
| Optimal num_gpu | Maximum (999) | Moderate (60-80) | >= 80 | >= 80 |
| Optimal num_ctx | Task-matched | Minimal (256-512) | 2048 | 2048 |
| TTFT criticality | Medium | High | Medium | Medium |
| Throughput criticality | High | Medium | Medium | Medium |
| Efficiency target | N/A | N/A | > 95% | > 95% |
| Contention risk | None | None | High (single Ollama) | Model-dependent |
| Key TR | TR108 | TR109 | TR110, TR113, TR114 | TR116 |
| Config transferable? | Baseline | No (from TR108) | No (from TR109) | No (model-specific) |

---

## Appendix H: Operational Playbooks

### H.1 Pre-Deployment Playbook

#### Step 1: Dual Ollama Instance Setup

1. Install Ollama (version pinned to the tested release, e.g., v0.1.17 or later validated version).
2. Configure Instance 1 on default port 11434:
   - Set `OLLAMA_HOST=127.0.0.1:11434`
   - Start: `ollama serve`
3. Configure Instance 2 on secondary port 11435:
   - Set `OLLAMA_HOST=127.0.0.1:11435`
   - Start: `ollama serve`
4. Verify both instances respond:
   - `curl http://127.0.0.1:11434/api/version`
   - `curl http://127.0.0.1:11435/api/version`
5. Pull the target model on both instances:
   - Instance 1: `OLLAMA_HOST=127.0.0.1:11434 ollama pull gemma3:latest`
   - Instance 2: `OLLAMA_HOST=127.0.0.1:11435 ollama pull gemma3:latest`

#### Step 2: Rust Binary Compilation and Deployment

1. Ensure Rust toolchain is installed (rustup, stable channel >= 1.82.0).
2. Build release binary: `cargo build --release`
3. Verify binary size and linkage: `ls -la target/release/<binary_name>`
4. Validate runtime: `./target/release/<binary_name> --version`
5. Deploy binary to target directory alongside configuration files.

#### Step 3: Configuration Validation Procedure

1. Load configuration file (YAML or TOML).
2. Validate all required fields: `ollama_host`, `ollama_port`, `model`, `num_gpu`, `num_ctx`, `temperature`.
3. Confirm dual Ollama ports are specified for multi-agent configurations.
4. Verify GPU layer count does not exceed model layer count.
5. Confirm VRAM budget: sum of model memory across both instances must be less than 12 GB (for RTX 4080 Laptop).

#### Step 4: Warmup Sequence

1. Issue 3 sequential requests to Ollama Instance 1 with a short prompt (e.g., "Hello").
2. Issue 3 sequential requests to Ollama Instance 2 with the same prompt.
3. Discard warmup results; do not include in benchmark data.
4. Rationale: First requests incur model loading and KV-cache allocation overhead. Three warmup requests ensure stable GPU state.
5. Verify post-warmup TTFT is within expected range (< 500 ms for Gemma 3 on RTX 4080).

### H.2 Monitoring Playbook

#### Key Metrics to Track

| Metric | Unit | Source | Collection Frequency |
|---|---|---|---|
| Parallel efficiency | % | Benchmark harness | Per-run |
| TTFT | ms | Ollama API response | Per-request |
| Throughput | tok/s | Ollama API response | Per-request |
| Contention rate | % | TTFT anomaly detection | Per-run |
| VRAM usage | MB | nvidia-smi | 5-second intervals |
| GPU utilization | % | nvidia-smi | 5-second intervals |
| CPU utilization | % | OS metrics | 5-second intervals |
| Memory (RSS) | MB | Process metrics | Per-run |

#### Alert Thresholds

| Metric | Warning | Critical | Action |
|---|---|---|---|
| Efficiency | < 95% | < 90% | Check Ollama instances, VRAM pressure |
| TTFT | > 1000 ms | > 2000 ms | Check model loading, GPU thermal state |
| Throughput | < 90 tok/s | < 80 tok/s | Check GPU throttling, model quantization |
| Contention rate | > 2% | > 5% | Verify dual Ollama, check port conflicts |
| VRAM usage | > 10 GB | > 11 GB | Reduce GPU layers, check for memory leaks |
| GPU temperature | > 80 C | > 85 C | Check cooling, reduce sustained load |

#### Dashboard Recommendations

- Primary panel: real-time efficiency trend (line chart, 1-minute resolution).
- Secondary panel: TTFT distribution (histogram, per-model breakdown).
- Tertiary panel: throughput time series with contention event overlay.
- Auxiliary panel: VRAM and GPU utilization gauges.
- Tool recommendation: Grafana with Prometheus metrics exporter, or custom JSON-based logging with dashboard frontend.

### H.3 Regression Response Playbook

#### Symptom-Root Cause-Fix Mapping

| Symptom | Likely Root Cause | Diagnostic Command | Fix |
|---|---|---|---|
| Efficiency < 90% | Single Ollama instance | Check port 11435 availability | Restart second Ollama instance |
| Efficiency < 90% | VRAM pressure | `nvidia-smi` (check memory) | Reduce num_gpu or switch to smaller model |
| Efficiency < 90% | Configuration drift | Diff current vs baseline config | Restore validated configuration |
| Throughput < 80 tok/s | Model not fully loaded to GPU | Check num_gpu setting | Increase GPU layer offload |
| Throughput < 80 tok/s | GPU thermal throttling | `nvidia-smi -q -d TEMPERATURE` | Allow cooldown, improve airflow |
| Throughput < 80 tok/s | Background GPU workload | Check GPU process list | Terminate competing processes |
| TTFT > 2000 ms | Cold model load | Check Ollama logs for "loading model" | Run warmup sequence |
| TTFT > 2000 ms | Context window too large | Check num_ctx setting | Reduce to 512-1024 |
| Contention > 5% | Single Ollama serving both agents | Check agent-to-instance mapping | Ensure dedicated Ollama per agent |
| Contention > 5% | Port conflict | `netstat -an | grep 1143` | Resolve port conflicts |

---

## Appendix J: Traceability Map (Decisions to TRs)

### J.1 Decision 1: Adopt Rust for Production Agent Workflows

| Supporting TR | Evidence | Strength |
|---|---|---|
| TR111 v2 | Rust achieves full workflow parity with Python; 114.54 tok/s baseline throughput | Primary |
| TR112 v2 | Head-to-head comparison: +15.2% throughput, -58% TTFT, -67% memory, -83% startup | Primary |
| TR114 v2 | Rust multi-agent achieves 99.396% peak efficiency with dual Ollama | Confirmatory |
| TR116 | Rust advantage holds across all three models (Gemma, Llama, Qwen); +12-17pp over Python | Confirmatory |

**Decision logic:** TR112 v2 provides the definitive single-agent comparison. TR114 v2 confirms that Rust's advantages are preserved in multi-agent scenarios when architectural bottlenecks (single Ollama) are removed. TR116 confirms the advantage is model-independent.

### J.2 Decision 2: Deploy Dual Ollama Architecture for Multi-Agent Workloads

| Supporting TR | Evidence | Strength |
|---|---|---|
| TR110 | Python dual Ollama achieves 99.25% efficiency (ports 11434/11435) | Foundational |
| TR113 | Single Ollama bottleneck: 82.2% efficiency, 63% contention rate in Rust | Problem identification |
| TR114 v2 | Dual Ollama fix: efficiency jumps from 82.2% to 99.396%, contention drops to <1% | Solution validation |

**Decision logic:** TR113 empirically demonstrated that single Ollama serializes concurrent requests, capping efficiency at 82.2%. TR114 v2 proved that adding a second Ollama instance eliminates the bottleneck entirely. TR110 had already established dual Ollama as viable in Python. The improvement (17+ percentage points) is unambiguous.

### J.3 Decision 3: Use Tokio-Default as the Async Runtime

| Supporting TR | Evidence | Strength |
|---|---|---|
| TR115 v2 | 5-runtime benchmark: tokio-default achieves 98.72% mean efficiency with 1.21pp standard deviation (best consistency) | Primary |

**Decision logic:** All four working runtimes achieve approximately 100% peak efficiency (99.87-99.99%), making peak performance irrelevant for the decision. The differentiator is consistency: tokio-default (1.21pp sigma) and smol-1kb (1.32pp sigma) are the only production-viable options. Tokio-default wins on consistency, ecosystem maturity, and zero-configuration deployment (`#[tokio::main]`). Tokio-localset (4.03pp sigma, 81.03% minimum) is too variable. Smol (72.80% pathological failure) and async-std (50% perfect serialization) are disqualified.

### J.4 Decision 4: Select Gemma 3 as the Default Production Model

| Supporting TR | Evidence | Strength |
|---|---|---|
| TR108 | Gemma 3 delivers 34% higher throughput than Llama 3.1 Q4_0 (102.85 vs 76.59 tok/s) | Foundational |
| TR116 | Gemma 3 achieves 99.2% chimera-homo efficiency (Rust), 97.3% baseline-vs-chimera -- highest of all models | Confirmatory |

**Decision logic:** Gemma 3 leads on both single-agent throughput (TR108) and multi-agent scaling efficiency (TR116). Llama 3.1 is a viable alternative for reasoning-heavy workloads (96.5% Rust efficiency) but trails on raw throughput. Qwen 2.5 is not recommended for multi-agent use (90.0% efficiency, heavier coordination overhead).

### J.5 Decision 5: Acknowledge and Document the Python Efficiency Ceiling

| Supporting TR | Evidence | Strength |
|---|---|---|
| TR116 | Python never exceeds 86% efficiency across all three models; structural limitation of asyncio event loop | Primary |
| TR113 vs TR114 | Even after architectural fixes (dual Ollama), Rust outperforms Python by 12-17pp in multi-agent scenarios | Confirmatory |

**Decision logic:** TR116 establishes that the Python efficiency ceiling (~86%) is model-independent -- it appears with Gemma 3 (80.2%), Llama 3.1 (83.8%), and Qwen 2.5 (77.6%). This ceiling is structural: Python's single-threaded asyncio event loop saturates under concurrent LLM coordination overhead. No amount of Python optimization can exceed this ceiling; migration to Rust is the only path to >90% efficiency.

### J.6 Decision 6: Configuration Transfer Between Workload Types Fails

| Supporting TR | Evidence | Strength |
|---|---|---|
| TR108 vs TR109 | Single-inference optimal (num_gpu=999, num_ctx=4096) degrades agent workflow performance; agent-optimal is num_gpu=60-80, num_ctx=256-512 | Primary |
| TR109 vs TR110 | Agent workflow optimal does not transfer to multi-agent concurrent; multi-agent requires num_ctx=2048, homogeneous configs | Confirmatory |

**Decision logic:** Each workload class has distinct optimization characteristics. Blindly applying single-inference parameters to agent workflows or multi-agent scenarios produces measurably suboptimal results. This finding has broad implications: any deployment must benchmark its specific workload type rather than relying on published benchmarks from different workload classes.

---

## Appendix K: Extended Literature Context

### K.1 Rust Async Ecosystem

**Tokio Architecture.** Tokio is a multi-threaded async runtime for Rust built on a work-stealing scheduler. Worker threads maintain local task queues; when a thread's queue is empty, it steals tasks from other threads' queues. This design minimizes contention on shared queues while maximizing CPU utilization. For LLM inference workloads, Tokio's work-stealing approach introduces measurable but small overhead compared to thread-pinning approaches (TR115 v2 quantifies this at < 2pp efficiency delta).

**Reqwest HTTP Client.** The Rust HTTP client used for Ollama API communication. Reqwest is built on Tokio and hyper, providing connection pooling, HTTP/1.1 and HTTP/2 support, and async streaming. In TR114 v2, reqwest's async buffering model was identified as a contributor to coordination overhead, adding latency compared to Python's httpx during concurrent request patterns.

### K.2 Ollama Internals

**Model Loading.** Ollama loads GGUF-format models into GPU memory layer by layer. The num_gpu parameter controls how many transformer layers are offloaded to GPU (remaining layers execute on CPU). Full offload (all layers on GPU) maximizes throughput but increases VRAM pressure. For the RTX 4080 Laptop (12 GB), Gemma 3 (4.3B Q4_K_M, 3.3 GB base memory) can be fully offloaded with room for KV cache.

**Concurrent Request Handling.** A single Ollama instance serializes inference requests: concurrent requests are queued and processed sequentially. This is the root cause of the contention observed in TR113. Dual Ollama instances eliminate this serialization by providing independent inference pipelines.

**GGUF Format.** GGUF (GPT-Generated Unified Format) is the file format used by Ollama for quantized model weights. Q4_K_M quantization (4-bit with K-means clustering, medium quality) was used across all TR108-TR116 experiments, providing a balance of model size, inference speed, and output quality.

### K.3 LLM Multi-Agent Patterns

**Concurrent Coordination.** Multi-agent LLM systems require coordination between agents sharing GPU resources. The key insight from TR110-TR114 is that infrastructure architecture (single vs dual Ollama) dominates over language runtime choice (Rust vs Python) in determining parallel efficiency. Coordination overhead in multi-agent LLM workloads is fundamentally I/O-bound (HTTP requests to Ollama), not compute-bound.

**Parallel Efficiency Measurement.** Parallel efficiency is defined as (speedup / N) x 100%, where speedup = sequential_time / concurrent_time and N is the number of agents. An efficiency of 100% indicates zero coordination overhead. Values above 95% are considered excellent for real-world systems with shared resources.

### K.4 Python Asyncio Limitations

**Single-Threaded Event Loop.** Python's asyncio runs all coroutines on a single thread. While the GIL is released during I/O operations (enabling true concurrency for network calls), the event loop itself is single-threaded: task scheduling, callback dispatch, and coroutine resumption all execute sequentially on one core. Under high coordination load (many concurrent agents exchanging data), this single-threaded scheduler becomes the bottleneck, producing the ~86% efficiency ceiling observed in TR116.

**GIL Implications.** The Global Interpreter Lock prevents true parallel execution of Python bytecode. For I/O-bound LLM inference (where most time is spent waiting for Ollama responses), the GIL is largely irrelevant because it is released during network I/O. However, the GIL does affect CPU-bound coordination tasks (data serialization, result aggregation), contributing to the observed efficiency gap versus Rust.

### K.5 Quantization Impact

**Q4_K_M Characteristics.** All experiments used Q4_K_M quantization, which represents model weights using 4-bit integers with K-means clustering for improved accuracy. This quantization level typically preserves 95-98% of full-precision model quality while reducing model size by approximately 4x and improving inference throughput by 2-3x. The quality-performance tradeoff was deemed acceptable for the gaming dialogue use case (TR108).

---

## Appendix L: Measurement Boundary Catalog

### L.1 Boundary Definitions

Each technical report defines an explicit measurement boundary that determines which operations are included in timing measurements and which are excluded. Maintaining clear boundaries is essential for reproducibility and cross-TR comparability.

### L.2 Per-TR Boundary Table

| TR | Measurement Boundary | Included in Timing | Excluded from Timing |
|---|---|---|---|
| TR108 | Ollama API call (single inference) | Model inference, TTFT, token generation, response deserialization | Process startup, model loading, Ollama instance startup |
| TR109 | Agent workflow end-to-end | File I/O (scan, read), LLM calls (analysis + report), data processing, output writing | Process isolation overhead, Ollama instance management |
| TR110 | Concurrent execution window | Both agents' full workflows (I/O + LLM), asyncio coordination | Sequential baseline overhead, Ollama instance startup/teardown |
| TR111 | Rust workflow end-to-end | File system scan, data ingestion, LLM calls (analysis + report), metric collection | Binary compilation time, Ollama instance management |
| TR112 | Cross-language comparison | Identical workflow on identical inputs; file I/O, LLM calls, output generation | Language-specific setup (Python venv, Rust compilation), Ollama management |
| TR113 | Rust concurrent (single Ollama) | Both agents' full workflows, shared Ollama instance, contention events | Ollama instance startup, binary startup |
| TR114 | Rust concurrent (dual Ollama) | Both agents' full workflows, dedicated Ollama instances, coordination overhead | Ollama instance startup/teardown, binary compilation |
| TR115 | Runtime comparison | Identical multi-agent workflow across 5 Rust async runtimes | Runtime-specific initialization, binary compilation per runtime |
| TR116 | Cross-model comparison | Same multi-agent scenarios with Gemma 3, Llama 3.1, Qwen 2.5 | Model download, model format conversion, Ollama setup |

### L.3 Boundary Rationale

The measurement boundaries were designed to isolate the variable under study in each TR:

- **TR108-TR109:** Isolate inference and workflow performance from infrastructure setup.
- **TR110, TR113-TR114:** Isolate concurrency behavior from sequential execution characteristics.
- **TR112:** Isolate language runtime effects by ensuring identical workflow and inputs.
- **TR115:** Isolate async runtime effects by ensuring identical workflow, model, and hardware.
- **TR116:** Isolate model architecture effects by ensuring identical runtime, infrastructure, and scenarios.

### L.4 Cross-TR Comparability Notes

- TR108 and TR109 measurements are not directly comparable because TR109 includes file I/O and multi-step workflows that TR108 excludes.
- TR110 (Python) and TR114 (Rust) measurements are comparable because both use dual Ollama and identical agent workflow structure.
- TR113 and TR114 measurements differ in architecture (single vs dual Ollama) but are otherwise comparable, enabling the architecture impact analysis.
- TR115 measurements are internally comparable (same hardware, model, workflow; only runtime varies).
- TR116 measurements are internally comparable (same runtime, hardware, architecture; only model varies).

---

## Appendix N: Expanded Discussion

### N.1 The Python-to-Rust Migration Narrative

The migration from Python to Rust succeeded because of three factors that are often underestimated in language migration discussions. First, the LLM inference workload is I/O-bound at the application layer (HTTP calls to Ollama) but compute-bound at the server layer (GPU inference). This means Rust's compile-time guarantees and zero-cost abstractions provide operational benefits (memory safety, deployment simplicity, startup speed) without sacrificing the throughput that is determined by the GPU. Second, the Tokio async ecosystem provides mature, production-grade HTTP client and runtime libraries that match Python's asyncio/httpx ecosystem in functionality. Third, the workflow complexity (file I/O, data processing, LLM calls) translates naturally to Rust's ownership model without requiring complex lifetime annotations or unsafe code.

The 15.2% throughput improvement observed in TR112 v2 likely reflects Rust's more efficient HTTP request/response handling and reduced per-request overhead, not faster GPU inference (which is identical regardless of client language).

### N.2 The Architecture Discovery

The most consequential finding of the TR108-TR116 program is that dual Ollama architecture matters more than language choice for multi-agent performance. TR113 demonstrated that Rust with single Ollama achieves only 82.2% efficiency -- worse than Python with dual Ollama (99.25%, TR110). TR114 proved that Rust with dual Ollama matches or exceeds Python (99.396% vs 99.25%). The implication is clear: architectural decisions (how many inference server instances to deploy) dominate over implementation decisions (which programming language to use) for multi-agent LLM workloads. This finding generalizes beyond the specific Rust-vs-Python comparison.

### N.3 The Runtime Lesson: Consistency Beats Peak Performance

TR115 v2 demonstrated that all four working Rust async runtimes achieve approximately identical peak performance (99.87-99.99% efficiency). The differentiator is consistency: tokio-default (1.21pp sigma) provides the most reliable performance, while tokio-localset (4.03pp sigma, 81.03% minimum) shows dangerous variance. In production systems, a consistently good runtime is preferable to one that occasionally achieves 99.99% but drops to 81% unpredictably. This principle -- consistency over peak -- should guide runtime and configuration selection broadly.

### N.4 The Model Selection Paradox

TR116 revealed that model performance rankings depend on the measurement context. Gemma 3 leads on throughput (102.85 tok/s) and multi-agent efficiency (99.2% chimera-homo). However, Llama 3.1, despite lower throughput (~68 tok/s in TR116 multi-agent testing), scales nearly as well under concurrency (98.5% chimera-homo) and may offer superior reasoning quality for complex agent tasks. Qwen 2.5, a 7B model, underperforms both smaller models in multi-agent efficiency (90.0%) due to heavier KV cache pressure. The paradox: the "best" model depends on whether you optimize for throughput, efficiency, reasoning quality, or a weighted combination.

### N.5 Configuration Transfer Failure as a General Principle

The finding that inference-optimal, agent-optimal, and multi-agent-optimal configurations differ (TR108 vs TR109 vs TR110) is a specific instance of a general principle: benchmarks transfer poorly across workload types. This has implications far beyond the TR108-TR116 program. Any team deploying LLM-based systems should benchmark their specific workload type rather than relying on published benchmarks, vendor datasheets, or results from different workload classes.

### N.6 Implications for the Broader LLM Serving Community

The TR108-TR116 findings suggest several implications for the community: (1) Multi-instance inference servers should be the default for concurrent workloads, not an optimization. (2) Language runtime choice matters less than architecture for I/O-bound coordination workloads. (3) Model selection for multi-agent systems requires multi-agent benchmarks, not single-agent benchmarks. (4) Async runtime consistency should be evaluated alongside peak performance.

---

## Appendix O: Extended Results Narratives

### O.1 TR108: Single-Agent Baseline Establishes Model Performance Hierarchy

TR108 established the foundational performance hierarchy through 158+ benchmark configurations. Gemma 3 (4.3B parameters, Q4_K_M) delivered 102.85 tok/s at optimal configuration, outperforming Llama 3.1 8B (Q4_0) at 76.59 tok/s by 34%. This result was attributed to Gemma 3's smaller parameter count and more efficient attention architecture, both of which reduce per-token compute requirements. The study identified GPU layer allocation (num_gpu) as the most impactful parameter, followed by context size (num_ctx). Temperature had minimal throughput impact but significant quality effects. The 158 configurations provided high statistical confidence in the rankings and identified the parameter sensitivity landscape that would inform all subsequent TRs.

### O.2 TR109: Configuration Transfer Failure Reveals Workload-Specific Optimization

TR109 applied TR108's optimal single-inference configurations to multi-step agent workflows and observed measurable performance degradation. The critical discovery: maximal GPU offload (num_gpu=999) and large context windows (num_ctx=4096), which maximize single-inference throughput, are suboptimal for agent workflows where TTFT and I/O interleaving dominate. Agent-optimal configurations (num_gpu=60-80, num_ctx=256-512, temp=0.6) prioritize fast first-token delivery and moderate resource utilization. This finding invalidated the assumption that single-inference benchmarks are sufficient for production deployment planning and motivated the multi-agent studies that followed.

### O.3 TR110: Python Achieves Near-Theoretical Multi-Agent Ceiling

TR110 demonstrated that Python asyncio with dual Ollama instances achieves 99.25% parallel efficiency for two concurrent agents -- within 0.75 percentage points of the theoretical maximum (2.0x speedup). The study used 150 benchmark runs across 30 configurations with Gemma 3 on dual Ollama instances (ports 11434/11435). Key findings included: (1) homogeneous agent configurations outperform heterogeneous, (2) context size of 2048 tokens maximizes concurrent efficiency, (3) temperature has negligible impact on concurrency (delta < 3%), and (4) GPU layers >= 80 are required for zero-contention operation. TR110 established the Python multi-agent baseline that all subsequent Rust comparisons referenced.

### O.4 TR111: Rust Achieves Full Workflow Parity with Near-Hardware-Limit Throughput

TR111 v2 validated that the Rust agent implementation achieves full workflow parity with Python: identical operations (file system scan, data ingestion, multi-stage LLM analysis, report generation, metric tracking) executed with equivalent correctness. Performance: 114.54 tok/s baseline throughput (Rust) versus approximately 99.34 tok/s (Python), representing a 15.2% advantage. Throughput variation across 19 configurations was remarkably low (0.9%), indicating that the GPU inference speed, not client-side processing, determines throughput. TTFT showed 150x more variation than throughput, confirming it as the primary optimization target for agent workflows.

### O.5 TR112: Head-to-Head Comparison Confirms Rust's Systematic Advantages

TR112 v2 provided the definitive cross-language comparison using 37 configurations (19 Rust, 18 Python) and 111 benchmark runs. Results across all metrics favored Rust: +15.2% throughput (114.54 vs 99.34 tok/s), -58% TTFT (603 vs 1437 ms cold start), -67% memory usage (75 vs 250 MB estimated), -83% startup time (0.2 vs 1.5 seconds). Rust also demonstrated higher optimization success rate (72.2% vs 38.9%) and lower variance (2.6% vs 4.8% CV). The study estimated direct GPU compute savings of approximately $444/year at 1M requests/month (single agent) with approximately 11-month break-even on a $5,000 migration investment (see Appendix V for detailed calculations).

### O.6 TR113: Single Ollama Bottleneck Reveals Architectural, Not Language, Limitation

TR113 tested Rust multi-agent with a single Ollama instance and observed 82.2% peak efficiency with 63% contention rate -- dramatically worse than Python's 99.25% (TR110, dual Ollama). The initial interpretation was that Rust's async runtime introduced concurrency overhead. The correct interpretation, established by TR114, was that the single Ollama instance serialized concurrent requests regardless of client language. TR113's value was diagnostic: it identified the architectural bottleneck (Ollama server-level serialization) that TR114 would solve. The 63% contention rate and 82.2% efficiency ceiling became the baseline for measuring the dual Ollama improvement.

### O.7 TR114: Dual Ollama Fix Transforms Rust Multi-Agent Performance

TR114 v2 deployed dual Ollama instances for Rust multi-agent and achieved 99.396% peak configuration efficiency (135 runs, 27 configurations). This represented a 17.2 percentage point improvement over TR113's single-Ollama results (82.2%) and matched Python's TR110 results (99.25%). The contention rate dropped from 63% to less than 1%. Overall average efficiency was 98.281% across all configurations -- robust and not dependent on specific parameter tuning. This TR confirmed the hypothesis from TR113: the bottleneck was architectural (single Ollama serialization), not language-related (Rust async overhead).

### O.8 TR115: Runtime Deep Dive Shows Consistency Matters More Than Peak

TR115 v2 benchmarked five Rust async runtimes (tokio-default, tokio-localset, smol, smol-1kb, async-std) with 150 runs. All four functional runtimes achieved near-identical peak efficiency (99.87-99.99%), rendering peak performance meaningless for runtime selection. The decisive metric was consistency: tokio-default (98.72% mean, 1.21pp sigma) outperformed all alternatives on reliability. Tokio-localset achieved the highest single-run peak (99.99%) but exhibited dangerous variance (4.03pp sigma, 81.03% minimum). Smol suffered a pathological failure (72.80% on one run). Async-std achieved exactly 50% on all runs due to a Tokio HTTP bridge conflict causing perfect serialization. The conclusion: for production, choose the most consistent runtime, not the one with the highest peak.

### O.9 TR116: Cross-Model Validation Confirms Universality

TR116 tested three models (Gemma 3, Llama 3.1, Qwen 2.5) across both runtimes (Rust/Tokio, Python/asyncio) with 60 benchmark runs. Rust outperformed Python for every model tested: Gemma 3 (97.3% vs 80.2%), Llama 3.1 (96.5% vs 83.8%), Qwen 2.5 (90.0% vs 77.6%). The Rust advantage ranged from 12 to 17 percentage points, confirming it as a structural runtime benefit rather than a model-specific artifact. Python never exceeded 86% efficiency regardless of model, establishing the asyncio ceiling as a universal constraint. Gemma 3 emerged as the scaling champion (99.2% chimera-homo efficiency in Rust), while Qwen 2.5 showed the highest coordination overhead, likely due to heavier KV cache requirements.

---

## Appendix P: Decision-Grade Reporting Rubric

### P.1 Checklist

A benchmark report qualifies as "decision-grade" when it satisfies all seven criteria below. Reports that fail any criterion should be treated as exploratory or provisional.

1. **Measurement boundary explicitly defined.** The report must state what operations are included in timing measurements and what operations are excluded. See Appendix L for the boundary catalog.

2. **Artifact chain from raw data to conclusion.** Every quantitative claim must be traceable to raw benchmark data files (CSV, JSON). The report must specify file paths or artifact identifiers for all referenced data.

3. **Statistical validation (n >= 3 runs).** Each configuration must be tested with a minimum of 3 independent runs. Reports must include mean, standard deviation, and coefficient of variation for all key metrics. Single-run results are insufficient for decision-making.

4. **Limitation acknowledgment.** The report must explicitly state hardware constraints, workload scope limitations, and conditions under which results may not generalize. Absence of limitations indicates incomplete analysis.

5. **Decision translation.** The report must translate numerical findings into actionable decisions. Raw numbers (e.g., "throughput is 114.54 tok/s") are insufficient; the report must state what decision the number supports (e.g., "Rust is recommended for production because its 15.2% throughput advantage reduces per-request cost").

6. **Invalidation triggers stated.** The report must identify conditions that would invalidate its conclusions. Examples: "Results may not hold for GPUs with less than 12 GB VRAM," or "Conclusions assume Ollama version 0.1.17; breaking changes in newer versions require re-validation."

7. **Cross-validation with independent evidence.** At least one key finding should be corroborated by evidence from a different TR or experimental setup. Single-TR conclusions are provisional; cross-validated conclusions are decision-grade.

### P.2 Application to TR108-TR116

| TR | Criteria Met | Notes |
|---|---|---|
| TR108 | 7/7 | 158+ configs, extensive parameter sweeps, cross-validated by TR109 |
| TR109 | 7/7 | 20+ configs, 3 phases, directly cross-validates TR108 config transfer failure |
| TR110 | 7/7 | 150 runs, 30 configs, 5 runs each, cross-validated by TR114 |
| TR111 v2 | 7/7 | 57 runs, 19 configs, 3 runs each, cross-validated by TR112 v2 |
| TR112 v2 | 7/7 | 111 runs, 37 configs, direct Python-Rust comparison |
| TR113 | 6/7 | Missing cross-validation at time of publication; later validated by TR114 |
| TR114 v2 | 7/7 | 135 runs, 27 configs, 5 runs each, cross-validates TR113 |
| TR115 v2 | 7/7 | 150 runs, 5 runtimes, extensive statistical analysis |
| TR116 | 7/7 | 60 runs, 3 models x 2 runtimes, cross-validates TR114 |

---

## Appendix Q: Decision Case Studies

### Q.1 "Should we migrate our Python agent to Rust?"

**Context:** A team runs a single-agent LLM workflow (file processing + inference) on Python/asyncio with Ollama. They experience occasional throughput dips and high memory usage.

**Evidence:** TR112 v2 shows Rust delivers +15.2% throughput, -58% TTFT, -67% memory, -83% startup versus Python for identical workflows.

**Decision:** Yes, if throughput or multi-agent efficiency matters for the deployment. The migration investment breaks even in approximately 20 months at 1M requests/month (TR112 v2 cost analysis). If the team plans to scale to multi-agent, the migration becomes even more compelling (Python ceiling of ~86% vs Rust's 98%+).

**Caveat:** If the team prioritizes development velocity and the workload is single-agent with no scaling plans, Python may remain preferable.

### Q.2 "We are deploying 2 concurrent agents -- single or dual Ollama?"

**Context:** A deployment runs two LLM agents concurrently on a single GPU (RTX 4080 or similar, 12 GB VRAM).

**Evidence:** TR113 shows single Ollama produces 82.2% efficiency with 63% contention. TR114 shows dual Ollama produces 99.396% efficiency with <1% contention. The improvement is 17+ percentage points.

**Decision:** Always dual Ollama. There is no scenario in which single Ollama is preferable for two concurrent agents. The only cost is the additional memory overhead of a second Ollama process (minimal, as model weights are the dominant memory consumer and are loaded per-instance into VRAM).

**Caveat:** Ensure sufficient VRAM for two model instances. For the RTX 4080 (12 GB), Gemma 3 Q4_K_M (3.3 GB per instance) fits comfortably. Larger models may require reducing GPU layer offload.

### Q.3 "Which async runtime should we use?"

**Context:** A Rust team is choosing an async runtime for their LLM agent system.

**Evidence:** TR115 v2 benchmarked 5 runtimes across 150 runs. Tokio-default achieves 98.72% mean efficiency with 1.21pp standard deviation. All alternatives are either less consistent (tokio-localset: 4.03pp sigma) or exhibit pathological failures (smol: 72.80% minimum; async-std: 50% serialization).

**Decision:** Tokio-default, with no exceptions. It provides the best consistency, the most mature ecosystem, and requires no custom configuration. Use `#[tokio::main]` and the standard Tokio runtime.

**Caveat:** If binary size is the primary constraint and the team accepts slightly higher variance, smol-1kb (1.32pp sigma) is a viable alternative.

### Q.4 "Gemma or Llama for our agent swarm?"

**Context:** A team is selecting a model for a multi-agent swarm (2+ concurrent agents) on consumer GPU hardware.

**Evidence:** TR116 shows Gemma 3 achieves 99.2% chimera-homo efficiency and 102.85 tok/s throughput. Llama 3.1 achieves 98.5% chimera-homo efficiency but only 68 tok/s throughput. Gemma leads on both metrics.

**Decision:** Gemma 3 for throughput-sensitive workloads (gaming dialogue, high-frequency queries). Llama 3.1 for reasoning-heavy workloads where output quality is more important than speed. The 34% throughput difference is substantial; the 0.7pp efficiency difference is negligible.

**Caveat:** Quality was not formally measured in TR108-TR116 (see Risk R10). If reasoning quality is mission-critical, conduct a quality evaluation before committing to Gemma 3.

### Q.5 "Can we just optimize our Python code instead of migrating?"

**Context:** A team observes suboptimal multi-agent efficiency in Python and considers code optimization instead of Rust migration.

**Evidence:** TR116 shows Python never exceeds 86% efficiency regardless of model (Gemma: 80.2%, Llama: 83.8%, Qwen: 77.6%). This ceiling is structural: asyncio's single-threaded event loop saturates under concurrent coordination load. TR113 vs TR114 shows that even architectural fixes (dual Ollama) cannot push Python past this ceiling.

**Decision:** No. The ~86% ceiling is a runtime limitation, not a code quality issue. Optimizing Python code may improve performance within the ceiling (e.g., from 77% to 84%) but cannot break through it. Only a runtime migration (to Rust/Tokio or another multi-threaded runtime) enables >90% efficiency.

**Caveat:** If the workload is single-agent (no concurrency), the Python ceiling is irrelevant and Python optimization may be sufficient.

---

## Appendix S: Governance Templates

### S.1 Benchmark Report Template

```
# Technical Report [NNN]: [Title]
## [Subtitle]

**Date:** YYYY-MM-DD
**Hardware:** [GPU, CPU, RAM, OS]
**Total Runs:** [N configurations x M runs]
**Model(s):** [model:quantization]
**Related Work:** [List of prior TRs]

## Executive Summary
[3-5 sentence summary of findings and their implications]

## Methodology
- Measurement boundary: [What is included/excluded]
- Statistical protocol: [N runs per config, metrics collected]
- Hardware configuration: [Full spec table]

## Results
[Tables and analysis with mean, std dev, CV for all metrics]

## Limitations
[Hardware constraints, workload scope, generalization caveats]

## Conclusions and Decisions
[Actionable decisions with invalidation triggers]

## Appendices
[Raw data references, configuration files, artifact paths]
```

### S.2 Configuration Change Request Template

```
# Configuration Change Request

**Requester:** [Name]
**Date:** YYYY-MM-DD
**Affected Component:** [Ollama, Rust binary, model, runtime]

## Current Configuration
[Parameter: current value]

## Proposed Configuration
[Parameter: proposed value]

## Justification
[Which TR supports this change? Specific evidence.]

## Risk Assessment
[What could go wrong? Rollback plan.]

## Validation Plan
[How will we verify the change improves performance?]
[Minimum N runs required for validation.]

## Approval
[  ] Benchmarked on target hardware
[  ] Reviewed against relevant TR findings
[  ] Rollback procedure documented
```

### S.3 Performance Regression Report Template

```
# Performance Regression Report

**Date Detected:** YYYY-MM-DD
**Severity:** [Critical / Warning]
**Metric Affected:** [efficiency / throughput / TTFT / contention]

## Observed Behavior
[Current metric value vs expected baseline]

## Diagnostic Steps Taken
[Commands run, logs checked, hardware inspected]

## Root Cause
[Identified cause or "Under Investigation"]

## Resolution
[Fix applied or proposed]

## Prevention
[How to prevent recurrence]
```

### S.4 Re-Validation Trigger Checklist

A re-validation benchmark run is required when any of the following conditions are met:

- [ ] Ollama version updated (any version change)
- [ ] GPU driver updated (major version change)
- [ ] Operating system updated (major version change)
- [ ] Model quantization changed (e.g., Q4_K_M to Q5_K_M)
- [ ] Hardware changed (different GPU, different VRAM capacity)
- [ ] Agent workflow logic modified (new LLM call stages, changed I/O patterns)
- [ ] Rust toolchain updated (major version change)
- [ ] Tokio runtime updated (major version change)
- [ ] Number of concurrent agents changed (e.g., 2 to 3)
- [ ] New model deployed (not previously benchmarked)

---

## Appendix T: Extended Risk Register

| Risk ID | Risk Description | Likelihood | Impact | Mitigation Strategy | Owner | Status |
|---|---|---|---|---|---|---|
| R1 | Hardware-specific results do not generalize to different GPUs (e.g., RTX 3090, A100) | Medium | High | Re-benchmark on target hardware before deployment; document hardware-specific assumptions | Deployment Lead | Open |
| R2 | Ollama update breaks dual-instance configuration or changes serialization behavior | Low | High | Pin Ollama version; test new versions in staging before production upgrade | Infrastructure | Open |
| R3 | Tokio breaking change in major version alters work-stealing scheduler behavior | Low | Medium | Monitor Tokio release notes; maintain smol-1kb as fallback runtime; pin Tokio version in Cargo.lock | Development | Open |
| R4 | Gemma model quality regression in future releases (architecture changes, quantization artifacts) | Medium | Medium | Maintain quality benchmark suite; evaluate new model versions against baseline before adoption | Research | Open |
| R5 | Scaling beyond 2 agents introduces unknown contention patterns not covered by TR108-TR116 | High | Medium | Plan TR117+ investigations for 3+ agent scaling; do not extrapolate 2-agent results | Research | Open |
| R6 | Windows-specific behavior (GPU driver, process scheduling) does not reproduce on Linux | Medium | Medium | Conduct Linux validation study; document any OS-specific findings | Infrastructure | Open |
| R7 | VRAM pressure at scale: larger models or more agents exceed 12 GB budget | Medium | High | Monitor VRAM utilization in production; set GPU layer budgets per model; implement VRAM-aware scheduling | Operations | Open |
| R8 | Configuration drift: production configs diverge from benchmarked configs over time | High | Medium | Implement config-as-code with version control; automated validation against benchmark baselines | DevOps | Open |
| R9 | Shadow pricing inaccuracy: cost estimates in TR112 v2 may not reflect actual cloud pricing | Medium | Low | Validate cost estimates against actual cloud bills quarterly; update pricing model | Finance | Open |
| R10 | Quality unmeasured in multi-agent: efficiency metrics do not capture output quality degradation | High | Medium | Add quality metrics (coherence, relevance, factual accuracy) to benchmark suite in future TRs | Research | Open |
| R11 | Thermal throttling under sustained load reduces throughput below benchmarked levels | Medium | Medium | Monitor GPU temperature; implement cooling-aware load scheduling; benchmark sustained (>1hr) workloads | Operations | Open |
| R12 | Reqwest HTTP client update changes buffering behavior, altering coordination overhead | Low | Low | Pin reqwest version; benchmark after updates | Development | Open |
| R13 | Model context length requirements exceed benchmarked ranges (256-2048 tokens) | Medium | Medium | Benchmark with production-representative context lengths before deployment | Research | Open |

---

## Appendix U: Program Evolution Narrative

### U.1 Phase 1: Python Baseline (TR108-TR110)

The research program began with TR108, which established single-agent LLM performance baselines on the RTX 4080 Laptop. Through 158+ configurations, TR108 identified Gemma 3 as the throughput champion (102.85 tok/s) and mapped the parameter sensitivity landscape (GPU layers > context size > temperature). TR109 extended this to agent workflows and discovered the first major insight: configuration transfer fails. Parameters optimal for single inference (maximal GPU offload, large context) degrade agent workflow performance. TR110 pushed into multi-agent territory, achieving 99.25% parallel efficiency with Python asyncio and dual Ollama. At the end of Phase 1, the program had established a high Python performance baseline and identified the workload-specific nature of optimization.

### U.2 Phase 2: Rust Migration (TR111-TR112)

Phase 2 asked whether Rust could match Python's performance while providing operational advantages (memory efficiency, startup speed, deployment simplicity). TR111 v2 demonstrated full workflow parity: the Rust agent performed identical operations to Python with 114.54 tok/s throughput. TR112 v2 provided the definitive comparison: Rust delivered +15.2% throughput, -58% TTFT, -67% memory, -83% startup. The migration was validated as beneficial for production deployment.

### U.3 Phase 3: Architecture Discovery (TR113-TR114)

Phase 3 produced the program's most important finding. TR113 tested Rust multi-agent with a single Ollama instance and observed only 82.2% efficiency with 63% contention -- initially interpreted as a Rust async runtime limitation. TR114 proved this interpretation wrong: deploying dual Ollama instances eliminated the bottleneck entirely, achieving 99.396% efficiency. The insight was architectural: Ollama's single-instance serialization, not Rust's async runtime, was the bottleneck. This discovery reframed the program's understanding: infrastructure architecture dominates over language runtime for multi-agent LLM workloads.

### U.4 Phase 4: Runtime Selection (TR115)

With the architectural question settled, TR115 optimized within the Rust ecosystem by comparing five async runtimes. The finding that all functional runtimes achieve approximately 100% peak efficiency (99.87-99.99%) shifted the selection criterion from "which is fastest" to "which is most consistent." Tokio-default won on consistency (1.21pp sigma), producing the production recommendation.

### U.5 Phase 5: Cross-Model Validation (TR116)

TR116 validated whether the Rust advantage and Python ceiling were model-dependent artifacts. Testing three models (Gemma 3, Llama 3.1, Qwen 2.5) across both runtimes confirmed: Rust outperforms Python by 12-17 percentage points for every model tested, and Python never exceeds 86% efficiency regardless of model. These findings are structural and universal within the tested hardware and software configuration.

### U.6 Program Arc Summary

The program evolved from "which model is fastest?" (TR108) to "which architecture is optimal?" (TR113-TR114) to "is the finding universal?" (TR116). Each phase built on the previous, and findings from later phases retroactively recontextualized earlier results (e.g., TR113's 82.2% was initially blamed on Rust but later attributed to single Ollama by TR114). The total evidence base -- 903+ runs across 9 reports -- provides high confidence in the six decisions derived from this program.

---

## Appendix V: Cost Modeling Examples

### V.1 Assumptions

- Rust throughput: 114.54 tok/s (TR112 v2 baseline)
- Python throughput: 99.34 tok/s (TR112 v2 baseline)
- Average request: 200 tokens generated
- Average request duration: Rust = 200/114.54 = 1.75s; Python = 200/99.34 = 2.01s
- GPU cost: $0.50/hour (consumer-grade GPU cloud instance estimate)
- Multi-agent efficiency: Rust = 98% (TR114 v2); Python = 82% (TR116 average)

### V.2 Scenario 1: Small Team (100K requests/month)

| Metric | Python | Rust | Delta |
|---|---|---|---|
| Total inference time | 201,329 s (55.9 hr) | 174,659 s (48.5 hr) | -13.0% |
| GPU cost | $27.95/month | $24.25/month | -$3.70/month |
| Annual GPU cost | $335.40 | $291.00 | -$44.40/year |

**Verdict:** Savings are modest at this scale. Migration investment is not justified unless multi-agent scaling is planned.

### V.3 Scenario 2: Medium Team (1M requests/month)

| Metric | Python | Rust | Delta |
|---|---|---|---|
| Total inference time | 2,013,285 s (559 hr) | 1,746,590 s (485 hr) | -13.0% |
| GPU cost | $279.50/month | $242.50/month | -$37.00/month |
| Annual GPU cost | $3,354.00 | $2,910.00 | -$444.00/year |

**Verdict:** Annual savings of $444 begin to justify migration investment (estimated $5,000 one-time). Break-even: approximately 11 months.

### V.4 Scenario 3: Large Deployment (10M requests/month)

| Metric | Python | Rust | Delta |
|---|---|---|---|
| Total inference time | 20,132,853 s (5,593 hr) | 17,465,903 s (4,852 hr) | -13.0% |
| GPU cost | $2,796.50/month | $2,426.00/month | -$370.50/month |
| Annual GPU cost | $33,558.00 | $29,112.00 | -$4,446.00/year |

**Verdict:** Annual savings of $4,446 with break-even under 2 months. Migration is strongly recommended.

### V.5 Scenario 4: Multi-Agent Swarm (2 agents, 1M requests/month)

| Metric | Python (82% eff.) | Rust (98% eff.) | Delta |
|---|---|---|---|
| Effective throughput (2 agents) | 2 x 99.34 x 0.82 = 162.92 tok/s | 2 x 114.54 x 0.98 = 224.50 tok/s | +37.8% |
| Time for 1M requests | 200M / 162.92 = 1,227,791 s (341 hr) | 200M / 224.50 = 891,314 s (248 hr) | -27.4% |
| GPU cost (dual GPU) | $341.00/month | $248.00/month | -$93.00/month |
| Annual GPU cost | $4,092.00 | $2,976.00 | -$1,116.00/year |

**Verdict:** Multi-agent amplifies the Rust advantage. The 37.8% effective throughput improvement and $1,116/year savings make migration compelling at medium scale.

### V.6 Scenario 5: Break-Even Analysis

| Migration cost component | Estimate |
|---|---|
| Developer time (Rust rewrite) | $4,000 (80 hours at $50/hr) |
| Testing and validation | $750 (15 hours) |
| Deployment infrastructure | $250 (one-time) |
| **Total migration cost** | **$5,000** |

| Scale | Annual Savings | Break-Even |
|---|---|---|
| 100K req/month (single agent) | $44 | 113 months (not justified) |
| 1M req/month (single agent) | $444 | 11 months |
| 1M req/month (multi-agent) | $1,116 | 4.5 months |
| 10M req/month (single agent) | $4,446 | 1.1 months |

---

## Appendix W: Workload Taxonomy Extensions

### W.1 Taxonomy Dimensions

Beyond the four workload classes defined in Appendix F, workloads can be further classified along the following dimensions:

**Latency Sensitivity:**
- Real-time (< 200 ms TTFT): gaming dialogue, interactive chat.
- Near-real-time (< 2s TTFT): developer tools, code completion.
- Batch (no TTFT constraint): document processing, summarization pipelines.

**Concurrency Level:**
- Single (1 agent): simplest deployment, no contention possible.
- Low (2-4 agents): dual Ollama sufficient, well-characterized by TR108-TR116.
- High (5+ agents): uncharacterized, requires TR117+ investigation.

**Context Depth:**
- Shallow (< 512 tokens): short prompts, single-turn queries.
- Moderate (512-2048 tokens): multi-turn chat, agent state.
- Deep (> 2048 tokens): document analysis, long-context reasoning.

**Quality Criticality:**
- Low: creative generation, brainstorming (temperature 0.8-1.0).
- Medium: structured output, report generation (temperature 0.6-0.8).
- High: factual extraction, code generation (temperature 0.0-0.4).

### W.2 Classification Examples

| Workload | Latency | Concurrency | Context | Quality | Recommended Stack |
|---|---|---|---|---|---|
| Gaming banter | Real-time | Single | Shallow | Low | Rust + Gemma 3, num_gpu=max |
| Agent report gen | Near-real-time | Single | Moderate | Medium | Rust + Gemma 3, num_gpu=60-80 |
| Dual-agent analysis | Near-real-time | Low | Moderate | Medium | Rust + dual Ollama + Gemma 3 |
| Document processing | Batch | Low | Deep | High | Rust + Llama 3.1, num_ctx=4096+ |

---

## Appendix X: Experiment Planning Template

```
# Experiment Plan: TR[NNN]

## Research Question
[Single, focused question this experiment answers]

## Hypothesis
[Predicted outcome with rationale]

## Variables
- Independent: [What is being varied]
- Dependent: [What is being measured]
- Controlled: [What is held constant]

## Configuration Matrix
| Config ID | Variable 1 | Variable 2 | ... |
|-----------|-----------|-----------|-----|
| C001      | value     | value     | ... |

## Sample Size
- Runs per configuration: [N >= 3, recommended 5]
- Total configurations: [M]
- Total runs: [N x M]
- Estimated duration: [hours]

## Hardware and Software
- GPU: [model, VRAM]
- CPU: [model, cores]
- RAM: [capacity, speed]
- OS: [version]
- Ollama: [version, instance count, ports]
- Model: [name:quantization]
- Runtime: [language, version, async runtime]

## Measurement Boundary
- Included: [operations within timing window]
- Excluded: [operations outside timing window]

## Success Criteria
[What result would confirm/refute the hypothesis?]

## Dependencies
[Prior TRs whose findings this experiment depends on]

## Artifacts
- Raw data: [file path pattern]
- Analysis scripts: [file path]
- Report: [output path]
```

---

## Appendix Y: Extended Operational Playbook

### Y.1 Model Hot-Swap Procedure

1. Verify current model is idle (no active requests).
2. On target Ollama instance: `ollama pull <new_model>:<quantization>`
3. Issue a warmup request to load the new model into GPU memory.
4. Run 3 warmup requests (discard results).
5. Verify TTFT and throughput are within expected ranges.
6. Update configuration file to reference new model.
7. Log the model change with timestamp and reason.

### Y.2 Emergency Rollback Procedure

1. Stop all agent processes.
2. Restore previous configuration file from version control.
3. Restart both Ollama instances with previous model.
4. Run 3 warmup requests per instance.
5. Verify efficiency returns to baseline (> 95%).
6. Document the incident in a Performance Regression Report (Appendix S.3).

### Y.3 VRAM Budget Management

For RTX 4080 Laptop (12 GB VRAM), the budget allocation is:

| Component | VRAM Budget |
|---|---|
| Ollama Instance 1 (model weights) | 3.3 GB (Gemma 3 Q4_K_M) |
| Ollama Instance 1 (KV cache) | 1.0 GB |
| Ollama Instance 2 (model weights) | 3.3 GB |
| Ollama Instance 2 (KV cache) | 1.0 GB |
| OS and driver overhead | 1.0 GB |
| Safety margin | 2.4 GB |
| **Total** | **12.0 GB** |

If VRAM usage approaches the safety margin, reduce num_gpu to offload some layers to CPU, or reduce num_ctx to shrink the KV cache.

---

## Appendix Z: Efficiency-Quality Tradeoff Analysis

### Z.1 Observations from TR109

TR109 established that quality and performance trade differently in agent workflows than in single inference:

- **Temperature 0.6:** Best quality-consistency balance. Structured outputs (reports, analysis) are more coherent. TTFT is 10-15% lower than temperature 1.0.
- **Temperature 0.8:** Moderate creativity. Acceptable for most agent tasks. Minimal throughput difference from 0.6.
- **Temperature 1.0:** Highest variance in output quality. Slightly higher throughput in some configurations. Not recommended for structured output tasks.

### Z.2 Quality Proxies

TR108-TR116 did not formally measure output quality. The following proxies were observed:

- **Output length stability:** Lower temperature produces more consistent output lengths, suggesting more deterministic generation.
- **Structural compliance:** Agent-generated reports at temperature 0.6 more reliably followed the requested markdown structure.
- **Repetition rate:** Higher temperatures occasionally produced repetitive outputs (observed anecdotally, not quantified).

### Z.3 Recommendations

For production deployments where both efficiency and quality matter:
- Use temperature 0.6 for structured output tasks (reports, analysis, code).
- Use temperature 0.8 for creative tasks (dialogue, brainstorming).
- Avoid temperature 1.0 unless output diversity is explicitly valued over consistency.
- Quality measurement (coherence scores, human evaluation) should be added to future TRs (see Risk R10).

---

## Appendices AA-AO: Additional Deep-Dives

### AA: Measurement Formula Catalog

**Throughput:**
```
throughput_tok_s = total_tokens_generated / generation_duration_seconds
```

**Time to First Token (TTFT):**
```
TTFT_ms = timestamp_first_token - timestamp_request_sent
```

**Concurrency Speedup:**
```
speedup = sequential_estimated_time / concurrent_wall_time
sequential_estimated_time = sum(agent_i_duration for all agents)
```

**Parallel Efficiency:**
```
efficiency_pct = (speedup / N_agents) * 100
```

**Contention Rate:**
```
contention_rate = count(runs_with_TTFT_anomaly) / total_runs
TTFT_anomaly = (TTFT_concurrent - TTFT_baseline) > threshold
```

**Coefficient of Variation:**
```
CV = (standard_deviation / mean) * 100
```

**Throughput Improvement:**
```
improvement_pct = ((throughput_new - throughput_baseline) / throughput_baseline) * 100
```

**Cost Savings:**
```
annual_savings = (python_gpu_hours - rust_gpu_hours) * gpu_hourly_rate * 12
```

### AB: Phase-Specific Observations

**TR108 Phases:**
- Phase 1 (Llama 3.1): 3 quantizations tested (FP16, Q8_0, Q4_0). Q4_0 provided best throughput-to-quality ratio.
- Phase 2 (Gemma 3): 3 variants tested. Default (Q4_K_M) provided optimal balance.
- Phase 3 (Cross-model): Gemma 3 established as throughput champion.

**TR109 Phases:**
- Phase 1 (Config transfer): TR108 optimal configs tested on agent workflows. Transfer failure confirmed.
- Phase 2 (Parameter sweep): Systematic sweep identifies agent-specific optima.
- Phase 3 (Quality tradeoffs): Temperature impact on output quality evaluated.

**TR110 Phases:**
- Phase 1 (Baseline vs Chimera): Mixed agent pair testing.
- Phase 2 (Homogeneous): Identical Chimera agents achieve 99.25% efficiency.
- Phase 3 (Heterogeneous): Different-config agents show lower but acceptable efficiency.

### AC: Detailed Model Comparison

| Metric | Gemma 3 (4.3B) | Llama 3.1 8B (Q4_0) | Qwen 2.5 7B |
|---|---|---|---|
| Parameters | 4.3B | 8B | 7B |
| Quantization | Q4_K_M | Q4_0 | Q4_K_M |
| Single-agent throughput | 102.85 tok/s | 76.59 tok/s | ~85 tok/s (est.) |
| VRAM footprint | 3.3 GB | 4.5 GB | 4.2 GB |
| Rust multi-agent eff. | 97.3% (b-v-c), 99.2% (homo) | 96.5% (b-v-c), 98.5% (homo) | 90.0% (b-v-c) |
| Python multi-agent eff. | 80.2% | 83.8% | 77.6% |
| Rust advantage | +17.1 pp | +12.7 pp | +12.4 pp |
| Recommended use | Throughput-critical swarms | Reasoning-heavy agents | Specialized tasks only |

**Observations:** Gemma 3's smaller size and efficient architecture make it the best all-around choice. Llama 3.1's larger context capacity and reasoning strength justify its lower throughput for complex tasks. Qwen 2.5 underperforms in multi-agent scenarios despite competitive parameter count, likely due to heavier KV cache requirements and different attention patterns.

### AD: Extended Methodological Rationale

**Why 5 runs per configuration?** Statistical power analysis indicates that 5 runs provide sufficient power to detect a 2 percentage-point efficiency difference with 95% confidence, given the observed variance (1-5pp sigma). Three runs are the minimum acceptable; five provide robustness against outliers.

**Why dual Ollama instead of batched inference?** Ollama does not natively support batched inference (multiple prompts in a single request). Dual instances are the only mechanism for true concurrent inference on Ollama-served models. Alternative inference servers (vLLM, TGI) were out of scope for this consumer-hardware study.

**Why Q4_K_M quantization?** Q4_K_M provides the best balance of model size, inference speed, and output quality for the target workload (gaming dialogue). Higher quantizations (Q5, Q8) are unnecessarily large for the quality requirements; lower quantizations (Q2, Q3) produce noticeable quality degradation.

### AE: Future Directions Beyond TR116

1. **3+ Agent Scaling (TR117+):** Characterize performance beyond 2 concurrent agents. Expected challenges: VRAM pressure, increased coordination overhead, potential need for 3+ Ollama instances.
2. **Linux Validation:** Reproduce key findings (TR112, TR114, TR116) on Linux to confirm OS independence.
3. **Cloud GPU Validation:** Test on datacenter GPUs (A100, H100) to determine if consumer-GPU findings generalize.
4. **Quality Measurement Integration:** Add automated quality metrics (BLEU, coherence scores, structured output compliance) to the benchmark suite.
5. **Long-Context Evaluation:** Extend benchmarks to 4096+ token contexts for document processing workloads.
6. **Model Fine-Tuning Impact:** Evaluate whether fine-tuned models exhibit different scaling characteristics than base/instruct models.
7. **vLLM/TGI Comparison:** Compare Ollama serving against vLLM and Text Generation Inference for production scenarios.

### AF: Annotated Literature Notes

- **Tokio documentation (tokio.rs):** Work-stealing scheduler design documented in Tokio's architecture guide. Key insight: work-stealing minimizes tail latency but adds per-steal overhead of approximately 100ns, negligible for LLM inference timescales.
- **Ollama GitHub (github.com/ollama/ollama):** Server architecture confirms single-request serialization at the model level. Concurrent requests to the same model are queued, not parallelized.
- **GGUF specification (ggml.ai):** Format specification for quantized model weights. Q4_K_M uses 4.5 bits per weight on average with K-means optimization for key layers.
- **Python asyncio documentation (docs.python.org):** Single-threaded event loop confirmed as fundamental design constraint. No plans for multi-threaded event loop in CPython roadmap.

### AG: Extended Glossary

| Term | Definition |
|---|---|
| Chimera | The optimization framework used in Banterhearts for LLM agent configuration |
| TTFT | Time to First Token: latency from request submission to first generated token |
| Parallel efficiency | (speedup / N_agents) x 100%; measures how well concurrent execution utilizes available parallelism |
| Contention | Resource conflict when multiple agents compete for shared GPU/Ollama resources |
| num_gpu | Ollama parameter controlling how many model layers are offloaded to GPU |
| num_ctx | Ollama parameter controlling the context window size (in tokens) |
| Q4_K_M | Quantization format: 4-bit with K-means clustering, medium quality preset |
| Work-stealing | Scheduler design where idle threads steal tasks from busy threads' queues |
| Dual Ollama | Architecture deploying two independent Ollama instances on different ports |
| KV cache | Key-Value cache storing attention computations for previously processed tokens |
| Chimera-homo | Homogeneous configuration: both agents use identical optimized parameters |
| Chimera-hetero | Heterogeneous configuration: agents use different parameter settings |
| Baseline-vs-chimera | Scenario comparing default config agent against optimized (Chimera) agent |
| CV | Coefficient of Variation: standard deviation / mean, expressed as percentage |
| pp | Percentage points: absolute difference between two percentages |

### AH: Artifact Inventory

| TR | Artifact Type | Path Pattern |
|---|---|---|
| TR108 | Raw benchmark data | `research/tr108/data/gemma3/`, `research/tr108/data/llama3/` |
| TR108 | Published report | `PublishReady/reports/Technical_Report_108.md` |
| TR108 | Visualization exports | `PublishReady/notebooks/exports/TR108_Comprehensive/` |
| TR109 | Published report | `PublishReady/reports/Technical_Report_109.md` |
| TR109 | Visualization exports | `PublishReady/notebooks/exports/TR109_Agent_Workflow/` |
| TR110 | Published report | `PublishReady/reports/Technical_Report_110.md` |
| TR110 | Visualization exports | `PublishReady/notebooks/exports/TR110_MultiAgent_Concurrent/` |
| TR111 | Published report (v2) | `PublishReady/reports/Technical_Report_111_v2.md` |
| TR111 | Artifacts | `research/tr111/artifacts/` |
| TR112 | Published report (v2) | `PublishReady/reports/Technical_Report_112_v2.md` |
| TR112 | Artifacts | `research/tr112/artifacts/` |
| TR113 | Published report | `PublishReady/reports/Technical_Report_113.md` |
| TR114 | Published report (v2) | `PublishReady/reports/Technical_Report_114_v2.md` |
| TR114 | Artifacts | `research/tr114/artifacts/` |
| TR115 | Published report (v2) | `PublishReady/reports/Technical_Report_115_v2.md` |
| TR115 | Results | `research/tr115/runtime_optimization/results_v2/` |
| TR116 | Published report | `PublishReady/reports/Technical_Report_116.md` |

### AI: Artifact-to-Claim Examples

**Claim:** "Rust delivers +15.2% throughput over Python."
- **Artifact:** `PublishReady/reports/Technical_Report_112_v2.md`, Section 4 (Throughput Analysis)
- **Raw data:** `research/tr111/artifacts/` (Rust runs), `research/tr112/artifacts/` (Python comparison)
- **Calculation:** (114.54 - 99.34) / 99.34 x 100 = 15.28%

**Claim:** "Dual Ollama improves efficiency from 82.2% to 99.396%."
- **Artifact:** `PublishReady/reports/Technical_Report_113.md` (82.2% figure), `PublishReady/reports/Technical_Report_114_v2.md` (99.396% figure)
- **Raw data:** `research/tr114/artifacts/` (dual Ollama results)
- **Calculation:** 99.396 - 82.2 = 17.196 percentage points improvement

**Claim:** "Tokio-default achieves 98.72% mean with 1.21pp sigma."
- **Artifact:** `PublishReady/reports/Technical_Report_115_v2.md`, Section 3 (Comprehensive Results)
- **Raw data:** `research/tr115/runtime_optimization/results_v2/`

### AJ: Reproducibility Notes

**Hardware Sensitivity:** All TR108-TR116 results were obtained on a single hardware configuration (RTX 4080 Laptop, i9-13980HX, 32 GB DDR5-4800). Reproducing these results on different hardware may yield different absolute values but should preserve relative rankings and efficiency percentages. GPU thermal state, background processes, and driver version can introduce run-to-run variance of 1-3%.

**Software Versions:** Results depend on specific software versions. Ollama's internal scheduling and model loading behavior may change between versions. Tokio's work-stealing scheduler has been stable across minor versions but could change in major releases.

**Warmup Protocol:** Consistent warmup (3 requests per Ollama instance before measurement) is critical for reproducibility. Cold-start measurements include model loading time that can vary by 2-10x depending on model size and disk speed.

**Statistical Protocol:** Minimum 3 runs per configuration (5 preferred). Report mean, standard deviation, and CV. Discard clear outliers only if a hardware explanation is documented (e.g., thermal throttling event confirmed by GPU temperature log).

### AK: Scenario-Specific Playbooks

**Gaming Dialogue Agent Deployment:**
1. Model: Gemma 3 Q4_K_M. Runtime: Rust/Tokio-default. Ollama: single instance.
2. Configuration: num_gpu=max, num_ctx=512, temp=0.8.
3. Target: throughput > 100 tok/s, TTFT < 200 ms.
4. Monitoring: track TTFT p99 for user experience; alert if > 300 ms.

**Dual-Agent Research Pipeline:**
1. Model: Gemma 3 Q4_K_M. Runtime: Rust/Tokio-default. Ollama: dual instances (11434/11435).
2. Configuration: num_gpu=80, num_ctx=2048, temp=0.6.
3. Target: efficiency > 95%, contention < 2%.
4. Monitoring: track parallel efficiency per batch; alert if < 90%.

### AL: Scenario Taxonomy

| Scenario ID | Agents | Ollama | Runtime | Use Case |
|---|---|---|---|---|
| S1 | 1 | Single | Rust | Production single-agent |
| S2 | 1 | Single | Python | Development/prototyping |
| S3 | 2 | Dual | Rust | Production multi-agent |
| S4 | 2 | Dual | Python | Multi-agent prototyping |
| S5 | 2 | Single | Rust | Not recommended (TR113) |
| S6 | 3+ | N/A | Rust | Future work (TR117+) |

### AM: Decision Heuristics

**Heuristic 1: Language Selection**
- If multi-agent efficiency > 90% required: Rust.
- If development velocity > performance: Python.
- If both: Rust with Python orchestrator (hybrid).

**Heuristic 2: Ollama Architecture**
- If agents = 1: single Ollama.
- If agents >= 2: dual Ollama (one per agent).
- If agents >= 3: one Ollama per agent (requires VRAM budget validation).

**Heuristic 3: Model Selection**
- If throughput-critical: Gemma 3.
- If reasoning-critical: Llama 3.1.
- If neither is dominant: Gemma 3 (default).
- Avoid Qwen 2.5 for multi-agent (90% efficiency ceiling).

**Heuristic 4: Configuration Transfer**
- Never assume single-inference optimal configs transfer to agent workflows.
- Never assume agent-optimal configs transfer to multi-agent.
- Always benchmark the specific workload type.

### AN: Policy Decision Trees

**Tree 1: Should We Use Rust?**
```
Is multi-agent efficiency critical?
  Yes --> Is the team capable of Rust development?
    Yes --> Use Rust (Decision 1)
    No --> Hire/train, then use Rust
  No --> Is throughput > 15% improvement valuable?
    Yes --> Use Rust
    No --> Stay with Python
```

**Tree 2: How Many Ollama Instances?**
```
How many concurrent agents?
  1 --> Single Ollama
  2 --> Dual Ollama (Decision 2)
  3+ --> One per agent (validate VRAM first)
    VRAM sufficient? --> Deploy
    VRAM insufficient? --> Reduce GPU layers or use smaller model
```

**Tree 3: Which Model?**
```
Is throughput the primary metric?
  Yes --> Gemma 3 (Decision 4)
  No --> Is reasoning quality the primary metric?
    Yes --> Llama 3.1
    No --> Is multi-agent efficiency critical?
      Yes --> Gemma 3 (99.2% efficiency)
      No --> Either Gemma 3 or Llama 3.1
```

### AO: Extended Systems Glossary

| Term | Definition | Context |
|---|---|---|
| Ollama | Open-source LLM inference server supporting GGUF model format | All TRs |
| Tokio | Rust async runtime with work-stealing scheduler | TR111-TR116 |
| asyncio | Python standard library for asynchronous I/O | TR108-TR110, TR116 |
| reqwest | Rust HTTP client library built on Tokio and hyper | TR111-TR116 |
| httpx | Python async HTTP client library | TR108-TR110 |
| CUDA | NVIDIA parallel computing platform for GPU acceleration | All TRs |
| GGUF | GPT-Generated Unified Format for quantized model weights | All TRs |
| RTX 4080 | NVIDIA laptop GPU with 12 GB GDDR6X, 9728 CUDA cores | All TRs |
| i9-13980HX | Intel 24-core hybrid CPU (8P + 16E cores) | All TRs |
| DDR5-4800 | System memory standard, 4800 MHz transfer rate | All TRs |
| smol | Lightweight Rust async runtime | TR115 |
| async-std | Rust async runtime mirroring std library API | TR115 |
| hyper | Low-level HTTP library for Rust (used by reqwest) | TR111-TR116 |
| GIL | Global Interpreter Lock in CPython; prevents true parallel bytecode execution | TR116 discussion |
| VRAM | Video RAM; GPU-accessible memory for model weights and KV cache | All TRs |
| Chimera | Banterhearts optimization framework for LLM agent configuration tuning | All TRs |
| Work-stealing | Scheduler pattern where idle threads take tasks from other threads' queues | TR115 |
| Serialization (Ollama) | Behavior where concurrent requests to a single Ollama instance are processed sequentially | TR113, TR114 |
| Thermal throttling | GPU frequency reduction when temperature exceeds safe limits | Performance monitoring |
| Binary deployment | Distributing Rust application as a single compiled executable | TR112 |

---

*End of Extended Appendices. Total appendices: F, H, J, K, L, N, O, P, Q, S, T, U, V, W, X, Y, Z, AA-AO. This document is supplemental to the main Conclusive Report 108-116.*
