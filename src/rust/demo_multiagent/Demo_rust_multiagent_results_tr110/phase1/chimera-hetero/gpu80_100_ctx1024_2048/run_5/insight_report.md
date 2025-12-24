# Chimera Agent B

Model: gemma3:latest
Ollama URL: http://localhost:11434
Configuration: num_gpu=100, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
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
- Throughput: 105.19 tok/s
- TTFT: 208.99 ms
- Total Duration: 991.04 ms
- Tokens Generated: 82
- Prompt Eval: 13.06 ms
- Eval Duration: 779.57 ms
- Load Duration: 193.38 ms
