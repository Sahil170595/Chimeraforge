# PRD: TR116 Cross-Model Benchmarks (Qwen 2.5 vs Gemma 3 vs Local Baseline)

## Goal
Extend Chimeraforge coverage beyond Gemma by benchmarking multiple locally runnable models (Qwen 2.5 7B, Gemma 3, and Llama 3.1 8B q4_0) across the full single- and multi-agent suites in both Python and Rust. Produce a publish-ready Technical Report 116 that answers whether model choice materially shifts single-agent performance and multi-agent efficiency when architecture and configs are held constant.

## Objectives
- Quantify per-model single-agent throughput, TTFT, latency, and consistency using TR111/112 parity configs.
- Quantify per-model dual-Ollama multi-agent efficiency and contention using TR110/114 parity configs.
- Document VRAM/quant trade-offs and any config downgrades required on 12GB GPUs.
- Deliver reproducible artifacts, summaries, and a TR116 report with recommendations.

## Scope
- Models: `qwen2.5:7b` (primary), `gemma3:latest` (baseline), `llama3.1:8b-instruct-q4_0` (local comparator). If VRAM allows, note optional `qwen2.5:14b` attempt; fall back if OOM.
- Bench types: Python single-agent, Rust single-agent, Python multi-agent (dual Ollama), Rust multi-agent (dual Ollama).
- Scenarios (multi-agent): `baseline_vs_chimera`, `chimera_homo`.
- Metrics: throughput, TTFT, latency (p50/p95), concurrency speedup/efficiency, contention flag, wall time; optional tokens-per-dollar and power sampling if available.

### Out of Scope
- Async runtime variants (covered in TR115).
- Additional models requiring >12GB VRAM unless remote GPU is provided.
- Quality evaluation of outputs (semantic quality).

## Constraints and Assumptions
- Hardware: RTX 4080 12GB; use quantized models where needed. Expect Qwen 2.5 14B to be impractical locally.
- Architecture: dual Ollama instances (ports 11434, 11435) for all multi-agent runs.
- Repetition: 3–5 runs per config per model; minimum 3 if time-boxed.
- Runtimes: Rust uses tokio-default only.

## Success Criteria
- Complete run matrix for all three models across single-agent (Python, Rust) and multi-agent (Python, Rust) with >=3 runs each.
- Per-run metrics.json and per-config summary.md generated with model/config metadata.
- Comparative tables showing per-model deltas for single-agent and multi-agent metrics.
- TR116 report drafted in `outputs/publish_ready/reports/Technical_Report_116.md` with reproducibility pointers.

## Deliverables
- Raw outputs: `experiments/TR116/results/single/{python|rust}/{model_slug}/...`
- Raw outputs: `experiments/TR116/results/multi/{python|rust}/{model_slug}/...`
- Optional large sweeps: `benchmarks/{python|rust}/tr116_{model_slug}/...`
- Report: `outputs/publish_ready/reports/Technical_Report_116.md`
- Any validation logs produced by reused TR111/114 scripts.

## Methodology
### Single-Agent Configs (per model, Python and Rust)
- GPU layers: 60, 80
- Context: 512, 1024
- Temperature: 0.8
- Runs: 5 (or 3 if constrained)
- Output dir template: `experiments/TR116/results/single/{lang}/{model_slug}/gpu{g}_ctx{c}_temp08`

### Multi-Agent Configs (per model, Python and Rust)
- Scenarios: `baseline_vs_chimera`, `chimera_homo`
- Python Chimera: GPU 80, CTX 2048, TEMP 1.0
- Rust Chimera: GPU 80, CTX 512, TEMP 1.0 (tokio-default)
- Dual Ollama URLs: collector -> 11434, insight -> 11435
- Runs: 3–5
- Output dir template: `experiments/TR116/results/multi/{lang}/{model_slug}/{scenario}_...`

### Models and VRAM Notes
- `qwen2.5:7b`: primary; should fit 12GB with Q4_K_M style quant (default pull is fine).
- `gemma3:latest`: baseline from prior TRs (Ollama “gemma3” naming; distinct from Gemma 2).
- `llama3.1:8b-instruct-q4_0`: local comparator; slower than Gemma per prior notes but included for grounding.
- If `qwen2.5:14b` is attempted and OOMs, document failure and rationale in the report.

### Pre-flight Checks
- Verify quant and model metadata before runs:
  - `ollama show qwen2.5:7b --modelfile`
  - `ollama show gemma3:latest --modelfile`
  - `ollama show llama3.1:8b-instruct-q4_0 --modelfile`
- Confirm dual Ollama services up on 11434/11435.

### Metrics to Collect
- Single-agent: throughput (tok/s), TTFT (ms), end-to-end latency, model load time if available, CPU/GPU mem if exposed.
- Multi-agent: concurrency speedup, efficiency, per-agent throughput/TTFT deltas, contention flag, wall time.
- Optional: tokens-per-dollar (if pricing known), joules-per-token (if power sampling enabled).

### Power Sampling (optional but recommended)
- Lightweight `nvidia-smi` polling during benchmarks:
  - `nvidia-smi --query-gpu=power.draw,utilization.gpu,temperature.gpu --format=csv,noheader,nounits -l 1 > power_log.csv &`
- Derive watts/token or joules/token for cost/efficiency comparisons.
- Post-process: compute mean power during active inference (exclude idle/load warmup) before deriving joules/token.

### Validation and QA
- Sanity checks: metrics.json present per run; expected run counts; non-empty summaries.
- Reuse TR111/114 validation scripts where applicable to check schema and counts.
- Outlier rule: flag if |value - median| > 2 × MAD for key metrics (throughput, TTFT); rerun flagged configs.

### Failure Logging (for expected OOMs/limits)
- Capture attempted config (model, GPU layers, ctx, temp), error message, observed VRAM at failure, and fallback decision (e.g., drop to 7B or lower ctx/gpu layers).

## Reporting Plan
- Structure TR116 similar to TR114/115: objective, setup, methodology, results (single-agent per model, multi-agent per model), cross-model comparison, VRAM/quant notes, recommendations.
- Include reproducibility steps (commands, commit hash, model IDs, Ollama ports).
- Add comparative views:
  - Normalized metrics table (e.g., throughput as % of Gemma baseline).
  - Cost/efficiency frontier if power sampling is present (tokens/joule vs tok/s).
  - “Winner by scenario” matrix (single-agent Python, single-agent Rust, multi-agent Python, multi-agent Rust).
- Highlight whether model choice changes multi-agent efficiency or if architecture dominates.

## Risks and Mitigations
- VRAM limits: prefer 7B; downscale ctx/gpu layers if needed and document.
- Model load failures: retry with lower quant or reduced ctx.
- Time budget: drop runs from 5 to 3 if necessary; preserve at least two scenarios in multi-agent.

## Open Questions
- Do we want power sampling for cost/energy KPIs? If yes, add `nvidia-smi` polling.
- Is a lighter Qwen quant (explicit `q4_K_M`) preferred for consistency across hosts?
