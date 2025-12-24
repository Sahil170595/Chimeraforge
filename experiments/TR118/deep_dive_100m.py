#!/usr/bin/env python3
"""Deep dive analysis of 100M anomaly."""

import json
import csv
import statistics
from pathlib import Path
from collections import defaultdict

def load_jsonl(path: Path) -> list[dict]:
    """Load JSONL file."""
    records = []
    if not path.exists():
        return records
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records

def load_model_config(model_path: Path) -> dict | None:
    """Load model config.json."""
    config_path = model_path / "config.json"
    if not config_path.exists():
        return None
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def analyze_runs(models_data: dict):
    """Analyze raw run data."""
    print("=" * 70)
    print("RAW RUN ANALYSIS (single_medium, transformers-gpu-compile)")
    print("=" * 70)
    print()
    
    for model_name, data in models_data.items():
        runs = data['runs']
        if not runs:
            print(f"{model_name}: No runs found")
            continue
        
        latencies = []
        throughputs = []
        warmup_latencies = []
        
        for run in runs:
            if run.get('status') == 'ok':
                latencies.extend(run.get('latencies_ms', []))
                throughputs.extend(run.get('throughput_tok_s', []))
                warmup_latencies.extend(run.get('warmup_latencies_ms', []))
        
        if not latencies:
            print(f"{model_name}: No valid latencies")
            continue
        
        print(f"{model_name.upper()}:")
        print(f"  Total runs: {len(runs)}")
        print(f"  Valid latencies: {len(latencies)}")
        print(f"  Latency stats:")
        print(f"    Mean: {statistics.mean(latencies):.2f} ms")
        print(f"    Median: {statistics.median(latencies):.2f} ms")
        print(f"    Std: {statistics.stdev(latencies) if len(latencies) > 1 else 0:.2f} ms")
        print(f"    Min: {min(latencies):.2f} ms")
        print(f"    Max: {max(latencies):.2f} ms")
        print(f"  Throughput stats:")
        if throughputs:
            print(f"    Mean: {statistics.mean(throughputs):.0f} tok/s")
            print(f"    Median: {statistics.median(throughputs):.0f} tok/s")
        print(f"  Warmup latencies:")
        if warmup_latencies:
            print(f"    Mean: {statistics.mean(warmup_latencies):.2f} ms")
            print(f"    First warmup: {warmup_latencies[0] if warmup_latencies else 'N/A':.2f} ms")
        print()

def analyze_model_configs(models_data: dict):
    """Compare model architectures."""
    print("=" * 70)
    print("MODEL ARCHITECTURE COMPARISON")
    print("=" * 70)
    print()
    
    for model_name, data in models_data.items():
        config = data['config']
        if not config:
            print(f"{model_name}: No config found")
            continue
        
        print(f"{model_name.upper()}:")
        print(f"  Layers: {config.get('n_layer', 'N/A')}")
        print(f"  Hidden: {config.get('n_embd', 'N/A')}")
        print(f"  Heads: {config.get('n_head', 'N/A')}")
        print(f"  FFN inner: {config.get('n_inner', 'N/A')}")
        print(f"  Vocab: {config.get('vocab_size', 'N/A')}")
        print(f"  Positions: {config.get('n_positions', 'N/A')}")
        print()

def analyze_degradation(models_data: dict):
    """Check for degradation/errors."""
    print("=" * 70)
    print("DEGRADATION & ERROR ANALYSIS")
    print("=" * 70)
    print()
    
    for model_name, data in models_data.items():
        runs = data['runs']
        if not runs:
            continue
        
        degraded = 0
        errors = 0
        error_messages = []
        
        for run in runs:
            if run.get('degraded_count', 0) > 0:
                degraded += 1
            if run.get('status') != 'ok':
                errors += 1
                error_messages.append(run.get('error', 'Unknown error'))
        
        print(f"{model_name.upper()}:")
        print(f"  Total runs: {len(runs)}")
        print(f"  Degraded: {degraded}")
        print(f"  Errors: {errors}")
        if error_messages:
            print(f"  Error messages: {set(error_messages)}")
        print()

