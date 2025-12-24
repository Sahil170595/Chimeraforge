#!/usr/bin/env python3
"""Analyze why 100M shows ONNX CPU faster than PyTorch GPU."""

import csv
from pathlib import Path

models = {
    '50m': Path('scripts/tr118/results/tr118v2_crossover/gpt2-50m/processed/latency_summary_prefill.csv'),
    '75m': Path('scripts/tr118/results/tr118v2_crossover/gpt2-75m/processed/latency_summary_prefill.csv'),
    '100m': Path('scripts/tr118/results/tr118v2_crossover/gpt2-100m/processed/latency_summary_prefill.csv'),
}

print("=" * 70)
print("ANALYZING 100M ANOMALY")
print("=" * 70)
print()

for name, path in models.items():
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
        onnx_cpu = [r for r in rows if r['backend'] == 'onnxruntime-cpu' and r['scenario'] == 'single_medium'][0]
        pytorch_gpu = [r for r in rows if r['backend'] == 'transformers-gpu-compile' and r['scenario'] == 'single_medium'][0]
        
        onnx_tps = float(onnx_cpu['throughput_mean_tok_s'])
        pytorch_tps = float(pytorch_gpu['throughput_mean_tok_s'])
        onnx_lat = float(onnx_cpu['mean'])
        pytorch_lat = float(pytorch_gpu['mean'])
        advantage = onnx_tps / pytorch_tps
        
        print(f"{name.upper()}:")
        print(f"  ONNX CPU:  {onnx_tps:7.0f} tok/s, {onnx_lat:6.2f} ms")
        print(f"  PyTorch:   {pytorch_tps:7.0f} tok/s, {pytorch_lat:6.2f} ms")
        print(f"  Advantage: {advantage:.2f}x ({'ONNX faster' if advantage > 1 else 'PyTorch faster'})")
        print(f"  Latency ratio: {pytorch_lat/onnx_lat:.2f}x")
        print()

print("=" * 70)
print("OBSERVATIONS")
print("=" * 70)
print("100M PyTorch GPU is unusually slow (832 tok/s vs 2209 for 75M)")
print("This could indicate:")
print("  1. Measurement variance/outlier")
print("  2. Model architecture difference (different layer config)")
print("  3. GPU memory/thermal throttling")
print("  4. Compilation issue with torch.compile")
print()
print("Recommendation: Re-run 100M benchmark or exclude from crossover fit")


