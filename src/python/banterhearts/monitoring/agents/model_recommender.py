"""Heuristic model recommendations based on collected metrics."""

from __future__ import annotations

from typing import Dict, List


class ModelRecommender:
    def recommend(self, summary: Dict[str, Dict[str, float]]) -> List[str]:
        suggestions: List[str] = []

        gpu_util = summary.get("gpu_util_percent", {})
        cpu_util = summary.get("cpu_percent", {})
        ttft = summary.get("ttft_ms", {})
        throughput = summary.get("throughput_tok_s", {})

        if gpu_util.get("p95", 0) > 90:
            suggestions.append("GPU at >90% util (p95): lower batch size or pin a lighter quantization.")
        if cpu_util.get("p95", 0) > 85:
            suggestions.append("CPU saturated: move tokenization off main loop or add more worker threads.")
        if ttft.get("avg", 0) > 800:
            suggestions.append("High TTFT: warm cache models or increase num_gpu layers for the first token path.")
        if throughput.get("avg", 0) < 10 and gpu_util.get("avg", 0) < 50:
            suggestions.append("Underutilized GPU with low throughput: consider larger context or concurrent streams.")

        if not suggestions:
            suggestions.append("Metrics are healthy; keep current model/quantization.")

        return suggestions
