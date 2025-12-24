# Chimera Agent B

Model: gemma3:latest
Ollama URL: http://localhost:11434
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
- Throughput: 101.31 tok/s
- TTFT: 3987.13 ms
- Total Duration: 11139.75 ms
- Tokens Generated: 724
- Prompt Eval: 28.09 ms
- Eval Duration: 7146.71 ms
- Load Duration: 194.93 ms
