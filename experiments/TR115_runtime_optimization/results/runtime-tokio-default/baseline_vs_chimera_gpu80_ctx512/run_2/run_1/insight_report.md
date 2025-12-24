# Chimera Insight

Model: gemma3:latest
Ollama URL: http://localhost:11435
Configuration: num_gpu=80, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
Prompt:
```
You are InsightAgent, a Chimera-optimised LLM operations specialist.
Given the repository context described previously, produce:
1. Executive summary of model performance.
2. Three optimisation recommendations that balance throughput, TTFT, and quality.
3. A risk/mitigation table with at least two rows.
Aim for 300-400 words, with numbered sections and bolded metric callouts.
```

## Metrics
- Throughput: 54.82 tok/s
- TTFT: 615.87 ms
- Total Duration: 12619.90 ms
- Tokens Generated: 633
- Prompt Eval: 12.29 ms
- Eval Duration: 11546.11 ms
- Load Duration: 283.91 ms
