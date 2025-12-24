# Chimera Insight

Model: gemma3:latest
Ollama URL: http://localhost:11434
Configuration: num_gpu=80, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
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
- Throughput: 97.58 tok/s
- TTFT: 3973.96 ms
- Total Duration: 10273.50 ms
- Tokens Generated: 611
- Prompt Eval: 377.23 ms
- Eval Duration: 6261.46 ms
- Load Duration: 3578.68 ms
