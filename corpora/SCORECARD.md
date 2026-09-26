# ChimeraForge prediction-vs-measured audit

- **Hardware:** 17 GPUs (third-party published benchmarks)
- **Matrix registered:** 2026-09-25
- **Matrix fingerprint:** `1db6b1fe4827d5aa`
- **Generated:** 2026-09-25
- **Cells:** 42 (1 skipped, 26 underspecified)
- **Predictions from:** bundled planner corpus

- **Pre-registered bands:** throughput_tps +-25%, ttft_ms +-50%, e2e_latency_ms +-25%

Combined over every per-GPU matrix in corpora/. Each per-GPU audit, with its own fingerprint, is in corpora/audits/.

# Evidence: third-party-measured

_Ground truth from published third-party benchmarks: different silicon, driver and engine build than any own-rig cell, each cell quoting its source and serving config. Reported on its own and never averaged with own-rig cells._

## roofline-estimate

_The out-of-sample path: no measured row exists, so the planner is predicting from first principles._

| Metric | n | In-band | Median abs | GMFE | Bias (median signed) | Worst cell | Worst |
|---|---|---|---|---|---|---|---|
| throughput_tps | 15 | 13% | 35.9% | 1.63x | -26.8% | `B200 180GB :: llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | +206.3% |
| ttft_ms | 14 | 14% | 135.4% | 2.68x | +135.4% | `RTX 3080 10GB :: llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | +183.9% |

## Underspecified cells (published, not scored)

_The source omits its engine version or serving flags, so these are kept out of every row above. Their errors are listed here rather than hidden._

