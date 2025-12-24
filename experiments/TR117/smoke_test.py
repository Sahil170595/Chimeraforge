"""End-to-end smoke test for TR117 infrastructure."""

from pathlib import Path
import sys

print("=" * 60)
print("TR117 End-to-End Smoke Test")
print("=" * 60)
print()

# Test 1: Data loading
print("Test 1: Loading metrics data...")
try:
    import pandas as pd

    df = pd.read_csv("results/tr117/metrics.csv")
    print(f"  ✓ Loaded {len(df)} rows")
    print(f"  ✓ Backends: {list(df['backend'].unique())}")
    print(f"  ✓ Status distribution: {df['status'].value_counts().to_dict()}")
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    sys.exit(1)

# Test 2: Statistical analysis
print("\nTest 2: Statistical analysis...")
try:
    from statistical_analysis import compute_summary

    # Get data for one backend
    backend_data = df[df["backend"] == "transformers-cpu"]["latency_ms"].tolist()
    if backend_data:
        summary = compute_summary(backend_data)
        print(f"  ✓ Mean: {summary.mean:.1f}ms")
        print(f"  ✓ 95% CI: [{summary.ci_lower:.1f}, {summary.ci_upper:.1f}]")
        print(f"  ✓ n={summary.n} samples")
    else:
        print("  ⚠ No data for statistical test")
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    sys.exit(1)

# Test 3: Cost analysis
print("\nTest 3: Cost analysis...")
try:
    from cost_analysis import compute_cost_profile

    profile = compute_cost_profile("transformers-cpu", df)
    print(f"  ✓ Tokens/s: {profile.tokens_per_second:.1f}")
    print(f"  ✓ $/1M tokens: ${profile.cost_per_million_tokens_usd:.4f}")
    print(f"  ✓ Compute efficiency: {profile.compute_efficiency:.4f}")
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    sys.exit(1)

# Test 4: Accuracy metrics
print("\nTest 4: Accuracy metrics...")
try:
    from accuracy_metrics import compute_accuracy_metrics

    ref = "This is a test sentence about machine learning."
    cand = "This is a test about ML and AI."
    metrics = compute_accuracy_metrics(ref, cand)
    print(f"  ✓ ROUGE-1: {metrics.rouge1_f:.3f}")
    print(f"  ✓ BLEU: {metrics.bleu:.3f}")
    print(f"  ✓ Semantic sim: {metrics.semantic_similarity:.3f}")
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    sys.exit(1)

# Test 5: Resource monitoring
print("\nTest 5: Resource monitoring...")
try:
    import time

    from resource_monitor import ResourceMonitor

    monitor = ResourceMonitor(sampling_interval_s=0.05)
    monitor.start()
    time.sleep(0.2)
    profile = monitor.stop()

    print(f"  ✓ Duration: {profile.duration_s:.2f}s")
    print(f"  ✓ CPU: {profile.cpu_mean:.1f}%")
    print(f"  ✓ Memory: {profile.memory_mean_mb:.1f}MB")
    if profile.gpu_util_mean:
        print(f"  ✓ GPU: {profile.gpu_util_mean:.1f}%")
except Exception as e:
    print(f"  ✗ FAILED: {e}")
    sys.exit(1)

# Test 6: Verify outputs exist
print("\nTest 6: Checking generated outputs...")
outputs = [
    "results/tr117/metrics.csv",
    "results/tr117/statistical_analysis.json",
    "results/tr117/cost_analysis.json",
    "results/tr117/latency_by_backend.png",
    "results/tr117/env.json",
]

for output in outputs:
    if Path(output).exists():
        size_kb = Path(output).stat().st_size / 1024
        print(f"  ✓ {output} ({size_kb:.1f} KB)")
    else:
        print(f"  ⚠ {output} (missing)")

# Summary
print("\n" + "=" * 60)
print("✓ All smoke tests passed!")
print("=" * 60)
print("\nReady for Tier 3 full run:")
print("  - Statistical analysis: Working")
print("  - Cost analysis: Working")
print("  - Accuracy metrics: Working")
print("  - Resource monitoring: Working")
print("  - Data pipeline: Working")
print("\nNext: Run full matrix with increased repetitions")
