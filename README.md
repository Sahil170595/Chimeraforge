# Chimeraforge

**Benchmarking hub for answering one question:** *How do we ship the fastest, most reliable LLM agents?*


This repository contains everything behind Technical Reports TR108 through TR123 — source code, benchmark harnesses, datasets, logs, and publish-ready technical reports. Every performance claim is backed by reproducible benchmarks, every number traces to raw data, and every finding is documented with full methodology.

---

## What This Repository Is About

Chimeraforge is the benchmark-only breakout from the Banterhearts program. It
contains every asset required to measure agent performance (Python and Rust),
run the TR-series test plans, and publish the technical reports that feed the
production decision process. Production APIs, orchestration services, and UX
assets stayed behind in the Banterhearts monolith so this repository can stay
lean, reproducible, and laser-focused on measurement.

When building AI agents that use Large Language Models (LLMs), you face a fundamental question: **Which programming language should you use?** Python offers rapid development and a rich ecosystem. Rust offers performance and memory efficiency. But what are the *real-world* differences when running production workloads?

**Chimeraforge answers this question with data, not opinions.**

Through **2000+ benchmark runs** across Technical Reports TR108–TR123 — including single-agent performance, multi-agent concurrency, optimization strategies, runtime choices, backend comparisons, cost analysis, and scaling studies — we've systematically compared Python and Rust implementations of LLM agents. We've tested inference backends (ONNX Runtime, TensorRT), quantified cost/energy economics, and root-caused performance anomalies. Every finding is reproducible, every claim is defensible, and every number comes from real benchmarks on real hardware.

---

## Why Chimeraforge Exists

### For Decision Makers (CTOs, Engineering Leads, Product Managers)

**The Problem:** Choosing between Python and Rust for LLM agents is often a gut-feel decision. "Rust is faster" or "Python is easier" are common refrains, but what does "faster" actually mean? How much faster? Under what conditions? What are the trade-offs?

**The Solution:** This repository provides **quantified, reproducible answers** to these questions. Every performance claim includes:
- The exact hardware and software configuration used
- The methodology for measurement
- Raw data you can inspect and verify
- Statistical analysis showing confidence levels

**The Value:** Make informed decisions based on data, not assumptions. Understand when Rust's performance gains justify its development overhead. Know when Python's velocity is the right trade-off.

### For Engineers

**The Problem:** You need to optimize LLM agent performance, but configuration space is vast. GPU layer allocation, context window size, temperature settings, runtime choices — each affects performance differently. What's optimal for single-agent might not work for multi-agent. What works in Python might not translate to Rust.

**The Solution:** This repository provides:
- **Proven optimal configurations** for different scenarios
- **Reproducible benchmark harnesses** you can run yourself
- **Analysis tools** for understanding your own results
- **Source code** showing exactly how optimizations are implemented

**The Value:** Skip the trial-and-error phase. Start with configurations that are known to work, then customize based on your specific needs.

### For Researchers

**The Problem:** LLM performance research often lacks reproducibility. Papers cite numbers without providing code. Benchmarks use different hardware, different models, different methodologies. Comparing results across studies is difficult.

**The Solution:** This repository provides:
- **Complete methodology documentation** for every experiment
- **Raw data** in structured formats (CSV, JSON)
- **Reproducible code** that runs the exact same benchmarks
- **Statistical analysis** with confidence intervals and variance measures

**The Value:** Build on solid foundations. Reproduce our results, extend our analysis, or use our methodology for your own research.

---

## Quick Takeaways: What We Discovered

All findings below are verified across 2000+ benchmark runs documented in Technical Reports TR108 through TR123. Every number is reproducible and traceable to raw data.

### Single-Agent Performance: Rust vs Python

| Metric | What It Means | Python | Rust | Winner | Why It Matters |
|--------|---------------|--------|------|--------|----------------|
| **Throughput** | How fast the agent generates text (tokens per second) | 99.34 tok/s | 114.54 tok/s | 🏆 Rust (+15.2%) | Higher throughput = more work done per second. For high-volume systems, 15% faster means 15% more capacity or 15% lower costs. |
| **TTFT (Time to First Token)** | How long until the agent starts responding (milliseconds) | 1,437 ms | 603 ms | 🏆 Rust (-58%) | Lower latency = better user experience. Users perceive 58% faster response time as significantly more responsive. |
| **Memory Usage** | How much RAM the agent consumes | ~250 MB | ~75 MB | 🏆 Rust (-67%) | Less memory = more agents per server, lower infrastructure costs, better resource utilization. |
| **Startup Time** | How long until the agent is ready to work | 1.5 seconds | 0.2 seconds | 🏆 Rust (-83%) | Faster startup = better for serverless, containers, and auto-scaling scenarios. |
| **Consistency (CV)** | How much performance varies between runs (lower is better) | 4.8% | 2.6% | 🏆 Rust (-46%) | More consistent = more predictable = easier to plan capacity and set SLAs. |

