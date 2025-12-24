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
- Throughput: 48.60 tok/s
- TTFT: 604.76 ms
- Total Duration: 13726.30 ms
- Tokens Generated: 616
- Prompt Eval: 14.23 ms
- Eval Duration: 12673.79 ms
- Load Duration: 265.46 ms
