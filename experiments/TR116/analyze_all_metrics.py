import json
import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict

# Load all extracted metrics
with open('experiments/TR116/all_metrics_extracted.json', 'r', encoding='utf-8') as f:
    all_data = json.load(f)

# Parse paths to extract: model, runtime, scenario, run
def parse_path(path_str):
    parts = path_str.split('\\')
    runtime = 'rust' if 'rust' in path_str else 'python'
    
    # Find model
    if 'qwen2p5_7b' in path_str or 'qwen2.5_7b' in path_str:
        model = 'qwen2.5'
    elif 'gemma3_latest' in path_str or 'gemma3_latest' in path_str:
        model = 'gemma3'
    elif 'llama3p1_8b_q4_0' in path_str or 'llama3.1_8b' in path_str:
        model = 'llama3.1'
    else:
        model = 'unknown'
    
    # Find scenario
    if 'baseline-vs-chimera' in path_str:
        scenario = 'baseline-vs-chimera'
    elif 'chimera-homo' in path_str:
        scenario = 'chimera-homo'
    else:
        scenario = 'unknown'
    
    # Find run number
    run = None
    for part in parts:
        if part.startswith('run_'):
            run = int(part.split('_')[1])
            break
    
    return model, runtime, scenario, run

# Extract all metrics into structured format
rows = []
for item in all_data:
    path = item['Path']
    data = item['Data']
    
    model, runtime, scenario, run = parse_path(path)
    
    row = {
        'model': model,
        'runtime': runtime,
        'scenario': scenario,
        'run': run,
        'speedup': data.get('concurrency_speedup'),
        'efficiency': data.get('efficiency_percent'),
        'throughput_delta': data.get('throughput_delta'),
        'ttft_delta_ms': data.get('ttft_delta_ms'),
        'contention': data.get('resource_contention_detected', False),
        'path': path
    }
    rows.append(row)

df = pd.DataFrame(rows)

# Save to CSV for inspection
df.to_csv('experiments/TR116/analysis_comprehensive.csv', index=False)

# Generate comprehensive markdown tables
output = []

output.append("# TR116 Comprehensive Per-Run Analysis")
output.append("## Generated from 60 benchmark runs\n")

# Table 1: Rust Qwen Baseline-vs-Chimera Per-Run
output.append("## 1. Rust: Qwen 2.5 7B - Baseline vs Chimera (Per-Run)\n")
rust_qwen_base = df[(df['model']=='qwen2.5') & (df['runtime']=='rust') & (df['scenario']=='baseline-vs-chimera')]
if not rust_qwen_base.empty:
    output.append("| Run | Speedup | Efficiency (%) | Throughput Δ (tok/s) | TTFT Δ (ms) | Contention |")
    output.append("|-----|---------|----------------|----------------------|-------------|------------|")
    for _, row in rust_qwen_base.sort_values('run').iterrows():
        output.append(f"| {row['run']} | {row['speedup']:.4f}x | {row['efficiency']:.2f}% | {row['throughput_delta']:+.2f} | {row['ttft_delta_ms']:+.2f} | {'Yes' if row['contention'] else 'No'} |")
    
    stats = rust_qwen_base['efficiency'].describe()
    output.append(f"\n**Statistics:** Mean={stats['mean']:.2f}%, Std={stats['std']:.2f}pp, Min={stats['min']:.2f}%, Max={stats['max']:.2f}%\n")

# Table 2: Rust Qwen Chimera-Homo Per-Run
output.append("## 2. Rust: Qwen 2.5 7B - Chimera Homo (Per-Run)\n")
rust_qwen_homo = df[(df['model']=='qwen2.5') & (df['runtime']=='rust') & (df['scenario']=='chimera-homo')]
if not rust_qwen_homo.empty:
    output.append("| Run | Speedup | Efficiency (%) | Throughput Δ (tok/s) | TTFT Δ (ms) | Contention |")
    output.append("|-----|---------|----------------|----------------------|-------------|------------|")
    for _, row in rust_qwen_homo.sort_values('run').iterrows():
        output.append(f"| {row['run']} | {row['speedup']:.4f}x | {row['efficiency']:.2f}% | {row['throughput_delta']:+.2f} | {row['ttft_delta_ms']:+.2f} | {'Yes' if row['contention'] else 'No'} |")
    
    stats = rust_qwen_homo['efficiency'].describe()
    output.append(f"\n**Statistics:** Mean={stats['mean']:.2f}%, Std={stats['std']:.2f}pp, Min={stats['min']:.2f}%, Max={stats['max']:.2f}%\n")