**Source:** Technical Report 112_v2 (111 benchmark runs, 37 configurations)

**Bottom Line:** For single-agent workloads, Rust is faster, uses less memory, starts faster, and is more consistent. The performance advantage is substantial and consistent across all metrics.

### Multi-Agent Performance: Concurrent Execution

When running multiple agents simultaneously, the question becomes: **Can we achieve near-perfect parallelism, or does coordination overhead eat into the gains?**

| Scenario | What It Means | Python Result | Rust Result | Winner | Why It Matters |
|----------|---------------|---------------|-------------|--------|----------------|
| **Peak Efficiency** | Best-case parallel efficiency (how close to 2x speedup with 2 agents) | 99.25% | 99.396% | 🏆 Rust (+0.15pp) | Near-perfect parallelism means you can double capacity with <1% overhead. Both languages achieve this, but Rust edges ahead. |
| **Mean Efficiency** | Average efficiency across all configurations | 95.8% | 98.281% | 🏆 Rust (+2.48pp) | Higher mean = more reliable performance across different workloads. Rust's advantage is more pronounced in average scenarios. |
| **Contention Rate** | How often agents compete for resources (lower is better) | 10-15% | 0.74% | 🏆 Rust (20x better) | Lower contention = more predictable performance, fewer slowdowns, better resource utilization. |

**Critical Requirement:** Both languages require **dual Ollama instances** (separate LLM servers on different ports) to achieve these results. Using a single Ollama instance caps Rust at 82.2% efficiency due to server-level serialization.

**Sources:** 
- Python: Technical Report 110 (150 benchmark runs, 30 configurations)
- Rust: Technical Report 114_v2 (135 benchmark runs, 27 configurations)

**Bottom Line:** For multi-agent workloads, both languages can achieve near-perfect parallelism, but Rust maintains a slight edge in consistency and contention handling.

### Optimization Success Rates

Not all configuration changes improve performance. Some make it worse. The question is: **How often do optimizations actually help?**

| Language | Success Rate | What It Means |
|----------|--------------|---------------|
| **Rust** | 72.2% of configs beat baseline | When you try a new configuration, there's a 72% chance it will improve performance. This makes optimization more predictable and reliable. |
| **Python** | 38.9% of configs beat baseline | When you try a new configuration, there's only a 39% chance it will help. More trial-and-error required, but when it works, gains can be larger. |

**Sources:** Technical Report 109 (Python) and Technical Report 111_v2 (Rust)

**Bottom Line:** Rust's optimization is more reliable (higher success rate), but Python occasionally achieves larger peak improvements when optimization works. Rust is better for predictable, incremental gains. Python is better for exploratory optimization where you're willing to try many configurations.

### Runtime Choice (Rust Only)

Rust supports multiple async runtimes (Tokio, async-std, smol). **Which one should you use for production?**

| Runtime | Peak Efficiency | Mean Efficiency | Consistency (σ) | Recommendation |
|---------|----------------|-----------------|-----------------|----------------|
| **Tokio-default** | 99.89% | 98.72% | 1.21pp | 🏆 **Recommended for production** - Best consistency, reliable performance |
| **Smol-1KB** | 99.94% | 98.61% | 1.32pp | ✅ **Alternative** - Slightly smaller binary, nearly as consistent |
| **Tokio-localset** | 99.99% | 97.95% | 4.03pp | ⚠️ **Avoid** - Highest peak but too variable (unpredictable) |
| **Smol** | 99.87% | 97.72% | 4.87pp | ❌ **Avoid** - Pathological failures (drops to 72.8% in some cases) |
| **Async-std** | 50.00% | 50.00% | N/A | ❌ **Unusable** - Perfect serialization (no parallelism) due to ecosystem conflicts |

**Source:** Technical Report 115_v2 (150 benchmark runs, 5 runtimes, 6 configurations each)

**Bottom Line:** Use **Tokio-default** for production. It's the most consistent and reliable. All working runtimes achieve ~100% peak efficiency, so consistency matters more than peak performance.

### Cross-Model Benchmarks (TR116)

**Question:** Does model choice (Gemma, Llama, Qwen) impact multi-agent coordination efficiency?

