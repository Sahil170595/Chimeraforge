# Chimera Agent B

Model: gemma3:latest
Ollama URL: http://localhost:11434
Configuration: num_gpu=120, num_ctx=1024, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.05
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
- Throughput: 100.74 tok/s
- TTFT: 3322.77 ms
- Total Duration: 4052.63 ms
- Tokens Generated: 70
- Prompt Eval: 245.61 ms
- Eval Duration: 694.84 ms
- Load Duration: 3067.04 ms
