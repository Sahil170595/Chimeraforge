# Chimera Agent B

Model: gemma3:latest
Ollama URL: http://127.0.0.1:11435
Configuration: num_gpu=80, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
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
- Throughput: 54.99 tok/s
- TTFT: 285.67 ms
- Total Duration: 11798.29 ms
- Tokens Generated: 610
- Prompt Eval: 17.74 ms
- Eval Duration: 11093.49 ms
- Load Duration: 263.83 ms
