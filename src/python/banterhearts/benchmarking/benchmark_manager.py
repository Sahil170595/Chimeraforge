"""
Benchmark Manager for Chimera Heart Self-Healing Pipeline
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any
from pathlib import Path


class BenchmarkManager:
    """Manages benchmark data for anomaly detection."""

    def __init__(self, repo_root: Path = None):
        if repo_root is None:
            # Default to current working directory, but allow override
            repo_root = Path.cwd()
        self.reports_dir = repo_root / "outputs" / "reports"
        self.csv_dir = repo_root / "data" / "csv"

    def get_recent_metrics(self, hours: int = 1) -> List[Dict[str, Any]]:
        """Get recent benchmark metrics."""
        # Simulate loading recent metrics
        return [
            {
                "timestamp": datetime.now(),
                "backend": "transformer_cuda_triton2508_summary",
                "metric_name": "latency_ms",
                "metric_value": 8.198,
                "unit": "ms",
                "test_name": "latency_test",
                "tags": {"compilation": "tensorrt"},
            },
            {
                "timestamp": datetime.now(),
                "backend": "transformer_cuda_triton2508_summary",
                "metric_name": "tokens_per_s",
                "metric_value": 1.158,
                "unit": "tokens/s",
                "test_name": "throughput_test",
                "tags": {"compilation": "tensorrt"},
            },
            {
                "timestamp": datetime.now(),
                "backend": "transformer_cuda_triton2508_summary",
                "metric_name": "latency_ms",
                "metric_value": 0.308,
                "unit": "ms",
                "test_name": "latency_test",
                "tags": {"compilation": "jit"},
            },
            {
                "timestamp": datetime.now(),
                "backend": "ollama_benchmark_summary",
                "metric_name": "latency_ms",
                "metric_value": 76.590,
                "unit": "ms",
                "test_name": "latency_test",
                "tags": {"quantization": "q4_0"},
            },
            {
                "timestamp": datetime.now(),
                "backend": "ollama_benchmark_summary",
                "metric_name": "latency_ms",
                "metric_value": 1024.000,
                "unit": "ms",
                "test_name": "latency_test",
                "tags": {"quantization": "99.00"},
            },
        ]

    def get_historical_metrics(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get historical benchmark metrics for pattern analysis."""
        # Generate simulated historical data with realistic patterns
        base_time = datetime.now() - timedelta(days=days)
        historical_data = []

        # JIT compilation performance (trending downward - good)
        jit_values = [0.350, 0.340, 0.330, 0.325, 0.320, 0.315, 0.308]  # Improving

        # TensorRT performance (recent regression - concerning)
        tensorrt_values = [2.100, 2.150, 2.200, 2.300, 3.100, 5.800, 8.198]  # Degrading

        # Ollama Q4_0 performance (stable)
        ollama_values = [76.2, 76.4, 76.1, 76.3, 76.0, 76.2, 76.590]

        for i in range(days):
            timestamp = base_time + timedelta(days=i)
            if i < len(jit_values):
                historical_data.extend(
                    [
                        {
                            "timestamp": timestamp,
                            "backend": "transformer_cuda_triton2508_summary",
                            "metric_name": "latency_ms",
                            "metric_value": jit_values[i],
                            "value": jit_values[i],  # For compatibility
                            "unit": "ms",
                            "tags": {"compilation": "jit"},
                        },
                        {
                            "timestamp": timestamp,
                            "backend": "transformer_cuda_triton2508_summary",
                            "metric_name": "latency_ms",
                            "metric_value": tensorrt_values[i],
                            "value": tensorrt_values[i],
                            "unit": "ms",
                            "tags": {"compilation": "tensorrt"},
                        },
                        {
                            "timestamp": timestamp,
                            "backend": "ollama_benchmark_summary",
                            "metric_name": "latency_ms",
                            "metric_value": ollama_values[i],
                            "value": ollama_values[i],
                            "unit": "ms",
                            "tags": {"quantization": "q4_0"},
                        },
                    ]
                )

        return historical_data

    # Fix the typo in the function
    def count_days(self, days):
        """Helper function to fix the typo."""
        return days
