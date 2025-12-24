import json

import pandas as pd

# Load 11M model data
gpt11m_prefill = pd.read_csv('results/tr118v2/20251213_153314_gpt2_11m/gpt2-1m/processed/latency_summary_prefill.csv')
gpt11m_generate = pd.read_csv('results/tr118v2/20251213_153314_gpt2_11m/gpt2-1m/processed/latency_summary_generate.csv')

# Aggregate by backend (overall means)
print('=== GPT-2 11M (11.18M params) PREFILL RESULTS ===')
gpt11m_p_agg = gpt11m_prefill.groupby('backend')['throughput_mean_tok_s'].mean().sort_values(ascending=False)
for backend, tput in gpt11m_p_agg.items():
    print(f'{backend}: {tput:.0f} tok/s')

print('\n=== GPT-2 11M GENERATE RESULTS ===')
gpt11m_g_valid = gpt11m_generate[gpt11m_generate['degraded_rate'] < 1.0]
gpt11m_g_agg = gpt11m_g_valid.groupby('backend')['throughput_mean_tok_s'].mean().sort_values(ascending=False)
for backend, tput in gpt11m_g_agg.items():
    print(f'{backend}: {tput:.0f} tok/s')

# Calculate vs PyTorch baseline
print('\n=== ONNX CPU vs PyTorch (Prefill) ===')
onnx_cpu = gpt11m_p_agg['onnxruntime-cpu']
pytorch = gpt11m_p_agg['transformers-gpu-compile']
ratio = onnx_cpu / pytorch
print(f'ONNX CPU: {onnx_cpu:.0f} tok/s')
print(f'PyTorch:  {pytorch:.0f} tok/s')
print(f'Ratio: {ratio:.2f}x ({"ONNX wins" if ratio > 1 else "PyTorch wins"})')

# Load param count
with open('results/tr118v2/20251213_153314_gpt2_11m/gpt2-1m/processed/experiment_manifest_1765657995.json') as f:
    manifest = json.load(f)
    print(f"\nModel: {manifest['model']['name']}")
    print(f"Params: {manifest['model'].get('parameter_count', 'N/A')}")

