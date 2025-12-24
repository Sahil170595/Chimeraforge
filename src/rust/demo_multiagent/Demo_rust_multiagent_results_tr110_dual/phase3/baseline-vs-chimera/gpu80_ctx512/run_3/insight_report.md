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
- Throughput: 56.73 tok/s
- TTFT: 316.51 ms
- Total Duration: 11976.59 ms
- Tokens Generated: 637
- Prompt Eval: 28.96 ms
- Eval Duration: 11229.55 ms
- Load Duration: 284.17 ms
