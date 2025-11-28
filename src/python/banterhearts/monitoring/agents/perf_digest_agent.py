"""Produce human-readable performance digests from monitoring data."""

from __future__ import annotations

from typing import Dict, List

from ..analysis import analyze_metrics, MetricPoint


class PerfDigestAgent:
    def __init__(self, points: List[MetricPoint]) -> None:
        self.points = points

    def build_digest(self) -> str:
        summary = analyze_metrics(self.points)
        lines = ["# Performance Digest", ""]
        for metric, stats in summary.items():
            if metric == "_slos":
                continue
            count = int(stats.get("count", 0))
            if not count:
                continue
            lines.append(
                f"- {metric}: p50={stats.get('p50', 0):.2f}{stats.get('unit','')} "
                f"p95={stats.get('p95', 0):.2f}{stats.get('unit','')} "
                f"max={stats.get('max', 0):.2f}{stats.get('unit','')} (n={count})"
            )

        slo_results = summary.get("_slos", {}).get("results", [])
        if slo_results:
            lines.append("")
            lines.append("## SLOs")
            for res in slo_results:
                status = "PASS" if res["ok"] else "FAIL"
                lines.append(f"- [{status}] {res['message']}")

        return "\n".join(lines)
