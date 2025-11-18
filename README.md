# Chimeraforge

> **A comprehensive research repository for optimizing Large Language Model (LLM) agent performance**  
> Benchmarking, analysis, and technical reports comparing Python vs Rust implementations for production LLM deployments.

---

## 🎯 What Is This?

Chimeraforge is a research and benchmarking repository that answers a critical question: **"How do we build the fastest, most efficient AI agents?"**

We've conducted extensive research comparing Python and Rust implementations of LLM agents, testing everything from single-agent performance to complex multi-agent systems. This repository contains all the code, data, and detailed technical reports from our research.

### The Big Picture

If you're building AI agents that need to be fast, efficient, and reliable, this repository will help you understand:
- **Which programming language performs better** (Python vs Rust)
- **How to optimize your agent configurations** (GPU layers, context windows, temperature)
- **How to run multiple agents concurrently** without performance degradation
- **What the real-world performance differences are** (not just theoretical)

---

## 🔍 What We Discovered

### TL;DR - Key Findings

After running **843+ benchmark tests** across 8 technical reports, here's what we learned:

#### **Rust vs Python: The Winner is Clear**

**For Single Agents:**
- 🚀 **Rust is 15% faster** at generating text (114.5 vs 99.3 tokens/second)
- ⚡ **Rust starts 58% faster** (603ms vs 1,437ms to first token)
- 💾 **Rust uses 67% less memory** (~75 MB vs ~250 MB)
- 📊 **Rust is 46% more consistent** (less variation between runs)

**For Multi-Agent Systems:**
- 🎯 **Rust achieves 98.3% parallel efficiency** (nearly perfect!)
- 🏆 **Rust beats Python by 2.5 percentage points** in multi-agent scenarios
- 🔧 **Both require dual Ollama instances** for true concurrency

**Bottom Line:** Rust is faster, uses less memory, and is more consistent. Python is easier to develop with and has a larger ecosystem.

---

## 📊 Research Journey: 8 Technical Reports

We conducted systematic research across 8 technical reports (TR108-TR115), each answering specific questions:

### **TR108: Single-Inference Optimization**
**Question:** What's the best configuration for a single LLM request?  
**Answer:** GPU=80 layers, Context=512 tokens, Temperature=0.8  
**Impact:** Established baseline for all future comparisons

### **TR109: Python Agent Workflows**
**Question:** Do agent workflows need different settings than single requests?  
**Answer:** Yes! Agents work better with smaller context windows (512-1024 vs 2048)  
**Impact:** Agent optimization requires different strategies than single-inference

### **TR110: Python Multi-Agent Performance**
**Question:** Can we run multiple agents at the same time efficiently?  
**Answer:** Yes! Achieved 99.25% efficiency with proper setup  
**Impact:** Proved multi-agent systems can nearly double capacity with minimal overhead

### **TR111: Rust Single-Agent Performance**
**Question:** How does Rust perform for single agents?  
**Answer:** 114.5 tokens/second baseline, 15% faster than Python  
**Impact:** Confirmed Rust's performance advantages

### **TR112: Rust vs Python Comparison**
**Question:** What are the real-world differences between Rust and Python?  
**Answer:** Rust is faster, uses less memory, and is more consistent across all metrics  
**Impact:** Clear performance data for production decisions

### **TR113: Rust Multi-Agent (Single Ollama)**
**Question:** Can Rust multi-agent work with one Ollama instance?  
**Answer:** Only 82% efficiency - identified the bottleneck  
**Impact:** Discovered that dual Ollama instances are essential

### **TR114: Rust Multi-Agent (Dual Ollama)**
**Question:** Does dual Ollama fix the bottleneck?  
**Answer:** Yes! Achieved 98.3% mean efficiency, 99.4% peak  
**Impact:** Validated architecture and exceeded Python performance

### **TR115: Rust Runtime Optimization**
**Question:** Which async runtime is best for Rust agents?  
**Answer:** Tokio-default (98.7% efficiency, most consistent)  
**Impact:** Production recommendation for Rust implementations

---

