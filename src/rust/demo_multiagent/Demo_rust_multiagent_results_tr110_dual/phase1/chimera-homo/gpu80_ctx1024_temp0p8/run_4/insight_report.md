# Chimera Agent B

Model: gemma3:latest
Ollama URL: http://127.0.0.1:11435
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
- Throughput: 56.01 tok/s
- TTFT: 280.95 ms
- Total Duration: 12472.23 ms
- Tokens Generated: 658
- Prompt Eval: 15.26 ms
- Eval Duration: 11747.81 ms
- Load Duration: 261.23 ms
