# TR117 Readiness & Requirements

This doc captures what is needed to run the TR117 investigations on this laptop and how to execute each pathway.

## Environment Requirements
- GPU + NVIDIA driver (verified via `nvidia-smi`).
- Python deps: `httpx`, `transformers`, `pandas`, `numpy` (already installed).  
  - Profiler uses the `py-spy` CLI (installed: `py-spy --version` works; it is a binary-only tool, no importable module).
- Ollama dual endpoints running on localhost (collector `11434`, insight `11435`) with the target models pulled (`gemma3:latest`, `qwen2.5:7b`, `llama3.1:8b-instruct-q4_0`).
- Optional: Hugging Face tokenizers cached locally. The tokenizer bench defaults to `local_files_only`; pass `--allow-download` to fetch if needed.

## Artifacts & Scripts
- `experiments/TR117/PRD.md` - plan and success criteria.
- Scripts: `experiments/TR117/scripts/`
  - `profiler_agent.py` - Python MRI (loop lag + chunk metrics). Supports `--read-buffer-size` A/B.
  - `dmon_wrapper.py` - GPU logging wrapper. Tries `nvidia-smi -lms 100`, falls back to a 100 ms polling loop if unsupported.
  - `bench_tokenizer.py` - tokenizer micro-bench (CPU-only). Local-only by default; use `--allow-download` to pull from HF.
  - `throttled_agent.py` - token-bucket throttling for flow-dynamics A/B.
  - `run_tr117_suite.py` - orchestrates the suite (defaults to the 25-run plan when a hardware template is supplied).
- Results root: `experiments/TR117/results/` (pre-created with `.gitkeep`).

## Quick Checks (completed)
- `nvidia-smi` reachable (RTX 4080 visible).
- `py-spy --version` -> 0.4.1 (CLI available).
- Python imports: `httpx`, `transformers`, `pandas`, `numpy` OK. `py_spy` import fails by design (binary tool).

## How to Run (minimal smoke)
1) Python MRI (default buffer):
```
python experiments/TR117/scripts/profiler_agent.py \
  --model gemma3:latest \
  --runs 1 \
  --scenario chimera_homo \
  --output-dir experiments/TR117/results/phase1/default
```
2) Python MRI (64KB buffer A/B):
```
python experiments/TR117/scripts/profiler_agent.py \
  --model gemma3:latest \
  --runs 1 \
  --scenario chimera_homo \
  --read-buffer-size 65536 \
  --output-dir experiments/TR117/results/phase1/buf64k
```
3) Throttle test (60 tok/s):
```
python experiments/TR117/scripts/throttled_agent.py \
  --model gemma3:latest \
  --runs 1 \
  --throttle-rate 60 \
  --output-dir experiments/TR117/results/phase3/60tps
```
4) GPU logging wrapper (replace CMD with your dual-agent run):
```
python experiments/TR117/scripts/dmon_wrapper.py \
  --output-dir experiments/TR117/results/phase2/gemma \
  -- your_benchmark_command_here
```
5) Tokenizer bench (local-only; add --allow-download if needed):
```
python experiments/TR117/scripts/bench_tokenizer.py \
  --bytes 1048576 \
  --iterations 3 \
  --output-dir experiments/TR117/results/phase2/tokenizers
```

## Notes / Caveats
- Ensure Ollama endpoints are live before running MRI/throttle scripts; they stream from `/api/generate`.
- Token counting in `throttled_agent.py` uses `response` fields per chunk as token proxies (approximate but sufficient for throttling A/B).
- `dmon_wrapper.py` writes `gpu_metrics.csv`; if `-lms` is unsupported, it falls back automatically to polling.
- Large HF downloads are avoided unless `--allow-download` is passed.

## Next Actions
- Install/confirm any missing model pulls in Ollama.
- Run one MRI and one throttle A/B to verify end-to-end metrics capture.
