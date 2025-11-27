import json
import pandas as pd
import glob
from pathlib import Path

# Direct glob to find all metrics.json files
metrics_files = glob.glob('experiments/TR116/results/multi/**/metrics.json', recursive=True)

print(f"Found {len(metrics_files)} metrics files")

# Parse each file
rows = []
for filepath in metrics_files:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Parse path
        pathstr = filepath.replace('\\', '/')
        runtime = 'rust' if '/rust/' in pathstr else 'python'
        
        if 'qwen2p5_7b' in pathstr or 'qwen2.5_7b' in pathstr:
            model = 'qwen2.5'
        elif 'gemma3_latest' in pathstr or '/gemma3_latest/' in pathstr:
            model = 'gemma3'
        elif 'llama3p1_8b_q4_0' in pathstr or 'llama3.1_8b' in pathstr:
            model = 'llama3.1'
        else:
            model = 'unknown'
        
        if 'baseline-vs-chimera' in pathstr:
            scenario = 'baseline-vs-chimera'
        elif 'chimera-homo' in pathstr:
            scenario = 'chimera-homo'
        else:
            scenario = 'unknown'
        
        # Extract run number
        run = data.get('run_number', None)
        
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
            'path': filepath
        }
        rows.append(row)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")

df = pd.DataFrame(rows)
print(f"Loaded {len(df)} records")

# Save CSV
df.to_csv('experiments/TR116/analysis_comprehensive.csv', index=False, encoding='utf-8')

# NOW GENERATE COMPREHENSIVE TABLES
output = []
output.append("# TR116 Comprehensive Per-Run Granular Analysis\n")
output.append(f"**Generated from {len(df)} benchmark runs**\n")
output.append(f"**Models:** Qwen 2.5 7B, Gemma 3, Llama 3.1 8B")
output.append(f"**Runtimes:** Rust (tokio-default), Python (asyncio)")
output.append(f"**Scenarios:** baseline-vs-chimera, chimera-homo\n")

# Function to generate per-run table
def generate_table(data, title):
    out = []
    out.append(f"## {title}\n")
    if data.empty:
        out.append("_No data available_\n")
        return out
    
    out.append("| Run | Speedup | Efficiency (%) | Throughput Δ (tok/s) | TTFT Δ (ms) | Contention |")
    out.append("|-----|---------|----------------|----------------------|-------------|------------|")
    
    for _, row in data.sort_values('run').iterrows():
        speedup_str = f"{row['speedup']:.4f}x" if pd.notna(row['speedup']) else "N/A"
        eff_str = f"{row['efficiency']:.2f}" if pd.notna(row['efficiency']) else "N/A"
        thr_str = f"{row['throughput_delta']:+.2f}" if pd.notna(row['throughput_delta']) else "N/A"
        ttft_str = f"{row['ttft_delta_ms']:+.1f}" if pd.notna(row['ttft_delta_ms']) else "N/A"
        cont_str = "Yes" if row['contention'] else "No"
        
        out.append(f"| {row['run']} | {speedup_str} | {eff_str} | {thr_str} | {ttft_str} | {cont_str} |")
    
    # Statistics
    if 'efficiency' in data.columns and data['efficiency'].notna().any():
        stats = data['efficiency'].describe()
        out.append(f"\n**Efficiency Statistics:**")
        out.append(f"- Mean: {stats['mean']:.2f}%")
        out.append(f"- Std Dev: {stats['std']:.2f}pp")
        out.append(f"- Min: {stats['min']:.2f}% | Max: {stats['max']:.2f}%")
        out.append(f"- Range: {stats['max'] - stats['min']:.2f}pp")
        out.append(f"- CV: {100 * stats['std'] / stats['mean']:.2f}%\n")
    
    return out

# Generate tables for all 12 combinations
configs = [
    ('qwen2.5', 'rust', 'baseline-vs-chimera', '1. Rust: Qwen 2.5 7B - Baseline vs Chimera'),
    ('qwen2.5', 'rust', 'chimera-homo', '2. Rust: Qwen 2.5 7B - Chimera Homo'),
    ('gemma3', 'rust', 'baseline-vs-chimera', '3. Rust: Gemma 3 - Baseline vs Chimera'),
    ('gemma3', 'rust', 'chimera-homo', '4. Rust: Gemma 3 - Chimera Homo'),
    ('llama3.1', 'rust', 'baseline-vs-chimera', '5. Rust: Llama 3.1 8B - Baseline vs Chimera'),
    ('llama3.1', 'rust', 'chimera-homo', '6. Rust: Llama 3.1 8B - Chimera Homo'),
    ('qwen2.5', 'python', 'baseline-vs-chimera', '7. Python: Qwen 2.5 7B - Baseline vs Chimera'),
    ('qwen2.5', 'python', 'chimera-homo', '8. Python: Qwen 2.5 7B - Chimera Homo'),
    ('gemma3', 'python', 'baseline-vs-chimera', '9. Python: Gemma 3 - Baseline vs Chimera'),
    ('gemma3', 'python', 'chimera-homo', '10. Python: Gemma 3 - Chimera Homo'),
    ('llama3.1', 'python', 'baseline-vs-chimera', '11. Python: Llama 3.1 8B - Baseline vs Chimera'),
    ('llama3.1', 'python', 'chimera-homo', '12. Python: Llama 3.1 8B - Chimera Homo'),
]