- `A100 40GB :: meta-llama/Meta-Llama-3-8B|FP16|vllm|c2048|p128|o128|b1` -- e2e_latency_ms -12.9% https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv
- `A100 40GB :: meta-llama/Meta-Llama-3-8B|FP16|vllm|c2048|p1024|o1024|b1` -- e2e_latency_ms -14.8% https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv
- `A100 40GB :: mistralai/Mistral-7B-v0.1|FP16|vllm|c2048|p128|o128|b1` -- e2e_latency_ms -16.8% https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv
- `A100 40GB :: mistralai/Mistral-7B-v0.1|FP16|vllm|c2048|p1024|o1024|b1` -- e2e_latency_ms -19.5% https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv
- `A100 80GB :: Meta-Llama-3-70B.Q4_K_M|Q4_K_M|ollama|c2048|p512|o512|b1` -- throughput_tps -6.1%, ttft_ms -7.6% https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md
- `A100 80GB :: Meta-Llama-3-8B.F16|FP16|ollama|c2048|p512|o512|b1` -- throughput_tps +99.3% https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md
- `A100 80GB :: Meta-Llama-3-8B.Q4_K_M|Q4_K_M|ollama|c2048|p512|o512|b1` -- throughput_tps +50.0%, ttft_ms -23.4% https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md
- `H100 80GB :: meta-llama/Meta-Llama-3-8B|FP16|vllm|c2048|p128|o128|b1` -- e2e_latency_ms -26.0% https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv
- `H100 80GB :: meta-llama/Meta-Llama-3-8B|FP16|vllm|c2048|p1024|o1024|b1` -- e2e_latency_ms -27.4% https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv
- `H100 80GB :: mistralai/Mistral-7B-v0.1|FP16|vllm|c2048|p128|o128|b1` -- e2e_latency_ms -29.7% https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv
- `H100 80GB :: mistralai/Mistral-7B-v0.1|FP16|vllm|c2048|p1024|o1024|b1` -- e2e_latency_ms -33.1% https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv
- `MI300X 192GB :: meta-llama/Meta-Llama-3-70B|FP16|vllm|c2048|p128|o128|b1` -- e2e_latency_ms -42.7% https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv
- `MI300X 192GB :: meta-llama/Meta-Llama-3-70B|FP16|vllm|c2048|p1024|o1024|b1` -- e2e_latency_ms -41.1% https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv
- `MI300X 192GB :: meta-llama/Meta-Llama-3-8B|FP16|vllm|c2048|p128|o128|b1` -- e2e_latency_ms -78.5% https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv
- `MI300X 192GB :: meta-llama/Meta-Llama-3-8B|FP16|vllm|c2048|p1024|o1024|b1` -- e2e_latency_ms -64.7% https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv
- `MI300X 192GB :: mistralai/Mistral-7B-v0.1|FP16|vllm|c2048|p128|o128|b1` -- e2e_latency_ms -57.9% https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv
- `MI300X 192GB :: mistralai/Mistral-7B-v0.1|FP16|vllm|c2048|p1024|o1024|b1` -- e2e_latency_ms -68.9% https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv
- `RTX 3080 10GB :: Meta-Llama-3-8B.Q4_K_M|Q4_K_M|ollama|c2048|p512|o512|b1` -- throughput_tps -31.1%, ttft_ms +151.6% https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md
- `RTX 3090 24GB :: Meta-Llama-3-8B.F16|FP16|ollama|c2048|p512|o512|b1` -- throughput_tps +3.4%, ttft_ms +151.3% https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md
- `RTX 3090 24GB :: Meta-Llama-3-8B.Q4_K_M|Q4_K_M|ollama|c2048|p512|o512|b1` -- throughput_tps -19.4%, ttft_ms +127.9% https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md
- `RTX 3090 24GB :: llama-3.1-8b.Q4_0|Q4_0|ollama|c2048|p512|o128|b1` -- throughput_tps -35.7% https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-14396472
- `RTX 4070 Ti 12GB :: Meta-Llama-3-8B.Q4_K_M|Q4_K_M|ollama|c2048|p512|o512|b1` -- throughput_tps -40.0%, ttft_ms +97.0% https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md
- `RTX 4080 16GB :: Meta-Llama-3-8B.Q4_K_M|Q4_K_M|ollama|c2048|p512|o512|b1` -- throughput_tps -34.1%, ttft_ms +121.9% https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md
- `RTX 4090 24GB :: Meta-Llama-3-8B.F16|FP16|ollama|c2048|p512|o512|b1` -- throughput_tps -3.9%, ttft_ms +128.0% https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md
- `RTX 4090 24GB :: Meta-Llama-3-8B.Q4_K_M|Q4_K_M|ollama|c2048|p512|o512|b1` -- throughput_tps -23.3%, ttft_ms +73.5% https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md
- `RTX 5070 12GB :: llama-2-7b.Q4_0|Q4_0|ollama|c2048|p512|o128|b1` -- throughput_tps -37.6%, ttft_ms +183.1% https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-14161275

## Skipped cells

- `RTX 4080 16GB :: Meta-Llama-3-8B.F16|FP16|ollama|c2048|p512|o512|b1` -- the planner refuses FP16 on ollama: vram: 16.7GB/GPU > 16GB

## Sources consulted (pre-registered)

- [used] https://github.com/ggml-org/llama.cpp/discussions/15013
- [used] https://github.com/ggml-org/llama.cpp/discussions/15021
- [used] https://github.com/ggml-org/llama.cpp/discussions/10879
- [used] https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md
- [used] https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv
- [used] https://github.com/sgl-project/sglang/issues/1008
- [used] https://www.amd.com/en/developer/resources/rocm-hub/dev-ai/performance-results.html
- [used] https://www.databasemart.com/blog/ollama-gpu-benchmark-rtx4090
- [unused] https://github.com/ggml-org/llama.cpp/discussions/4167 -- no GPU from the planner's database (Apple Silicon)
- [unused] https://github.com/ggml-org/llama.cpp/discussions/15396 -- MXFP4 MoE quant, not in the planner's quant set
- [unused] https://www.localscore.ai/ -- each figure averages 8 tests of different prompt/output lengths; no engine version; implausible outliers
- [unused] https://hud.pytorch.org/benchmark/llms -- HTTP 403 to automated fetch
- [unused] https://blog.vllm.ai/2024/09/05/perf-update.html -- seen as a search result only, not opened
- [unused] https://docs.nvidia.com/nim/benchmarking/llm/latest/performance.html -- latest URL 404; v1.0.0 page does not state which engine produced the figures
- [unused] https://modal.com/llm-almanac -- interactive only, no raw export; TTFT includes ~150 ms network overhead by the page's own statement
- [unused] https://github.com/sgl-project/sglang/pull/1341 -- batch-1 logs without the GPU stated
- [unused] https://github.com/huggingface/text-generation-inference/issues/1452 -- batch 4 on 2x RTX 3090; no batch-1 TGI tables found
- [unused] https://www.databasemart.com/blog/vllm-gpu-benchmark-h100 -- aggregate throughput over 50-100 concurrent requests
- [unused] https://techcommunity.microsoft.com/ -- Azure HPC vLLM blogs: aggregate throughput under load on variable-length datasets, no vLLM version

