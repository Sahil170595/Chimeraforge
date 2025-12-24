# Chimera Agent B

Model: gemma3:latest
Ollama URL: http://localhost:11435
Configuration: num_gpu=100, num_ctx=512, temp=1, top_p=default, top_k=default, repeat_penalty=default
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
- Throughput: 60.85 tok/s
- TTFT: 616.58 ms
- Total Duration: 12738.02 ms
- Tokens Generated: 708
- Prompt Eval: 14.16 ms
- Eval Duration: 11634.58 ms
- Load Duration: 272.11 ms