## 🎓 Key Insights for Different Audiences

### **For Product Managers & Decision Makers**

**The Question:** Should we use Python or Rust for our AI agents?

**The Answer:**
- **Use Rust if:** Performance, memory efficiency, and consistency are critical. You're building high-throughput systems where every millisecond matters.
- **Use Python if:** Development speed, ecosystem, and team familiarity are priorities. You need to iterate quickly and have a Python-heavy team.

**The Numbers:**
- Rust: 15% faster, 67% less memory, 46% more consistent
- Python: Easier to develop, larger ecosystem, more developers available

**Our Recommendation:** For production systems handling significant load, Rust's advantages are substantial. For prototypes and smaller systems, Python's development speed may outweigh performance differences.

### **For Engineers & Developers**

**Configuration Recommendations:**

**Single Agent (Best Performance):**
- **Rust:** GPU=60-80, Context=512-1024, Temperature=0.8
- **Python:** GPU=60-80, Context=512-1024, Temperature=0.6-0.8

**Multi-Agent (Best Efficiency):**
- **Rust:** GPU=80/100 (heterogeneous), Context=512/1024, Temperature=1.0
- **Python:** GPU=80, Context=2048, Temperature=1.0
- **Critical:** Use dual Ollama instances (ports 11434/11435)

**Runtime Selection (Rust):**
- **Production:** Tokio-default (best consistency)
- **Alternative:** Smol-1KB (smaller binary size)

### **For Researchers & Academics**

**Methodology Highlights:**
- **843+ benchmark runs** across all reports
- **Statistical rigor:** Mean, median, stddev, percentiles, coefficient of variation
- **Process isolation:** Separate processes to avoid warm-cache bias
- **Multiple runs:** 3-5 runs per configuration for confidence intervals
- **Reproducible:** All code, data, and methodology documented

**Research Questions Answered:**
1. ✅ Rust is faster than Python for LLM inference (15.2% throughput advantage)
2. ✅ Rust's single-agent advantage extends to multi-agent (+2.48pp efficiency)
3. ✅ Dual Ollama architecture is necessary (reduces contention 63% → 0.74%)
4. ✅ Tokio-default is optimal Rust runtime (98.72% mean, 1.21pp σ)
5. ✅ Heterogeneous GPU allocation optimizes multi-agent performance

---

## 🚀 What's In This Repository?

### **Source Code**
- **Python Agents** (`src/python/banterhearts/`): Complete Python implementation with benchmarking tools
- **Rust Agents** (`src/rust/`): Production-grade Rust implementations with multiple runtime support

### **Research Experiments**
- **TR111-TR115** (`experiments/`): All experiment code, scripts, and analysis tools
- **Data** (`data/`): Baseline measurements, CSV exports, and research data
- **Results** (`outputs/`): All benchmark results, reports, and publishable findings

### **Documentation**
- **User Guides** (`docs/`): Installation, quick start, benchmarking guides
- **Technical Reports** (`outputs/publish_ready/reports/`): Complete detailed analysis
- **API Documentation** (`docs/API.md`): Code reference and examples

### **Tools & Scripts**
- **Benchmarking Scripts** (`scripts/`): Automated benchmark execution
- **Analysis Tools** (`scripts/`): Data processing and visualization
- **Windows Utilities** (`scripts/windows/`): PowerShell helpers for Windows users

---

## 📈 Performance Summary

### Single-Agent Performance

| Metric | Python | Rust | Winner |
|--------|--------|------|--------|
| **Throughput** | 99.3 tok/s | 114.5 tok/s | 🏆 Rust (+15.2%) |
| **Time to First Token** | 1,437ms | 603ms | 🏆 Rust (-58%) |
| **Memory Usage** | ~250 MB | ~75 MB | 🏆 Rust (-67%) |
| **Consistency (CV)** | 4.8% | 2.6% | 🏆 Rust (46% better) |
| **Startup Time** | 1.5s | 0.2s | 🏆 Rust (-83%) |

### Multi-Agent Performance

