# Chimera Insight

Model: gemma3:latest
Ollama URL: http://localhost:11434
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
- Throughput: 97.96 tok/s
- TTFT: 8485.28 ms
- Total Duration: 15211.35 ms
- Tokens Generated: 656
- Prompt Eval: 456.14 ms
- Eval Duration: 6696.35 ms
- Load Duration: 7990.54 ms
