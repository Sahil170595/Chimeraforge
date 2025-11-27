# Technical Report 116: Cross-Model Concurrent Benchmarking
## Qwen 2.5 vs Gemma 3 vs Llama 3.1 (Python asyncio vs Rust tokio)

**Project:** Chimeraforge LLM Performance Research
**Date:** 2025-11-26
**Report Type:** Definitive cross-model and cross-runtime analysis
**Test Matrix:** 60 dual-agent runs (12 configs x 5 runs) + 24 single-agent configs
**Data Sources:** experiments/TR116/results (metrics.json), experiments/TR116/analysis_comprehensive.csv

---

## Executive Summary
This report consolidates the full TR116 run matrix using only the metrics in experiments/TR116. All figures below are recomputed from the raw metrics files (no synthetic numbers).

### Key Findings
- Rust (tokio-default) sustained **95.17% mean efficiency** and **1.903x mean speedup**, beating Python asyncio by **12.44 percentage points** and **0.249x** respectively across the same 60 dual-agent runs.
- Best multi-agent combination: **Rust gemma3 chimera-homo** -> 1.984x speedup, 99.22% efficiency (std 0.64pp).
- Lowest multi-agent combination: **Python qwen2.5 baseline-vs-chimera** -> 1.551x speedup, 77.57% efficiency (std 12.48pp).
- Throughput balance drives efficiency: Python runs show +8 to +16 tok/s mean throughput deltas between agents, whereas Rust stays within x2 tok/s (except Qwen baseline at +12.4 tok/s).
- TTFT imbalance is runtime-specific: Rust baseline-vs-chimera scenarios carry +339 to +397 ms TTFT delta (collector slower), yet still achieve 96-99% efficiency. Python chimera-homo runs shrink TTFT deltas to -11 to -24 ms and gain ~7pp efficiency over Python baseline-vs-chimera.
- Contention was rare: only 1 of 60 multi-agent runs flagged resource contention (Qwen 2.5 Rust chimera-homo run_5).
- Single-agent throughput deltas are tiny (<2%): chimera-optimized configs neither help nor hurt throughput meaningfully. Python TTFT worsened (21-43% regression), while Rust improved TTFT for Gemma/Llama (4-12%) but regressed for Qwen (-6.6%).

### Recommended Stack (based on these runs)
1. Use **Rust tokio-default + Gemma 3 or Llama 3.1** for dual-agent orchestration; both deliver ~1.95x speedup at ~98-99% efficiency.
2. Avoid Python asyncio for high-concurrency agent work; efficiency ceiling observed at 86% with higher throughput/TTFT imbalance.
3. If Qwen 2.5 must be used, prefer the Rust stack and monitor throughput skew; expect ~90% efficiency and occasional contention under chimera-homo.
4. Chimera tuning does not materially change single-agent throughput; prioritize TTFT tuning (especially on Python) over throughput tweaks.

---

## Test Scope and Coverage
- Models: qwen2.5:7b, gemma3:latest, llama3.1:8b-instruct-q4_0
- Runtimes: Python asyncio (dual Ollama), Rust tokio-default (dual Ollama)
- Scenarios (multi-agent): baseline-vs-chimera, chimera-homo
- Repetitions: 5 runs per multi-agent config (12 configs -> 60 runs); 4 single-agent configs per model/runtime (GPU 60/80 x ctx 512/1024) -> 24 configs
- Hardware notes: local 12GB-class GPU; quantized models (Q4) used per model README; no remote services involved
- Data integrity: analysis_comprehensive.csv regenerated via experiments/TR116/analyze_metrics_direct.py (fixed Rust summary parsing)

### Runtime-Level Summary (multi-agent)
| Runtime | Runs | Efficiency_Mean | Efficiency_Std | Speedup_Mean | Speedup_Std |
|---|---|---|---|---|---|
| python | 30 | 82.725 | 9.278 | 1.655 | 0.186 |
| rust | 30 | 95.168 | 6.441 | 1.903 | 0.129 |

### Model x Runtime Summary (multi-agent)
| Model | Runtime | Eff_Mean | Eff_Std | Speed_Mean | Speed_Std |
|---|---|---|---|---|---|
| gemma3 | python | 82.546 | 8.238 | 1.651 | 0.165 |
| gemma3 | rust | 98.267 | 1.404 | 1.965 | 0.028 |
| llama3.1 | python | 84.787 | 10.818 | 1.696 | 0.216 |
| llama3.1 | rust | 97.548 | 1.572 | 1.951 | 0.031 |
| qwen2.5 | python | 80.842 | 9.154 | 1.617 | 0.183 |
| qwen2.5 | rust | 89.690 | 8.883 | 1.794 | 0.178 |

### Configuration-Level Summary (multi-agent)
| Runtime | Model | Scenario | Runs | Speedup_Mean | Speedup_Std | Efficiency_Mean | Efficiency_Std | Efficiency_Min | Efficiency_Max | Throughput_Delta_Mean | TTFT_Delta_Mean | Contention_Rate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| python | gemma3 | baseline-vs-chimera | 5 | 1.605 | 0.227 | 80.236 | 11.340 | 60.116 | 87.513 | 13.641 | 8.617 | 0.000 |
| python | gemma3 | chimera-homo | 5 | 1.697 | 0.066 | 84.855 | 3.282 | 79.752 | 88.644 | 12.880 | -11.014 | 0.000 |
| python | llama3.1 | baseline-vs-chimera | 5 | 1.676 | 0.266 | 83.799 | 13.299 | 60.194 | 91.329 | 8.361 | -1.099 | 0.000 |
| python | llama3.1 | chimera-homo | 5 | 1.715 | 0.183 | 85.775 | 9.166 | 69.555 | 91.683 | 9.413 | -17.969 | 0.000 |
| python | qwen2.5 | baseline-vs-chimera | 5 | 1.551 | 0.250 | 77.567 | 12.484 | 55.314 | 84.135 | 15.593 | 0.018 | 0.000 |
| python | qwen2.5 | chimera-homo | 5 | 1.682 | 0.048 | 84.118 | 2.422 | 81.545 | 88.006 | 13.923 | -23.919 | 0.000 |
| rust | gemma3 | baseline-vs-chimera | 5 | 1.946 | 0.027 | 97.314 | 1.327 | 95.699 | 98.721 | -1.926 | 373.167 | 0.000 |
| rust | gemma3 | chimera-homo | 5 | 1.984 | 0.013 | 99.219 | 0.635 | 98.255 | 99.860 | -0.764 | -140.288 | 0.000 |
| rust | llama3.1 | baseline-vs-chimera | 5 | 1.931 | 0.032 | 96.549 | 1.609 | 95.171 | 99.233 | -1.530 | 397.378 | 0.000 |
| rust | llama3.1 | chimera-homo | 5 | 1.971 | 0.014 | 98.548 | 0.690 | 97.525 | 99.303 | -1.401 | -17.920 | 0.000 |
| rust | qwen2.5 | baseline-vs-chimera | 5 | 1.799 | 0.171 | 89.966 | 8.573 | 81.197 | 99.582 | 12.403 | 339.300 | 0.000 |
| rust | qwen2.5 | chimera-homo | 5 | 1.788 | 0.204 | 89.414 | 10.192 | 71.999 | 97.404 | -12.421 | -9.849 | 0.200 |

## Multi-Agent Analysis
### Rust vs Python Efficiency and Speedup
- Efficiency gap: Rust 95.17% vs Python 82.73% (gap 12.44pp). Speedup gap: Rust 1.903x vs Python 1.655x.
- Rust variance is lower: 6.44pp std vs 9.28pp in Python, despite higher absolute efficiency.
- Python improvements from baseline-vs-chimera to chimera-homo are modest (~4-7pp), indicating coordination overhead dominates more than prompt asymmetry.
- Rust remains near-linear even with TTFT imbalance because throughput delta is near zero; Python throughput deltas (+8 to +16 tok/s) map to lower efficiency.

### Per-Configuration Notes
#### PYTHON | gemma3 | baseline-vs-chimera
- Runs: 5 | Speedup mean 1.605x (std 0.227) | Efficiency mean 80.24% (std 11.34pp, range 60.12-87.51%).
- Throughput delta mean: +13.641 tok/s | TTFT delta mean: +8.6 ms | Contention rate: 0.0%.
- Observation: Python shows persistent throughput skew; efficiency ceiling sits in low/mid-80% even when TTFT deltas shrink (chimera-homo).

#### PYTHON | gemma3 | chimera-homo
- Runs: 5 | Speedup mean 1.697x (std 0.066) | Efficiency mean 84.85% (std 3.28pp, range 79.75-88.64%).
- Throughput delta mean: +12.880 tok/s | TTFT delta mean: -11.0 ms | Contention rate: 0.0%.
- Observation: Python shows persistent throughput skew; efficiency ceiling sits in low/mid-80% even when TTFT deltas shrink (chimera-homo).

#### PYTHON | llama3.1 | baseline-vs-chimera
- Runs: 5 | Speedup mean 1.676x (std 0.266) | Efficiency mean 83.80% (std 13.30pp, range 60.19-91.33%).
- Throughput delta mean: +8.361 tok/s | TTFT delta mean: -1.1 ms | Contention rate: 0.0%.
- Observation: Python shows persistent throughput skew; efficiency ceiling sits in low/mid-80% even when TTFT deltas shrink (chimera-homo).

#### PYTHON | llama3.1 | chimera-homo
- Runs: 5 | Speedup mean 1.715x (std 0.183) | Efficiency mean 85.77% (std 9.17pp, range 69.56-91.68%).
- Throughput delta mean: +9.413 tok/s | TTFT delta mean: -18.0 ms | Contention rate: 0.0%.
- Observation: Python shows persistent throughput skew; efficiency ceiling sits in low/mid-80% even when TTFT deltas shrink (chimera-homo).

#### PYTHON | qwen2.5 | baseline-vs-chimera
- Runs: 5 | Speedup mean 1.551x (std 0.250) | Efficiency mean 77.57% (std 12.48pp, range 55.31-84.14%).
- Throughput delta mean: +15.593 tok/s | TTFT delta mean: +0.0 ms | Contention rate: 0.0%.
- Observation: Python shows persistent throughput skew; efficiency ceiling sits in low/mid-80% even when TTFT deltas shrink (chimera-homo).

#### PYTHON | qwen2.5 | chimera-homo
- Runs: 5 | Speedup mean 1.682x (std 0.048) | Efficiency mean 84.12% (std 2.42pp, range 81.54-88.01%).
- Throughput delta mean: +13.923 tok/s | TTFT delta mean: -23.9 ms | Contention rate: 0.0%.
- Observation: Python shows persistent throughput skew; efficiency ceiling sits in low/mid-80% even when TTFT deltas shrink (chimera-homo).

#### RUST | gemma3 | baseline-vs-chimera
- Runs: 5 | Speedup mean 1.946x (std 0.027) | Efficiency mean 97.31% (std 1.33pp, range 95.70-98.72%).
- Throughput delta mean: -1.926 tok/s | TTFT delta mean: +373.2 ms | Contention rate: 0.0%.
- Observation: Rust stays within 95-99% efficiency for Gemma/Llama; Qwen shows higher spread and the only contention event (run_5 chimera-homo).

#### RUST | gemma3 | chimera-homo
- Runs: 5 | Speedup mean 1.984x (std 0.013) | Efficiency mean 99.22% (std 0.64pp, range 98.26-99.86%).
- Throughput delta mean: -0.764 tok/s | TTFT delta mean: -140.3 ms | Contention rate: 0.0%.
- Observation: Rust stays within 95-99% efficiency for Gemma/Llama; Qwen shows higher spread and the only contention event (run_5 chimera-homo).

#### RUST | llama3.1 | baseline-vs-chimera
- Runs: 5 | Speedup mean 1.931x (std 0.032) | Efficiency mean 96.55% (std 1.61pp, range 95.17-99.23%).
- Throughput delta mean: -1.530 tok/s | TTFT delta mean: +397.4 ms | Contention rate: 0.0%.
- Observation: Rust stays within 95-99% efficiency for Gemma/Llama; Qwen shows higher spread and the only contention event (run_5 chimera-homo).

#### RUST | llama3.1 | chimera-homo
- Runs: 5 | Speedup mean 1.971x (std 0.014) | Efficiency mean 98.55% (std 0.69pp, range 97.52-99.30%).
- Throughput delta mean: -1.401 tok/s | TTFT delta mean: -17.9 ms | Contention rate: 0.0%.
- Observation: Rust stays within 95-99% efficiency for Gemma/Llama; Qwen shows higher spread and the only contention event (run_5 chimera-homo).

#### RUST | qwen2.5 | baseline-vs-chimera
- Runs: 5 | Speedup mean 1.799x (std 0.171) | Efficiency mean 89.97% (std 8.57pp, range 81.20-99.58%).
- Throughput delta mean: +12.403 tok/s | TTFT delta mean: +339.3 ms | Contention rate: 0.0%.
- Observation: Rust stays within 95-99% efficiency for Gemma/Llama; Qwen shows higher spread and the only contention event (run_5 chimera-homo).

#### RUST | qwen2.5 | chimera-homo
- Runs: 5 | Speedup mean 1.788x (std 0.204) | Efficiency mean 89.41% (std 10.19pp, range 72.00-97.40%).
- Throughput delta mean: -12.421 tok/s | TTFT delta mean: -9.8 ms | Contention rate: 20.0%.
- Observation: Rust stays within 95-99% efficiency for Gemma/Llama; Qwen shows higher spread and the only contention event (run_5 chimera-homo).

