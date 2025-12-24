#!/usr/bin/env python3
"""
TR117 Instrumentation: Memory, power, and resource monitoring.

Provides utilities to capture:
- GPU memory (VRAM usage, peak allocation)
- CPU memory (RSS, swap)
- GPU power (Watts, temperature)
- CPU power (RAPL via Windows Energy Meter counters when available)

Usage:
    with ResourceMonitor() as monitor:
        # Run inference
        ...
    metrics = monitor.get_metrics()
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ResourceSnapshot:
    """Single point-in-time resource measurement."""

    timestamp: float
    # GPU
    gpu_memory_used_mb: float
    gpu_memory_total_mb: float
    gpu_utilization_pct: float
    gpu_power_watts: float | None
    gpu_temperature_c: float | None
    # CPU
    cpu_memory_rss_mb: float
    cpu_memory_percent: float
    cpu_utilization_pct: float
    cpu_power_watts: float | None


class ResourceMonitor:
    """
    Context manager for monitoring system resources during benchmark runs.

    Example:
        with ResourceMonitor(sample_interval_s=0.1) as monitor:
            result = run_inference(...)
        metrics = monitor.get_metrics()
        print(f"Peak GPU memory: {metrics['gpu_memory_peak_mb']:.1f} MB")
    """

    def __init__(self, sample_interval_s: float = 0.1, enable_power: bool = True):
        self.sample_interval_s = sample_interval_s
        self.enable_power = enable_power
        self.snapshots: list[ResourceSnapshot] = []
        self._monitoring = False
        self._thread = None
        self._nvml_initialized = False
        self._pdh_query = None
        self._pdh_power_counters: list[Any] = []
        self._has_energy_meter = False

        # Check dependencies
        self.has_nvidia_smi = self._check_nvidia_smi()
        self.has_psutil = self._check_psutil()
        self._has_energy_meter = self._check_energy_meter()

    def _check_nvidia_smi(self) -> bool:
        """Check if nvidia-ml-py is available."""
        try:
            import pynvml  # noqa: F401

            return True
        except ImportError:
            logger.warning("nvidia-ml-py not installed, GPU monitoring disabled")
            return False

    def _check_psutil(self) -> bool:
        """Check if psutil is available."""
        try:
            import psutil  # noqa: F401

            return True
        except ImportError:
            logger.warning("psutil not installed, CPU monitoring disabled")
            return False

    def _check_energy_meter(self) -> bool:
        """Check if Windows Energy Meter counters are available."""
        if os.name != "nt":
            return False
        try:
            import win32pdh  # type: ignore

            _, instances = win32pdh.EnumObjectItems(
                None, None, "Energy Meter", win32pdh.PERF_DETAIL_WIZARD
            )
            return bool(instances)
        except Exception:
            return False

    def _init_energy_counters(self) -> None:
        if not self._has_energy_meter or not self.enable_power:
            return
        try:
            import win32pdh  # type: ignore

            _, instances = win32pdh.EnumObjectItems(
                None, None, "Energy Meter", win32pdh.PERF_DETAIL_WIZARD
            )
            instances_lower = [str(i) for i in instances]
            pkg_instances = [
                inst for inst in instances_lower if "rapl_package" in inst.lower() and inst.lower().endswith("_pkg")
            ]
            if not pkg_instances:
                pkg_instances = [inst for inst in instances_lower if "rapl_package" in inst.lower()]
            if not pkg_instances:
                return
            self._pdh_query = win32pdh.OpenQuery()
            for inst in pkg_instances:
                path = f"\\Energy Meter({inst})\\Power"
                try:
                    handle = win32pdh.AddCounter(self._pdh_query, path)
                    self._pdh_power_counters.append(handle)
                except Exception:
                    continue
            if not self._pdh_power_counters:
                win32pdh.CloseQuery(self._pdh_query)
                self._pdh_query = None
            else:
                try:
                    win32pdh.CollectQueryData(self._pdh_query)
                except Exception:
                    pass
        except Exception as exc:
            logger.debug("Energy meter init failed: %s", exc)
            self._pdh_query = None
            self._pdh_power_counters = []

    def __enter__(self):
        """Start monitoring."""
        self._monitoring = True
        self._init_energy_counters()
        if self.has_nvidia_smi:
            import pynvml

            try:
                pynvml.nvmlInit()
                self._nvml_initialized = True
            except Exception as exc:
                # `pynvml` on Windows historically hardcodes the NVSMI path. Fall back
                # to the system loader which can resolve `nvml.dll` from System32.
                if os.name == "nt":
                    try:
                        import ctypes

                        pynvml.nvmlLib = ctypes.CDLL("nvml.dll")  # type: ignore[attr-defined]
                        pynvml.nvmlInit()
                        self._nvml_initialized = True
                    except Exception:
                        self.has_nvidia_smi = False
                        logger.warning("NVML init failed, GPU monitoring disabled: %s", exc)
                else:
                    self.has_nvidia_smi = False
                    logger.warning("NVML init failed, GPU monitoring disabled: %s", exc)
        # Start background sampling thread
        import threading

        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *args):
        """Stop monitoring."""
        self._monitoring = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._pdh_query is not None:
            try:
                import win32pdh  # type: ignore

                win32pdh.CloseQuery(self._pdh_query)
            except Exception:
                pass
            self._pdh_query = None
            self._pdh_power_counters = []
        if self._nvml_initialized:
            import pynvml

            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
            self._nvml_initialized = False

    def _sample_loop(self):
        """Background sampling loop."""
        while self._monitoring:
            snapshot = self._capture_snapshot()
            if snapshot:
                self.snapshots.append(snapshot)
            time.sleep(self.sample_interval_s)

    def _capture_snapshot(self) -> ResourceSnapshot | None:
        """Capture a single resource snapshot."""
        try:
            timestamp = time.time()

            # GPU metrics
            gpu_mem_used = 0.0
            gpu_mem_total = 0.0
            gpu_util = 0.0
            gpu_power = None
            gpu_temp = None

            if self.has_nvidia_smi:
                import pynvml

                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                gpu_mem_used = mem_info.used / (1024**2)  # MB
                gpu_mem_total = mem_info.total / (1024**2)
                util_info = pynvml.nvmlDeviceGetUtilizationRates(handle)
                gpu_util = util_info.gpu

                if self.enable_power:
                    try:
                        gpu_power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # mW → W
                        gpu_temp = pynvml.nvmlDeviceGetTemperature(
                            handle, pynvml.NVML_TEMPERATURE_GPU
                        )
                    except pynvml.NVMLError:
                        pass  # Power/temp not supported on all GPUs

            # CPU metrics
            cpu_mem_rss = 0.0
            cpu_mem_pct = 0.0
            cpu_util = 0.0
            cpu_power = None

            if self.has_psutil:
                import psutil

                process = psutil.Process(os.getpid())
                mem_info = process.memory_info()
                cpu_mem_rss = mem_info.rss / (1024**2)  # MB
                cpu_mem_pct = process.memory_percent()
                cpu_util = process.cpu_percent(interval=None)  # Non-blocking

            if self._pdh_query is not None and self._pdh_power_counters:
                try:
                    import win32pdh  # type: ignore

                    win32pdh.CollectQueryData(self._pdh_query)
                    readings = []
                    for counter in self._pdh_power_counters:
                        _, value = win32pdh.GetFormattedCounterValue(counter, win32pdh.PDH_FMT_DOUBLE)
                        if value is None:
                            continue
                        readings.append(float(value))
                    if readings:
                        total = sum(readings)
                        cpu_power = total / 1000.0 if total > 1000.0 else total
                except Exception:
                    cpu_power = None

            return ResourceSnapshot(
                timestamp=timestamp,
                gpu_memory_used_mb=gpu_mem_used,
                gpu_memory_total_mb=gpu_mem_total,
                gpu_utilization_pct=gpu_util,
                gpu_power_watts=gpu_power,
                gpu_temperature_c=gpu_temp,
                cpu_memory_rss_mb=cpu_mem_rss,
                cpu_memory_percent=cpu_mem_pct,
                cpu_utilization_pct=cpu_util,
                cpu_power_watts=cpu_power,
            )

        except Exception as exc:
            logger.debug(f"Failed to capture resource snapshot: {exc}")
            return None

    def get_metrics(self) -> dict[str, Any]:
        """
        Aggregate snapshots into summary metrics.

        Returns:
            Dict with mean/peak/min for each metric
        """
        if not self.snapshots:
            return {}

        gpu_mem_values = [s.gpu_memory_used_mb for s in self.snapshots]
        gpu_util_values = [s.gpu_utilization_pct for s in self.snapshots]
        gpu_power_values = [s.gpu_power_watts for s in self.snapshots if s.gpu_power_watts]
        gpu_temp_values = [s.gpu_temperature_c for s in self.snapshots if s.gpu_temperature_c]
        cpu_mem_values = [s.cpu_memory_rss_mb for s in self.snapshots]
        cpu_util_values = [s.cpu_utilization_pct for s in self.snapshots]
        cpu_power_values = [s.cpu_power_watts for s in self.snapshots if s.cpu_power_watts]

        metrics = {
            "samples": len(self.snapshots),
            "duration_s": self.snapshots[-1].timestamp - self.snapshots[0].timestamp,
            "gpu_memory_mean_mb": sum(gpu_mem_values) / len(gpu_mem_values) if gpu_mem_values else 0,
            "gpu_memory_peak_mb": max(gpu_mem_values) if gpu_mem_values else 0,
            "gpu_memory_total_mb": self.snapshots[0].gpu_memory_total_mb,
            "gpu_utilization_mean_pct": (
                sum(gpu_util_values) / len(gpu_util_values) if gpu_util_values else 0
            ),
            "gpu_power_mean_watts": (
                sum(gpu_power_values) / len(gpu_power_values) if gpu_power_values else None
            ),
            "gpu_power_peak_watts": max(gpu_power_values) if gpu_power_values else None,
            "gpu_temperature_mean_c": (
                sum(gpu_temp_values) / len(gpu_temp_values) if gpu_temp_values else None
            ),
            "gpu_temperature_peak_c": max(gpu_temp_values) if gpu_temp_values else None,
            "cpu_memory_mean_mb": sum(cpu_mem_values) / len(cpu_mem_values) if cpu_mem_values else 0,
            "cpu_memory_peak_mb": max(cpu_mem_values) if cpu_mem_values else 0,
            "cpu_utilization_mean_pct": (
                sum(cpu_util_values) / len(cpu_util_values) if cpu_util_values else 0
            ),
            "cpu_power_mean_watts": (
                sum(cpu_power_values) / len(cpu_power_values) if cpu_power_values else None
            ),
            "cpu_power_peak_watts": max(cpu_power_values) if cpu_power_values else None,
        }

        return metrics

    def get_snapshots(self) -> list[dict[str, Any]]:
        """Return all snapshots as list of dicts."""
        return [asdict(s) for s in self.snapshots]
