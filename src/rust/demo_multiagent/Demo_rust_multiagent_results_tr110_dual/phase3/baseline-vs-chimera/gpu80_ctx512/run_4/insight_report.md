# Chimera Insight

Model: gemma3:latest
Ollama URL: http://127.0.0.1:11435
Configuration: num_gpu=80, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
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
- Throughput: 42.20 tok/s
- TTFT: 310.84 ms
- Total Duration: 1533.05 ms
- Tokens Generated: 50
- Prompt Eval: 28.70 ms
- Eval Duration: 1184.88 ms
- Load Duration: 278.58 ms
