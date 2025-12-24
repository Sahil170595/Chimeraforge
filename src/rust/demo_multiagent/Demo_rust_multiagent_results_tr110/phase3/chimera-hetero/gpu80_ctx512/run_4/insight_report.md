# Chimera Agent B

Model: gemma3:latest
Ollama URL: http://localhost:11434
Configuration: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
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
- Throughput: 100.99 tok/s
- TTFT: 200.74 ms
- Total Duration: 6682.23 ms
- Tokens Generated: 654
- Prompt Eval: 13.62 ms
- Eval Duration: 6475.81 ms
- Load Duration: 184.57 ms