def analyze_resource_metrics(models_data: dict):
    """Analyze GPU resource metrics."""
    print("=" * 70)
    print("GPU RESOURCE METRICS")
    print("=" * 70)
    print()
    
    for model_name, data in models_data.items():
        runs = data['runs']
        if not runs:
            continue
        
        gpu_memory = []
        gpu_util = []
        gpu_power = []
        gpu_temp = []
        
        for run in runs:
            if run.get('status') == 'ok':
                metrics = run.get('resource_metrics', {})
                if metrics:
                    gpu_memory.append(metrics.get('gpu_memory_mean_mb', 0))
                    gpu_util.append(metrics.get('gpu_utilization_mean_pct', 0))
                    gpu_power.append(metrics.get('gpu_power_mean_watts', 0))
                    gpu_temp.append(metrics.get('gpu_temperature_mean_c', 0))
        
        if gpu_memory:
            print(f"{model_name.upper()}:")
            print(f"  GPU Memory: {statistics.mean(gpu_memory):.0f} MB (mean)")
            print(f"  GPU Utilization: {statistics.mean(gpu_util):.1f}% (mean)")
            print(f"  GPU Power: {statistics.mean(gpu_power):.1f} W (mean)")
            print(f"  GPU Temperature: {statistics.mean(gpu_temp):.1f}°C (mean)")
            print()

def analyze_all_scenarios():
    """Check if anomaly exists across all scenarios."""
    print("=" * 70)
    print("CROSS-SCENARIO ANALYSIS (PyTorch GPU)")
    print("=" * 70)
    print()
    
    models = ['gpt2-50m', 'gpt2-75m', 'gpt2-100m']
    scenarios = ['single_micro', 'single_short', 'single_medium', 'single_long', 'batch_short', 'batch_medium']
    
    for model in models:
        csv_path = Path(f"scripts/tr118/results/tr118v2_crossover/{model}/processed/latency_summary_prefill.csv")
        if not csv_path.exists():
            continue
        
        print(f"{model.upper()}:")
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
            for scenario in scenarios:
                pytorch = [r for r in rows if r['backend'] == 'transformers-gpu-compile' and r['scenario'] == scenario]
                if pytorch:
                    tps = float(pytorch[0]['throughput_mean_tok_s'])
                    lat = float(pytorch[0]['mean'])
                    print(f"  {scenario:15} {tps:7.0f} tok/s, {lat:6.2f} ms")
        print()

def main():
    """Main analysis."""
    models = {
        '50m': {
            'raw': Path('scripts/tr118/results/tr118v2_crossover/gpt2-50m/raw'),
            'model': Path('models/gpt2-50m'),
        },
        '75m': {
            'raw': Path('scripts/tr118/results/tr118v2_crossover/gpt2-75m/raw'),
            'model': Path('models/gpt2-75m'),
        },
        '100m': {
            'raw': Path('scripts/tr118/results/tr118v2_crossover/gpt2-100m/raw'),
            'model': Path('models/gpt2-100m'),
        },
    }
    
    models_data = {}
    
    for name, paths in models.items():
        # Load raw runs
        raw_files = list(paths['raw'].glob('bench_prefill_*.jsonl'))
        runs = []
        if raw_files:
            runs = load_jsonl(raw_files[0])
        
        # Filter for single_medium, transformers-gpu-compile
        filtered_runs = [
            r for r in runs
            if r.get('spec', {}).get('scenario') == 'single_medium' and
               r.get('spec', {}).get('backend') == 'transformers-gpu-compile'
        ]
        
        # Load model config
        config = load_model_config(paths['model'])
        
        models_data[name] = {
            'runs': filtered_runs,
            'config': config,
        }
    
    analyze_runs(models_data)
    analyze_model_configs(models_data)
    analyze_degradation(models_data)
    analyze_resource_metrics(models_data)
    analyze_all_scenarios()
    
    print("=" * 70)
    print("SUMMARY & RECOMMENDATIONS")
    print("=" * 70)
    print()
    print("Key findings:")
    print("1. Check if 100M has different architecture (layers/hidden)")
    print("2. Verify GPU resource metrics (memory, temp, throttling)")
    print("3. Compare variance across all scenarios")
    print("4. Check for compilation differences (torch.compile)")
    print("5. Consider re-running 100M benchmark")
    print()

if __name__ == "__main__":
    main()


