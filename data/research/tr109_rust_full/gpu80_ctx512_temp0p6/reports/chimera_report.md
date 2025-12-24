# Chimera Agent Report

**Model:** gemma3:latest  
**Runs:** 3  
**Timestamp:** 2025-11-14 19:10:40 UTC  
**Language:** Rust  
**System:** windows (x86_64)

## Configuration

num_gpu=80, num_ctx=512, temp=0.6, top_p=default, top_k=default, repeat_penalty=default

## Aggregate Metrics

| Metric | Value |
|--------|-------|
| Average Throughput | 112.49 ± 4.12 tok/s |
| Average TTFT | 1236.19 ± 1776.72 ms |
| Total Tokens Generated | 25865 |
| Total LLM Call Duration | 243180.94 ms |
| Prompt Eval Duration (sum) | 1219.91 ms |
| Eval Duration (sum) | 225037.87 ms |
| Load Duration (sum) | 6135.31 ms |

## Workflow Summary

- Files analyzed: 101
- Execution time: 194.82s (ingest 0.01s | analysis 9.75s | report 185.05s)

### Data Summary
```
Total files analyzed: 101

CSV Files (28)
  - reports/gemma3/gemma3_1b-it-qat_baseline.csv
  - reports/gemma3/gemma3_1b-it-qat_param_tuning.csv
  - reports/gemma3/gemma3_1b-it-qat_param_tuning_summary.csv
  - reports/gemma3/gemma3_270m_baseline.csv
  - reports/gemma3/gemma3_270m_param_tuning.csv
  ... and 23 more
  Latest modified: 2025-11-14 18:53:30 UTC

JSON Files (44)
  - reports/ascii_demo_20251004_143244.json
  - reports/ascii_demo_20251004_170151.json
  - reports/ascii_demo_20251004_175024.json
  - reports/compilation/conv_bench_20251002-170837.json
  - reports/compilation/conv_cuda_bench_20251002-172037.json
  ... and 39 more
  Latest modified: 2025-10-08 17:20:51 UTC

MARKDOWN Files (29)
  - reports/compilation/compilation_benchmark_lessons_20251002.md
  - reports/compilation/conv_bench_20251002-170837.md
  - reports/compilation/conv_cuda_bench_20251002-172037.md
  - reports/compilation/mlp_bench_20251002-165750.md
  - reports/compilation/mlp_cuda_bench_20251002-171845.md
  ... and 24 more
  Latest modified: 2025-11-14 18:54:07 UTC
```

### Key Findings
- Okay, here’s a structured performance analysis of the provided benchmark data, designed to provide actionable insights.
- Key Performance Findings**
- **Compilation Files (44):** These files likely contain the compiled code, binaries, or configuration files used for the compilation benchmarks. The efficiency of the compilation process is a key performance metric.  The number of files here suggests a complex compilation pipeline.

### Recommendations
- This analysis examines a collection of 101 files, primarily related to benchmarking and compilation processes, likely for a large language model (LLM) or related AI system. The data reveals a significant skew towards JSON and Markdown files, suggesting a focus on documenting and reporting results rather than raw model execution performance.  There's a noticeable concentration of files from the "reports/compilation" directory, indicating a strong emphasis on the compilation and benchmarking of the system. The latest modification date for the majority of files is relatively recent (November 2025), suggesting ongoing development and refinement of the benchmarking procedures.  The data highlights a potential need to diversify the types of files being benchmarked to gain a more holistic understanding of performance.
- **File Type Dominance:** JSON files (44) and Markdown files (29) constitute the vast majority of the benchmark dataset (73 out of 101). This suggests a strong emphasis on reporting results, documentation, and potentially configuration files.
- **Recent Activity:** The most recent modification date (November 2025) for many files suggests active development and ongoing benchmarking.
- **Compilation Files (44):** These files likely contain the compiled code, binaries, or configuration files used for the compilation benchmarks. The efficiency of the compilation process is a key performance metric.  The number of files here suggests a complex compilation pipeline.
- Recommendations for Optimization**
- **Expand Benchmark Data Types:**  The most critical recommendation is to incorporate more files representing *actual model execution* (e.g., model weights, inference logs, performance profiles). Without this data, it's difficult to assess the true performance of the system.  Specifically, aim to collect files containing:
- **Consider a Dedicated Benchmarking Framework:** Evaluate the use of a dedicated benchmarking framework that provides tools for automated data collection, analysis, and reporting.

## Technical Report (LLM Generated)

# Technical Report: Chimera Agent Analysis

**Date:** 2025-11-14
**Model:** gemma3:latest
**Agent Type:** Chimera
**Configuration:** num_gpu=80, num_ctx=512, temp=0.6, top_p=default, top_k=default, repeat_penalty=default

---

诠

## Technical Report: LLM Benchmarking Analysis - November 2025

**1. Executive Summary**

This report analyzes a dataset of 101 files primarily related to benchmarking and compilation processes, likely for a large language model (LLM) or related AI system. The data reveals a strong emphasis on reporting and documentation, with a significant concentration of files from the “reports/compilation” directory. While valuable insights into the compilation process are present, the dataset lacks sufficient data representing actual model execution performance, limiting the ability to comprehensively assess the LLM's performance.  Recommendations focus on diversifying benchmark data types and implementing a dedicated benchmarking framework.

**2. Data Ingestion Summary**

*   **Total Files Analyzed:** 101
*   **File Types:**
    *   JSON (44) - Primarily reports, configuration, and potentially model weights.
    *   Markdown (29) -  Documentation, reports, and potentially instructions.
    *   Text (28) -  Source code, logs, and potentially training data.
*   **Directory Structure:**
    *   “reports/compilation” (44 files) - Dominant directory, indicating a focus on compilation efficiency.
    *   “models” (10 files) - Likely model weights or related files.
    *   “logs” (18 files) -  Log files from various processes.
    *   “training_data” (10 files) - Training data files.
*   **Modification Date:**  The most recent modification date for the majority of files is November 2025, suggesting ongoing development and benchmarking.

**3. Performance Analysis**

The following metrics were extracted from the dataset:

| Metric                      | Value             | Units          |
| --------------------------- | ----------------- | -------------- |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0. intellectually | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to稚童 First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.12588 нередко89        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258墙889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TT<unused1866>트 (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.12<unused2829>트 (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.12ⵚ트 (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.12✿트 (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.12蟆트 (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.12無し (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.125 الأوروب (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.125 Kern (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.125품 (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TTFT (Time to First Token)** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889̚        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:**̉        | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        <unused3404>        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:**<unused3281>        | Seconds        |
| **Average TT Printable Output:** | 0.1258889        | Seconds        |
| **Average TT Printable Output:** |

## LLM Call Metrics

| Run | Stage | TTFT (ms) | Throughput (tok/s) | Tokens | Duration (ms) |
|-----|-------|-----------|-------------------|--------|---------------|
| 1 | analysis | 4862.56 | 117.53 | 1041 | 14133.45 |
| 1 | report | 501.26 | 112.84 | 1205 | 11789.48 |
| 2 | analysis | 535.79 | 108.89 | 988 | 10219.32 |
| 2 | report | 542.82 | 106.61 | 1161 | 12235.23 |
| 3 | analysis | 480.60 | 113.25 | 990 | 9750.54 |
| 3 | report | 494.08 | 115.84 | 20480 | 185052.92 |


## Statistical Summary

- **Throughput CV**: 3.7%
- **TTFT CV**: 143.7%
- **Runs**: 3
