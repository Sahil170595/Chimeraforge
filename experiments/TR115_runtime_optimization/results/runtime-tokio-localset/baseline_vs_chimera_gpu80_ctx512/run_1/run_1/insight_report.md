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
- Throughput: 53.66 tok/s
- TTFT: 7661.75 ms
- Total Duration: 20182.52 ms
- Tokens Generated: 645
- Prompt Eval: 34.71 ms
- Eval Duration: 12020.57 ms
- Load Duration: 7262.10 ms
