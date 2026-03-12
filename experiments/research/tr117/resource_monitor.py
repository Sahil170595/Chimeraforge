"""Resource monitoring for TR117 benchmark runs."""

from __future__ import annotations

from dataclasses import dataclass
import json
import threading
import time
from typing import TYPE_CHECKING, Any

import psutil

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class ResourceSnapshot:
    """Single snapshot of resource utilization."""

    timestamp: float
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    gpu_util_percent: float | None
    gpu_memory_mb: float | None
    gpu_memory_percent: float | None
    gpu_temperature_c: float | None


@dataclass
class ResourceProfile:
    """Aggregate resource profile over a measurement period."""

    duration_s: float
    cpu_mean: float
    cpu_max: float
    memory_mean_mb: float
    memory_max_mb: float
    memory_peak_percent: float
    gpu_util_mean: float | None
    gpu_util_max: float | None
    gpu_memory_mean_mb: float | None
    gpu_memory_max_mb: float | None
    gpu_temperature_mean_c: float | None
    gpu_temperature_max_c: float | None
    samples: int


class ResourceMonitor:
    """Monitor CPU, memory, and GPU resources during inference."""

    def __init__(self, sampling_interval_s: float = 0.1):
        self.sampling_interval = sampling_interval_s
        self.snapshots: list[ResourceSnapshot] = []
        self._monitoring = False
        self._thread: threading.Thread | None = None
        self._process = psutil.Process()

        # Try to import GPU monitoring
        try:
            import pynvml  # type: ignore

            pynvml.nvmlInit()
            self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self._gpu_available = True
        except Exception:
            self._gpu_available = False

    def start(self) -> None:
        """Start monitoring in background thread."""
        if self._monitoring:
            return

        self._monitoring = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self) -> ResourceProfile:
        """Stop monitoring and return aggregate profile."""
        self._monitoring = False
        if self._thread:
            self._thread.join(timeout=1.0)

        return self._compute_profile()

    def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        start_time = time.time()

        while self._monitoring:
            snapshot = self._capture_snapshot(time.time() - start_time)
            self.snapshots.append(snapshot)
            time.sleep(self.sampling_interval)

    def _capture_snapshot(self, timestamp: float) -> ResourceSnapshot:
        """Capture single resource snapshot."""
        # CPU and memory from psutil
        cpu_percent = self._process.cpu_percent()
        mem_info = self._process.memory_info()
        memory_mb = mem_info.rss / (1024 * 1024)
        memory_percent = self._process.memory_percent()

        # GPU metrics
        gpu_util = None
        gpu_memory_mb = None
        gpu_memory_percent = None
        gpu_temp = None

        if self._gpu_available:
            try:
                import pynvml  # type: ignore

                util = pynvml.nvmlDeviceGetUtilizationRates(self._gpu_handle)
                gpu_util = float(util.gpu)

                mem_info_gpu = pynvml.nvmlDeviceGetMemoryInfo(self._gpu_handle)
                gpu_memory_mb = mem_info_gpu.used / (1024 * 1024)
                gpu_memory_percent = (mem_info_gpu.used / mem_info_gpu.total) * 100

                gpu_temp = float(
                    pynvml.nvmlDeviceGetTemperature(
                        self._gpu_handle, pynvml.NVML_TEMPERATURE_GPU
                    )
                )
            except Exception:
                pass

        return ResourceSnapshot(
            timestamp=timestamp,
            cpu_percent=cpu_percent,
            memory_mb=memory_mb,
            memory_percent=memory_percent,
            gpu_util_percent=gpu_util,
            gpu_memory_mb=gpu_memory_mb,
            gpu_memory_percent=gpu_memory_percent,
            gpu_temperature_c=gpu_temp,
        )

    def _compute_profile(self) -> ResourceProfile:
        """Compute aggregate profile from snapshots."""
        if not self.snapshots:
            return ResourceProfile(
                duration_s=0.0,
                cpu_mean=0.0,
                cpu_max=0.0,
                memory_mean_mb=0.0,
                memory_max_mb=0.0,
                memory_peak_percent=0.0,
                gpu_util_mean=None,
                gpu_util_max=None,
                gpu_memory_mean_mb=None,
                gpu_memory_max_mb=None,
                gpu_temperature_mean_c=None,
                gpu_temperature_max_c=None,
                samples=0,
            )

        duration = self.snapshots[-1].timestamp if self.snapshots else 0.0

        cpu_values = [s.cpu_percent for s in self.snapshots]
        memory_values = [s.memory_mb for s in self.snapshots]
        memory_pct_values = [s.memory_percent for s in self.snapshots]

        gpu_util_values = [
            s.gpu_util_percent for s in self.snapshots if s.gpu_util_percent is not None
        ]
        gpu_memory_values = [
            s.gpu_memory_mb for s in self.snapshots if s.gpu_memory_mb is not None
        ]
        gpu_temp_values = [
            s.gpu_temperature_c
            for s in self.snapshots
            if s.gpu_temperature_c is not None
        ]

        return ResourceProfile(
            duration_s=duration,
            cpu_mean=sum(cpu_values) / len(cpu_values) if cpu_values else 0.0,
            cpu_max=max(cpu_values) if cpu_values else 0.0,
            memory_mean_mb=(
                sum(memory_values) / len(memory_values) if memory_values else 0.0
            ),
            memory_max_mb=max(memory_values) if memory_values else 0.0,
            memory_peak_percent=max(memory_pct_values) if memory_pct_values else 0.0,
            gpu_util_mean=(
                sum(gpu_util_values) / len(gpu_util_values) if gpu_util_values else None
            ),
            gpu_util_max=max(gpu_util_values) if gpu_util_values else None,
            gpu_memory_mean_mb=(
                sum(gpu_memory_values) / len(gpu_memory_values)
                if gpu_memory_values
                else None
            ),
            gpu_memory_max_mb=max(gpu_memory_values) if gpu_memory_values else None,
            gpu_temperature_mean_c=(
                sum(gpu_temp_values) / len(gpu_temp_values) if gpu_temp_values else None
            ),
            gpu_temperature_max_c=max(gpu_temp_values) if gpu_temp_values else None,
            samples=len(self.snapshots),
        )

    def reset(self) -> None:
        """Reset snapshots for new measurement."""
        self.snapshots.clear()