| Model | Rust Efficiency | Python Efficiency | Verdict |
|-------|----------------|-------------------|---------|
| **Gemma 3** | **99.2%** | 84.9% | 🏆 **Best Scaling** |
| **Llama 3.1** | 98.5% | 85.8% | ✅ Excellent |
| **Qwen 2.5** | 90.0% | 77.6% | ⚠️ Throughput Imbalance |

**Key Findings:**
1. **Rust Dominates:** Rust is **+12-17pp more efficient** than Python across ALL models.
2. **Gemma 3 is King:** Achieves near-perfect 99.2% efficiency in Rust.
3. **Qwen Issues:** Throughput imbalance (+12 tok/s delta) hurts efficiency in both languages.
4. **Python Ceiling:** Python never exceeds 86% efficiency, regardless of model.

### Backend & Infrastructure Studies (TR117-TR121)

**Inference Backend Performance (TR117):**
- **Best Mean Latency:** GPU-compile (389ms) - but reveals "compile paradox" (wins mean, loses median)
- **Best Median Latency:** Plain GPU (323ms) - more consistent
- **Python Efficiency Ceiling:** 86% maximum due to event loop lag (16ms spikes)
- **Scale:** 3,017 inference runs across multiple backends

**Specialized Runtime Performance (TR118_v2.2):**
- **Best Prefill:** TensorRT-fp16 (2.48ms, -87% vs baseline)
- **Best Generate:** ONNX Runtime-CPU (43.3ms, -73% vs baseline)
- **Degraded Rate:** 25% of runs with explicit reasons documented
- **Key Insight:** Specialized runtimes offer substantial gains but require careful optimization

**Cost & Energy Economics (TR119):**
- **Best Cost Efficiency:** onnxruntime-gpu ($0.1279/1M tokens on-demand)
- **Spot Pricing:** 69.8% savings vs on-demand
- **Energy Efficiency:** 503M tokens/kWh
- **Carbon Impact:** ~1.0 gCO2e per 1M tokens

**Root Cause Analysis (TR120):**
- **Compile Paradox Explained:** TR117 compile label was misattributed; shape stability is the critical factor
- **Key Insight:** Shape stability matters more than compilation for consistent performance
- **Production Impact:** Padding/bucketing strategies can collapse compiled tail to sub-millisecond

**Model Scaling (TR121v1):**
- **Scale Range:** 5M to 20B parameters
- **Pipeline Established:** Consistent phase definitions (prefill vs decode)
- **Two-Family Study:** HuggingFace local models (5M-124M) + Ollama models (270M-20B)

---

## Research Journey: Technical Reports TR108-TR123

Our research progressed systematically, with each report building on previous findings and answering specific questions. We've conducted **2000+ benchmark runs** across **16 technical reports** (TR108-TR123, with TR122 and TR123 planned), covering single-agent performance, multi-agent concurrency, runtime optimization, backend comparisons, cost analysis, and scaling studies.

### TR108: Single-Inference Optimization
**Question:** What's the best configuration for a single LLM request?  
**Answer:** GPU=80 layers, Context=512 tokens, Temperature=0.8  
**Why It Matters:** Established the baseline for all future comparisons. Single-inference optimization is different from agent optimization.  
**Scale:** 150+ benchmark runs  
**Key Insight:** Optimal settings for simple requests don't necessarily work for complex agent workflows.

### TR109: Python Agent Workflow Optimization
**Question:** Do agent workflows need different settings than single requests?  
**Answer:** Yes! Agents work better with smaller context windows (512-1024 vs 2048) and have lower optimization success rates (39% vs higher for single-inference).  
**Why It Matters:** You can't just copy single-inference settings to agents. Agent workflows have different characteristics.  
**Scale:** 54 benchmark runs (18 configurations × 3 runs)  
**Key Insight:** Agent tasks require distinct optimization strategies. What works for one-shot requests doesn't work for multi-step workflows.

### TR110: Python Multi-Agent Concurrent Execution
**Question:** Can we run multiple Python agents at the same time efficiently?  
**Answer:** Yes! With dual Ollama instances, Python achieves 99.25% peak efficiency (nearly perfect parallelism).  
**Why It Matters:** Proves that multi-agent systems can nearly double capacity with minimal overhead. Critical for scaling.  
**Scale:** 150 benchmark runs, 30 configurations  
**Key Insight:** Dual Ollama architecture is essential. Single Ollama instance creates a bottleneck that prevents true concurrency.

