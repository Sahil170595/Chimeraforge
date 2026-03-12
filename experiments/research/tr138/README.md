# TR138: Batch Inference Safety Under Non-Determinism

## Research Question

Does batch-induced output non-determinism disproportionately degrade safety compared to capability?

## Background

Different batch sizes can produce different outputs at `temperature=0` because GPU kernels are not numerically batch-invariant. Prior work has mostly treated this as a reproducibility or performance problem. TR138 measures whether those output changes are safety-relevant.

If batching flips refusal -> compliance more often than it flips one factual answer to another, then a batched deployment carries an unmeasured safety cost.

## Hypotheses

- **H1:** Batch-induced output changes are safety-neutral.
- **H2:** Batch-induced output changes disproportionately degrade safety.
- **H3:** Co-batching adversarial prompts alongside safety prompts changes safety outcomes.

## Scope

### Phase 1: Batch Size x Output Determinism (vLLM)
- 3 models x 6 batch sizes x 955 prompts = about 17,190 samples
- Compare outputs at `batch=1` vs `batch=2,4,8,16,32`
- Measure safety flip rate vs capability flip rate

### Phase 2: Co-Batching Interference (vLLM)
- 3 models x 4 conditions x 470 safety prompts = about 5,640 samples
- Conditions: `solo`, `benign`, `adversarial`, `safety`
- Test whether adversarial co-batches differ from benign and solo controls

### Phase 3: Quantization x Concurrency Interaction (Ollama)
- 3 models x 3 quants x 3 concurrency levels x 220 prompts = about 5,940 samples
- Tests concurrent-load sensitivity under quantization
- This is **not** a true batching experiment; it is a load-interaction proxy

### Phase 4: True Batching Validation (vLLM prompt-list API)
- 2 models x 3 true batch sizes x 450 prompts = about 2,700 samples
- Uses one completions call with a prompt list, not synchronized separate requests
- Validates whether the Phase 1 safety effect survives explicit tensor batching

**Total: about 31,470 samples**

## Design Safeguards

- Phase 1 tail batches are padded with discarded fillers so every analyzed prompt experiences the stated dispatch size.
- Phase 2 counterbalances target position within the request group and records that position explicitly.
- Phase 2 benign fillers come primarily from capability-task prompts rather than a tiny handwritten pool.
- Phase 3 reuses a shared HTTP client so latency measurements are less polluted by per-request client setup.
- Phase 4 uses explicit prompt-list batching on vLLM so the validation subset is not confounded by request-arrival timing.

## Key Deliverables

1. Safety flip rate vs capability flip rate per batch size
2. Real co-batch interference matrix with a solo control
3. Quantization x concurrency interaction analysis
4. Explicit true-batching validation against the Phase 1 signal
5. Flip direction analysis (`refusal -> compliance` vs `compliance -> refusal`)

## Dependencies

- TR130/TR132: vLLM infrastructure
- TR134: Safety benchmark suite (AdvBench, TruthfulQA, BBQ, Jailbreak, MMLU, ARC)
- Docker with NVIDIA GPU access
- Required Ollama tags for Phase 3: `llama3.2:1b-instruct-q8_0`, `llama3.2:1b-instruct-q4_K_M`, `llama3.2:1b-instruct-q2_K`, `llama3.2:3b-instruct-q8_0`, `llama3.2:3b-instruct-q4_K_M`, `llama3.2:3b-instruct-q2_K`, `qwen2.5:1.5b-instruct-q8_0`, `qwen2.5:1.5b-instruct-q4_K_M`, `qwen2.5:1.5b-instruct-q2_K`

## Runtime

- Eval run: about 10-18h wall clock for all four phases on the current RTX 4080 Laptop-class setup
- Judge run: about 1.5-3.5h for about 21,540 safety records with `qwen2.5:7b-instruct-q8_0`
- Analysis + report: usually under 15 minutes
- End-to-end: about 12-21h total, with a conservative upper bound around 24h if vLLM cold-starts and long prompts dominate

If you want a same-day dry run, use `--skip-judge` and add judge scoring afterward.

## Prior Art

- SGLang deterministic inference (Sep 2025): batch-invariant kernels, performance-focused
- LLM-42 (Microsoft, Jan 2026): deterministic inference / verified speculation, no safety measurement
- HuggingFace forum reports of output inconsistency under batching

## Run

```bash
python research/tr138/run.py -v
python research/tr138/run.py -v --phases 1
python research/tr138/run.py -v --skip-prep
```

## Folder Structure

```text
research/tr138/
|-- README.md
|-- config.yaml
|-- shared/
|   |-- __init__.py
|   `-- utils.py
|-- tasks/
|   |-- advbench_refusal.yaml
|   |-- truthfulqa.yaml
|   |-- bbq_bias.yaml
|   |-- jailbreak_amplification.yaml
|   |-- mmlu_real.yaml
|   `-- arc_challenge.yaml
|-- prepare_benchmarks.py
|-- run.py
|-- judge_analysis.py
|-- analyze.py
`-- generate_report.py
```