# Table 3: Rust Gemma Baseline-vs-Chimera
output.append("## 3. Rust: Gemma 3 - Baseline vs Chimera (Per-Run)\n")
rust_gemma_base = df[(df['model']=='gemma3') & (df['runtime']=='rust') & (df['scenario']=='baseline-vs-chimera')]
if not rust_gemma_base.empty:
    output.append("| Run | Speedup | Efficiency (%) | Throughput Δ (tok/s) | TTFT Δ (ms) | Contention |")
    output.append("|-----|---------|----------------|----------------------|-------------|------------|")
    for _, row in rust_gemma_base.sort_values('run').iterrows():
        output.append(f"| {row['run']} | {row['speedup']:.4f}x | {row['efficiency']:.2f}% | {row['throughput_delta']:+.2f} | {row['ttft_delta_ms']:+.2f} | {'Yes' if row['contention'] else 'No'} |")
    
    stats = rust_gemma_base['efficiency'].describe()
    output.append(f"\n**Statistics:** Mean={stats['mean']:.2f}%, Std={stats['std']:.2f}pp, Min={stats['min']:.2f}%, Max={stats['max']:.2f}%\n")

# Table 4: Rust Gemma Chimera-Homo
output.append("## 4. Rust: Gemma 3 - Chimera Homo (Per-Run)\n")
rust_gemma_homo = df[(df['model']=='gemma3') & (df['runtime']=='rust') & (df['scenario']=='chimera-homo')]
if not rust_gemma_homo.empty:
    output.append("| Run | Speedup | Efficiency (%) | Throughput Δ (tok/s) | TTFT Δ (ms) | Contention |")
    output.append("|-----|---------|----------------|----------------------|-------------|------------|")
    for _, row in rust_gemma_homo.sort_values('run').iterrows():
        output.append(f"| {row['run']} | {row['speedup']:.4f}x | {row['efficiency']:.2f}% | {row['throughput_delta']:+.2f} | {row['ttft_delta_ms']:+.2f} | {'Yes' if row['contention'] else 'No'} |")
    
    stats = rust_gemma_homo['efficiency'].describe()
    output.append(f"\n**Statistics:** Mean={stats['mean']:.2f}%, Std={stats['std']:.2f}pp, Min={stats['min']:.2f}%, Max={stats['max']:.2f}%\n")

# Continue for all 12 configurations...
# Table 5-6: Rust Llama
# Table 7-12: Python (all 3 models × 2 scenarios)

# Correlation Analysis
output.append("## Statistical Correlation Analysis\n")
output.append("### Throughput Delta vs Efficiency (All Models, Rust)\n")
rust_data = df[df['runtime']=='rust'].copy()
if not rust_data.empty and 'throughput_delta' in rust_data.columns:
    for model in ['qwen2.5', 'gemma3', 'llama3.1']:
        model_data = rust_data[rust_data['model']==model]
        if len(model_data) >= 5:
            corr = model_data[['throughput_delta', 'efficiency']].corr().iloc[0,1]
            output.append(f"- **{model.upper()}**: Correlation = {corr:.3f}")
            output.append(f"  - Interpretation: {'Strong negative' if corr < -0.7 else 'Moderate negative' if corr < -0.4 else 'Weak' if abs(corr) < 0.3 else 'Moderate positive' if corr < 0.7 else 'Strong positive'}")

# Variance decomposition
output.append("\n### Variance Decomposition\n")
rust_eff = rust_data.groupby('model')['efficiency'].agg(['mean', 'std'])
between_model_var = rust_eff['mean'].var()
within_model_var = rust_eff['std'].mean() ** 2
total_var = between_model_var + within_model_var
output.append(f"**Rust:**")
output.append(f"- Between-Model Variance: {between_model_var:.2f} pp²")
output.append(f"- Within-Model Variance: {within_model_var:.2f} pp²")
output.append(f"- Between-Model as % of Total: {100*between_model_var/total_var:.1f}%")

# Write output
with open('experiments/TR116/COMPREHENSIVE_ANALYSIS.md', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))

print("Analysis complete! Generated:")
print("- experiments/TR116/analysis_comprehensive.csv")
print("- experiments/TR116/COMPREHENSIVE_ANALYSIS.md")
print(f"Total runs analyzed: {len(df)}")