### TR111_v2: Rust Single-Agent Performance
**Question:** How fast can a Rust agent go?  
**Answer:** 114.54 tokens/second baseline, which is 15.2% faster than Python's 99.34 tok/s.  
**Why It Matters:** First comprehensive Rust agent benchmark with full workflow parity (not just micro-benchmarks).  
**Scale:** 57 benchmark runs, 19 configurations  
**Key Insight:** Rust's performance advantage is real and substantial. The 15% throughput gain is consistent and reproducible.

### TR112_v2: Rust vs Python Single-Agent Comparison
**Question:** What are the real-world differences between Rust and Python for single agents?  
**Answer:** Rust is faster (15.2%), uses less memory (67% less), starts faster (83% faster), and is more consistent (46% better).  
**Why It Matters:** Comprehensive apples-to-apples comparison with identical workflows. Provides definitive data for decision-making.  
**Scale:** 111 benchmark runs, 37 configurations (19 Rust + 18 Python)  
**Key Insight:** Rust's advantages are consistent across all metrics. The performance gap is real and significant.

### TR113: Rust Multi-Agent (Single Ollama)
**Question:** What happens if we run Rust multi-agent with one Ollama instance?  
**Answer:** Efficiency caps at 82.2% because both agents share one inference queue, creating serialization.  
**Why It Matters:** Identified the architectural bottleneck. Proved that dual Ollama is necessary, not optional.  
**Scale:** 19 configurations (single-run exploratory sweep)  
**Key Insight:** Server-level serialization is the limiting factor, not Rust's async runtime.

### TR114_v2: Rust Multi-Agent (Dual Ollama)
**Question:** Does dual Ollama fix the bottleneck and enable true Rust concurrency?  
**Answer:** Yes! Rust achieves 98.281% mean efficiency and 99.396% peak efficiency, exceeding Python's 95.8% mean and 99.25% peak.  
**Why It Matters:** Validates that Rust can achieve near-perfect parallelism and even exceed Python in multi-agent scenarios.  
**Scale:** 135 benchmark runs, 27 configurations  
**Key Insight:** With proper architecture (dual Ollama), Rust's single-agent advantage translates to multi-agent superiority.

### TR115_v2: Rust Runtime Optimization
**Question:** Which Rust async runtime is best for multi-agent workloads?  
**Answer:** Tokio-default is recommended (98.72% mean, 1.21pp consistency). All working runtimes achieve ~100% peak, so consistency matters more than peak.  
**Why It Matters:** Provides production guidance. Peak performance is similar across runtimes, but consistency varies dramatically.  
**Scale:** 150 benchmark runs, 5 runtimes, 6 configurations each  
**Key Insight:** For production, choose based on consistency, not peak performance. Tokio-default is the most reliable.

### TR116: Cross-Model Multi-Agent Benchmarks
**Question:** Does model choice (Gemma, Llama, Qwen) impact multi-agent coordination efficiency?  
**Answer:** Yes! Gemma 3 achieves 99.2% efficiency in Rust (best scaling), while Python never exceeds 86% regardless of model.  
**Why It Matters:** Model choice affects scaling characteristics. Rust's advantages hold across all models, but some models scale better than others.  
**Scale:** 60+ multi-agent runs across 3 models  
**Key Insight:** Rust + Gemma 3 is the optimal combination for high-concurrency agent swarms.

### TR117: Cross-Backend Inference Benchmark & Multi-Agent Root Cause
**Question:** Which inference backend is fastest, and why does Python have an 86% efficiency ceiling?  
**Answer:** GPU-compile wins on mean latency (389ms), but plain GPU wins on median (323ms) - revealing the "compile paradox". Python's 86% ceiling is caused by event loop lag (16ms spikes).  
**Why It Matters:** Backend choice matters for latency, and Python's structural limitations prevent >86% efficiency in multi-agent scenarios.  
**Scale:** 3,017 inference runs + multi-agent root cause analysis  
**Key Insight:** Transformers-gpu-compile for best mean latency, but Python's event loop is the bottleneck preventing higher efficiency.

### TR118_v2.2: ONNX Runtime + TensorRT Deep Dive
**Question:** Can specialized runtimes (ONNX, TensorRT) beat PyTorch for inference?  
**Answer:** TensorRT-fp16 achieves best prefill latency (2.48ms, -87% vs baseline), but requires careful optimization.  
**Why It Matters:** Specialized runtimes can provide significant latency improvements for production workloads.  
**Scale:** Comprehensive ONNX/TensorRT optimization study  
**Key Insight:** TensorRT offers substantial gains but requires infrastructure investment.

