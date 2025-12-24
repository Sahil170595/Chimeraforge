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