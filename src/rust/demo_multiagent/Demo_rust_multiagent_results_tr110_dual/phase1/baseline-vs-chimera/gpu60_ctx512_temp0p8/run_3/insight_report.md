# Chimera Insight

Model: gemma3:latest
Ollama URL: http://127.0.0.1:11435
Configuration: num_gpu=60, num_ctx=512, temp=0.8, top_p=0.9, top_k=40, repeat_penalty=1.1
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
- Throughput: 50.94 tok/s
- TTFT: 306.90 ms
- Total Duration: 12890.73 ms
- Tokens Generated: 618
- Prompt Eval: 27.61 ms
- Eval Duration: 12131.03 ms
- Load Duration: 276.07 ms
