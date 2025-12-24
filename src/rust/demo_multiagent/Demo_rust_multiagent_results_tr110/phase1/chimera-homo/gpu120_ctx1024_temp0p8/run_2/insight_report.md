# Chimera Agent B

Model: gemma3:latest
Ollama URL: http://localhost:11434
Configuration: num_gpu=120, num_ctx=1024, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
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
- Throughput: 99.56 tok/s
- TTFT: 222.42 ms
- Total Duration: 6725.78 ms
- Tokens Generated: 647
- Prompt Eval: 24.93 ms
- Eval Duration: 6498.62 ms
- Load Duration: 192.62 ms
