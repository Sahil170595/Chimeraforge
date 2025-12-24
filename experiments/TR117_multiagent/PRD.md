# Technical Report 117: Root Cause Analysis of Multi-Agent Efficiency Anomalies
## "The Why Behind The Numbers"

**Status:** Draft  
**Owner:** Research Team  
**Date:** 2025-11-26  
**Parent:** [TR116](../TR116/README.md)

---

## 1. Executive Summary & Objectives

**Context:**  
TR116 established *what* happens: Rust dominates (99% vs 86%), Qwen underperforms (90% vs 99%), and Python rankings flip (slower models perform better).  
TR117 is dedicated to explaining **why** these phenomena occur with forensic precision. We move from observation to causality.

**Primary Objectives:**
1.  **Decode the "Python Ceiling" (86%):** Prove exactly which operation saturates the `asyncio` event loop (JSON parsing? Buffer management? HTTP overhead?).
2.  **Solve the "Qwen Mystery" (90%):** Isolate the bottleneck causing Qwen 2.5's 10pp efficiency deficit vs Gemma 3. (Memory bandwidth? Tokenizer CPU cost? Attention patterns?).
3.  **Explain the "Ranking Flip":** Prove the "Tortoise & Hare" hypothesis—that slower models (Llama) yield higher system efficiency in Python by reducing backpressure on the event loop.

---

## 2. Research Pathways & Experiments

### Pathway 1: The "Python MRI" (Event Loop Instrumentation)
**Goal:** Visualize the internal state of the Python `asyncio` loop during high-throughput generation.

**Hypothesis:**  
The single-threaded event loop is blocked by synchronous CPU-bound operations (likely `json.loads` or `httpx` buffer concatenation) when processing high-velocity streams (100+ tok/s), causing "Loop Lag" that delays the *next* HTTP request.

**Instrumentation Plan:**
1.  **Loop Lag Monitor:**
    - Inject a background task: `while True: start=now; await sleep(0.001); lag = (now - start) - 0.001`
    - Log `loop_lag_ms` (p50, p99, max) every 100ms.
    - **Trigger:** Flag any lag > 10ms as a "Stall Event".
2.  **Operation Profiling:**
    - Decorate critical paths (`_read_stream`, `_parse_json`) with high-res timers.
    - Log per-chunk: `bytes_per_chunk`, `inter_chunk_gap_ms`, `json_parse_duration_ms`.
3.  **Flamegraph Analysis:**
    - Run `py-spy record --native --rate 100` during a benchmark to capture C-extension (JSON/SSL) overhead.

**Experiment 1.1: The Ceiling Stress Test**
- **Config:** Python + Gemma 3 (Fastest Model) + Chimera Homo.
- **Run:** 2 runs of 500 tokens.
- **Success Criteria:** Correlation (r > 0.8) between `loop_lag_ms` spikes and efficiency drops.

**Experiment 1.2: Buffer Size A/B**
- **Config:** Same as 1.1.
- **Variable:** `httpx` read buffer (Default vs 64KB).
- **Goal:** Determine if larger buffers reduce loop overhead (transport vs parsing).

---

### Pathway 2: Hardware Forensics (The Qwen Detective)
**Goal:** Determine if Qwen's inefficiency is a Hardware (Memory/Compute) or Software (Tokenizer) bottleneck.

**Hypothesis A (Hardware):** Qwen's 7B parameter size + architecture saturates Memory Bandwidth or PCIe lanes during dual-agent inference, unlike Gemma (4B).  
**Hypothesis B (Software):** Qwen's BPE tokenizer is significantly more expensive than Gemma's SentencePiece, consuming CPU cycles needed for GPU submission.

**Instrumentation Plan:**
1.  **High-Freq Hardware Logging:**
    - Use `nvidia-smi --query-gpu=timestamp,power.draw,utilization.gpu,memory.used,pcie.rx,pcie.tx --format=csv -lms 100`.
    - Capture: Power (W), SM (%), Mem (MB), PCIe RX/TX (MB/s).