### TR119: Cost & Energy Analysis
**Question:** What are the cost and energy implications of different backends?  
**Answer:** onnxruntime-gpu provides best cost efficiency ($0.1279/1M tokens on-demand).  
**Why It Matters:** Cost and energy efficiency are critical for production deployment at scale.  
**Scale:** Comprehensive cost/energy economics analysis  
**Key Insight:** Backend choice significantly impacts operational costs.

### TR120: The "Compile Paradox" Root-Cause Audit
**Question:** Why does GPU-compile win on mean but lose on median?  
**Answer:** TR117 compile label was misattributed; shape stability is the critical factor, not compilation itself.  
**Why It Matters:** Understanding the true cause of performance differences enables better optimization strategies.  
**Scale:** Root-cause analysis of compile paradox  
**Key Insight:** Shape stability matters more than compilation for consistent performance.

### TR121v1: Model Scaling Study
**Question:** How does performance scale from 5M to 20B parameters?  
**Answer:** Scaling pipeline established, demonstrating performance characteristics across model sizes.  
**Why It Matters:** Understanding scaling behavior is essential for choosing appropriate model sizes.  
**Scale:** Model scaling study from 5M to 20B parameters  
**Key Insight:** Performance characteristics vary significantly with model size.

---

## Understanding the Metrics

### Throughput (Tokens per Second)
**What it is:** How many tokens the agent generates per second. A token is roughly 0.75 words.  
**Why it matters:** Higher throughput = more work done per second = better capacity utilization = lower costs.  
**Real-world impact:** 15% faster throughput means you can handle 15% more requests with the same hardware, or use 15% less hardware for the same workload.

### TTFT (Time to First Token)
**What it is:** How long from when you send a request until the agent starts generating a response.  
**Why it matters:** Users perceive latency, not throughput. 58% faster TTFT feels significantly more responsive.  
**Real-world impact:** Faster TTFT = better user experience = higher user satisfaction = better product metrics.

### Memory Usage
**What it is:** How much RAM the agent process consumes.  
**Why it matters:** Less memory = more agents per server = better resource utilization = lower infrastructure costs.  
**Real-world impact:** 67% less memory means you can run 3x more Rust agents than Python agents on the same hardware.

### Parallel Efficiency
**What it is:** For multi-agent systems, how close you get to perfect parallelism. 100% = perfect (2 agents = 2x speedup), 50% = no benefit (2 agents = 1x speedup).  
**Why it matters:** High efficiency means you can scale horizontally with minimal overhead. Low efficiency means adding agents doesn't help much.  
**Real-world impact:** 99% efficiency means doubling your agent count nearly doubles your capacity with <1% overhead. This is critical for scaling.

### Contention Rate
**What it is:** How often agents compete for the same resources (GPU, memory, network), causing slowdowns.  
**Why it matters:** Lower contention = more predictable performance = easier capacity planning = better SLAs.  
**Real-world impact:** 0.74% contention means agents rarely interfere with each other. 15% contention means frequent slowdowns and unpredictable performance.

### Coefficient of Variation (CV)
**What it is:** A measure of consistency. Lower CV = more consistent performance.  
**Why it matters:** Consistent performance = predictable capacity = easier planning = better user experience.  
**Real-world impact:** 2.6% CV means performance is very predictable. 4.8% CV means more variation, making capacity planning harder.

---

## Who Should Read This Repository

### For CTOs and Engineering Leaders

**What you'll learn:**
- When Rust's performance gains justify its development overhead
- When Python's velocity is the right trade-off
- Infrastructure cost implications of language choice
- Scaling characteristics of different architectures

**How to use this repo:**
1. Read the "Quick Takeaways" section above for executive summary
2. Review the "Report Guide" section for high-level findings
3. Check Technical Report 112_v2 for business impact analysis (includes cost calculations)
4. Use the findings to inform architecture decisions

**Key decision framework:**
- **Choose Rust if:** Performance, memory efficiency, and consistency are critical. You're building high-throughput systems where every millisecond matters. You have Rust expertise or are willing to invest in it.
- **Choose Python if:** Development velocity, ecosystem, and team familiarity are priorities. You need to iterate quickly. You have a Python-heavy team.

### For Engineers and Developers

**What you'll learn:**
- Optimal configurations for different scenarios
- How to reproduce our benchmarks
- Implementation patterns for high-performance agents
- Optimization strategies that actually work

**How to use this repo:**
1. Follow `docs/quick_start.md` to run your first benchmark
2. Review `docs/benchmarking.md` for comprehensive methodology
3. Check `docs/rust_vs_python.md` for detailed comparison tables
4. Use `scripts/` for automation and analysis
5. Study source code in `src/` to understand implementations

