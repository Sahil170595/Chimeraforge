# Chimera Agent B

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
- Throughput: 54.49 tok/s
- TTFT: 599.17 ms
- Total Duration: 12620.18 ms
- Tokens Generated: 630
- Prompt Eval: 14.39 ms
- Eval Duration: 11562.41 ms
- Load Duration: 266.44 ms
