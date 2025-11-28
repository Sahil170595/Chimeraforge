"""Periodically capture system and GPU metrics for ML runs."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional

import psutil

from .analysis import MetricPoint, SLO, analyze_metrics
from .logging import get_logger
from .nvidia_tools import get_gpu_snapshots
from .agents.aggregator import MetricAggregator
from .agents.perf_digest_agent import PerfDigestAgent
from .agents.suggestions import SuggestionsAgent

logger = get_logger(__name__)


class PerformanceMonitor:
    def __init__(self, *, interval: float = 2.0, aggregator: Optional[MetricAggregator] = None) -> None:
        self.interval = interval
        self.aggregator = aggregator or MetricAggregator()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("performance_monitor.started", interval=self.interval)

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=self.interval * 2)
            self._thread = None
        logger.info("performance_monitor.stopped")

    def capture_snapshot(self) -> None:
        now = datetime.now(timezone.utc)
        tags = {"ts": now.isoformat()}

        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        net = psutil.net_io_counters()
        disk = psutil.disk_io_counters()

        self.aggregator.add_point(MetricPoint("cpu_percent", cpu, "%", tags=tags))
        self.aggregator.add_point(MetricPoint("mem_used_mb", mem.used / (1024 * 1024), "MB", tags=tags))
        self.aggregator.add_point(MetricPoint("mem_percent", mem.percent, "%", tags=tags))
        if net:
            self.aggregator.add_point(MetricPoint("net_bytes_sent", net.bytes_sent, "bytes", tags=tags))
            self.aggregator.add_point(MetricPoint("net_bytes_recv", net.bytes_recv, "bytes", tags=tags))
        if disk:
            self.aggregator.add_point(MetricPoint("disk_read_mb", disk.read_bytes / (1024 * 1024), "MB", tags=tags))
            self.aggregator.add_point(MetricPoint("disk_write_mb", disk.write_bytes / (1024 * 1024), "MB", tags=tags))

        for gpu in get_gpu_snapshots():
            gpu_tags = {**tags, "gpu_index": str(gpu["gpu_index"])}
            self.aggregator.add_point(MetricPoint("gpu_util_percent", gpu["utilization"], "%", tags=gpu_tags))
            self.aggregator.add_point(MetricPoint("gpu_mem_used_mb", gpu["mem_used_mb"], "MB", tags=gpu_tags))
            self.aggregator.add_point(MetricPoint("gpu_mem_total_mb", gpu["mem_total_mb"], "MB", tags=gpu_tags))
            self.aggregator.add_point(MetricPoint("gpu_temp_c", gpu["temperature_c"], "C", tags=gpu_tags))

    def _run_loop(self) -> None:
        while self._running:
            try:
                self.capture_snapshot()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("performance_monitor.capture_failed", error=str(exc))
            time.sleep(self.interval)

    def summarize(self, slos: Optional[list[SLO]] = None) -> Dict[str, Dict[str, float]]:
        return analyze_metrics(self.aggregator.points, slos=slos)

    def build_digest(self, slos: Optional[list[SLO]] = None) -> Dict[str, object]:
        summary = self.summarize(slos=slos)
        digest = PerfDigestAgent(self.aggregator.points).build_digest()
        suggestions = SuggestionsAgent().suggest(summary)
        return {"summary": summary, "digest": digest, "suggestions": suggestions}
