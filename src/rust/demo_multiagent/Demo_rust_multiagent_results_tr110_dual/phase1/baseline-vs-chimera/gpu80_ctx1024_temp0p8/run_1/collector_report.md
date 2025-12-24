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
- Throughput: 41.20 tok/s
- TTFT: 311.44 ms
- Total Duration: 9446.07 ms
- Tokens Generated: 365
- Prompt Eval: 18.60 ms
- Eval Duration: 8858.41 ms
- Load Duration: 285.70 ms