**Key takeaways:**
- Start with proven configurations, then customize
- Dual Ollama is essential for multi-agent (not optional)
- Rust: Use Tokio-default runtime
- Python: Use asyncio with dual Ollama instances
- Optimization success rates differ by language (Rust more reliable)

### For Researchers and Academics

**What you'll learn:**
- Reproducible methodology for LLM agent benchmarking
- Statistical analysis techniques for performance evaluation
- How to structure experiments for valid comparisons
- Raw data formats and analysis tools

**How to use this repo:**
1. Review `docs/methodology.md` for experimental design
2. Study Technical Reports for analysis techniques
3. Examine raw data in `benchmarks/` and `outputs/`
4. Use our code as a foundation for your own research
5. Check `docs/statistical_analysis.md` for analysis methods

**Key contributions:**
- Full reproducibility: code, data, and methodology all available
- Statistical rigor: confidence intervals, variance measures, multiple runs
- Process isolation: cold-start testing to avoid warm-cache bias
- Comprehensive coverage: 2000+ benchmark runs across Technical Reports TR108–TR123 (including TR117 with 3,017 inference runs)

---

## Report Guide: What Each Technical Report Answers

| Report | Core Question | Headline Outcome | Why It Matters |
|--------|---------------|------------------|----------------|
| **TR108** | What is the best single-inference baseline? | GPU 80 / CTX 512 / TEMP 0.8 is the reference config. | Establishes baseline for all comparisons. Shows that single-inference optimization is different from agent optimization. |
| **TR109** | Do agent workflows need different tuning? | Yes: 512–1024 ctx, only 39% of configs beat baseline. | Proves you can't copy single-inference settings to agents. Agent workflows have different characteristics. |
| **TR110** | Can Python run agents concurrently? | Dual Ollama yields 99.25% peak, 95.8% mean efficiency. | Validates that multi-agent systems can achieve near-perfect parallelism. Critical for scaling. |
| **TR111_v2** | How fast can a Rust agent go? | 114.54 tok/s baseline (+15.2% vs Python). | First comprehensive Rust agent benchmark. Proves Rust's performance advantage is real. |
| **TR112_v2** | Apples-to-apples Python vs Rust? | Rust: –58% TTFT, –67% memory, 2.6% CV, +83% faster startup. | Definitive comparison with identical workflows. Provides data for decision-making. |
| **TR113** | What if we keep one Ollama? | Rust stalls at 82.2% efficiency (contention). | Identifies architectural bottleneck. Proves dual Ollama is necessary. |
| **TR114_v2** | Does dual Ollama unblock Rust? | 98.281% mean, 99.396% peak, 0.74% contention. | Validates Rust can exceed Python in multi-agent scenarios with proper architecture. |
| **TR115_v2** | Which Rust runtime should we ship? | Tokio-default: 99.89% peak / 98.72% mean / 1.21 pp sigma. | Production guidance. Consistency matters more than peak performance. |
| **TR116** | Does model choice matter for multi-agent? | Rust + Gemma 3 is king (99.2%). Qwen shows imbalance. | Proves Rust's advantage holds across models (+12-17pp efficiency). |
| **TR117** | Which inference backend is fastest? | GPU-compile wins mean (389ms), plain GPU wins median (323ms) - "compile paradox". Python 86% ceiling from event loop lag. | Backend choice matters for latency. Python's structural limitations prevent >86% efficiency. |
| **TR117_multi_agent** | Why does Python have an 86% efficiency ceiling? | Event loop saturation: 5.33ms mean lag, 15.22ms max. CPU-bound JSON parsing monopolizes single-threaded loop. | Python limitation is structural. Rust's multi-threaded runtime eliminates this bottleneck. |
| **TR118_v2.2** | Can specialized runtimes beat PyTorch? | TensorRT-fp16: 2.48ms prefill (-87% vs baseline). ONNX Runtime-CPU: 43.3ms generate (-73% vs baseline). | Specialized runtimes provide significant latency improvements but require infrastructure investment. |
| **TR119** | What are the cost/energy implications? | onnxruntime-gpu: $0.1279/1M tokens (on-demand), best cost efficiency. | Backend choice significantly impacts operational costs and energy consumption. |
| **TR120** | Why does GPU-compile win mean but lose median? | TR117 compile label misattributed; shape stability is critical, not compilation. | Understanding true cause enables better optimization. Shape stability matters more than compilation. |
| **TR121v1** | How does performance scale with model size? | Scaling pipeline established from 5M to 20B parameters. | Understanding scaling behavior essential for choosing appropriate model sizes. |

**Full report links:** See `docs/technical_reports.md` for complete index, or browse `outputs/publish_ready/reports/` for all technical reports.

