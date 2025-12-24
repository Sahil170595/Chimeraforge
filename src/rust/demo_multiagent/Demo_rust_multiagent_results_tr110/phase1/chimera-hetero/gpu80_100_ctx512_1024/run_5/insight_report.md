# Chimera Agent B

Model: gemma3:latest
Ollama URL: http://localhost:11434
Configuration: num_gpu=100, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
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
- Throughput: 101.11 tok/s
- TTFT: 10008.92 ms
- Total Duration: 16343.76 ms
- Tokens Generated: 638
- Prompt Eval: 240.72 ms
- Eval Duration: 6309.95 ms
- Load Duration: 9764.88 ms
