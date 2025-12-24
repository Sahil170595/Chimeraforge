#!/usr/bin/env python3
"""Check benchmark artifacts for all new models."""

import json
from pathlib import Path

models = ['gpt2-5m', 'gpt2-25m', 'gpt2-50m', 'gpt2-75m', 'gpt2-100m']
base_dir = Path("scripts/tr118/results/tr118v2_crossover")

print("=" * 70)
print("BENCHMARK ARTIFACTS SUMMARY")
print("=" * 70)
print()

for model in models:
    model_dir = base_dir / model
    print(f"{model}:")
    
    # Check raw data
    raw_dir = model_dir / "raw"
    prefill_files = list(raw_dir.glob("bench_prefill_*.jsonl"))
    generate_files = list(raw_dir.glob("bench_generate_*.jsonl"))
    
    prefill_runs = 0
    generate_runs = 0
    
    if prefill_files:
        with open(prefill_files[0], 'r', encoding='utf-8') as f:
            prefill_runs = len([line for line in f if line.strip()])
    
    if generate_files:
        with open(generate_files[0], 'r', encoding='utf-8') as f:
            generate_runs = len([line for line in f if line.strip()])
    
    print(f"  Raw data: {prefill_runs} prefill runs, {generate_runs} generate runs")
    
    # Check processed data
    processed_dir = model_dir / "processed"
    has_latency_prefill = (processed_dir / "latency_summary_prefill.csv").exists()
    has_latency_generate = (processed_dir / "latency_summary_generate.csv").exists()
    has_perplexity = (processed_dir / "perplexity_results.json").exists()
    has_stats_prefill = (processed_dir / "statistical_analysis_prefill.json").exists()
    has_stats_generate = (processed_dir / "statistical_analysis_generate.json").exists()
    
    print(f"  Processed: prefill={has_latency_prefill}, generate={has_latency_generate}, "
          f"perplexity={has_perplexity}, stats={has_stats_prefill and has_stats_generate}")
    
    # Check plots
    plots_dir = model_dir / "plots"
    plot_files = list(plots_dir.glob("*.png")) if plots_dir.exists() else []
    print(f"  Plots: {len(plot_files)} files")
    
    # Check ONNX CPU vs PyTorch GPU for crossover analysis
    if has_latency_prefill:
        import csv
        with open(processed_dir / "latency_summary_prefill.csv", 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
            # Find single_medium scenario (standard comparison point)
            onnx_cpu = [r for r in rows if r['backend'] == 'onnxruntime-cpu' and r['scenario'] == 'single_medium']
            pytorch_gpu = [r for r in rows if r['backend'] == 'transformers-gpu-compile' and r['scenario'] == 'single_medium']
            
            if onnx_cpu and pytorch_gpu:
                onnx_tps = float(onnx_cpu[0]['throughput_mean_tok_s'])
                pytorch_tps = float(pytorch_gpu[0]['throughput_mean_tok_s'])
                advantage = onnx_tps / pytorch_tps
                print(f"  Crossover data (single_medium): ONNX CPU {onnx_tps:.0f} tok/s vs PyTorch GPU {pytorch_tps:.0f} tok/s = {advantage:.2f}x")
    
    print()

print("=" * 70)
print("ARTIFACTS CHECK COMPLETE")
print("=" * 70)


