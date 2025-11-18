# TR115: Runtime Optimization for Multi-Agent LLM Concurrency

## Objective

Close the 3.6pp efficiency gap between Rust (95.7% peak, TR114) and Python (99.25% peak, TR110) multi-agent deployments by systematically testing alternative async runtimes and HTTP client optimizations.

## Hypothesis

The TR114 efficiency gap is attributable to:
1. **Tokio work-stealing overhead** (~2-3pp): Context switching between agents causes cache thrashing
2. **Reqwest buffering** (~1-2pp): 8KB chunks vs Python httpx's 1KB creates I/O interleaving delays

**Expected outcome**: LocalSet/smol with 1KB chunking can recover **+3-4pp**, achieving **98-99% efficiency**.

## Test Matrix

### Runtime Variants (5)

1. **tokio-default** (baseline)
   - Current TR114 implementation
   - Work-stealing scheduler
   - Reqwest (8KB buffering)
   - Baseline: 95.7% peak efficiency

2. **tokio-localset** (expected +2-3pp)
   - Single-threaded LocalSet
   - Eliminates work-stealing overhead
   - Reqwest (8KB buffering)
   - Target: 97-98% efficiency

3. **async-std** (expected +1-2pp)
   - Simpler scheduler than tokio
   - Less aggressive work-stealing
   - Reqwest (8KB buffering)
   - Target: 96-97% efficiency

4. **smol** (expected +2-3pp)
   - Lightweight runtime
   - Minimal overhead
   - Reqwest (8KB buffering)
   - Target: 97-98% efficiency

5. **smol-1kb** (expected +3-4pp total)
   - smol runtime
   - Custom hyper-based HTTP client
   - 1KB chunk buffering
   - Target: 98-99% efficiency

### Test Configurations (6)

Based on TR114's top-performing configurations:

1. **baseline_vs_chimera** (GPU=80, CTX=512, TEMP=1.0)
2. **chimera_hetero** (GPU=80/100, CTX=512/1024, TEMP=1.0)
3. **chimera_homo** (GPU=80, CTX=512, TEMP=1.0)
4. **chimera_homo** (GPU=80, CTX=1024, TEMP=1.0)
5. **chimera_homo** (GPU=80, CTX=2048, TEMP=1.0)
6. **chimera_homo** (GPU=100, CTX=512, TEMP=1.0)

### Statistical Rigor

- **Runs per configuration**: 5
- **Total benchmarks**: 5 runtimes × 6 configs × 5 runs = **150 benchmarks**
- **Expected duration**: 8-10 hours (hands-off)

## Success Criteria

### Primary Goal
- **Achieve ≥98% peak efficiency** (within 1.25pp of Python's 99.25%)

### Secondary Goals
- **Identify optimal runtime** for production deployment
- **Validate hypothesis** (expected +3-4pp gain from LocalSet/smol + 1KB chunking)
- **Statistical significance** (p < 0.05 vs TR114 baseline)

## Methodology

### Benchmark Execution
1. Build each runtime variant with `cargo build --release --features=<runtime>`
2. Execute 6 configs × 5 runs per runtime
3. Save results to `TR115_runtime_optimization/results/<runtime>/<config>/<run>/`
4. Aggregate metrics per runtime

### Analysis
1. Calculate efficiency gains vs TR114 baseline (95.7%)
2. Calculate gap vs TR110 target (99.25%)
3. Statistical tests (t-test for each runtime vs baseline)
4. Configuration sensitivity analysis
5. Generate TR115 technical report

## Implementation Timeline

### Day 1: Setup (4-6 hours)
- ✅ Create TR115 workspace
- ✅ Add runtime feature flags to Cargo.toml
- ✅ Refactor main.rs for runtime variants
- ✅ Implement custom 1KB HTTP client
- ✅ Create orchestration scripts

### Day 2: Execution (8-10 hours, automated)
- Run comprehensive sweep (150 benchmarks)
- Monitor progress
- Collect metrics

### Day 3: Analysis (4-6 hours)
- Analyze results
- Compare to TR114/TR110
- Write TR115 technical report
- Generate production recommendations

## Expected Outcomes

### Optimistic Scenario (98-99% efficiency)
- **smol-1kb achieves 99%+** efficiency
- Gap effectively closed
- Rust viable alternative to Python

### Realistic Scenario (97-98% efficiency)
- **LocalSet or smol achieves 97-98%** efficiency
- Significant improvement (+2-3pp)
- Residual gap <2pp acceptable for production

### Pessimistic Scenario (<97% efficiency)
- Runtime changes insufficient
- Gap remains >3pp
- Requires deeper investigation (profiling, custom schedulers)

## Risk Mitigation

### Risk: Build failures
- **Mitigation**: Test build for each runtime before sweep

### Risk: Benchmark timeouts
- **Mitigation**: 10-minute timeout per benchmark, skip failures

### Risk: Inconclusive results
- **Mitigation**: 5 runs per config ensures statistical significance

## References

- [TR114: Rust Multi-Agent (Dual Ollama)](../../PublishReady/reports/Technical_Report_114.md)
- [TR110: Python Multi-Agent](../../PublishReady/reports/Technical_Report_110.md)
- [TR114 Section 8.3: Future Work](../../PublishReady/reports/Technical_Report_114.md#83-future-work)

---

**Status**: Planning complete, ready for execution  
**Created**: November 2025  
**Owner**: Banterhearts Research Team