---

## How to Use This Repository

### Getting Started (5 Minutes)

1. **Set up the environment** – Follow `docs/installation.md`
   - Python 3.11+, Rust 1.70+, CUDA 11.8+, Ollama
   - RTX 4080-class GPU (12GB+ VRAM recommended)
   - Windows/macOS/Linux supported

2. **Get a first run working** – Follow `docs/quick_start.md`
   - Walks through Python and Rust single-agent benchmarks
   - Shows how to interpret results
   - Takes about 10-15 minutes for first run

3. **Enable true concurrency** – Follow `docs/dual_ollama_setup.md`
   - Required for multi-agent benchmarks (TR110/TR114)
   - Shows how to run two Ollama instances on ports 11434/11435
   - Critical for reproducing multi-agent results

### Going Deeper

4. **Understand the methodology** – Read `docs/benchmarking.md` and `docs/methodology.md`
   - How we ensure fair comparisons
   - Statistical analysis techniques
   - How to interpret results

5. **Compare languages** – Read `docs/rust_vs_python.md`
   - Detailed comparison tables
   - When to use each language
   - Trade-off analysis

6. **Optimize performance** – Read `docs/performance_tuning.md` and `docs/chimera_optimization.md`
   - Configuration optimization strategies
   - Parameter tuning guidance
   - Common pitfalls to avoid

### Automation and Analysis

7. **Automate benchmarks** – Use `scripts/benchmark_cli.py` for cross-platform runs
   - Or use PowerShell helpers in `scripts/windows/` on Windows
   - Batch processing for multiple configurations
   - Results automatically written to `benchmarks/` or `outputs/`

8. **Analyze your data** – Use notebooks in `outputs/publish_ready/notebooks/`
   - Jupyter notebooks for data analysis
   - Visualization tools
   - Statistical analysis scripts

All scripts write outputs into `benchmarks/` or `outputs/` so the data stays co-located with the research.

---

## Repository Structure: Where Everything Lives

| Path | Contents | When to Use |
|------|----------|-------------|
| **`src/python/banterhearts/`** | Python agent source code | When you want to understand or modify Python implementations |
| **`src/rust/demo_agent/`** | Rust single-agent implementation | When you want to understand or modify Rust single-agent code |
| **`src/rust/demo_multiagent/`** | Rust multi-agent implementation | When you want to understand or modify Rust multi-agent code |
| **`experiments/TR111/`** through **`TR115/`** | Research experiment code and scripts | When you want to reproduce specific technical report results |
| **`scripts/`** | Python automation scripts | When you want to automate benchmarks or analysis |
| **`scripts/windows/`** | PowerShell wrappers for Windows | When running on Windows and need platform-specific helpers |
| **`benchmarks/`** | Replayable benchmark artifacts | When you want to inspect raw benchmark data |
| **`data/baselines/`** | Canonical baseline measurements | When you need reference points for regression testing |
| **`data/csv/`** | CSV exports of benchmark data | When you want to analyze data in Excel, Python, or other tools |
| **`data/research/`** | Research data from experiments | When you want to access experiment-specific datasets |
| **`outputs/reports/`** | Intermediate technical reports | When you want to see work-in-progress analysis |
| **`outputs/publish_ready/reports/`** | Final technical reports (TR108-TR123) | **Start here** for comprehensive findings and analysis |
| **`outputs/publish_ready/notebooks/`** | Jupyter notebooks for analysis | When you want to reproduce analysis or create visualizations |
| **`outputs/artifacts/`** | Generated visualizations, profiles | When you want to see charts, graphs, or performance profiles |
| **`outputs/runs/`** | Benchmark run outputs | When you want to inspect individual benchmark execution logs |
| **`logs/benchmarks/`** | Archived benchmark logs | When you need historical log data |
| **`resources/prompts/`** | Benchmark and test prompts | When you want to understand what prompts were used |
| **`resources/patches/`** | Patch notes and changelogs | When you want to understand what changed and when |
| **`docs/`** | All documentation | **Start here** for guides, API docs, and explanations |

**Rule of thumb:** 
- Code lives in `src/`
- Automation lives in `scripts/`
- Generated data lives in `benchmarks/` or `outputs/`
- Explanations live in `docs/`
- Final reports live in `outputs/publish_ready/reports/`

---

## Trust but Verify: How We Ensure Accuracy

Every number in this repository is reproducible and verifiable. Here's how we ensure accuracy:

### Experimental Rigor