| Metric | Python | Rust | Winner |
|--------|--------|------|--------|
| **Mean Efficiency** | 95.8% | 98.3% | 🏆 Rust (+2.5pp) |
| **Peak Efficiency** | 99.25% | 99.4% | 🏆 Rust (+0.15pp) |
| **Contention Rate** | 10-15% | 0.74% | 🏆 Rust (20x better) |
| **Consistency (StdDev)** | 7.4pp | 4.9pp | 🏆 Rust (34% better) |

**Efficiency** = How close to perfect parallelism (2.0x speedup for 2 agents)  
**Contention** = Resource conflicts that slow down execution

---

## 🏁 Quick Start

### Prerequisites
- Python 3.11+ (for Python agents)
- Rust 1.70+ (for Rust agents)
- Ollama (for running LLM models)
- NVIDIA GPU with CUDA (12GB+ VRAM recommended)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/Sahil170595/Chimeraforge.git
cd Chimeraforge

# 2. Install Python dependencies
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Build Rust agents (optional)
cd src/rust/demo_agent && cargo build --release
cd ../demo_multiagent && cargo build --release
cd ../../..

# 4. Pull the model
ollama pull gemma3:latest
```

### Run Your First Benchmark

**Python Single-Agent:**
```bash
python src/python/banterhearts/demo_agent/run_demo.py \
  --model gemma3:latest \
  --runs 3
```

**Rust Single-Agent:**
```bash
cd src/rust/demo_agent
cargo run --release -- --model gemma3:latest --runs 3
cd ../../..
```

See [`docs/quick_start.md`](docs/quick_start.md) for detailed instructions.

---

## 📚 Understanding the Results

### What Do These Numbers Mean?

**Throughput (tokens/second):** How fast the agent generates text. Higher is better.  
**TTFT (Time to First Token):** How long until the agent starts responding. Lower is better.  
**Efficiency:** For multi-agent, how close to perfect parallelism. 100% = perfect, 50% = no benefit.  
**Contention:** Resource conflicts. 0% = no conflicts, 100% = constant conflicts.

### Reading the Technical Reports

All technical reports are in `outputs/publish_ready/reports/`:
- **TR108-TR110:** Python performance analysis
- **TR111-TR115:** Rust performance analysis and optimization

Each report includes:
- Executive summary
- Methodology
- Detailed results
- Statistical analysis
- Production recommendations

---

## 🎯 Use Cases

### **When to Use This Repository**

1. **Evaluating Python vs Rust** for your LLM agent project
2. **Optimizing agent configurations** for your hardware
3. **Designing multi-agent systems** that need high efficiency
4. **Understanding LLM performance** characteristics
5. **Reproducing our research** or extending it

### **What This Repository Is NOT**

- ❌ Not a production-ready agent framework (it's benchmarking code)
- ❌ Not a general-purpose LLM library
- ❌ Not optimized for all hardware configurations
- ❌ Not a replacement for production monitoring tools

---

## 📖 Documentation

### **Getting Started**
- **[Quick Start Guide](docs/quick_start.md)** - Get running in 5 minutes
- **[Installation Guide](docs/installation.md)** - Detailed setup instructions
- **[Architecture Overview](docs/ARCHITECTURE.md)** - How everything works

### **Running Benchmarks**
- **[Benchmarking Guide](docs/benchmarking.md)** - Complete benchmark walkthrough
- **[Multi-Agent Guide](docs/multi_agent.md)** - Concurrent execution setup
- **[Dual Ollama Setup](docs/dual_ollama_setup.md)** - Required for multi-agent

### **Understanding Results**
- **[Technical Reports](docs/technical_reports.md)** - Index of all reports
- **[Statistical Analysis](docs/statistical_analysis.md)** - How we analyze data
- **[Rust vs Python](docs/rust_vs_python.md)** - Detailed comparison

### **Optimization**
- **[Chimera Optimization](docs/chimera_optimization.md)** - Configuration tuning
- **[Performance Tuning](docs/performance_tuning.md)** - Advanced optimization

### **Reference**
- **[API Documentation](docs/API.md)** - Code reference
- **[FAQ](docs/faq.md)** - Common questions
- **[Contributing](CONTRIBUTING.md)** - How to contribute

---

## 🔬 Research Methodology

### How We Ensure Accuracy

1. **Multiple Runs:** Every configuration tested 3-5 times
2. **Process Isolation:** Separate processes to avoid interference
3. **Cold Starts:** Force model reloads between runs
4. **Statistical Analysis:** Mean, median, stddev, confidence intervals
5. **Reproducibility:** All code, data, and methodology documented

### Hardware & Software

- **Hardware:** NVIDIA RTX 4080 (12GB VRAM), Intel i9-13980HX
- **Model:** gemma3:latest (4.3B parameters, Q4_K_M quantization)
- **Python:** 3.11+ with asyncio
- **Rust:** 1.70+ with Tokio/async-std/smol runtimes
- **Ollama:** Latest version with dual-instance support

---

## 📊 Repository Structure

```
Chimeraforge/
├── src/                          # Source code
│   ├── python/banterhearts/      # Python agent implementations
│   └── rust/                     # Rust agent implementations
│       ├── demo_agent/           # Single-agent
│       └── demo_multiagent/      # Multi-agent
│
├── experiments/                  # Research experiments
│   ├── TR111/                    # Rust single-agent study
│   ├── TR112/                    # Rust vs Python comparison
│   ├── TR114/                    # Rust multi-agent (dual Ollama)
│   └── TR115_runtime_optimization/  # Runtime comparison
│
├── data/                         # Research data
│   ├── baselines/                # Baseline measurements
│   ├── csv/                      # CSV exports
│   └── research/                 # Experiment data
│
├── outputs/                      # Generated outputs
│   ├── artifacts/                # Visualizations, profiles
│   ├── reports/                  # Intermediate reports
│   ├── runs/                     # Benchmark run outputs
│   └── publish_ready/            # Final technical reports
│
├── docs/                         # Comprehensive documentation
├── scripts/                      # Utility scripts
└── benchmarks/                   # Benchmark results
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for detailed structure.