Positive error means predicted above measured: **optimistic** for a rate (throughput), **pessimistic** for a latency (TTFT, end-to-end, p95), where the planner predicted slower than measured.
GMFE is the geometric mean fold error: 2x too high and 2x too low both score 2.0x.

Every cell, including the worst, is retained in the raw JSON alongside this report so the table can be re-derived independently.

## By memory type

_The combined rows above average two populations whose errors have opposite signs. Fully specified cells only, as above._

| Memory | Metric | n | In-band | Median abs | GMFE | Bias (median signed) |
|---|---|---|---|---|---|---|
| HBM | throughput_tps | 6 | 17% | 57.8% | 1.77x | +57.8% |
| HBM | ttft_ms | 5 | 20% | 65.5% | 3.21x | -65.5% |
| GDDR | throughput_tps | 9 | 11% | 35.9% | 1.54x | -35.9% |
| GDDR | ttft_ms | 9 | 11% | 148.3% | 2.43x | +148.3% |

## Every scored cell

| GPU | Cell | Class | Metric | Predicted | Measured (basis) | Error | Source |
|---|---|---|---|---|---|---|---|
| B200 180GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | throughput_tps | 911.9 | 297.7 (decode_tps_single_stream) | +206.3% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-14781873) |
| RTX 3080 10GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | ttft_ms | 289.9 | 102.1 (prefill_tps) | +183.9% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-13963584) |
| RTX 5070 12GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` (underspecified) | roofline-estimate | ttft_ms | 279.6 | 98.8 (prefill_tps) | +183.1% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-14161275) |
| RTX 4080 16GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | ttft_ms | 176.9 | 63.7 (prefill_tps) | +177.5% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-14032320) |
| MI300X 192GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | throughput_tps | 627.7 | 232.9 (decode_tps_single_stream) | +169.5% | [link](https://github.com/ggml-org/llama.cpp/discussions/15021#discussioncomment-14003622) |
| RTX 5070 Ti 16GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | ttft_ms | 196.2 | 73.6 (prefill_tps) | +166.4% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-15183261) |
| RTX 4060 Ti 8GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | ttft_ms | 391.2 | 150.8 (prefill_tps) | +159.4% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-13972383) |
| RTX 3080 10GB | `Meta-Llama-3-8B.Q4_K_M\|Q4_K_M\|ollama\|c2048\|p512\|o512\|b1` (underspecified) | roofline-estimate | ttft_ms | 345.5 | 137.3 (prefill_tps) | +151.6% | [link](https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md) |
| RTX 3090 24GB | `Meta-Llama-3-8B.F16\|FP16\|ollama\|c2048\|p512\|o512\|b1` (underspecified) | roofline-estimate | ttft_ms | 289.5 | 115.2 (prefill_tps) | +151.3% | [link](https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md) |
| RTX 5080 16GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | ttft_ms | 153.2 | 61.7 (prefill_tps) | +148.3% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-14244491) |
| RTX 3090 24GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | ttft_ms | 243.0 | 98.9 (prefill_tps) | +145.6% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-13960712) |
| RTX 4090 24GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | ttft_ms | 104.4 | 42.7 (prefill_tps) | +144.5% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-14016393) |
| RTX 4090 24GB | `Meta-Llama-3-8B.F16\|FP16\|ollama\|c2048\|p512\|o512\|b1` (underspecified) | roofline-estimate | ttft_ms | 124.4 | 54.6 (prefill_tps) | +128.0% | [link](https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md) |
| RTX 3090 24GB | `Meta-Llama-3-8B.Q4_K_M\|Q4_K_M\|ollama\|c2048\|p512\|o512\|b1` (underspecified) | roofline-estimate | ttft_ms | 289.5 | 127.0 (prefill_tps) | +127.9% | [link](https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md) |
| RTX 5090 32GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | ttft_ms | 82.3 | 36.4 (prefill_tps) | +126.2% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-14761847) |
| RTX 4080 16GB | `Meta-Llama-3-8B.Q4_K_M\|Q4_K_M\|ollama\|c2048\|p512\|o512\|b1` (underspecified) | roofline-estimate | ttft_ms | 210.8 | 95.0 (prefill_tps) | +121.9% | [link](https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md) |
| A100 80GB | `Meta-Llama-3-8B.F16\|FP16\|ollama\|c2048\|p512\|o512\|b1` (underspecified) | roofline-estimate | throughput_tps | 106.6 | 53.5 (decode_tps_single_stream) | +99.3% | [link](https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md) |
| RTX 4070 Ti 12GB | `Meta-Llama-3-8B.Q4_K_M\|Q4_K_M\|ollama\|c2048\|p512\|o512\|b1` (underspecified) | roofline-estimate | ttft_ms | 256.3 | 130.1 (prefill_tps) | +97.0% | [link](https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md) |
| H200 141GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | throughput_tps | 568.4 | 307.8 (decode_tps_single_stream) | +84.7% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-14978771) |
| B200 180GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | ttft_ms | 7.7 | 48.6 (prefill_tps) | -84.2% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-14781873) |
| MI300X 192GB | `meta-llama/Meta-Llama-3-8B\|FP16\|vllm\|c2048\|p128\|o128\|b1` (underspecified) | roofline-estimate | e2e_latency_ms | 465.7 | 2169.9 (e2e_latency_ms) | -78.5% | [link](https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv) |
| RTX 4090 24GB | `Meta-Llama-3-8B.Q4_K_M\|Q4_K_M\|ollama\|c2048\|p512\|o512\|b1` (underspecified) | roofline-estimate | ttft_ms | 124.4 | 71.7 (prefill_tps) | +73.5% | [link](https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md) |
| MI300X 192GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | ttft_ms | 13.2 | 46.5 (prefill_tps) | -71.6% | [link](https://github.com/ggml-org/llama.cpp/discussions/15021#discussioncomment-14003622) |
| MI300X 192GB | `mistralai/Mistral-7B-v0.1\|FP16\|vllm\|c2048\|p1024\|o1024\|b1` (underspecified) | roofline-estimate | e2e_latency_ms | 3359.6 | 10805.1 (e2e_latency_ms) | -68.9% | [link](https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv) |
| H100 80GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | ttft_ms | 17.4 | 50.4 (prefill_tps) | -65.5% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-14978771) |
| MI300X 192GB | `meta-llama/Meta-Llama-3-8B\|FP16\|vllm\|c2048\|p1024\|o1024\|b1` (underspecified) | roofline-estimate | e2e_latency_ms | 3725.6 | 10540.3 (e2e_latency_ms) | -64.7% | [link](https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv) |
| H200 141GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | ttft_ms | 17.4 | 49.1 (prefill_tps) | -64.6% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-14978771) |
| MI300X 192GB | `mistralai/Mistral-7B-v0.1\|FP16\|vllm\|c2048\|p128\|o128\|b1` (underspecified) | roofline-estimate | e2e_latency_ms | 419.9 | 998.5 (e2e_latency_ms) | -57.9% | [link](https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv) |
| A100 80GB | `Meta-Llama-3-8B.Q4_K_M\|Q4_K_M\|ollama\|c2048\|p512\|o512\|b1` (underspecified) | roofline-estimate | throughput_tps | 202.6 | 135.0 (decode_tps_single_stream) | +50.0% | [link](https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md) |
| RTX 4060 Ti 8GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | throughput_tps | 34.1 | 63.9 (decode_tps_single_stream) | -46.6% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-13972383) |
| A100 80GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | ttft_ms | 55.3 | 103.1 (prefill_tps) | -46.4% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-14978771) |
| MI300X 192GB | `meta-llama/Meta-Llama-3-70B\|FP16\|vllm\|c2048\|p128\|o128\|b1` (underspecified) | roofline-estimate | e2e_latency_ms | 4085.1 | 7126.7 (e2e_latency_ms) | -42.7% | [link](https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv) |
| MI300X 192GB | `meta-llama/Meta-Llama-3-70B\|FP16\|vllm\|c2048\|p1024\|o1024\|b1` (underspecified) | roofline-estimate | e2e_latency_ms | 32681.5 | 55496.4 (e2e_latency_ms) | -41.1% | [link](https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv) |
| RTX 4080 16GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | throughput_tps | 84.9 | 142.5 (decode_tps_single_stream) | -40.4% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-14032320) |
| RTX 5070 Ti 16GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | throughput_tps | 106.1 | 176.8 (decode_tps_single_stream) | -40.0% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-15183261) |
| RTX 4070 Ti 12GB | `Meta-Llama-3-8B.Q4_K_M\|Q4_K_M\|ollama\|c2048\|p512\|o512\|b1` (underspecified) | roofline-estimate | throughput_tps | 50.1 | 83.5 (decode_tps_single_stream) | -40.0% | [link](https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md) |
| RTX 5070 12GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` (underspecified) | roofline-estimate | throughput_tps | 79.6 | 127.5 (decode_tps_single_stream) | -37.6% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-14161275) |
| RTX 5080 16GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | throughput_tps | 113.7 | 182.0 (decode_tps_single_stream) | -37.5% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-14244491) |
| T4 16GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | ttft_ms | 265.4 | 420.0 (prefill_tps) | -36.8% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-14104555) |
| RTX 4090 24GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | throughput_tps | 119.4 | 186.2 (decode_tps_single_stream) | -35.9% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-14016393) |
| RTX 3090 24GB | `llama-3.1-8b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` (underspecified) | roofline-estimate | throughput_tps | 93.0 | 144.7 (decode_tps_single_stream) | -35.7% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-14396472) |
| RTX 3080 10GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | throughput_tps | 90.0 | 139.7 (decode_tps_single_stream) | -35.6% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-13963584) |
| RTX 4080 16GB | `Meta-Llama-3-8B.Q4_K_M\|Q4_K_M\|ollama\|c2048\|p512\|o512\|b1` (underspecified) | roofline-estimate | throughput_tps | 71.3 | 108.2 (decode_tps_single_stream) | -34.1% | [link](https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md) |
| H100 80GB | `mistralai/Mistral-7B-v0.1\|FP16\|vllm\|c2048\|p1024\|o1024\|b1` (underspecified) | roofline-estimate | e2e_latency_ms | 5305.0 | 7924.0 (e2e_latency_ms) | -33.1% | [link](https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv) |
| RTX 3080 10GB | `Meta-Llama-3-8B.Q4_K_M\|Q4_K_M\|ollama\|c2048\|p512\|o512\|b1` (underspecified) | roofline-estimate | throughput_tps | 75.5 | 109.6 (decode_tps_single_stream) | -31.1% | [link](https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md) |
| H100 80GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | throughput_tps | 397.0 | 303.1 (decode_tps_single_stream) | +31.0% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-14978771) |
| RTX 3090 24GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | throughput_tps | 110.8 | 158.2 (decode_tps_single_stream) | -29.9% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-13960712) |
| H100 80GB | `mistralai/Mistral-7B-v0.1\|FP16\|vllm\|c2048\|p128\|o128\|b1` (underspecified) | roofline-estimate | e2e_latency_ms | 663.5 | 943.8 (e2e_latency_ms) | -29.7% | [link](https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv) |
| H100 80GB | `meta-llama/Meta-Llama-3-8B\|FP16\|sglang\|c2048\|p128\|o8\|b1` | roofline-estimate | throughput_tps | 175.3 | 135.6 (decode_tps_single_stream) | +29.2% | [link](https://github.com/sgl-project/sglang/issues/1008) |
| H100 80GB | `meta-llama/Meta-Llama-3-8B\|FP16\|vllm\|c2048\|p1024\|o1024\|b1` (underspecified) | roofline-estimate | e2e_latency_ms | 5883.0 | 8097.8 (e2e_latency_ms) | -27.4% | [link](https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv) |
| RTX 5090 32GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | throughput_tps | 212.2 | 290.0 (decode_tps_single_stream) | -26.8% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-14761847) |
| H100 80GB | `meta-llama/Meta-Llama-3-8B\|FP16\|vllm\|c2048\|p128\|o128\|b1` (underspecified) | roofline-estimate | e2e_latency_ms | 735.9 | 993.9 (e2e_latency_ms) | -26.0% | [link](https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv) |
| A100 80GB | `Meta-Llama-3-8B.Q4_K_M\|Q4_K_M\|ollama\|c2048\|p512\|o512\|b1` (underspecified) | roofline-estimate | ttft_ms | 65.9 | 86.1 (prefill_tps) | -23.4% | [link](https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md) |
| RTX 4090 24GB | `Meta-Llama-3-8B.Q4_K_M\|Q4_K_M\|ollama\|c2048\|p512\|o512\|b1` (underspecified) | roofline-estimate | throughput_tps | 100.2 | 130.6 (decode_tps_single_stream) | -23.3% | [link](https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md) |
| A100 80GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | throughput_tps | 241.5 | 200.1 (decode_tps_single_stream) | +20.7% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-14978771) |
| A100 40GB | `mistralai/Mistral-7B-v0.1\|FP16\|vllm\|c2048\|p1024\|o1024\|b1` (underspecified) | roofline-estimate | e2e_latency_ms | 11471.3 | 14241.8 (e2e_latency_ms) | -19.5% | [link](https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv) |
| RTX 3090 24GB | `Meta-Llama-3-8B.Q4_K_M\|Q4_K_M\|ollama\|c2048\|p512\|o512\|b1` (underspecified) | roofline-estimate | throughput_tps | 93.0 | 115.4 (decode_tps_single_stream) | -19.4% | [link](https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md) |
| T4 16GB | `llama-2-7b.Q4_0\|Q4_0\|ollama\|c2048\|p512\|o128\|b1` | roofline-estimate | throughput_tps | 37.9 | 46.4 (decode_tps_single_stream) | -18.3% | [link](https://github.com/ggml-org/llama.cpp/discussions/15013#discussioncomment-14104555) |
| A100 40GB | `mistralai/Mistral-7B-v0.1\|FP16\|vllm\|c2048\|p128\|o128\|b1` (underspecified) | roofline-estimate | e2e_latency_ms | 1434.0 | 1723.6 (e2e_latency_ms) | -16.8% | [link](https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv) |
| A100 40GB | `meta-llama/Meta-Llama-3-8B\|FP16\|vllm\|c2048\|p1024\|o1024\|b1` (underspecified) | roofline-estimate | e2e_latency_ms | 12727.1 | 14935.7 (e2e_latency_ms) | -14.8% | [link](https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv) |
| A100 40GB | `meta-llama/Meta-Llama-3-8B\|FP16\|vllm\|c2048\|p128\|o128\|b1` (underspecified) | roofline-estimate | e2e_latency_ms | 1590.9 | 1826.3 (e2e_latency_ms) | -12.9% | [link](https://github.com/argonne-lcf/LLM-Inference-Bench/blob/ae7e7a41173badc99f7b59da1657a0172813e5e5/Plots/All_results.csv) |
| A100 80GB | `Meta-Llama-3-70B.Q4_K_M\|Q4_K_M\|ollama\|c2048\|p512\|o512\|b1` (underspecified) | roofline-estimate | ttft_ms | 578.9 | 626.2 (prefill_tps) | -7.6% | [link](https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md) |
| A100 80GB | `Meta-Llama-3-70B.Q4_K_M\|Q4_K_M\|ollama\|c2048\|p512\|o512\|b1` (underspecified) | roofline-estimate | throughput_tps | 23.1 | 24.6 (decode_tps_single_stream) | -6.1% | [link](https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md) |
| RTX 4090 24GB | `Meta-Llama-3-8B.F16\|FP16\|ollama\|c2048\|p512\|o512\|b1` (underspecified) | roofline-estimate | throughput_tps | 52.7 | 54.8 (decode_tps_single_stream) | -3.9% | [link](https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md) |
| RTX 3090 24GB | `Meta-Llama-3-8B.F16\|FP16\|ollama\|c2048\|p512\|o512\|b1` (underspecified) | roofline-estimate | throughput_tps | 49.0 | 47.4 (decode_tps_single_stream) | +3.4% | [link](https://github.com/XiongjieDai/GPU-Benchmarks-on-LLM-Inference/blob/aa72e0ec86c356c41f8281c9733e9a13c3675800/README.md) |

## Matrix fingerprints

- A100 40GB: `27e7c883d974fc1a23e7964313cab595a06fa80355fb4063d7f1eaa7d1c64651`
- A100 80GB: `eb830b850c5df1d7833a70f0fc7b65de1fc7fd1a695f8496dfeaced5dd1df10e`
- B200 180GB: `0eab2916e620f07c24e89403d5e1fcf15da70a4e29c9339a9f8fe0e7f1913c8f`
- H100 80GB: `14d66639c132b5efc4bcf0939146fad00dee1491564eaad8cee05efda0162985`
- H200 141GB: `d91108755517fb5b87f12db27e36003124500c88c97fe79bde5d5041833b488a`
- MI300X 192GB: `40c60688c296aa1386172fd4653a35d0afb20e3a887b9df58c58ef1a0ff90c0f`
- RTX 3080 10GB: `337ba7cea6620d1e90d4dc217e989acb61156c2d13fbfb793407a7e263eea2de`
- RTX 3090 24GB: `011c3be4a89f85112a057c61ba0f364e96b87d8b84cef245bae061d89f282125`
- RTX 4060 Ti 8GB: `673dae3a42399ed92e5c75c353bc01cc454ab3e2ac5b77831d55426ddfb45193`
- RTX 4070 Ti 12GB: `011d57782d0ae8ad1c2e6e331c192fc6da7efefeb28453dbb84114d59788d25a`
- RTX 4080 16GB: `4a4f134755e83985be2b552c20e162fee11734437e3e1a5bc0668f5aedf61500`
- RTX 4090 24GB: `b0dfca8ed08899bf3bd684420bfb3b419ff29b095703914a6b1fef2fa7634e2c`
- RTX 5070 12GB: `16bbc1e2beb5338962858638adfe801b35aea3fa40d7dce91d26c60ca0cf8c27`
- RTX 5070 Ti 16GB: `5b772fc0fb6f13edf24027601276327ddc7c93f5b483b339b4062c931fdbbd0a`
- RTX 5080 16GB: `dbb1c0399385df4e91ed720005af60aec524da93aa4739b2d8c3bffed9e93425`
- RTX 5090 32GB: `f20f20886ecd59770abae04edfec09be61649e0525db4dfb046d24f43722d430`
- T4 16GB: `e91b47e8940d107c53d01e68f2fc5e7dda54e387d17d3268bba635f2d66697bf`