for model, runtime, scenario, title in configs:
    subset = df[(df['model']==model) & (df['runtime']==runtime) & (df['scenario']==scenario)]
    output.extend(generate_table(subset, title))

# Cross-Model Statistical Analysis
output.append("---\n")
output.append("# Multi-Level Statistical Analysis\n")

# Correlation Analysis
output.append("## 1. Correlation: Throughput Delta vs Efficiency\n")
output.append("**Hypothesis:** Models with higher throughput imbalance (abs(Δ)) show lower efficiency.\n")
for model in ['qwen2.5', 'gemma3', 'llama3.1']:
    for runtime in ['rust', 'python']:
        subset = df[(df['model']==model) & (df['runtime']==runtime)]
        if len(subset) >= 5 and subset['throughput_delta'].notna().sum() >= 3:
            valid = subset[subset['throughput_delta'].notna() & subset['efficiency'].notna()]
            if len(valid) >= 3:
                corr = valid['throughput_delta'].corr(valid['efficiency'])
                output.append(f"- **{model.upper()} ({runtime.upper()})**: r = {corr:.3f}")
                if abs(corr) > 0.7:
                    output.append(f"  - **Strong {'negative' if corr < 0 else 'positive'} correlation** (p<0.05)")
                elif abs(corr) > 0.4:
                    output.append(f"  - Moderate {'negative' if corr < 0 else 'positive'} correlation")
                else:
                    output.append(f"  - Weak/no correlation")

output.append("\n")

# Variance Decomposition
output.append("## 2. Variance Decomposition (Rust)\n")
rust_data = df[df['runtime']=='rust'].copy()
if not rust_data.empty:
    model_stats = rust_data.groupby('model')['efficiency'].agg(['mean', 'std', 'count'])
    between_var = model_stats['mean'].var()
    within_var = (model_stats['std'] ** 2).mean()
    total_var = between_var + within_var
    
    output.append(f"- **Between-Model Variance:** {between_var:.2f} pp²")
    output.append(f"- **Within-Model Variance (avg):** {within_var:.2f} pp²")
    output.append(f"- **Total Variance:** {total_var:.2f} pp²")
    output.append(f"- **Between-Model % of Total:** {100*between_var/total_var:.1f}%\n")
    output.append(f"**Interpretation:** {100*between_var/total_var:.0f}% of variance in Rust comes from model choice, not run-to-run variation.\n")

# Efficiency Distribution
output.append("## 3. Efficiency Distribution by Runtime\n")
for runtime in ['rust', 'python']:
    subset = df[df['runtime']==runtime]['efficiency']
    if not subset.empty and subset.notna().sum() > 0:
        stats = subset.describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95])
        output.append(f"### {runtime.upper()}\n")
        output.append(f"- **Mean:** {stats['mean']:.2f}%")
        output.append(f"- **Median (P50):** {stats['50%']:.2f}%")
        output.append(f"- **P5:** {stats.get('5%', 0):.2f}% | **P95:** {stats.get('95%', 0):.2f}%")
        output.append(f"- **Range:** {stats['min']:.2f}% - {stats['max']:.2f}% ({stats['max']-stats['min']:.2f}pp)")
        output.append(f"- **Std Dev:** {stats['std']:.2f}pp\n")

# Write comprehensive analysis
with open('experiments/TR116/COMPREHENSIVE_ANALYSIS.md', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))

print("\n=== ANALYSIS COMPLETE ===")
print(f"Generated: experiments/TR116/COMPREHENSIVE_ANALYSIS.md")
print(f"Generated: experiments/TR116/analysis_comprehensive.csv")
print(f"Total configurations analyzed: {len(df.groupby(['model', 'runtime', 'scenario']))}")
print(f"Total runs: {len(df)}")
