"""GPU instrumentation via nvidia-smi polling.

Runs in a background thread, polls GPU metrics every *interval* seconds,
and returns timestamped samples.  Copied from TR128, adapted for TR129.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import logging
from pathlib import Path
import subprocess
import threading
import time

log = logging.getLogger("tr129.gpu_monitor")

_QUERY_FIELDS = (
    "utilization.gpu,"
    "utilization.memory,"
    "temperature.gpu,"
    "power.draw,"
    "memory.used,"
    "memory.total,"
    "clocks.current.sm"
)

_CSV_HEADER = [
    "timestamp",
    "elapsed_s",
    "gpu_util_pct",
    "mem_util_pct",
    "temp_c",
    "power_w",
    "mem_used_mb",
    "mem_total_mb",
    "clock_mhz",
]


@dataclass
class GpuSample:
    """Single nvidia-smi sample."""

    timestamp: float = 0.0
    elapsed_s: float = 0.0
    gpu_util_pct: float = 0.0
    mem_util_pct: float = 0.0
    temp_c: float = 0.0
    power_w: float = 0.0
    mem_used_mb: float = 0.0
    mem_total_mb: float = 0.0
    clock_mhz: float = 0.0


def _poll_once() -> GpuSample | None:
    """Run nvidia-smi once and parse the output."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                f"--query-gpu={_QUERY_FIELDS}",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        parts = [p.strip() for p in result.stdout.strip().split(",")]
        if len(parts) < 7:
            return None
        return GpuSample(
            timestamp=time.time(),
            gpu_util_pct=float(parts[0]),
            mem_util_pct=float(parts[1]),
            temp_c=float(parts[2]),
            power_w=float(parts[3]),
            mem_used_mb=float(parts[4]),
            mem_total_mb=float(parts[5]),
            clock_mhz=float(parts[6]),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError) as exc:
        log.debug("nvidia-smi poll failed: %s", exc)
        return None


class GpuMonitor:
    """Background GPU metrics collector.

    Usage::

        mon = GpuMonitor(interval=1.0)
        mon.start()
        # ... run experiment ...
        samples = mon.stop()
        mon.save_csv(samples, Path("gpu_metrics.csv"))
    """

    def __init__(self, interval: float = 1.0):
        self._interval = interval
        self._samples: list[GpuSample] = []
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._t0: float = 0.0

    def start(self) -> None:
        """Start background polling thread."""
        test = _poll_once()
        if test is None:
            log.warning("nvidia-smi not available — GPU monitoring disabled")
            return

        self._samples = []
        self._stop_event.clear()
        self._t0 = time.time()
        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="gpu-monitor",
        )
        self._thread.start()
        log.info(
            "GPU monitor started (%.1fs interval, %s, %.0f MB VRAM)",
            self._interval,
            test.temp_c,
            test.mem_total_mb,
        )

    def stop(self) -> list[GpuSample]:
        """Stop polling and return collected samples."""
        if self._thread is None:
            return []
        self._stop_event.set()
        self._thread.join(timeout=self._interval * 3)
        self._thread = None
        log.info(
            "GPU monitor stopped: %d samples over %.1fs",
            len(self._samples),
            self._samples[-1].elapsed_s if self._samples else 0,
        )
        return list(self._samples)

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            sample = _poll_once()
            if sample is not None:
                sample.elapsed_s = round(time.time() - self._t0, 2)
                self._samples.append(sample)
            self._stop_event.wait(self._interval)

    @staticmethod
    def save_csv(samples: list[GpuSample], path: Path) -> None:
        """Write samples to CSV."""
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_CSV_HEADER)
            writer.writeheader()
            for s in samples:
                row = asdict(s)
                for k in row:
                    if isinstance(row[k], float):
                        row[k] = round(row[k], 2)
                writer.writerow(row)

    @staticmethod
    def summarize(samples: list[GpuSample]) -> dict:
        """Produce summary statistics from a list of samples."""
        if not samples:
            return {"n_samples": 0}

        import numpy as np

        temps = [s.temp_c for s in samples]
        utils = [s.gpu_util_pct for s in samples]
        mems = [s.mem_used_mb for s in samples]
        powers = [s.power_w for s in samples]
        clocks = [s.clock_mhz for s in samples]

        peak_clock = max(clocks) if clocks else 0
        throttle_samples = [
            s
            for s in samples
            if s.temp_c > 80 and peak_clock > 0 and s.clock_mhz < peak_clock * 0.9
        ]

        return {
            "n_samples": len(samples),
            "duration_s": round(samples[-1].elapsed_s, 1),
            "temp_c": {
                "min": round(min(temps), 1),
                "max": round(max(temps), 1),
                "mean": round(float(np.mean(temps)), 1),
                "final": round(temps[-1], 1),
            },
            "gpu_util_pct": {
                "min": round(min(utils), 1),
                "max": round(max(utils), 1),
                "mean": round(float(np.mean(utils)), 1),
            },
            "mem_used_mb": {
                "min": round(min(mems), 1),
                "max": round(max(mems), 1),
                "mean": round(float(np.mean(mems)), 1),
            },
            "power_w": {
                "mean": round(float(np.mean(powers)), 1),
                "max": round(max(powers), 1),
            },
            "clock_mhz": {
                "peak": round(peak_clock, 0),
                "min": round(min(clocks), 0),
                "mean": round(float(np.mean(clocks)), 0),
            },
            "thermal_throttle": {
                "detected": len(throttle_samples) > 0,
                "n_samples": len(throttle_samples),
                "pct_of_run": round(len(throttle_samples) / len(samples) * 100, 1),
                "threshold": "temp > 80C AND clock < 90% of peak",
            },
        }