2.  **Tokenizer Micro-Benchmark:**
    - Create `bench_tokenizer.py` / `bench_tokenizer.rs`.
    - Task: Tokenize 10MB of identical text (CPU-only).
    - Metric: Tokens/sec, Latency.
    - **Threshold:** 2–3x slowdown for Qwen vs Gemma flags CPU bottleneck.

**Experiment 2.1: The Saturation Sweep**
- **Config:** Rust + Qwen 2.5 vs Rust + Gemma 3.
- **Run:** 1 run each, dual-agent.
- **Analysis:** Overlay `mem_usage` and `pwr_usage` graphs. Look for "redlining" (100% util) on Qwen that is absent on Gemma.

**Experiment 2.2: The Tokenizer Race**
- **Run:** Tokenize "The Great Gatsby" (or similar corpus) with Qwen vs Gemma tokenizers.
- **Success Criteria:** If Qwen is >2x slower, CPU bottleneck is confirmed.

---

### Pathway 3: Flow Dynamics (The Tortoise & Hare)
**Goal:** Prove that "Slower is Faster" in Python.

**Hypothesis:**  
Python's efficiency *increases* as model speed *decreases* because the event loop has more "breathing room" to process overheads between chunks.

**Experiment 3.1: Artificial Throttling**
- **Config:** Python + Gemma 3 (normally ~100 tok/s).
- **Modification:** Implement a "Token Bucket" throttler in the agent to cap speed at:
    - 100 tok/s (Baseline)
    - 60 tok/s (Llama speed)
- **Prediction:** System Efficiency (%) will **rise** as Token Limit **falls**.
- **Success Criteria:** Higher efficiency at 60 tok/s than 100 tok/s. (Expand to 40/80 only if trend is unclear).

---

## 3. Implementation Plan

### 3.1 New Tools & Scripts
| Tool | Path | Purpose |
|------|------|---------|
| `profiler_agent.py` | `experiments/TR117_multiagent/scripts/` | Instrumented Python agent with Loop Lag Monitor and chunk metrics. |
| `bench_tokenizer.py` / `bench_tokenizer.rs` | `experiments/TR117_multiagent/scripts/` | Tokenizer throughput bench (CPU-only). |
| `dmon_wrapper.py` | `experiments/TR117_multiagent/scripts/` | Wrapper to sync `nvidia-smi` query with benchmark start/stop. |
| `throttled_agent.py` | `experiments/TR117_multiagent/scripts/` | Token-bucket throttling for Experiment 3.1. |

### 3.2 Execution Schedule
1.  **Day 1:** Build Instrumentation (Python MRI + Tokenizer Bench).
2.  **Day 2:** Run Exp 1.1 (Python Ceiling) & Exp 2.2 (Tokenizer).
3.  **Day 3:** Run Exp 2.1 (Hardware) & Exp 3.1 (Throttling).
4.  **Day 4:** Analysis & Report Writing.

---

## 4. Success Metrics & Deliverables

**Deliverables:**
1.  **TR117 Report:** "The Root Cause Analysis".
2.  **Forensic Artifacts:**
    - `loop_lag.csv`: Timestamp, Lag(ms), Chunks/sec.
    - `chunk_metrics.csv`: Bytes, Gap(ms), ParseTime(ms).
    - `gpu_metrics.csv`: 100ms resolution power/mem/pcie logs.
    - `tokenizer_bench.txt`: Comparative throughput/latency.
    - `flamegraph.svg`: py-spy visualization of Python agent.
3.  **Optimized Python Runtime?** (Stretch goal: Can we fix the ceiling based on findings? e.g., `uvloop` or thread-offloading JSON).

**Go/No-Go for Publication:**
- Must definitively identify the bottleneck for Python (Ceiling).
- Must definitively identify the bottleneck for Qwen (Inefficiency).
- Must empirically prove the Ranking Flip mechanism.

---

**Approved By:** ____________________  
**Date:** ____________________
