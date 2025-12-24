# Chimera Insight

Model: gemma3:latest
Ollama URL: http://localhost:11434
Configuration: num_gpu=120, num_ctx=512, temp=0.6, top_p=0.9, top_k=40, repeat_penalty=1.1
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
- Throughput: 97.45 tok/s
- TTFT: 3990.11 ms
- Total Duration: 10781.91 ms
- Tokens Generated: 659
- Prompt Eval: 304.87 ms
- Eval Duration: 6762.63 ms
- Load Duration: 3667.21 ms
