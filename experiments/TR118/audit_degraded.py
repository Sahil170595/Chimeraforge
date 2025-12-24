import json

# Check GPT-2 generate degraded by backend
path = 'results/tr118v2/20251213_135135_deep/gpt2/raw/bench_generate_1765652089.jsonl'
with open(path) as f:
    runs = [json.loads(line.strip()) for line in f if line.strip()]

backends_degraded = {}
for r in runs:
    backend = r.get('spec', {}).get('backend')
    status = r.get('status')
    degraded_count = r.get('degraded_count', 0)

    if backend not in backends_degraded:
        backends_degraded[backend] = {'total': 0, 'ok': 0, 'degraded': 0}

    backends_degraded[backend]['total'] += 1
    if status == 'ok' and degraded_count == 0:
        backends_degraded[backend]['ok'] += 1
    else:
        backends_degraded[backend]['degraded'] += 1

print('GPT-2 Generate Mode Degraded Status:')
for backend, counts in sorted(backends_degraded.items()):
    rate = counts['degraded'] / counts['total'] * 100 if counts['total'] > 0 else 0
    print(f'  {backend}: {counts["degraded"]}/{counts["total"]} degraded ({rate:.0f}%)')