def profile_function(
    func: Any, *args: Any, **kwargs: Any
) -> tuple[Any, ResourceProfile]:
    """Profile resource usage of a function call."""
    monitor = ResourceMonitor(sampling_interval_s=0.05)
    monitor.start()

    result = func(*args, **kwargs)

    profile = monitor.stop()
    return result, profile


def save_resource_profile(profile: ResourceProfile, output_path: Path) -> None:
    """Save resource profile to JSON."""
    data = {
        "duration_s": profile.duration_s,
        "cpu_mean_percent": profile.cpu_mean,
        "cpu_max_percent": profile.cpu_max,
        "memory_mean_mb": profile.memory_mean_mb,
        "memory_max_mb": profile.memory_max_mb,
        "memory_peak_percent": profile.memory_peak_percent,
        "gpu_util_mean_percent": profile.gpu_util_mean,
        "gpu_util_max_percent": profile.gpu_util_max,
        "gpu_memory_mean_mb": profile.gpu_memory_mean_mb,
        "gpu_memory_max_mb": profile.gpu_memory_max_mb,
        "gpu_temperature_mean_c": profile.gpu_temperature_mean_c,
        "gpu_temperature_max_c": profile.gpu_temperature_max_c,
        "samples": profile.samples,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> None:
    """Example usage."""
    import time

    def example_workload():
        """Simulate some work."""
        total = 0
        for i in range(10000000):
            total += i
        time.sleep(1)
        return total

    print("Profiling example workload...")
    _result, profile = profile_function(example_workload)

    print("\nResource Profile:")
    print(f"  Duration: {profile.duration_s:.2f}s")
    print(f"  CPU: {profile.cpu_mean:.1f}% avg, {profile.cpu_max:.1f}% peak")
    print(
        f"  Memory: {profile.memory_mean_mb:.1f}MB avg, {profile.memory_max_mb:.1f}MB peak"
    )

    if profile.gpu_util_mean is not None:
        print(
            f"  GPU Util: {profile.gpu_util_mean:.1f}% avg, {profile.gpu_util_max:.1f}% peak"
        )
        print(
            f"  GPU Memory: {profile.gpu_memory_mean_mb:.1f}MB avg, {profile.gpu_memory_max_mb:.1f}MB peak"
        )
        print(
            f"  GPU Temp: {profile.gpu_temperature_mean_c:.1f}°C avg, {profile.gpu_temperature_max_c:.1f}°C peak"
        )


if __name__ == "__main__":
    main()
