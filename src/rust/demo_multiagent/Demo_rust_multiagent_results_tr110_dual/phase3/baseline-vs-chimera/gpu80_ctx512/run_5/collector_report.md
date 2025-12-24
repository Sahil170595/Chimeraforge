# Baseline Collector

Model: gemma3:latest
Ollama URL: http://127.0.0.1:11434
Configuration: Ollama defaults
Prompt:
```
You are DataCollector-9000, a systems analyst tasked with scanning benchmark artifacts.
Produce a concise data inventory with bullet points that highlight:
1. Directory coverage (reports/, csv_data/, artifacts/).
2. File counts per type (md, csv, json) and the latest modified timestamp you observe.
3. Any gaps or missing telemetry that could impact model evaluation.
Keep the response under 250 words but include concrete metrics so a second agent can reason over them.
```

## Metrics
- Throughput: 41.12 tok/s
- TTFT: 315.56 ms
- Total Duration: 9249.95 ms
- Tokens Generated: 357
- Prompt Eval: 30.57 ms
- Eval Duration: 8682.95 ms
- Load Duration: 280.18 ms
