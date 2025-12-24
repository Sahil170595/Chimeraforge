# Chimera Insight

Model: gemma3:latest
Ollama URL: http://localhost:11434
Configuration: num_gpu=80, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
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
- Throughput: 97.63 tok/s
- TTFT: 8313.38 ms
- Total Duration: 14833.89 ms
- Tokens Generated: 633
- Prompt Eval: 415.74 ms
- Eval Duration: 6483.91 ms
- Load Duration: 7851.44 ms
