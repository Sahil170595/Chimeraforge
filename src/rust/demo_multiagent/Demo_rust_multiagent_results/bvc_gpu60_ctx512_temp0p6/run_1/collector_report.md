# Baseline Collector

Model: gemma3:latest
Ollama URL: http://localhost:11434
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
- Throughput: 97.18 tok/s
- TTFT: 15077.01 ms
- Total Duration: 19400.00 ms
- Tokens Generated: 417
- Prompt Eval: 372.80 ms
- Eval Duration: 4291.07 ms
- Load Duration: 14692.11 ms
