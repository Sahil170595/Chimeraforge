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
- Throughput: 120.95 tok/s
- TTFT: 563.08 ms
- Total Duration: 6221.65 ms
- Tokens Generated: 655
- Prompt Eval: 11.80 ms
- Eval Duration: 5415.49 ms
- Load Duration: 244.59 ms
