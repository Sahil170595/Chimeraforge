# Ollama Prompt Suite Lessons  2025-10-02

## Context
- Benchmarked three local llam3.1 instruct quantizations (`q4_0`, `q5_K_M`, `q8_0`) using `scripts/ollama/run_prompt_suite.py`.
- Prompt set: `prompts/banter_prompts.txt` (5 gameplay scenarios).
- Runtime options: `temperature=0.3`, `top_p=0.9`, HTTP host forced to `http://127.0.0.1:11434` to bypass the default `0.0.0.0` binding.
- Artifacts: `reports/ollama/20251002-151824/prompt_suite_runs.csv` and `.../prompt_suite_summary.json`.

## Key Metrics (mean across 5 prompts)
| Model Tag | Mean TTFT (s) | Mean Tokens/s | Notes |
| --------- | ------------- | ------------- | ----- |
| `llama3.1:8b-instruct-q4_0` | **0.651** | **77.62** | Warm-up hit first prompt (2.86 s); subsequent calls stayed =0.14 s TTFT. |
| `llama3.1:8b-instruct-q5_K_M` | 1.551 | 65.11 | Higher load/prompt-eval costs, throughput ~16% lower than q4_0. |
| `llama3.1:8b-instruct-q8_0` | 2.006 | 46.40 | Throughput ~40% lower than q4_0; not competitive for current prompts. |

## Operational Lessons
1. **Host configuration matters**  the Windows Ollama service exposes `localhost` but the Python client defaults to `http://0.0.0.0:11434`, which is invalid for outbound requests. The revamped script now normalises `OLLAMA_HOST` and provides a `--host` override to avoid silent failures.
2. **REST > SDK for resilience**  Direct `httpx` calls yield clearer error messages (WinError 10049, missing protocol) than the `ollama` Python package, speeding up troubleshooting.
3. **First-call warm-up remains a bottleneck**  each quantization showed a multi-second TTFT on the first prompt (engine load). A single warm-up invocation should precede production traffic.
4. **q4_0 still leads**  despite the warm-up spike, q4_0 sustained ~77.6 tok/s, validating prior recommendations; q5_K_M offers no quality-compensating speed benefit, and q8_0 is substantially slower.
5. **Script ergonomics**  `scripts/ollama/run_prompt_suite.py` now:
   - Normalises host strings.
   - Emits both CSV and JSON with options embedded per row.
   - Accepts dynamic option/host overrides for future sweeps.
6. **Failure artifacts retained**  earlier timestamped folders (`20251002-151204`, `...151446`, `...151615`) document the connection issues; keep them for RCA or prune once notes are captured.

## Suggested Next Actions
- Automate a warm-up request in any benchmark or production start sequence to mask TTFT spikes.
- Extend the prompt suite to cover longer contexts (`--options num_ctx=2048`) to observe throughput curvature.
- Add GPU telemetry capture (power/utilisation) alongside the prompt runs to correlate throughput with hardware behaviour.
- If higher-quality outputs are essential, consider q5_K_M only with targeted prompts to justify the slower TTFT.

---
Generated: 2025-10-02 19:18 UTC by `scripts/ollama/run_prompt_suite.py`.