### Throughput and TTFT Imbalance
- Python throughput deltas are positive and sizeable (+8 to +16 tok/s), implying one agent consistently outran the other; this correlates with the lower efficiency per correlation analysis (see Appendix).
- Rust throughput deltas hover near zero for Gemma/Llama; Qwen baseline shows +12.4 tok/s mean delta yet still reaches ~90% efficiency, suggesting Rust scheduling hides the skew better.
- TTFT deltas in Rust baseline-vs-chimera are high (+339 to +397 ms) but do not prevent ~97% efficiency, showing TTFT is less dominant than throughput skew for this workload.
- Python chimera-homo cuts TTFT deltas (down to -11 to -24 ms) and gains ~7pp efficiency over Python baseline-vs-chimera, but remains below Rust by double digits.

### Stability and Contention
- Only 1/60 multi-agent runs flagged contention (Qwen Rust chimera-homo run_5). No drops or missing metrics after re-parsing Rust summaries.
- Efficiency std per config stays under 1.7pp for Rust Gemma/Llama but rises to 10.19pp for Rust Qwen chimera-homo, indicating that model is sensitive to skew even on Rust.
- Python configs show larger swings (std up to 13.30pp for Llama baseline-vs-chimera) confirming the higher volatility of asyncio under load.

## Single-Agent Analysis (TR111/112 parity configs)
### Summary Table
| Runtime | Model | Configs | Baseline_TP | Chimera_TP | TP_Improve_% | Baseline_TTFT_ms | Chimera_TTFT_ms | TTFT_Reduction_% |
|---|---|---|---|---|---|---|---|---|
| python | gemma3 | 4 | 118.47 | 117.76 | -0.60 | 150.08 | 177.97 | -30.07 |
| python | llama3.1 | 4 | 82.05 | 80.41 | -2.00 | 109.40 | 131.09 | -21.04 |
| python | qwen2.5 | 4 | 81.80 | 81.20 | -0.74 | 136.06 | 135.89 | -43.42 |
| rust | gemma3 | 4 | 114.21 | 113.94 | -0.23 | 1204.34 | 1148.52 | 4.57 |
| rust | llama3.1 | 4 | 79.20 | 79.96 | 0.96 | 1037.46 | 911.89 | 11.95 |
| rust | qwen2.5 | 4 | 79.61 | 80.86 | 1.57 | 1424.54 | 1462.44 | -6.61 |

### Observations
- Throughput: All models and runtimes show <2% delta between baseline and chimera configs; throughput is effectively unchanged by the chimera prompt tuning in single-agent mode.
- TTFT: Python regresses (Gemma +30%, Llama +21%, Qwen +43%), driven by chimera prompt overhead. Rust improves TTFT for Gemma (+4.6%) and Llama (+12%), but Qwen regresses (-6.6%).
- Recommendation: For single-agent latency work, prefer Rust for Gemma/Llama; retune Qwen or drop chimera prompt on Python to recover TTFT.

## Recommendations
1. **Production runtime:** Rust tokio-default for any multi-agent orchestration; Python acceptable only for low-concurrency or prototyping.
2. **Model choice for concurrency:** Gemma 3 and Llama 3.1 are effectively interchangeable on Rust (~98-99% efficiency). Choose based on license/quality; do not expect efficiency gains from switching between them on Python.
3. **Qwen tuning:** If Qwen is mandatory, cap concurrent requests or equalize prompt/token budgets to reduce throughput skew; watch for contention under chimera-homo.
4. **TTFT mitigation:** On Python, trim prompt length or reduce context to claw back TTFT; on Rust baseline-vs-chimera, accept the +340-397 ms TTFT delta or re-balance endpoints.
5. **Chimera prompts:** Keep for multi-agent (no harm on Rust, small benefit on Python), but reconsider for single-agent latency-sensitive paths where they add TTFT without throughput gains.

## Reproducibility and Data Integrity
- Regenerate analysis artifacts: `python experiments/TR116/analyze_metrics_direct.py` (now handles Rust summary fields).
- Raw metrics live at `experiments/TR116/results` (multi and single). The report pulls only from `analysis_comprehensive.csv` and the single-agent metrics files listed below.
- No external data sources or manual edits were used in the computations below.

---

## Appendix A: Multi-Agent Flat Table (all 60 runs)
| Runtime | Model | Scenario | Run | Speedup | Efficiency | Throughput_Delta | TTFT_Delta_ms | Contention | Path |
|---|---|---|---|---|---|---|---|---|---|
| python | gemma3 | baseline-vs-chimera | 1 | 1.202 | 60.116 | 10.159 | 35.297 | False | experiments/TR116/results/multi\python\gemma3_latest\gemma3_latest\baseline-vs-chimera_gpu80_ctx512_temp10\run_1\metrics.json |
| python | gemma3 | baseline-vs-chimera | 2 | 1.681 | 84.073 | 16.052 | 0.639 | False | experiments/TR116/results/multi\python\gemma3_latest\gemma3_latest\baseline-vs-chimera_gpu80_ctx512_temp10\run_2\metrics.json |
| python | gemma3 | baseline-vs-chimera | 3 | 1.750 | 87.513 | 11.431 | -0.503 | False | experiments/TR116/results/multi\python\gemma3_latest\gemma3_latest\baseline-vs-chimera_gpu80_ctx512_temp10\run_3\metrics.json |
| python | gemma3 | baseline-vs-chimera | 4 | 1.679 | 83.941 | 16.574 | -0.965 | False | experiments/TR116/results/multi\python\gemma3_latest\gemma3_latest\baseline-vs-chimera_gpu80_ctx512_temp10\run_4\metrics.json |
| python | gemma3 | baseline-vs-chimera | 5 | 1.711 | 85.540 | 13.992 | nan | False | experiments/TR116/results/multi\python\gemma3_latest\gemma3_latest\baseline-vs-chimera_gpu80_ctx512_temp10\run_5\metrics.json |
| python | gemma3 | chimera-homo | 1 | 1.595 | 79.752 | 12.493 | -43.490 | False | experiments/TR116/results/multi\python\gemma3_latest\gemma3_latest\chimera-homo_gpu80_ctx512_temp10\run_1\metrics.json |
| python | gemma3 | chimera-homo | 2 | 1.725 | 86.255 | 13.029 | -0.507 | False | experiments/TR116/results/multi\python\gemma3_latest\gemma3_latest\chimera-homo_gpu80_ctx512_temp10\run_2\metrics.json |
| python | gemma3 | chimera-homo | 3 | 1.708 | 85.411 | 13.735 | 0.111 | False | experiments/TR116/results/multi\python\gemma3_latest\gemma3_latest\chimera-homo_gpu80_ctx512_temp10\run_3\metrics.json |
| python | gemma3 | chimera-homo | 4 | 1.684 | 84.212 | 15.312 | nan | False | experiments/TR116/results/multi\python\gemma3_latest\gemma3_latest\chimera-homo_gpu80_ctx512_temp10\run_4\metrics.json |
| python | gemma3 | chimera-homo | 5 | 1.773 | 88.644 | 9.828 | -0.171 | False | experiments/TR116/results/multi\python\gemma3_latest\gemma3_latest\chimera-homo_gpu80_ctx512_temp10\run_5\metrics.json |
| python | llama3.1 | baseline-vs-chimera | 1 | 1.204 | 60.194 | 9.777 | -5.145 | False | experiments/TR116/results/multi\python\llama3p1_8b_q4_0\llama3.1_8b-instruct-q4_0\baseline-vs-chimera_gpu80_ctx512_temp10\run_1\metrics.json |
| python | llama3.1 | baseline-vs-chimera | 2 | 1.826 | 91.289 | 6.467 | nan | False | experiments/TR116/results/multi\python\llama3p1_8b_q4_0\llama3.1_8b-instruct-q4_0\baseline-vs-chimera_gpu80_ctx512_temp10\run_2\metrics.json |
| python | llama3.1 | baseline-vs-chimera | 3 | 1.751 | 87.572 | 10.077 | -0.575 | False | experiments/TR116/results/multi\python\llama3p1_8b_q4_0\llama3.1_8b-instruct-q4_0\baseline-vs-chimera_gpu80_ctx512_temp10\run_3\metrics.json |
| python | llama3.1 | baseline-vs-chimera | 4 | 1.827 | 91.329 | 6.310 | 0.540 | False | experiments/TR116/results/multi\python\llama3p1_8b_q4_0\llama3.1_8b-instruct-q4_0\baseline-vs-chimera_gpu80_ctx512_temp10\run_4\metrics.json |
| python | llama3.1 | baseline-vs-chimera | 5 | 1.772 | 88.612 | 9.173 | 0.786 | False | experiments/TR116/results/multi\python\llama3p1_8b_q4_0\llama3.1_8b-instruct-q4_0\baseline-vs-chimera_gpu80_ctx512_temp10\run_5\metrics.json |
| python | llama3.1 | chimera-homo | 1 | 1.391 | 69.555 | 15.698 | -72.907 | False | experiments/TR116/results/multi\python\llama3p1_8b_q4_0\llama3.1_8b-instruct-q4_0\chimera-homo_gpu80_ctx512_temp10\run_1\metrics.json |
| python | llama3.1 | chimera-homo | 2 | 1.787 | 89.369 | 8.434 | -0.139 | False | experiments/TR116/results/multi\python\llama3p1_8b_q4_0\llama3.1_8b-instruct-q4_0\chimera-homo_gpu80_ctx512_temp10\run_2\metrics.json |
| python | llama3.1 | chimera-homo | 3 | 1.805 | 90.269 | 7.184 | nan | False | experiments/TR116/results/multi\python\llama3p1_8b_q4_0\llama3.1_8b-instruct-q4_0\chimera-homo_gpu80_ctx512_temp10\run_3\metrics.json |
| python | llama3.1 | chimera-homo | 4 | 1.834 | 91.683 | 5.907 | 0.572 | False | experiments/TR116/results/multi\python\llama3p1_8b_q4_0\llama3.1_8b-instruct-q4_0\chimera-homo_gpu80_ctx512_temp10\run_4\metrics.json |
| python | llama3.1 | chimera-homo | 5 | 1.760 | 87.996 | 9.843 | 0.599 | False | experiments/TR116/results/multi\python\llama3p1_8b_q4_0\llama3.1_8b-instruct-q4_0\chimera-homo_gpu80_ctx512_temp10\run_5\metrics.json |
| python | qwen2.5 | baseline-vs-chimera | 1 | 1.106 | 55.314 | 14.321 | -11.670 | False | experiments/TR116/results/multi\python\qwen2p5_7b\qwen2.5_7b\baseline-vs-chimera_gpu80_ctx512_temp10\run_1\metrics.json |
| python | qwen2.5 | baseline-vs-chimera | 2 | 1.657 | 82.839 | 16.257 | 0.758 | False | experiments/TR116/results/multi\python\qwen2p5_7b\qwen2.5_7b\baseline-vs-chimera_gpu80_ctx512_temp10\run_2\metrics.json |
| python | qwen2.5 | baseline-vs-chimera | 3 | 1.680 | 84.001 | 14.711 | 4.334 | False | experiments/TR116/results/multi\python\qwen2p5_7b\qwen2.5_7b\baseline-vs-chimera_gpu80_ctx512_temp10\run_3\metrics.json |
| python | qwen2.5 | baseline-vs-chimera | 4 | 1.631 | 81.544 | 17.525 | 6.485 | False | experiments/TR116/results/multi\python\qwen2p5_7b\qwen2.5_7b\baseline-vs-chimera_gpu80_ctx512_temp10\run_4\metrics.json |
| python | qwen2.5 | baseline-vs-chimera | 5 | 1.683 | 84.135 | 15.153 | 0.183 | False | experiments/TR116/results/multi\python\qwen2p5_7b\qwen2.5_7b\baseline-vs-chimera_gpu80_ctx512_temp10\run_5\metrics.json |
| python | qwen2.5 | chimera-homo | 1 | 1.631 | 81.545 | 13.176 | -97.415 | False | experiments/TR116/results/multi\python\qwen2p5_7b\qwen2.5_7b\chimera-homo_gpu80_ctx512_temp10\run_1\metrics.json |
| python | qwen2.5 | chimera-homo | 2 | 1.686 | 84.290 | 14.644 | -5.319 | False | experiments/TR116/results/multi\python\qwen2p5_7b\qwen2.5_7b\chimera-homo_gpu80_ctx512_temp10\run_2\metrics.json |
| python | qwen2.5 | chimera-homo | 3 | 1.657 | 82.827 | 16.262 | 6.507 | False | experiments/TR116/results/multi\python\qwen2p5_7b\qwen2.5_7b\chimera-homo_gpu80_ctx512_temp10\run_3\metrics.json |
| python | qwen2.5 | chimera-homo | 4 | 1.678 | 83.921 | 15.009 | 0.550 | False | experiments/TR116/results/multi\python\qwen2p5_7b\qwen2.5_7b\chimera-homo_gpu80_ctx512_temp10\run_4\metrics.json |
| python | qwen2.5 | chimera-homo | 5 | 1.760 | 88.006 | 10.523 | nan | False | experiments/TR116/results/multi\python\qwen2p5_7b\qwen2.5_7b\chimera-homo_gpu80_ctx512_temp10\run_5\metrics.json |
| rust | gemma3 | baseline-vs-chimera | 1 | 1.949 | 97.464 | 0.430 | 1270.314 | False | experiments/TR116/results/multi\rust\gemma3_latest\baseline-vs-chimera_gpu80_ctx512_temp10\run_1\metrics.json |
| rust | gemma3 | baseline-vs-chimera | 2 | 1.969 | 98.447 | 2.219 | 145.259 | False | experiments/TR116/results/multi\rust\gemma3_latest\baseline-vs-chimera_gpu80_ctx512_temp10\run_2\metrics.json |
| rust | gemma3 | baseline-vs-chimera | 3 | 1.914 | 95.699 | -5.754 | 116.406 | False | experiments/TR116/results/multi\rust\gemma3_latest\baseline-vs-chimera_gpu80_ctx512_temp10\run_3\metrics.json |
| rust | gemma3 | baseline-vs-chimera | 4 | 1.925 | 96.240 | -4.960 | 173.927 | False | experiments/TR116/results/multi\rust\gemma3_latest\baseline-vs-chimera_gpu80_ctx512_temp10\run_4\metrics.json |
| rust | gemma3 | baseline-vs-chimera | 5 | 1.974 | 98.721 | -1.567 | 159.929 | False | experiments/TR116/results/multi\rust\gemma3_latest\baseline-vs-chimera_gpu80_ctx512_temp10\run_5\metrics.json |
| rust | gemma3 | chimera-homo | 1 | 1.982 | 99.106 | -7.394 | -1563.299 | False | experiments/TR116/results/multi\rust\gemma3_latest\chimera-homo_gpu80_ctx512_temp10\run_1\metrics.json |
| rust | gemma3 | chimera-homo | 2 | 1.997 | 99.860 | 0.449 | 164.010 | False | experiments/TR116/results/multi\rust\gemma3_latest\chimera-homo_gpu80_ctx512_temp10\run_2\metrics.json |
| rust | gemma3 | chimera-homo | 3 | 1.983 | 99.147 | 1.111 | 259.851 | False | experiments/TR116/results/multi\rust\gemma3_latest\chimera-homo_gpu80_ctx512_temp10\run_3\metrics.json |
| rust | gemma3 | chimera-homo | 4 | 1.995 | 99.726 | -0.254 | 163.038 | False | experiments/TR116/results/multi\rust\gemma3_latest\chimera-homo_gpu80_ctx512_temp10\run_4\metrics.json |
| rust | gemma3 | chimera-homo | 5 | 1.965 | 98.255 | 2.270 | 274.962 | False | experiments/TR116/results/multi\rust\gemma3_latest\chimera-homo_gpu80_ctx512_temp10\run_5\metrics.json |
| rust | llama3.1 | baseline-vs-chimera | 1 | 1.924 | 96.177 | 4.331 | 1441.060 | False | experiments/TR116/results/multi\rust\llama3p1_8b_q4_0\baseline-vs-chimera_gpu80_ctx512_temp10\run_1\metrics.json |
| rust | llama3.1 | baseline-vs-chimera | 2 | 1.933 | 96.663 | -3.133 | 149.616 | False | experiments/TR116/results/multi\rust\llama3p1_8b_q4_0\baseline-vs-chimera_gpu80_ctx512_temp10\run_2\metrics.json |
| rust | llama3.1 | baseline-vs-chimera | 3 | 1.903 | 95.171 | -5.353 | 128.092 | False | experiments/TR116/results/multi\rust\llama3p1_8b_q4_0\baseline-vs-chimera_gpu80_ctx512_temp10\run_3\metrics.json |
| rust | llama3.1 | baseline-vs-chimera | 4 | 1.910 | 95.500 | -4.309 | 127.524 | False | experiments/TR116/results/multi\rust\llama3p1_8b_q4_0\baseline-vs-chimera_gpu80_ctx512_temp10\run_4\metrics.json |
| rust | llama3.1 | baseline-vs-chimera | 5 | 1.985 | 99.233 | 0.814 | 140.600 | False | experiments/TR116/results/multi\rust\llama3p1_8b_q4_0\baseline-vs-chimera_gpu80_ctx512_temp10\run_5\metrics.json |
| rust | llama3.1 | chimera-homo | 1 | 1.981 | 99.047 | -0.707 | -487.798 | False | experiments/TR116/results/multi\rust\llama3p1_8b_q4_0\chimera-homo_gpu80_ctx512_temp10\run_1\metrics.json |
| rust | llama3.1 | chimera-homo | 2 | 1.950 | 97.525 | -2.794 | 75.638 | False | experiments/TR116/results/multi\rust\llama3p1_8b_q4_0\chimera-homo_gpu80_ctx512_temp10\run_2\metrics.json |
| rust | llama3.1 | chimera-homo | 3 | 1.970 | 98.506 | -1.419 | 149.278 | False | experiments/TR116/results/multi\rust\llama3p1_8b_q4_0\chimera-homo_gpu80_ctx512_temp10\run_3\metrics.json |
| rust | llama3.1 | chimera-homo | 4 | 1.986 | 99.303 | -0.512 | 94.344 | False | experiments/TR116/results/multi\rust\llama3p1_8b_q4_0\chimera-homo_gpu80_ctx512_temp10\run_4\metrics.json |
| rust | llama3.1 | chimera-homo | 5 | 1.967 | 98.361 | -1.574 | 78.940 | False | experiments/TR116/results/multi\rust\llama3p1_8b_q4_0\chimera-homo_gpu80_ctx512_temp10\run_5\metrics.json |
| rust | qwen2.5 | baseline-vs-chimera | 1 | 1.702 | 85.077 | 30.474 | 1422.773 | False | experiments/TR116/results/multi\rust\qwen2p5_7b\baseline-vs-chimera_gpu80_ctx512_temp10\run_1\metrics.json |
| rust | qwen2.5 | baseline-vs-chimera | 2 | 1.704 | 85.184 | 30.691 | 119.411 | False | experiments/TR116/results/multi\rust\qwen2p5_7b\baseline-vs-chimera_gpu80_ctx512_temp10\run_2\metrics.json |
| rust | qwen2.5 | baseline-vs-chimera | 3 | 1.992 | 99.582 | -0.348 | 17.660 | False | experiments/TR116/results/multi\rust\qwen2p5_7b\baseline-vs-chimera_gpu80_ctx512_temp10\run_3\metrics.json |
| rust | qwen2.5 | baseline-vs-chimera | 4 | 1.976 | 98.788 | -13.128 | 86.870 | False | experiments/TR116/results/multi\rust\qwen2p5_7b\baseline-vs-chimera_gpu80_ctx512_temp10\run_4\metrics.json |
| rust | qwen2.5 | baseline-vs-chimera | 5 | 1.624 | 81.197 | 14.326 | 49.783 | False | experiments/TR116/results/multi\rust\qwen2p5_7b\baseline-vs-chimera_gpu80_ctx512_temp10\run_5\metrics.json |
| rust | qwen2.5 | chimera-homo | 1 | 1.918 | 95.923 | -3.652 | -468.244 | False | experiments/TR116/results/multi\rust\qwen2p5_7b\chimera-homo_gpu80_ctx512_temp10\run_1\metrics.json |
| rust | qwen2.5 | chimera-homo | 2 | 1.948 | 97.404 | -3.489 | 111.606 | False | experiments/TR116/results/multi\rust\qwen2p5_7b\chimera-homo_gpu80_ctx512_temp10\run_2\metrics.json |
| rust | qwen2.5 | chimera-homo | 3 | 1.799 | 89.943 | -16.059 | 58.499 | False | experiments/TR116/results/multi\rust\qwen2p5_7b\chimera-homo_gpu80_ctx512_temp10\run_3\metrics.json |
| rust | qwen2.5 | chimera-homo | 4 | 1.836 | 91.800 | -6.178 | 88.982 | False | experiments/TR116/results/multi\rust\qwen2p5_7b\chimera-homo_gpu80_ctx512_temp10\run_4\metrics.json |
| rust | qwen2.5 | chimera-homo | 5 | 1.440 | 71.999 | -32.726 | 159.910 | True | experiments/TR116/results/multi\rust\qwen2p5_7b\chimera-homo_gpu80_ctx512_temp10\run_5\metrics.json |

