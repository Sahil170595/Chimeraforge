import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

# Ensure src/python is importable when running tests locally
ROOT = Path(__file__).resolve().parents[1]
SRC_PYTHON = ROOT / "src" / "python"
if str(SRC_PYTHON) not in sys.path:
    sys.path.insert(0, str(SRC_PYTHON))

from banterhearts.monitoring.analysis import MetricPoint, SLO, analyze_metrics
from banterhearts.monitoring.agents.aggregator import MetricAggregator
from banterhearts.monitoring.agents.parsers import parse_log_lines
from banterhearts.monitoring.agents.model_recommender import ModelRecommender
from banterhearts.monitoring.performance_monitor import PerformanceMonitor


def test_analyze_metrics_with_slo_pass():
    points = [MetricPoint("latency_ms", 50), MetricPoint("latency_ms", 60)]
    slo = SLO(name="latency_ms", target=100, comparator="<=")
    summary = analyze_metrics(points, slos=[slo])
    assert summary["latency_ms"]["p95"] == pytest.approx(60, rel=0.05)
    assert summary["_slos"]["results"][0]["ok"] is True


def test_parse_log_lines_extracts_metrics():
    lines = [
        "latency_ms=123 throughput=9.8",
        json.dumps({"latency_ms": 77, "ttft_ms": 12}),
    ]
    points = parse_log_lines(lines, default_tags={"role": "collector"})
    names = {p.name for p in points}
    assert {"latency_ms", "throughput_tok_s", "ttft_ms"} <= names
    assert all(p.tags.get("role") == "collector" for p in points)


def test_thread_safe_aggregator():
    agg = MetricAggregator()
    for _ in range(100):
        agg.add_point(MetricPoint("cpu_percent", 10.0))
    summary = agg.summarize()
    assert summary["cpu_percent"]["count"] == 100


def test_model_recommender_flags_high_util():
    summary = {
        "gpu_util_percent": {"p95": 95},
        "cpu_percent": {"p95": 10},
        "ttft_ms": {"avg": 100},
        "throughput_tok_s": {"avg": 50},
    }
    recs = ModelRecommender().recommend(summary)
    assert any("GPU at >90% util" in r for r in recs)


def test_performance_monitor_digest_smoke(monkeypatch):
    # Avoid hitting psutil in environments without permissions by mocking capture_snapshot.
    pm = PerformanceMonitor(interval=0.01)
    def fake_capture():
        pm.aggregator.add_point(MetricPoint("cpu_percent", 1.0, "%"))
    pm.capture_snapshot = fake_capture  # type: ignore
    pm.start()
    pm.stop()
    digest = pm.build_digest()
    assert "summary" in digest and "digest" in digest and "suggestions" in digest