- **Process isolation:** Each benchmark run launches a fresh Ollama process to avoid warm-cache bias
- **Multiple runs:** Every configuration is tested 3-5 times for statistical confidence (except TR113's exploratory single-run sweep, which is clearly labeled in the report)
- **Cold starts:** Forced model reloads between runs to ensure fair comparisons
- **Structured logging:** All metrics collected in structured formats (JSON, CSV) with timestamps

### Data Provenance

- **Metadata tracking:** Every dataset, CSV, and figure includes metadata showing:
  - The exact command that produced it
  - The configuration used
  - The hardware and software environment
  - The date and time of execution
- **Version control:** All code, data, and reports are version-controlled
- **Reproducibility:** Anyone can clone this repo and reproduce our results

### Verification Process

To audit any number in this repository:

1. **Find the claim** in a Technical Report (e.g., "Rust is 15.2% faster")
2. **Check the report** in `outputs/publish_ready/reports/` for methodology
3. **Follow the reference** to the data folder (e.g., `benchmarks/rust/demo_agent/...`)
4. **Inspect the raw data** (CSV files, JSON logs)
5. **Reproduce the analysis** using the provided scripts or notebooks

### Statistical Validation

All reports include:
- **Mean, median, standard deviation** for all metrics
- **Confidence intervals** where applicable
- **Coefficient of variation** (CV) for consistency measures
- **Percentile analysis** (p50, p95, p99) for latency metrics
- **Multiple runs** to establish statistical significance

---

## Need More Detail?

### For Specific Topics

- **`docs/rust_vs_python.md`** – Extended comparison tables with detailed metrics
- **`docs/performance_tuning.md`** – Guidance on optimizing agent performance
- **`docs/chimera_optimization.md`** – Configuration optimization strategies
- **`docs/statistical_analysis.md`** – How we analyze and interpret benchmark data
- **`docs/multi_agent.md`** – Multi-agent architecture and setup
- **`docs/dual_ollama_setup.md`** – Critical setup for multi-agent benchmarks
- **`docs/API.md`** – Code reference and API documentation

### For Understanding the Research

- **`docs/technical_reports.md`** – Complete index of all technical reports
- **`outputs/publish_ready/reports/`** – All technical reports (TR108-TR123) with full analysis
- **`outputs/publish_ready/notebooks/`** – Jupyter notebooks for data analysis
- **`resources/patches/`** – Narrative changelog of major updates and discoveries

### For Getting Help

- **Open an issue** on GitHub for questions or problems
- **Start from the relevant Technical Report** that cites the data you need
- **Check `docs/faq.md`** for common questions
- **Review `docs/README.md`** for documentation navigation

---

## Research Scale and Methodology

### Total Research Investment

- **2000+ benchmark runs** across all published studies (TR108–TR123, including TR117 with 3,017 inference runs)
- **Up to 30 configurations per major report** (see "Research Journey" above for exact counts)
- **16+ comprehensive technical reports** documenting findings (TR108-TR123, with TR122 and TR123 planned)
- **Multiple hardware/software combinations** validated
- **Statistical analysis** with confidence intervals on all key metrics

### Methodology Highlights

- **Process isolation:** Fresh processes for every run to avoid bias
- **Cold starts:** Forced model reloads between runs
- **Multiple repetitions:** 3-5 runs per configuration for statistical confidence (TR113 noted as single-run exploratory)
- **Structured data collection:** All metrics in machine-readable formats
- **Reproducible code:** Every benchmark is runnable with provided scripts
- **Full documentation:** Methodology documented in every technical report

### Hardware and Software

- **GPU:** NVIDIA RTX 4080 (12GB VRAM, 9,728 CUDA cores)
- **CPU:** Intel Core i9-13980HX (24 cores, 32 threads)
- **Model:** gemma3:latest (4.3B parameters, Q4_K_M quantization)
- **Python:** 3.11+ with asyncio
- **Rust:** 1.70+ with Tokio/async-std/smol runtimes
- **Ollama:** Latest version with dual-instance support

---

## Contributing

We welcome contributions! See [`CONTRIBUTING.md`](CONTRIBUTING.md) for guidelines.

**Areas for contribution:**
- Additional benchmark configurations
- New optimization strategies
- Documentation improvements
- Analysis tools and visualizations
- Support for additional models or hardware

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

## Acknowledgments

This research was conducted as part of the Banterhearts program, focusing specifically on benchmarking and performance optimization. Production APIs and orchestration services remain in the main Banterhearts repository.

---

**Last Updated:** latest report: November 26, 2025
**Repository:** https://github.com/Sahil170595/Chimeraforge  
**Status:** ✅ Active Research & Development