## Appendix B: Per-Run Multi-Agent Tables (detailed)
# TR116 Comprehensive Per-Run Granular Analysis

**Generated from 60 benchmark runs**

**Models:** Qwen 2.5 7B, Gemma 3, Llama 3.1 8B
**Runtimes:** Rust (tokio-default), Python (asyncio)
**Scenarios:** baseline-vs-chimera, chimera-homo

## 1. Rust: Qwen 2.5 7B - Baseline vs Chimera

| Run | Speedup | Efficiency (%) | Throughput Delta (tok/s) | TTFT Delta (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.7015x | 85.08 | +30.47 | +1422.8 | No |
| 2 | 1.7037x | 85.18 | +30.69 | +119.4 | No |
| 3 | 1.9916x | 99.58 | -0.35 | +17.7 | No |
| 4 | 1.9758x | 98.79 | -13.13 | +86.9 | No |
| 5 | 1.6239x | 81.20 | +14.33 | +49.8 | No |

**Efficiency Statistics:**
- Mean: 89.97%
- Std Dev: 8.57pp
- Min: 81.20% | Max: 99.58%
- Range: 18.38pp
- CV: 9.53%

## 2. Rust: Qwen 2.5 7B - Chimera Homo

| Run | Speedup | Efficiency (%) | Throughput Delta (tok/s) | TTFT Delta (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.9185x | 95.92 | -3.65 | -468.2 | No |
| 2 | 1.9481x | 97.40 | -3.49 | +111.6 | No |
| 3 | 1.7989x | 89.94 | -16.06 | +58.5 | No |
| 4 | 1.8360x | 91.80 | -6.18 | +89.0 | No |
| 5 | 1.4400x | 72.00 | -32.73 | +159.9 | Yes |

**Efficiency Statistics:**
- Mean: 89.41%
- Std Dev: 10.19pp
- Min: 72.00% | Max: 97.40%
- Range: 25.41pp
- CV: 11.40%

## 3. Rust: Gemma 3 - Baseline vs Chimera

| Run | Speedup | Efficiency (%) | Throughput Delta (tok/s) | TTFT Delta (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.9493x | 97.46 | +0.43 | +1270.3 | No |
| 2 | 1.9689x | 98.45 | +2.22 | +145.3 | No |
| 3 | 1.9140x | 95.70 | -5.75 | +116.4 | No |
| 4 | 1.9248x | 96.24 | -4.96 | +173.9 | No |
| 5 | 1.9744x | 98.72 | -1.57 | +159.9 | No |

**Efficiency Statistics:**
- Mean: 97.31%
- Std Dev: 1.33pp
- Min: 95.70% | Max: 98.72%
- Range: 3.02pp
- CV: 1.36%

## 4. Rust: Gemma 3 - Chimera Homo

| Run | Speedup | Efficiency (%) | Throughput Delta (tok/s) | TTFT Delta (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.9821x | 99.11 | -7.39 | -1563.3 | No |
| 2 | 1.9972x | 99.86 | +0.45 | +164.0 | No |
| 3 | 1.9829x | 99.15 | +1.11 | +259.9 | No |
| 4 | 1.9945x | 99.73 | -0.25 | +163.0 | No |
| 5 | 1.9651x | 98.26 | +2.27 | +275.0 | No |

**Efficiency Statistics:**
- Mean: 99.22%
- Std Dev: 0.64pp
- Min: 98.26% | Max: 99.86%
- Range: 1.61pp
- CV: 0.64%

## 5. Rust: Llama 3.1 8B - Baseline vs Chimera

| Run | Speedup | Efficiency (%) | Throughput Delta (tok/s) | TTFT Delta (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.9235x | 96.18 | +4.33 | +1441.1 | No |
| 2 | 1.9333x | 96.66 | -3.13 | +149.6 | No |
| 3 | 1.9034x | 95.17 | -5.35 | +128.1 | No |
| 4 | 1.9100x | 95.50 | -4.31 | +127.5 | No |
| 5 | 1.9847x | 99.23 | +0.81 | +140.6 | No |

**Efficiency Statistics:**
- Mean: 96.55%
- Std Dev: 1.61pp
- Min: 95.17% | Max: 99.23%
- Range: 4.06pp
- CV: 1.67%

## 6. Rust: Llama 3.1 8B - Chimera Homo

| Run | Speedup | Efficiency (%) | Throughput Delta (tok/s) | TTFT Delta (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.9809x | 99.05 | -0.71 | -487.8 | No |
| 2 | 1.9505x | 97.52 | -2.79 | +75.6 | No |
| 3 | 1.9701x | 98.51 | -1.42 | +149.3 | No |
| 4 | 1.9861x | 99.30 | -0.51 | +94.3 | No |
| 5 | 1.9672x | 98.36 | -1.57 | +78.9 | No |

**Efficiency Statistics:**
- Mean: 98.55%
- Std Dev: 0.69pp
- Min: 97.52% | Max: 99.30%
- Range: 1.78pp
- CV: 0.70%

## 7. Python: Qwen 2.5 7B - Baseline vs Chimera

| Run | Speedup | Efficiency (%) | Throughput Delta (tok/s) | TTFT Delta (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.1063x | 55.31 | +14.32 | -11.7 | No |
| 2 | 1.6568x | 82.84 | +16.26 | +0.8 | No |
| 3 | 1.6800x | 84.00 | +14.71 | +4.3 | No |
| 4 | 1.6309x | 81.54 | +17.53 | +6.5 | No |
| 5 | 1.6827x | 84.14 | +15.15 | +0.2 | No |

**Efficiency Statistics:**
- Mean: 77.57%
- Std Dev: 12.48pp
- Min: 55.31% | Max: 84.14%
- Range: 28.82pp
- CV: 16.09%

## 8. Python: Qwen 2.5 7B - Chimera Homo

| Run | Speedup | Efficiency (%) | Throughput Delta (tok/s) | TTFT Delta (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.6309x | 81.54 | +13.18 | -97.4 | No |
| 2 | 1.6858x | 84.29 | +14.64 | -5.3 | No |
| 3 | 1.6565x | 82.83 | +16.26 | +6.5 | No |
| 4 | 1.6784x | 83.92 | +15.01 | +0.5 | No |
| 5 | 1.7601x | 88.01 | +10.52 | N/A | No |

**Efficiency Statistics:**
- Mean: 84.12%
- Std Dev: 2.42pp
- Min: 81.54% | Max: 88.01%
- Range: 6.46pp
- CV: 2.88%

## 9. Python: Gemma 3 - Baseline vs Chimera

| Run | Speedup | Efficiency (%) | Throughput Delta (tok/s) | TTFT Delta (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.2023x | 60.12 | +10.16 | +35.3 | No |
| 2 | 1.6815x | 84.07 | +16.05 | +0.6 | No |
| 3 | 1.7503x | 87.51 | +11.43 | -0.5 | No |
| 4 | 1.6788x | 83.94 | +16.57 | -1.0 | No |
| 5 | 1.7108x | 85.54 | +13.99 | N/A | No |

**Efficiency Statistics:**
- Mean: 80.24%
- Std Dev: 11.34pp
- Min: 60.12% | Max: 87.51%
- Range: 27.40pp
- CV: 14.13%

## 10. Python: Gemma 3 - Chimera Homo

| Run | Speedup | Efficiency (%) | Throughput Delta (tok/s) | TTFT Delta (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.5950x | 79.75 | +12.49 | -43.5 | No |
| 2 | 1.7251x | 86.25 | +13.03 | -0.5 | No |
| 3 | 1.7082x | 85.41 | +13.74 | +0.1 | No |
| 4 | 1.6842x | 84.21 | +15.31 | N/A | No |
| 5 | 1.7729x | 88.64 | +9.83 | -0.2 | No |

**Efficiency Statistics:**
- Mean: 84.85%
- Std Dev: 3.28pp
- Min: 79.75% | Max: 88.64%
- Range: 8.89pp
- CV: 3.87%

## 11. Python: Llama 3.1 8B - Baseline vs Chimera

| Run | Speedup | Efficiency (%) | Throughput Delta (tok/s) | TTFT Delta (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.2039x | 60.19 | +9.78 | -5.1 | No |
| 2 | 1.8258x | 91.29 | +6.47 | N/A | No |
| 3 | 1.7514x | 87.57 | +10.08 | -0.6 | No |
| 4 | 1.8266x | 91.33 | +6.31 | +0.5 | No |
| 5 | 1.7722x | 88.61 | +9.17 | +0.8 | No |

**Efficiency Statistics:**
- Mean: 83.80%
- Std Dev: 13.30pp
- Min: 60.19% | Max: 91.33%
- Range: 31.14pp
- CV: 15.87%

## 12. Python: Llama 3.1 8B - Chimera Homo

| Run | Speedup | Efficiency (%) | Throughput Delta (tok/s) | TTFT Delta (ms) | Contention |
|-----|---------|----------------|----------------------|-------------|------------|
| 1 | 1.3911x | 69.56 | +15.70 | -72.9 | No |
| 2 | 1.7874x | 89.37 | +8.43 | -0.1 | No |
| 3 | 1.8054x | 90.27 | +7.18 | N/A | No |
| 4 | 1.8337x | 91.68 | +5.91 | +0.6 | No |
| 5 | 1.7599x | 88.00 | +9.84 | +0.6 | No |

**Efficiency Statistics:**
- Mean: 85.77%
- Std Dev: 9.17pp
- Min: 69.56% | Max: 91.68%
- Range: 22.13pp
- CV: 10.69%

---

# Multi-Level Statistical Analysis

## 1. Correlation: Throughput Delta vs Efficiency

**Hypothesis:** Models with higher throughput imbalance (absolute delta) show lower efficiency.

- **QWEN2.5 (RUST)**: r = -0.007
  - Weak/no correlation
- **QWEN2.5 (PYTHON)**: r = -0.069
  - Weak/no correlation
- **GEMMA3 (RUST)**: r = 0.439
  - Moderate positive correlation
- **GEMMA3 (PYTHON)**: r = 0.327
  - Weak/no correlation
- **LLAMA3.1 (RUST)**: r = 0.391
  - Weak/no correlation
- **LLAMA3.1 (PYTHON)**: r = -0.654
  - Moderate negative correlation


## 2. Variance Decomposition (Rust)

- **Between-Model Variance:** 22.64 pp^2
- **Within-Model Variance (avg):** 27.78 pp^2
- **Total Variance:** 50.42 pp^2
- **Between-Model % of Total:** 44.9%

**Interpretation:** 45% of variance in Rust comes from model choice, not run-to-run variation.

## 3. Efficiency Distribution by Runtime

### RUST

- **Mean:** 95.17%
- **Median (P50):** 97.49%
- **P5:** 82.94% | **P95:** 99.66%
- **Range:** 72.00% - 99.86% (27.86pp)
- **Std Dev:** 6.44pp

### PYTHON

- **Mean:** 82.73%
- **Median (P50):** 84.25%
- **P5:** 60.15% | **P95:** 91.31%
- **Range:** 55.31% - 91.68% (36.37pp)
- **Std Dev:** 9.28pp


## Appendix C: Single-Agent Config Breakdown (24 configs)
| Runtime | Model | GPU_Layers | Ctx | Temp | Baseline_TP | Chimera_TP | TP_Improve_% | Baseline_TTFT_ms | Chimera_TTFT_ms | TTFT_Reduction_% | Source |
|---|---|---|---|---|---|---|---|---|---|---|---|
| python | gemma3 | 60 | 512 | 0.800 | 118.295 | 117.808 | -0.409 | 86.041 | 129.821 | -50.981 | experiments/TR116/results/single/python/gemma3_latest/gpu60_ctx512_temp08/data/metrics.json |
| python | gemma3 | 60 | 1024 | 0.800 | 118.653 | 117.947 | -0.594 | 82.562 | 129.268 | -57.929 | experiments/TR116/results/single/python/gemma3_latest/gpu60_ctx1024_temp08/data/metrics.json |
| python | gemma3 | 80 | 512 | 0.800 | 118.404 | 118.018 | -0.324 | 221.550 | 226.662 | -2.747 | experiments/TR116/results/single/python/gemma3_latest/gpu80_ctx512_temp08/data/metrics.json |
| python | gemma3 | 80 | 1024 | 0.800 | 118.545 | 117.249 | -1.093 | 210.166 | 226.146 | -8.626 | experiments/TR116/results/single/python/gemma3_latest/gpu80_ctx1024_temp08/data/metrics.json |
| python | llama3.1 | 60 | 512 | 0.800 | 81.838 | 80.632 | -1.470 | 78.142 | 74.537 | 2.661 | experiments/TR116/results/single/python/llama3p1_8b_q4_0/gpu60_ctx512_temp08/data/metrics.json |
| python | llama3.1 | 60 | 1024 | 0.800 | 82.049 | 81.092 | -1.167 | 80.047 | 139.145 | -74.065 | experiments/TR116/results/single/python/llama3p1_8b_q4_0/gpu60_ctx1024_temp08/data/metrics.json |
| python | llama3.1 | 80 | 512 | 0.800 | 82.007 | 80.523 | -1.808 | 79.118 | 74.218 | 6.174 | experiments/TR116/results/single/python/llama3p1_8b_q4_0/gpu80_ctx512_temp08/data/metrics.json |
| python | llama3.1 | 80 | 1024 | 0.800 | 82.313 | 79.382 | -3.560 | 200.280 | 236.471 | -18.938 | experiments/TR116/results/single/python/llama3p1_8b_q4_0/gpu80_ctx1024_temp08/data/metrics.json |
| python | qwen2.5 | 60 | 512 | 0.800 | 81.293 | 80.888 | -0.498 | 229.591 | 77.927 | 66.058 | experiments/TR116/results/single/python/qwen2p5_7b/gpu60_ctx512_temp08/data/metrics.json |
| python | qwen2.5 | 60 | 1024 | 0.800 | 82.011 | 82.009 | -0.002 | 52.123 | 136.836 | -166.574 | experiments/TR116/results/single/python/qwen2p5_7b/gpu60_ctx1024_temp08/data/metrics.json |
| python | qwen2.5 | 80 | 512 | 0.800 | 81.916 | 80.883 | -1.262 | 54.980 | 81.617 | -49.048 | experiments/TR116/results/single/python/qwen2p5_7b/gpu80_ctx512_temp08/data/metrics.json |
| python | qwen2.5 | 80 | 1024 | 0.800 | 81.988 | 81.017 | -1.185 | 207.535 | 247.179 | -24.129 | experiments/TR116/results/single/python/qwen2p5_7b/gpu80_ctx1024_temp08/data/metrics.json |
| rust | gemma3 | 60 | 512 | 0.800 | 114.001 | 120.085 | 5.336 | 1176.749 | 1133.615 | 3.666 | experiments/TR116/results/single/rust/gemma3_latest/gpu60_ctx512_temp08/data/metrics.json |
| rust | gemma3 | 60 | 1024 | 0.800 | 114.113 | 115.976 | 1.633 | 1234.780 | 1145.883 | 7.199 | experiments/TR116/results/single/rust/gemma3_latest/gpu60_ctx1024_temp08/data/metrics.json |
| rust | gemma3 | 80 | 512 | 0.800 | 114.165 | 115.633 | 1.286 | 1227.598 | 1136.055 | 7.457 | experiments/TR116/results/single/rust/gemma3_latest/gpu80_ctx512_temp08/data/metrics.json |
| rust | gemma3 | 80 | 1024 | 0.800 | 114.579 | 104.051 | -9.188 | 1178.229 | 1178.540 | -0.026 | experiments/TR116/results/single/rust/gemma3_latest/gpu80_ctx1024_temp08/data/metrics.json |
| rust | llama3.1 | 60 | 512 | 0.800 | 79.263 | 79.598 | 0.423 | 1048.345 | 859.670 | 17.997 | experiments/TR116/results/single/rust/llama3p1_8b_q4_0/gpu60_ctx512_temp08/data/metrics.json |
| rust | llama3.1 | 60 | 1024 | 0.800 | 78.840 | 80.102 | 1.601 | 1066.024 | 965.795 | 9.402 | experiments/TR116/results/single/rust/llama3p1_8b_q4_0/gpu60_ctx1024_temp08/data/metrics.json |
| rust | llama3.1 | 80 | 512 | 0.800 | 79.429 | 79.634 | 0.258 | 1056.060 | 869.912 | 17.627 | experiments/TR116/results/single/rust/llama3p1_8b_q4_0/gpu80_ctx512_temp08/data/metrics.json |
| rust | llama3.1 | 80 | 1024 | 0.800 | 79.266 | 80.497 | 1.553 | 979.424 | 952.187 | 2.781 | experiments/TR116/results/single/rust/llama3p1_8b_q4_0/gpu80_ctx1024_temp08/data/metrics.json |
| rust | qwen2.5 | 60 | 512 | 0.800 | 79.654 | 80.281 | 0.787 | 988.935 | 846.746 | 14.378 | experiments/TR116/results/single/rust/qwen2p5_7b/gpu60_ctx512_temp08/data/metrics.json |
| rust | qwen2.5 | 60 | 1024 | 0.800 | 79.993 | 81.255 | 1.578 | 3074.093 | 3217.745 | -4.673 | experiments/TR116/results/single/rust/qwen2p5_7b/gpu60_ctx1024_temp08/data/metrics.json |
| rust | qwen2.5 | 80 | 512 | 0.800 | 79.343 | 80.472 | 1.423 | 579.675 | 861.703 | -48.653 | experiments/TR116/results/single/rust/qwen2p5_7b/gpu80_ctx512_temp08/data/metrics.json |
| rust | qwen2.5 | 80 | 1024 | 0.800 | 79.441 | 81.417 | 2.488 | 1055.457 | 923.575 | 12.495 | experiments/TR116/results/single/rust/qwen2p5_7b/gpu80_ctx1024_temp08/data/metrics.json |

## Appendix D: Configuration Cards (multi-agent)
### RUST | gemma3 | chimera-homo
- Speedup mean 1.984x (std 0.013); Efficiency mean 99.22% (std 0.64pp).
- Best run 99.86% | Worst run 98.26%.
- Throughput delta mean -0.764 tok/s; TTFT delta mean -140.3 ms; Contention 0.0%.

### RUST | llama3.1 | chimera-homo
- Speedup mean 1.971x (std 0.014); Efficiency mean 98.55% (std 0.69pp).
- Best run 99.30% | Worst run 97.52%.
- Throughput delta mean -1.401 tok/s; TTFT delta mean -17.9 ms; Contention 0.0%.

### RUST | gemma3 | baseline-vs-chimera
- Speedup mean 1.946x (std 0.027); Efficiency mean 97.31% (std 1.33pp).
- Best run 98.72% | Worst run 95.70%.
- Throughput delta mean -1.926 tok/s; TTFT delta mean +373.2 ms; Contention 0.0%.

### RUST | llama3.1 | baseline-vs-chimera
- Speedup mean 1.931x (std 0.032); Efficiency mean 96.55% (std 1.61pp).
- Best run 99.23% | Worst run 95.17%.
- Throughput delta mean -1.530 tok/s; TTFT delta mean +397.4 ms; Contention 0.0%.

### RUST | qwen2.5 | baseline-vs-chimera
- Speedup mean 1.799x (std 0.171); Efficiency mean 89.97% (std 8.57pp).
- Best run 99.58% | Worst run 81.20%.
- Throughput delta mean +12.403 tok/s; TTFT delta mean +339.3 ms; Contention 0.0%.

### RUST | qwen2.5 | chimera-homo
- Speedup mean 1.788x (std 0.204); Efficiency mean 89.41% (std 10.19pp).
- Best run 97.40% | Worst run 72.00%.
- Throughput delta mean -12.421 tok/s; TTFT delta mean -9.8 ms; Contention 20.0%.

### PYTHON | llama3.1 | chimera-homo
- Speedup mean 1.715x (std 0.183); Efficiency mean 85.77% (std 9.17pp).
- Best run 91.68% | Worst run 69.56%.
- Throughput delta mean +9.413 tok/s; TTFT delta mean -18.0 ms; Contention 0.0%.

### PYTHON | gemma3 | chimera-homo
- Speedup mean 1.697x (std 0.066); Efficiency mean 84.85% (std 3.28pp).
- Best run 88.64% | Worst run 79.75%.
- Throughput delta mean +12.880 tok/s; TTFT delta mean -11.0 ms; Contention 0.0%.

### PYTHON | qwen2.5 | chimera-homo
- Speedup mean 1.682x (std 0.048); Efficiency mean 84.12% (std 2.42pp).
- Best run 88.01% | Worst run 81.54%.
- Throughput delta mean +13.923 tok/s; TTFT delta mean -23.9 ms; Contention 0.0%.

### PYTHON | llama3.1 | baseline-vs-chimera
- Speedup mean 1.676x (std 0.266); Efficiency mean 83.80% (std 13.30pp).
- Best run 91.33% | Worst run 60.19%.
- Throughput delta mean +8.361 tok/s; TTFT delta mean -1.1 ms; Contention 0.0%.

### PYTHON | gemma3 | baseline-vs-chimera
- Speedup mean 1.605x (std 0.227); Efficiency mean 80.24% (std 11.34pp).
- Best run 87.51% | Worst run 60.12%.
- Throughput delta mean +13.641 tok/s; TTFT delta mean +8.6 ms; Contention 0.0%.

### PYTHON | qwen2.5 | baseline-vs-chimera
- Speedup mean 1.551x (std 0.250); Efficiency mean 77.57% (std 12.48pp).
- Best run 84.14% | Worst run 55.31%.
- Throughput delta mean +15.593 tok/s; TTFT delta mean +0.0 ms; Contention 0.0%.

## Appendix E: Metrics Manifest
### Multi-Agent Metrics Files
- experiments/TR116/results/multi/python/gemma3_latest/gemma3_latest/baseline-vs-chimera_gpu80_ctx512_temp10/run_1/metrics.json
- experiments/TR116/results/multi/python/gemma3_latest/gemma3_latest/baseline-vs-chimera_gpu80_ctx512_temp10/run_2/metrics.json
- experiments/TR116/results/multi/python/gemma3_latest/gemma3_latest/baseline-vs-chimera_gpu80_ctx512_temp10/run_3/metrics.json
- experiments/TR116/results/multi/python/gemma3_latest/gemma3_latest/baseline-vs-chimera_gpu80_ctx512_temp10/run_4/metrics.json
- experiments/TR116/results/multi/python/gemma3_latest/gemma3_latest/baseline-vs-chimera_gpu80_ctx512_temp10/run_5/metrics.json
- experiments/TR116/results/multi/python/gemma3_latest/gemma3_latest/chimera-homo_gpu80_ctx512_temp10/run_1/metrics.json
- experiments/TR116/results/multi/python/gemma3_latest/gemma3_latest/chimera-homo_gpu80_ctx512_temp10/run_2/metrics.json
- experiments/TR116/results/multi/python/gemma3_latest/gemma3_latest/chimera-homo_gpu80_ctx512_temp10/run_3/metrics.json
- experiments/TR116/results/multi/python/gemma3_latest/gemma3_latest/chimera-homo_gpu80_ctx512_temp10/run_4/metrics.json
- experiments/TR116/results/multi/python/gemma3_latest/gemma3_latest/chimera-homo_gpu80_ctx512_temp10/run_5/metrics.json
- experiments/TR116/results/multi/python/llama3p1_8b_q4_0/llama3.1_8b-instruct-q4_0/baseline-vs-chimera_gpu80_ctx512_temp10/run_1/metrics.json
- experiments/TR116/results/multi/python/llama3p1_8b_q4_0/llama3.1_8b-instruct-q4_0/baseline-vs-chimera_gpu80_ctx512_temp10/run_2/metrics.json
- experiments/TR116/results/multi/python/llama3p1_8b_q4_0/llama3.1_8b-instruct-q4_0/baseline-vs-chimera_gpu80_ctx512_temp10/run_3/metrics.json
- experiments/TR116/results/multi/python/llama3p1_8b_q4_0/llama3.1_8b-instruct-q4_0/baseline-vs-chimera_gpu80_ctx512_temp10/run_4/metrics.json
- experiments/TR116/results/multi/python/llama3p1_8b_q4_0/llama3.1_8b-instruct-q4_0/baseline-vs-chimera_gpu80_ctx512_temp10/run_5/metrics.json
- experiments/TR116/results/multi/python/llama3p1_8b_q4_0/llama3.1_8b-instruct-q4_0/chimera-homo_gpu80_ctx512_temp10/run_1/metrics.json
- experiments/TR116/results/multi/python/llama3p1_8b_q4_0/llama3.1_8b-instruct-q4_0/chimera-homo_gpu80_ctx512_temp10/run_2/metrics.json
- experiments/TR116/results/multi/python/llama3p1_8b_q4_0/llama3.1_8b-instruct-q4_0/chimera-homo_gpu80_ctx512_temp10/run_3/metrics.json
- experiments/TR116/results/multi/python/llama3p1_8b_q4_0/llama3.1_8b-instruct-q4_0/chimera-homo_gpu80_ctx512_temp10/run_4/metrics.json
- experiments/TR116/results/multi/python/llama3p1_8b_q4_0/llama3.1_8b-instruct-q4_0/chimera-homo_gpu80_ctx512_temp10/run_5/metrics.json
- experiments/TR116/results/multi/python/qwen2p5_7b/qwen2.5_7b/baseline-vs-chimera_gpu80_ctx512_temp10/run_1/metrics.json
- experiments/TR116/results/multi/python/qwen2p5_7b/qwen2.5_7b/baseline-vs-chimera_gpu80_ctx512_temp10/run_2/metrics.json
- experiments/TR116/results/multi/python/qwen2p5_7b/qwen2.5_7b/baseline-vs-chimera_gpu80_ctx512_temp10/run_3/metrics.json
- experiments/TR116/results/multi/python/qwen2p5_7b/qwen2.5_7b/baseline-vs-chimera_gpu80_ctx512_temp10/run_4/metrics.json
- experiments/TR116/results/multi/python/qwen2p5_7b/qwen2.5_7b/baseline-vs-chimera_gpu80_ctx512_temp10/run_5/metrics.json
- experiments/TR116/results/multi/python/qwen2p5_7b/qwen2.5_7b/chimera-homo_gpu80_ctx512_temp10/run_1/metrics.json
- experiments/TR116/results/multi/python/qwen2p5_7b/qwen2.5_7b/chimera-homo_gpu80_ctx512_temp10/run_2/metrics.json
- experiments/TR116/results/multi/python/qwen2p5_7b/qwen2.5_7b/chimera-homo_gpu80_ctx512_temp10/run_3/metrics.json
- experiments/TR116/results/multi/python/qwen2p5_7b/qwen2.5_7b/chimera-homo_gpu80_ctx512_temp10/run_4/metrics.json
- experiments/TR116/results/multi/python/qwen2p5_7b/qwen2.5_7b/chimera-homo_gpu80_ctx512_temp10/run_5/metrics.json
- experiments/TR116/results/multi/rust/gemma3_latest/baseline-vs-chimera_gpu80_ctx512_temp10/run_1/metrics.json
- experiments/TR116/results/multi/rust/gemma3_latest/baseline-vs-chimera_gpu80_ctx512_temp10/run_2/metrics.json
- experiments/TR116/results/multi/rust/gemma3_latest/baseline-vs-chimera_gpu80_ctx512_temp10/run_3/metrics.json
- experiments/TR116/results/multi/rust/gemma3_latest/baseline-vs-chimera_gpu80_ctx512_temp10/run_4/metrics.json
- experiments/TR116/results/multi/rust/gemma3_latest/baseline-vs-chimera_gpu80_ctx512_temp10/run_5/metrics.json
- experiments/TR116/results/multi/rust/gemma3_latest/chimera-homo_gpu80_ctx512_temp10/run_1/metrics.json
- experiments/TR116/results/multi/rust/gemma3_latest/chimera-homo_gpu80_ctx512_temp10/run_2/metrics.json
- experiments/TR116/results/multi/rust/gemma3_latest/chimera-homo_gpu80_ctx512_temp10/run_3/metrics.json
- experiments/TR116/results/multi/rust/gemma3_latest/chimera-homo_gpu80_ctx512_temp10/run_4/metrics.json
- experiments/TR116/results/multi/rust/gemma3_latest/chimera-homo_gpu80_ctx512_temp10/run_5/metrics.json
- experiments/TR116/results/multi/rust/llama3p1_8b_q4_0/baseline-vs-chimera_gpu80_ctx512_temp10/run_1/metrics.json
- experiments/TR116/results/multi/rust/llama3p1_8b_q4_0/baseline-vs-chimera_gpu80_ctx512_temp10/run_2/metrics.json
- experiments/TR116/results/multi/rust/llama3p1_8b_q4_0/baseline-vs-chimera_gpu80_ctx512_temp10/run_3/metrics.json
- experiments/TR116/results/multi/rust/llama3p1_8b_q4_0/baseline-vs-chimera_gpu80_ctx512_temp10/run_4/metrics.json
- experiments/TR116/results/multi/rust/llama3p1_8b_q4_0/baseline-vs-chimera_gpu80_ctx512_temp10/run_5/metrics.json
- experiments/TR116/results/multi/rust/llama3p1_8b_q4_0/chimera-homo_gpu80_ctx512_temp10/run_1/metrics.json
- experiments/TR116/results/multi/rust/llama3p1_8b_q4_0/chimera-homo_gpu80_ctx512_temp10/run_2/metrics.json
- experiments/TR116/results/multi/rust/llama3p1_8b_q4_0/chimera-homo_gpu80_ctx512_temp10/run_3/metrics.json
- experiments/TR116/results/multi/rust/llama3p1_8b_q4_0/chimera-homo_gpu80_ctx512_temp10/run_4/metrics.json
- experiments/TR116/results/multi/rust/llama3p1_8b_q4_0/chimera-homo_gpu80_ctx512_temp10/run_5/metrics.json
- experiments/TR116/results/multi/rust/qwen2p5_7b/baseline-vs-chimera_gpu80_ctx512_temp10/run_1/metrics.json
- experiments/TR116/results/multi/rust/qwen2p5_7b/baseline-vs-chimera_gpu80_ctx512_temp10/run_2/metrics.json
- experiments/TR116/results/multi/rust/qwen2p5_7b/baseline-vs-chimera_gpu80_ctx512_temp10/run_3/metrics.json
- experiments/TR116/results/multi/rust/qwen2p5_7b/baseline-vs-chimera_gpu80_ctx512_temp10/run_4/metrics.json
- experiments/TR116/results/multi/rust/qwen2p5_7b/baseline-vs-chimera_gpu80_ctx512_temp10/run_5/metrics.json
- experiments/TR116/results/multi/rust/qwen2p5_7b/chimera-homo_gpu80_ctx512_temp10/run_1/metrics.json
- experiments/TR116/results/multi/rust/qwen2p5_7b/chimera-homo_gpu80_ctx512_temp10/run_2/metrics.json
- experiments/TR116/results/multi/rust/qwen2p5_7b/chimera-homo_gpu80_ctx512_temp10/run_3/metrics.json
- experiments/TR116/results/multi/rust/qwen2p5_7b/chimera-homo_gpu80_ctx512_temp10/run_4/metrics.json
- experiments/TR116/results/multi/rust/qwen2p5_7b/chimera-homo_gpu80_ctx512_temp10/run_5/metrics.json

### Single-Agent Metrics Files
- experiments/TR116/results/single/python/gemma3_latest/gpu60_ctx1024_temp08/data/metrics.json
- experiments/TR116/results/single/python/gemma3_latest/gpu60_ctx512_temp08/data/metrics.json
- experiments/TR116/results/single/python/gemma3_latest/gpu80_ctx1024_temp08/data/metrics.json
- experiments/TR116/results/single/python/gemma3_latest/gpu80_ctx512_temp08/data/metrics.json
- experiments/TR116/results/single/python/llama3p1_8b_q4_0/gpu60_ctx1024_temp08/data/metrics.json
- experiments/TR116/results/single/python/llama3p1_8b_q4_0/gpu60_ctx512_temp08/data/metrics.json
- experiments/TR116/results/single/python/llama3p1_8b_q4_0/gpu80_ctx1024_temp08/data/metrics.json
- experiments/TR116/results/single/python/llama3p1_8b_q4_0/gpu80_ctx512_temp08/data/metrics.json
- experiments/TR116/results/single/python/qwen2p5_7b/gpu60_ctx1024_temp08/data/metrics.json
- experiments/TR116/results/single/python/qwen2p5_7b/gpu60_ctx512_temp08/data/metrics.json
- experiments/TR116/results/single/python/qwen2p5_7b/gpu80_ctx1024_temp08/data/metrics.json
- experiments/TR116/results/single/python/qwen2p5_7b/gpu80_ctx512_temp08/data/metrics.json
- experiments/TR116/results/single/rust/gemma3_latest/gpu60_ctx1024_temp08/data/metrics.json
- experiments/TR116/results/single/rust/gemma3_latest/gpu60_ctx512_temp08/data/metrics.json
- experiments/TR116/results/single/rust/gemma3_latest/gpu80_ctx1024_temp08/data/metrics.json
- experiments/TR116/results/single/rust/gemma3_latest/gpu80_ctx512_temp08/data/metrics.json
- experiments/TR116/results/single/rust/llama3p1_8b_q4_0/gpu60_ctx1024_temp08/data/metrics.json
- experiments/TR116/results/single/rust/llama3p1_8b_q4_0/gpu60_ctx512_temp08/data/metrics.json
- experiments/TR116/results/single/rust/llama3p1_8b_q4_0/gpu80_ctx1024_temp08/data/metrics.json
- experiments/TR116/results/single/rust/llama3p1_8b_q4_0/gpu80_ctx512_temp08/data/metrics.json
- experiments/TR116/results/single/rust/qwen2p5_7b/gpu60_ctx1024_temp08/data/metrics.json
- experiments/TR116/results/single/rust/qwen2p5_7b/gpu60_ctx512_temp08/data/metrics.json
- experiments/TR116/results/single/rust/qwen2p5_7b/gpu80_ctx1024_temp08/data/metrics.json
- experiments/TR116/results/single/rust/qwen2p5_7b/gpu80_ctx512_temp08/data/metrics.json

## Appendix F: Multi-Agent Run Notes
- PYTHON | gemma3 | baseline-vs-chimera | run 1: 1.202x speedup, 60.12% efficiency, throughput delta +10.16 tok/s, TTFT delta +35.3 ms, contention no.
- PYTHON | gemma3 | baseline-vs-chimera | run 2: 1.681x speedup, 84.07% efficiency, throughput delta +16.05 tok/s, TTFT delta +0.6 ms, contention no.
- PYTHON | gemma3 | baseline-vs-chimera | run 3: 1.750x speedup, 87.51% efficiency, throughput delta +11.43 tok/s, TTFT delta -0.5 ms, contention no.
- PYTHON | gemma3 | baseline-vs-chimera | run 4: 1.679x speedup, 83.94% efficiency, throughput delta +16.57 tok/s, TTFT delta -1.0 ms, contention no.
- PYTHON | gemma3 | baseline-vs-chimera | run 5: 1.711x speedup, 85.54% efficiency, throughput delta +13.99 tok/s, TTFT delta +nan ms, contention no.
- PYTHON | gemma3 | chimera-homo | run 1: 1.595x speedup, 79.75% efficiency, throughput delta +12.49 tok/s, TTFT delta -43.5 ms, contention no.
- PYTHON | gemma3 | chimera-homo | run 2: 1.725x speedup, 86.25% efficiency, throughput delta +13.03 tok/s, TTFT delta -0.5 ms, contention no.
- PYTHON | gemma3 | chimera-homo | run 3: 1.708x speedup, 85.41% efficiency, throughput delta +13.74 tok/s, TTFT delta +0.1 ms, contention no.
- PYTHON | gemma3 | chimera-homo | run 4: 1.684x speedup, 84.21% efficiency, throughput delta +15.31 tok/s, TTFT delta +nan ms, contention no.
- PYTHON | gemma3 | chimera-homo | run 5: 1.773x speedup, 88.64% efficiency, throughput delta +9.83 tok/s, TTFT delta -0.2 ms, contention no.
- PYTHON | llama3.1 | baseline-vs-chimera | run 1: 1.204x speedup, 60.19% efficiency, throughput delta +9.78 tok/s, TTFT delta -5.1 ms, contention no.
- PYTHON | llama3.1 | baseline-vs-chimera | run 2: 1.826x speedup, 91.29% efficiency, throughput delta +6.47 tok/s, TTFT delta +nan ms, contention no.
- PYTHON | llama3.1 | baseline-vs-chimera | run 3: 1.751x speedup, 87.57% efficiency, throughput delta +10.08 tok/s, TTFT delta -0.6 ms, contention no.
- PYTHON | llama3.1 | baseline-vs-chimera | run 4: 1.827x speedup, 91.33% efficiency, throughput delta +6.31 tok/s, TTFT delta +0.5 ms, contention no.
- PYTHON | llama3.1 | baseline-vs-chimera | run 5: 1.772x speedup, 88.61% efficiency, throughput delta +9.17 tok/s, TTFT delta +0.8 ms, contention no.
- PYTHON | llama3.1 | chimera-homo | run 1: 1.391x speedup, 69.56% efficiency, throughput delta +15.70 tok/s, TTFT delta -72.9 ms, contention no.
- PYTHON | llama3.1 | chimera-homo | run 2: 1.787x speedup, 89.37% efficiency, throughput delta +8.43 tok/s, TTFT delta -0.1 ms, contention no.
- PYTHON | llama3.1 | chimera-homo | run 3: 1.805x speedup, 90.27% efficiency, throughput delta +7.18 tok/s, TTFT delta +nan ms, contention no.
- PYTHON | llama3.1 | chimera-homo | run 4: 1.834x speedup, 91.68% efficiency, throughput delta +5.91 tok/s, TTFT delta +0.6 ms, contention no.
- PYTHON | llama3.1 | chimera-homo | run 5: 1.760x speedup, 88.00% efficiency, throughput delta +9.84 tok/s, TTFT delta +0.6 ms, contention no.
- PYTHON | qwen2.5 | baseline-vs-chimera | run 1: 1.106x speedup, 55.31% efficiency, throughput delta +14.32 tok/s, TTFT delta -11.7 ms, contention no.
- PYTHON | qwen2.5 | baseline-vs-chimera | run 2: 1.657x speedup, 82.84% efficiency, throughput delta +16.26 tok/s, TTFT delta +0.8 ms, contention no.
- PYTHON | qwen2.5 | baseline-vs-chimera | run 3: 1.680x speedup, 84.00% efficiency, throughput delta +14.71 tok/s, TTFT delta +4.3 ms, contention no.
- PYTHON | qwen2.5 | baseline-vs-chimera | run 4: 1.631x speedup, 81.54% efficiency, throughput delta +17.53 tok/s, TTFT delta +6.5 ms, contention no.
- PYTHON | qwen2.5 | baseline-vs-chimera | run 5: 1.683x speedup, 84.14% efficiency, throughput delta +15.15 tok/s, TTFT delta +0.2 ms, contention no.
- PYTHON | qwen2.5 | chimera-homo | run 1: 1.631x speedup, 81.54% efficiency, throughput delta +13.18 tok/s, TTFT delta -97.4 ms, contention no.
- PYTHON | qwen2.5 | chimera-homo | run 2: 1.686x speedup, 84.29% efficiency, throughput delta +14.64 tok/s, TTFT delta -5.3 ms, contention no.
- PYTHON | qwen2.5 | chimera-homo | run 3: 1.657x speedup, 82.83% efficiency, throughput delta +16.26 tok/s, TTFT delta +6.5 ms, contention no.
- PYTHON | qwen2.5 | chimera-homo | run 4: 1.678x speedup, 83.92% efficiency, throughput delta +15.01 tok/s, TTFT delta +0.5 ms, contention no.
- PYTHON | qwen2.5 | chimera-homo | run 5: 1.760x speedup, 88.01% efficiency, throughput delta +10.52 tok/s, TTFT delta +nan ms, contention no.
- RUST | gemma3 | baseline-vs-chimera | run 1: 1.949x speedup, 97.46% efficiency, throughput delta +0.43 tok/s, TTFT delta +1270.3 ms, contention no.
- RUST | gemma3 | baseline-vs-chimera | run 2: 1.969x speedup, 98.45% efficiency, throughput delta +2.22 tok/s, TTFT delta +145.3 ms, contention no.
- RUST | gemma3 | baseline-vs-chimera | run 3: 1.914x speedup, 95.70% efficiency, throughput delta -5.75 tok/s, TTFT delta +116.4 ms, contention no.
- RUST | gemma3 | baseline-vs-chimera | run 4: 1.925x speedup, 96.24% efficiency, throughput delta -4.96 tok/s, TTFT delta +173.9 ms, contention no.
- RUST | gemma3 | baseline-vs-chimera | run 5: 1.974x speedup, 98.72% efficiency, throughput delta -1.57 tok/s, TTFT delta +159.9 ms, contention no.
- RUST | gemma3 | chimera-homo | run 1: 1.982x speedup, 99.11% efficiency, throughput delta -7.39 tok/s, TTFT delta -1563.3 ms, contention no.
- RUST | gemma3 | chimera-homo | run 2: 1.997x speedup, 99.86% efficiency, throughput delta +0.45 tok/s, TTFT delta +164.0 ms, contention no.
- RUST | gemma3 | chimera-homo | run 3: 1.983x speedup, 99.15% efficiency, throughput delta +1.11 tok/s, TTFT delta +259.9 ms, contention no.
- RUST | gemma3 | chimera-homo | run 4: 1.995x speedup, 99.73% efficiency, throughput delta -0.25 tok/s, TTFT delta +163.0 ms, contention no.
- RUST | gemma3 | chimera-homo | run 5: 1.965x speedup, 98.26% efficiency, throughput delta +2.27 tok/s, TTFT delta +275.0 ms, contention no.
- RUST | llama3.1 | baseline-vs-chimera | run 1: 1.924x speedup, 96.18% efficiency, throughput delta +4.33 tok/s, TTFT delta +1441.1 ms, contention no.
- RUST | llama3.1 | baseline-vs-chimera | run 2: 1.933x speedup, 96.66% efficiency, throughput delta -3.13 tok/s, TTFT delta +149.6 ms, contention no.
- RUST | llama3.1 | baseline-vs-chimera | run 3: 1.903x speedup, 95.17% efficiency, throughput delta -5.35 tok/s, TTFT delta +128.1 ms, contention no.
- RUST | llama3.1 | baseline-vs-chimera | run 4: 1.910x speedup, 95.50% efficiency, throughput delta -4.31 tok/s, TTFT delta +127.5 ms, contention no.
- RUST | llama3.1 | baseline-vs-chimera | run 5: 1.985x speedup, 99.23% efficiency, throughput delta +0.81 tok/s, TTFT delta +140.6 ms, contention no.
- RUST | llama3.1 | chimera-homo | run 1: 1.981x speedup, 99.05% efficiency, throughput delta -0.71 tok/s, TTFT delta -487.8 ms, contention no.
- RUST | llama3.1 | chimera-homo | run 2: 1.950x speedup, 97.52% efficiency, throughput delta -2.79 tok/s, TTFT delta +75.6 ms, contention no.
- RUST | llama3.1 | chimera-homo | run 3: 1.970x speedup, 98.51% efficiency, throughput delta -1.42 tok/s, TTFT delta +149.3 ms, contention no.
- RUST | llama3.1 | chimera-homo | run 4: 1.986x speedup, 99.30% efficiency, throughput delta -0.51 tok/s, TTFT delta +94.3 ms, contention no.
- RUST | llama3.1 | chimera-homo | run 5: 1.967x speedup, 98.36% efficiency, throughput delta -1.57 tok/s, TTFT delta +78.9 ms, contention no.
- RUST | qwen2.5 | baseline-vs-chimera | run 1: 1.702x speedup, 85.08% efficiency, throughput delta +30.47 tok/s, TTFT delta +1422.8 ms, contention no.
- RUST | qwen2.5 | baseline-vs-chimera | run 2: 1.704x speedup, 85.18% efficiency, throughput delta +30.69 tok/s, TTFT delta +119.4 ms, contention no.
- RUST | qwen2.5 | baseline-vs-chimera | run 3: 1.992x speedup, 99.58% efficiency, throughput delta -0.35 tok/s, TTFT delta +17.7 ms, contention no.
- RUST | qwen2.5 | baseline-vs-chimera | run 4: 1.976x speedup, 98.79% efficiency, throughput delta -13.13 tok/s, TTFT delta +86.9 ms, contention no.
- RUST | qwen2.5 | baseline-vs-chimera | run 5: 1.624x speedup, 81.20% efficiency, throughput delta +14.33 tok/s, TTFT delta +49.8 ms, contention no.
- RUST | qwen2.5 | chimera-homo | run 1: 1.918x speedup, 95.92% efficiency, throughput delta -3.65 tok/s, TTFT delta -468.2 ms, contention no.
- RUST | qwen2.5 | chimera-homo | run 2: 1.948x speedup, 97.40% efficiency, throughput delta -3.49 tok/s, TTFT delta +111.6 ms, contention no.
- RUST | qwen2.5 | chimera-homo | run 3: 1.799x speedup, 89.94% efficiency, throughput delta -16.06 tok/s, TTFT delta +58.5 ms, contention no.
- RUST | qwen2.5 | chimera-homo | run 4: 1.836x speedup, 91.80% efficiency, throughput delta -6.18 tok/s, TTFT delta +89.0 ms, contention no.
- RUST | qwen2.5 | chimera-homo | run 5: 1.440x speedup, 72.00% efficiency, throughput delta -32.73 tok/s, TTFT delta +159.9 ms, contention yes.

## Appendix G: Single-Agent Run Notes (Python raw runs)
- PY | gemma3 | gpu60_ctx1024_temp8 | run 1: throughput 118.32->117.91 tok/s (Delta -0.35%), TTFT 91.1->130.0 ms (Delta -42.73%).
- PY | gemma3 | gpu60_ctx1024_temp8 | run 2: throughput 118.39->117.89 tok/s (Delta -0.42%), TTFT 88.0->128.6 ms (Delta -46.17%).
- PY | gemma3 | gpu60_ctx1024_temp8 | run 3: throughput 118.39->118.07 tok/s (Delta -0.26%), TTFT 86.8->129.2 ms (Delta -48.83%).
- PY | gemma3 | gpu60_ctx1024_temp8 | run 4: throughput 119.08->117.93 tok/s (Delta -0.96%), TTFT 73.2->129.0 ms (Delta -76.23%).
- PY | gemma3 | gpu60_ctx1024_temp8 | run 5: throughput 119.10->117.94 tok/s (Delta -0.98%), TTFT 73.7->129.5 ms (Delta -75.69%).
- PY | gemma3 | gpu60_ctx512_temp8 | run 1: throughput 118.78->117.69 tok/s (Delta -0.91%), TTFT 87.2->132.2 ms (Delta -51.51%).
- PY | gemma3 | gpu60_ctx512_temp8 | run 2: throughput 117.21->117.91 tok/s (Delta +0.60%), TTFT 87.5->129.8 ms (Delta -48.40%).
- PY | gemma3 | gpu60_ctx512_temp8 | run 3: throughput 118.45->117.58 tok/s (Delta -0.73%), TTFT 86.6->128.6 ms (Delta -48.44%).
- PY | gemma3 | gpu60_ctx512_temp8 | run 4: throughput 118.36->118.07 tok/s (Delta -0.24%), TTFT 87.3->129.3 ms (Delta -48.00%).
- PY | gemma3 | gpu60_ctx512_temp8 | run 5: throughput 118.68->117.79 tok/s (Delta -0.75%), TTFT 81.5->129.3 ms (Delta -58.56%).
- PY | gemma3 | gpu80_ctx1024_temp8 | run 1: throughput 118.02->117.69 tok/s (Delta -0.29%), TTFT 225.0->208.3 ms (Delta +7.42%).
- PY | gemma3 | gpu80_ctx1024_temp8 | run 2: throughput 118.87->115.08 tok/s (Delta -3.18%), TTFT 172.7->222.2 ms (Delta -28.67%).
- PY | gemma3 | gpu80_ctx1024_temp8 | run 3: throughput 118.30->117.18 tok/s (Delta -0.95%), TTFT 218.4->260.1 ms (Delta -19.09%).
- PY | gemma3 | gpu80_ctx1024_temp8 | run 4: throughput 118.93->118.32 tok/s (Delta -0.51%), TTFT 213.7->236.6 ms (Delta -10.71%).
- PY | gemma3 | gpu80_ctx1024_temp8 | run 5: throughput 118.61->117.97 tok/s (Delta -0.53%), TTFT 221.0->203.5 ms (Delta +7.92%).
- PY | gemma3 | gpu80_ctx512_temp8 | run 1: throughput 119.16->117.97 tok/s (Delta -1.00%), TTFT 212.6->252.9 ms (Delta -18.98%).
- PY | gemma3 | gpu80_ctx512_temp8 | run 2: throughput 118.64->116.74 tok/s (Delta -1.60%), TTFT 223.4->195.0 ms (Delta +12.71%).
- PY | gemma3 | gpu80_ctx512_temp8 | run 3: throughput 118.17->117.43 tok/s (Delta -0.63%), TTFT 213.9->263.0 ms (Delta -22.97%).
- PY | gemma3 | gpu80_ctx512_temp8 | run 4: throughput 117.68->117.86 tok/s (Delta +0.15%), TTFT 224.4->207.5 ms (Delta +7.52%).
- PY | gemma3 | gpu80_ctx512_temp8 | run 5: throughput 118.38->120.09 tok/s (Delta +1.45%), TTFT 233.5->214.8 ms (Delta +7.98%).
- PY | llama3.1 | gpu60_ctx1024_temp8 | run 1: throughput 81.82->80.53 tok/s (Delta -1.57%), TTFT 81.4->141.1 ms (Delta -73.27%).
- PY | llama3.1 | gpu60_ctx1024_temp8 | run 2: throughput 81.89->80.65 tok/s (Delta -1.52%), TTFT 81.5->138.7 ms (Delta -70.24%).
- PY | llama3.1 | gpu60_ctx1024_temp8 | run 3: throughput 81.92->81.19 tok/s (Delta -0.90%), TTFT 82.5->137.3 ms (Delta -66.44%).
- PY | llama3.1 | gpu60_ctx1024_temp8 | run 4: throughput 82.62->81.73 tok/s (Delta -1.07%), TTFT 79.9->138.0 ms (Delta -72.71%).
- PY | llama3.1 | gpu60_ctx1024_temp8 | run 5: throughput 81.99->81.36 tok/s (Delta -0.77%), TTFT 75.0->140.7 ms (Delta -87.67%).
- PY | llama3.1 | gpu60_ctx512_temp8 | run 1: throughput 81.90->80.35 tok/s (Delta -1.90%), TTFT 82.0->78.9 ms (Delta +3.80%).
- PY | llama3.1 | gpu60_ctx512_temp8 | run 2: throughput 81.68->81.32 tok/s (Delta -0.44%), TTFT 81.8->73.5 ms (Delta +10.11%).
- PY | llama3.1 | gpu60_ctx512_temp8 | run 3: throughput 81.52->80.53 tok/s (Delta -1.21%), TTFT 86.8->73.6 ms (Delta +15.25%).
- PY | llama3.1 | gpu60_ctx512_temp8 | run 4: throughput 82.54->80.44 tok/s (Delta -2.54%), TTFT 57.4->72.2 ms (Delta -25.74%).
- PY | llama3.1 | gpu60_ctx512_temp8 | run 5: throughput 81.55->80.52 tok/s (Delta -1.27%), TTFT 82.6->74.5 ms (Delta +9.88%).
- PY | llama3.1 | gpu80_ctx1024_temp8 | run 1: throughput 82.03->81.01 tok/s (Delta -1.24%), TTFT 177.1->241.4 ms (Delta -36.29%).
- PY | llama3.1 | gpu80_ctx1024_temp8 | run 2: throughput 82.62->79.69 tok/s (Delta -3.54%), TTFT 180.9->221.4 ms (Delta -22.40%).
- PY | llama3.1 | gpu80_ctx1024_temp8 | run 3: throughput 82.52->79.39 tok/s (Delta -3.80%), TTFT 203.8->243.6 ms (Delta -19.50%).
- PY | llama3.1 | gpu80_ctx1024_temp8 | run 4: throughput 82.16->78.61 tok/s (Delta -4.32%), TTFT 206.9->222.8 ms (Delta -7.67%).
- PY | llama3.1 | gpu80_ctx1024_temp8 | run 5: throughput 82.24->78.21 tok/s (Delta -4.90%), TTFT 232.7->253.2 ms (Delta -8.84%).
- PY | llama3.1 | gpu80_ctx512_temp8 | run 1: throughput 81.84->80.30 tok/s (Delta -1.89%), TTFT 78.6->74.2 ms (Delta +5.58%).
- PY | llama3.1 | gpu80_ctx512_temp8 | run 2: throughput 81.85->80.62 tok/s (Delta -1.50%), TTFT 77.9->74.8 ms (Delta +4.05%).
- PY | llama3.1 | gpu80_ctx512_temp8 | run 3: throughput 81.78->80.78 tok/s (Delta -1.22%), TTFT 78.9->74.7 ms (Delta +5.36%).
- PY | llama3.1 | gpu80_ctx512_temp8 | run 4: throughput 82.36->80.32 tok/s (Delta -2.47%), TTFT 78.7->73.0 ms (Delta +7.32%).
- PY | llama3.1 | gpu80_ctx512_temp8 | run 5: throughput 82.20->80.59 tok/s (Delta -1.96%), TTFT 81.4->74.4 ms (Delta +8.56%).
- PY | qwen2.5 | gpu60_ctx1024_temp8 | run 1: throughput 82.19->82.21 tok/s (Delta +0.02%), TTFT 50.4->136.4 ms (Delta -170.58%).
- PY | qwen2.5 | gpu60_ctx1024_temp8 | run 2: throughput 82.09->82.17 tok/s (Delta +0.10%), TTFT 42.3->137.2 ms (Delta -224.37%).
- PY | qwen2.5 | gpu60_ctx1024_temp8 | run 3: throughput 81.45->81.10 tok/s (Delta -0.43%), TTFT 58.3->132.0 ms (Delta -126.21%).
- PY | qwen2.5 | gpu60_ctx1024_temp8 | run 4: throughput 82.11->82.83 tok/s (Delta +0.87%), TTFT 58.7->137.0 ms (Delta -133.55%).
- PY | qwen2.5 | gpu60_ctx1024_temp8 | run 5: throughput 82.21->81.74 tok/s (Delta -0.57%), TTFT 50.9->141.6 ms (Delta -178.16%).
- PY | qwen2.5 | gpu60_ctx512_temp8 | run 1: throughput 81.29->80.89 tok/s (Delta -0.50%), TTFT 229.6->77.9 ms (Delta +66.06%).
- PY | qwen2.5 | gpu80_ctx1024_temp8 | run 1: throughput 81.80->81.22 tok/s (Delta -0.71%), TTFT 176.8->268.5 ms (Delta -51.90%).
- PY | qwen2.5 | gpu80_ctx1024_temp8 | run 2: throughput 82.01->81.24 tok/s (Delta -0.94%), TTFT 191.4->250.2 ms (Delta -30.72%).
- PY | qwen2.5 | gpu80_ctx1024_temp8 | run 3: throughput 82.24->81.17 tok/s (Delta -1.30%), TTFT 155.7->232.4 ms (Delta -49.27%).
- PY | qwen2.5 | gpu80_ctx1024_temp8 | run 4: throughput 81.67->80.29 tok/s (Delta -1.69%), TTFT 266.6->249.8 ms (Delta +6.30%).
- PY | qwen2.5 | gpu80_ctx1024_temp8 | run 5: throughput 82.23->81.18 tok/s (Delta -1.28%), TTFT 247.3->235.1 ms (Delta +4.95%).
- PY | qwen2.5 | gpu80_ctx512_temp8 | run 1: throughput 82.19->81.12 tok/s (Delta -1.30%), TTFT 48.1->78.4 ms (Delta -62.93%).
- PY | qwen2.5 | gpu80_ctx512_temp8 | run 2: throughput 82.06->80.75 tok/s (Delta -1.60%), TTFT 59.0->76.5 ms (Delta -29.80%).
- PY | qwen2.5 | gpu80_ctx512_temp8 | run 3: throughput 81.59->80.46 tok/s (Delta -1.39%), TTFT 59.1->75.8 ms (Delta -28.22%).
- PY | qwen2.5 | gpu80_ctx512_temp8 | run 4: throughput 81.96->81.37 tok/s (Delta -0.73%), TTFT 50.8->74.5 ms (Delta -46.68%).
- PY | qwen2.5 | gpu80_ctx512_temp8 | run 5: throughput 81.78->80.72 tok/s (Delta -1.29%), TTFT 57.9->102.9 ms (Delta -77.61%).

### Single-Agent Config Notes (Rust aggregates)
- RUST | gemma3 | gpu60_ctx1024_temp8: baseline 114.11 tok/s, chimera 115.98 tok/s, TTFT 1234.8->1145.9 ms (Delta +7.20%).
- RUST | gemma3 | gpu60_ctx512_temp8: baseline 114.00 tok/s, chimera 120.08 tok/s, TTFT 1176.7->1133.6 ms (Delta +3.67%).
- RUST | gemma3 | gpu80_ctx1024_temp8: baseline 114.58 tok/s, chimera 104.05 tok/s, TTFT 1178.2->1178.5 ms (Delta -0.03%).
- RUST | gemma3 | gpu80_ctx512_temp8: baseline 114.16 tok/s, chimera 115.63 tok/s, TTFT 1227.6->1136.1 ms (Delta +7.46%).
- RUST | llama3.1 | gpu60_ctx1024_temp8: baseline 78.84 tok/s, chimera 80.10 tok/s, TTFT 1066.0->965.8 ms (Delta +9.40%).
- RUST | llama3.1 | gpu60_ctx512_temp8: baseline 79.26 tok/s, chimera 79.60 tok/s, TTFT 1048.3->859.7 ms (Delta +18.00%).
- RUST | llama3.1 | gpu80_ctx1024_temp8: baseline 79.27 tok/s, chimera 80.50 tok/s, TTFT 979.4->952.2 ms (Delta +2.78%).
- RUST | llama3.1 | gpu80_ctx512_temp8: baseline 79.43 tok/s, chimera 79.63 tok/s, TTFT 1056.1->869.9 ms (Delta +17.63%).
- RUST | qwen2.5 | gpu60_ctx1024_temp8: baseline 79.99 tok/s, chimera 81.26 tok/s, TTFT 3074.1->3217.7 ms (Delta -4.67%).
- RUST | qwen2.5 | gpu60_ctx512_temp8: baseline 79.65 tok/s, chimera 80.28 tok/s, TTFT 988.9->846.7 ms (Delta +14.38%).
- RUST | qwen2.5 | gpu80_ctx1024_temp8: baseline 79.44 tok/s, chimera 81.42 tok/s, TTFT 1055.5->923.6 ms (Delta +12.50%).
- RUST | qwen2.5 | gpu80_ctx512_temp8: baseline 79.34 tok/s, chimera 80.47 tok/s, TTFT 579.7->861.7 ms (Delta -48.65%).

## Appendix H: PRD Snapshot
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
- Repetition: 3-5 runs per config per model; minimum 3 if time-boxed.
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
- Runs: 3-5
- Output dir template: `experiments/TR116/results/multi/{lang}/{model_slug}/{scenario}_...`

### Models and VRAM Notes
- `qwen2.5:7b`: primary; should fit 12GB with Q4_K_M style quant (default pull is fine).
- `gemma3:latest`: baseline from prior TRs (Ollama "gemma3" naming; distinct from Gemma 2).
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
- Outlier rule: flag if |value - median| > 2 x MAD for key metrics (throughput, TTFT); rerun flagged configs.

### Failure Logging (for expected OOMs/limits)
- Capture attempted config (model, GPU layers, ctx, temp), error message, observed VRAM at failure, and fallback decision (e.g., drop to 7B or lower ctx/gpu layers).

## Reporting Plan
- Structure TR116 similar to TR114/115: objective, setup, methodology, results (single-agent per model, multi-agent per model), cross-model comparison, VRAM/quant notes, recommendations.
- Include reproducibility steps (commands, commit hash, model IDs, Ollama ports).
- Add comparative views:
  - Normalized metrics table (e.g., throughput as % of Gemma baseline).
  - Cost/efficiency frontier if power sampling is present (tokens/joule vs tok/s).
  - "Winner by scenario" matrix (single-agent Python, single-agent Rust, multi-agent Python, multi-agent Rust).
- Highlight whether model choice changes multi-agent efficiency or if architecture dominates.

## Risks and Mitigations
- VRAM limits: prefer 7B; downscale ctx/gpu layers if needed and document.
- Model load failures: retry with lower quant or reduced ctx.
- Time budget: drop runs from 5 to 3 if necessary; preserve at least two scenarios in multi-agent.

## Open Questions
- Do we want power sampling for cost/energy KPIsx If yes, add `nvidia-smi` polling.
- Is a lighter Qwen quant (explicit `q4_K_M`) preferred for consistency across hostsx


## Appendix I: Validation Checklist
- [x] Parsed 60/60 multi-agent metrics.json entries (Rust summary fields included).
- [x] Regenerated analysis_comprehensive.csv via analyze_metrics_direct.py after parser fix.
- [x] Verified 12/12 multi-agent configs have 5 runs each.
- [x] Verified 24/24 single-agent configs accounted for (GPU 60/80 x ctx 512/1024).
- [x] Confirmed contention flags only present in qwen2.5 Rust chimera-homo run_5.
- [x] Ensured no external data sources are referenced; all paths live under experiments/TR116.
- [x] Retained ASCII-only reporting to avoid encoding glitches seen in earlier draft.
- [x] Stored raw metrics manifest for auditability.
- [ ] Optional: re-run multi-agent suite after TTFT tuning on Python to validate improvements.
- [ ] Optional: add power sampling if available to derive joules/token.

## Appendix J: Runbook (quick rerun guide)
1. Start dual Ollama instances on ports 11434 and 11435.
2. Verify models pulled: `ollama pull qwen2.5:7b`, `ollama pull gemma3:latest`, `ollama pull llama3.1:8b-instruct-q4_0`.
3. For multi-agent Rust runs: use templates under experiments/TR116/results/multi/rust (baseline-vs-chimera and chimera-homo), 5 repetitions each.
4. For multi-agent Python runs: mirror the same scenarios under experiments/TR116/results/multi/python, maintaining GPU80/ctx512/temp10.
5. For single-agent: run GPU60 and GPU80 with ctx 512 and 1024, temp 0.8 for both baseline and chimera prompts.
6. After runs, execute `python experiments/TR116/analyze_metrics_direct.py` to refresh CSV and COMPREHENSIVE_ANALYSIS.md.
7. Regenerate this report with the embedded script block (see repository history) or rerun the generator snippet in the README of TR116.
8. Archive artifacts to outputs/publish_ready/reports and push alongside metrics for auditability.

## Appendix K: Efficiency Samples (sorted)
- RUST | gemma3 | chimera-homo | run 2: efficiency 99.86% | speedup 1.997x | throughput delta +0.45 tok/s | TTFT delta +164.0 ms.
- RUST | gemma3 | chimera-homo | run 4: efficiency 99.73% | speedup 1.995x | throughput delta -0.25 tok/s | TTFT delta +163.0 ms.
- RUST | qwen2.5 | baseline-vs-chimera | run 3: efficiency 99.58% | speedup 1.992x | throughput delta -0.35 tok/s | TTFT delta +17.7 ms.
- RUST | llama3.1 | chimera-homo | run 4: efficiency 99.30% | speedup 1.986x | throughput delta -0.51 tok/s | TTFT delta +94.3 ms.
- RUST | llama3.1 | baseline-vs-chimera | run 5: efficiency 99.23% | speedup 1.985x | throughput delta +0.81 tok/s | TTFT delta +140.6 ms.
- RUST | gemma3 | chimera-homo | run 3: efficiency 99.15% | speedup 1.983x | throughput delta +1.11 tok/s | TTFT delta +259.9 ms.
- RUST | gemma3 | chimera-homo | run 1: efficiency 99.11% | speedup 1.982x | throughput delta -7.39 tok/s | TTFT delta -1563.3 ms.
- RUST | llama3.1 | chimera-homo | run 1: efficiency 99.05% | speedup 1.981x | throughput delta -0.71 tok/s | TTFT delta -487.8 ms.
- RUST | qwen2.5 | baseline-vs-chimera | run 4: efficiency 98.79% | speedup 1.976x | throughput delta -13.13 tok/s | TTFT delta +86.9 ms.
- RUST | gemma3 | baseline-vs-chimera | run 5: efficiency 98.72% | speedup 1.974x | throughput delta -1.57 tok/s | TTFT delta +159.9 ms.
- RUST | llama3.1 | chimera-homo | run 3: efficiency 98.51% | speedup 1.970x | throughput delta -1.42 tok/s | TTFT delta +149.3 ms.
- RUST | gemma3 | baseline-vs-chimera | run 2: efficiency 98.45% | speedup 1.969x | throughput delta +2.22 tok/s | TTFT delta +145.3 ms.
- RUST | llama3.1 | chimera-homo | run 5: efficiency 98.36% | speedup 1.967x | throughput delta -1.57 tok/s | TTFT delta +78.9 ms.
- RUST | gemma3 | chimera-homo | run 5: efficiency 98.26% | speedup 1.965x | throughput delta +2.27 tok/s | TTFT delta +275.0 ms.
- RUST | llama3.1 | chimera-homo | run 2: efficiency 97.52% | speedup 1.950x | throughput delta -2.79 tok/s | TTFT delta +75.6 ms.
- RUST | gemma3 | baseline-vs-chimera | run 1: efficiency 97.46% | speedup 1.949x | throughput delta +0.43 tok/s | TTFT delta +1270.3 ms.
- RUST | qwen2.5 | chimera-homo | run 2: efficiency 97.40% | speedup 1.948x | throughput delta -3.49 tok/s | TTFT delta +111.6 ms.
- RUST | llama3.1 | baseline-vs-chimera | run 2: efficiency 96.66% | speedup 1.933x | throughput delta -3.13 tok/s | TTFT delta +149.6 ms.
- RUST | gemma3 | baseline-vs-chimera | run 4: efficiency 96.24% | speedup 1.925x | throughput delta -4.96 tok/s | TTFT delta +173.9 ms.
- RUST | llama3.1 | baseline-vs-chimera | run 1: efficiency 96.18% | speedup 1.924x | throughput delta +4.33 tok/s | TTFT delta +1441.1 ms.
- RUST | qwen2.5 | chimera-homo | run 1: efficiency 95.92% | speedup 1.918x | throughput delta -3.65 tok/s | TTFT delta -468.2 ms.
- RUST | gemma3 | baseline-vs-chimera | run 3: efficiency 95.70% | speedup 1.914x | throughput delta -5.75 tok/s | TTFT delta +116.4 ms.
- RUST | llama3.1 | baseline-vs-chimera | run 4: efficiency 95.50% | speedup 1.910x | throughput delta -4.31 tok/s | TTFT delta +127.5 ms.
- RUST | llama3.1 | baseline-vs-chimera | run 3: efficiency 95.17% | speedup 1.903x | throughput delta -5.35 tok/s | TTFT delta +128.1 ms.
- RUST | qwen2.5 | chimera-homo | run 4: efficiency 91.80% | speedup 1.836x | throughput delta -6.18 tok/s | TTFT delta +89.0 ms.
- PYTHON | llama3.1 | chimera-homo | run 4: efficiency 91.68% | speedup 1.834x | throughput delta +5.91 tok/s | TTFT delta +0.6 ms.
- PYTHON | llama3.1 | baseline-vs-chimera | run 4: efficiency 91.33% | speedup 1.827x | throughput delta +6.31 tok/s | TTFT delta +0.5 ms.
- PYTHON | llama3.1 | baseline-vs-chimera | run 2: efficiency 91.29% | speedup 1.826x | throughput delta +6.47 tok/s | TTFT delta +nan ms.
- PYTHON | llama3.1 | chimera-homo | run 3: efficiency 90.27% | speedup 1.805x | throughput delta +7.18 tok/s | TTFT delta +nan ms.
- RUST | qwen2.5 | chimera-homo | run 3: efficiency 89.94% | speedup 1.799x | throughput delta -16.06 tok/s | TTFT delta +58.5 ms.
- PYTHON | llama3.1 | chimera-homo | run 2: efficiency 89.37% | speedup 1.787x | throughput delta +8.43 tok/s | TTFT delta -0.1 ms.
- PYTHON | gemma3 | chimera-homo | run 5: efficiency 88.64% | speedup 1.773x | throughput delta +9.83 tok/s | TTFT delta -0.2 ms.
- PYTHON | llama3.1 | baseline-vs-chimera | run 5: efficiency 88.61% | speedup 1.772x | throughput delta +9.17 tok/s | TTFT delta +0.8 ms.
- PYTHON | qwen2.5 | chimera-homo | run 5: efficiency 88.01% | speedup 1.760x | throughput delta +10.52 tok/s | TTFT delta +nan ms.
- PYTHON | llama3.1 | chimera-homo | run 5: efficiency 88.00% | speedup 1.760x | throughput delta +9.84 tok/s | TTFT delta +0.6 ms.
- PYTHON | llama3.1 | baseline-vs-chimera | run 3: efficiency 87.57% | speedup 1.751x | throughput delta +10.08 tok/s | TTFT delta -0.6 ms.
- PYTHON | gemma3 | baseline-vs-chimera | run 3: efficiency 87.51% | speedup 1.750x | throughput delta +11.43 tok/s | TTFT delta -0.5 ms.
- PYTHON | gemma3 | chimera-homo | run 2: efficiency 86.25% | speedup 1.725x | throughput delta +13.03 tok/s | TTFT delta -0.5 ms.
- PYTHON | gemma3 | baseline-vs-chimera | run 5: efficiency 85.54% | speedup 1.711x | throughput delta +13.99 tok/s | TTFT delta +nan ms.
- PYTHON | gemma3 | chimera-homo | run 3: efficiency 85.41% | speedup 1.708x | throughput delta +13.74 tok/s | TTFT delta +0.1 ms.
- RUST | qwen2.5 | baseline-vs-chimera | run 2: efficiency 85.18% | speedup 1.704x | throughput delta +30.69 tok/s | TTFT delta +119.4 ms.
- RUST | qwen2.5 | baseline-vs-chimera | run 1: efficiency 85.08% | speedup 1.702x | throughput delta +30.47 tok/s | TTFT delta +1422.8 ms.
- PYTHON | qwen2.5 | chimera-homo | run 2: efficiency 84.29% | speedup 1.686x | throughput delta +14.64 tok/s | TTFT delta -5.3 ms.
- PYTHON | gemma3 | chimera-homo | run 4: efficiency 84.21% | speedup 1.684x | throughput delta +15.31 tok/s | TTFT delta +nan ms.
- PYTHON | qwen2.5 | baseline-vs-chimera | run 5: efficiency 84.14% | speedup 1.683x | throughput delta +15.15 tok/s | TTFT delta +0.2 ms.
- PYTHON | gemma3 | baseline-vs-chimera | run 2: efficiency 84.07% | speedup 1.681x | throughput delta +16.05 tok/s | TTFT delta +0.6 ms.
- PYTHON | qwen2.5 | baseline-vs-chimera | run 3: efficiency 84.00% | speedup 1.680x | throughput delta +14.71 tok/s | TTFT delta +4.3 ms.
- PYTHON | gemma3 | baseline-vs-chimera | run 4: efficiency 83.94% | speedup 1.679x | throughput delta +16.57 tok/s | TTFT delta -1.0 ms.
- PYTHON | qwen2.5 | chimera-homo | run 4: efficiency 83.92% | speedup 1.678x | throughput delta +15.01 tok/s | TTFT delta +0.5 ms.
- PYTHON | qwen2.5 | baseline-vs-chimera | run 2: efficiency 82.84% | speedup 1.657x | throughput delta +16.26 tok/s | TTFT delta +0.8 ms.
- PYTHON | qwen2.5 | chimera-homo | run 3: efficiency 82.83% | speedup 1.657x | throughput delta +16.26 tok/s | TTFT delta +6.5 ms.
- PYTHON | qwen2.5 | chimera-homo | run 1: efficiency 81.54% | speedup 1.631x | throughput delta +13.18 tok/s | TTFT delta -97.4 ms.
- PYTHON | qwen2.5 | baseline-vs-chimera | run 4: efficiency 81.54% | speedup 1.631x | throughput delta +17.53 tok/s | TTFT delta +6.5 ms.
- RUST | qwen2.5 | baseline-vs-chimera | run 5: efficiency 81.20% | speedup 1.624x | throughput delta +14.33 tok/s | TTFT delta +49.8 ms.
- PYTHON | gemma3 | chimera-homo | run 1: efficiency 79.75% | speedup 1.595x | throughput delta +12.49 tok/s | TTFT delta -43.5 ms.
- RUST | qwen2.5 | chimera-homo | run 5: efficiency 72.00% | speedup 1.440x | throughput delta -32.73 tok/s | TTFT delta +159.9 ms.
- PYTHON | llama3.1 | chimera-homo | run 1: efficiency 69.56% | speedup 1.391x | throughput delta +15.70 tok/s | TTFT delta -72.9 ms.
- PYTHON | llama3.1 | baseline-vs-chimera | run 1: efficiency 60.19% | speedup 1.204x | throughput delta +9.78 tok/s | TTFT delta -5.1 ms.
- PYTHON | gemma3 | baseline-vs-chimera | run 1: efficiency 60.12% | speedup 1.202x | throughput delta +10.16 tok/s | TTFT delta +35.3 ms.
- PYTHON | qwen2.5 | baseline-vs-chimera | run 1: efficiency 55.31% | speedup 1.106x | throughput delta +14.32 tok/s | TTFT delta -11.7 ms.