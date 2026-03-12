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
- Throughput: 101.09 tok/s
- TTFT: 206.03 ms
- Total Duration: 4007.37 ms
- Tokens Generated: 384
- Prompt Eval: 12.51 ms
- Eval Duration: 3798.77 ms
- Load Duration: 181.88 ms
