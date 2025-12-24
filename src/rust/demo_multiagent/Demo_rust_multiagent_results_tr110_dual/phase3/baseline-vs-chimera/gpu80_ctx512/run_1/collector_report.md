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
- Throughput: 73.42 tok/s
- TTFT: 5544.83 ms
- Total Duration: 11246.59 ms
- Tokens Generated: 395
- Prompt Eval: 60.67 ms
- Eval Duration: 5379.72 ms
- Load Duration: 5446.71 ms
