# Chimera Agent B

Model: gemma3:latest
Ollama URL: http://127.0.0.1:11435
Configuration: num_gpu=100, num_ctx=2048, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.05
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
- Throughput: 57.35 tok/s
- TTFT: 273.09 ms
- Total Duration: 12576.55 ms
- Tokens Generated: 677
- Prompt Eval: 14.19 ms
- Eval Duration: 11804.54 ms
- Load Duration: 255.56 ms