---

## 🎓 Key Takeaways

### **For Production Systems**

1. **Rust provides significant advantages** in performance, memory, and consistency
2. **Multi-agent systems can achieve near-perfect efficiency** (98%+) with proper setup
3. **Dual Ollama instances are essential** for multi-agent concurrency
4. **Configuration matters:** Optimal settings differ for single vs multi-agent
5. **Runtime choice matters:** Tokio-default is best for Rust production

### **For Development Teams**

1. **Python is faster to develop** but Rust is faster to run
2. **Both languages can achieve excellent results** with proper optimization
3. **Multi-agent architecture requires careful design** (dual Ollama, resource coordination)
4. **Benchmarking is essential** - theoretical performance ≠ real-world performance

### **For Researchers**

1. **Comprehensive methodology** with 843+ benchmark runs
2. **Reproducible results** with full code and data
3. **Statistical rigor** with proper confidence intervals
4. **Open research** - all findings and data available

---

## 🤝 Contributing

We welcome contributions! See [`CONTRIBUTING.md`](CONTRIBUTING.md) for guidelines.

**Areas for Contribution:**
- Additional benchmark configurations
- New optimization strategies
- Documentation improvements
- Analysis tools and visualizations
- Support for additional models/hardware

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

This research was conducted as part of the Banterhearts program, focusing specifically on benchmarking and performance optimization. Production APIs and orchestration services remain in the main Banterhearts repository.

---

## 📞 Questions?

- **Documentation:** Check [`docs/`](docs/) directory
- **FAQ:** See [`docs/faq.md`](docs/faq.md)
- **Issues:** Open an issue on GitHub
- **Technical Reports:** See [`outputs/publish_ready/reports/`](outputs/publish_ready/reports/)

---

## 🌟 Star History

If you find this research useful, please consider starring the repository! It helps others discover this work.

---

**Last Updated:** January 2025  
**Repository:** https://github.com/Sahil170595/Chimeraforge  
**Status:** ✅ Active Research & Development
