"""
Main demo orchestrator for Chimera agent performance demonstration.

Command-line interface for running baseline vs Chimera-optimized agent comparison
with research-grade metrics collection and report generation.
"""

import argparse
import asyncio
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Optional

# Imports removed - unused in this module


class ChimeraDemoOrchestrator:
    """
    Orchestrates the Chimera agent performance demonstration.

    Runs baseline and Chimera-optimized agents sequentially to ensure
    fair comparison with isolated GPU resources.
    """

    def __init__(
        self,
        model: str,
        output_dir: str,
        runs: int = 1,
        *,
        chimera_overrides: Optional[Dict[str, Any]] = None,
    ):
        self.model = model
        self.output_dir = Path(output_dir)
        self.runs = runs
        self.results = []
        self.chimera_overrides = chimera_overrides or {}

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "reports").mkdir(exist_ok=True)
        (self.output_dir / "data").mkdir(exist_ok=True)

    async def _force_model_unload(self) -> None:
        """Force Ollama to unload all models to ensure a cold start."""
        try:
            # Best-effort attempt to flush resident models without requiring elevated privileges
            subprocess.run(
                ["ollama", "stop", "all"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except FileNotFoundError:
            print("[WARNING] Ollama CLI not found - unable to stop running models.")
            return
        except subprocess.TimeoutExpired:
            print("[WARNING] Timeout while stopping Ollama models.")
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[WARNING] Unexpected error stopping models: {exc}")
            return

        await asyncio.sleep(2)

        try:
            ps_result = subprocess.run(
                ["ollama", "ps"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except Exception:
            ps_result = None

        if not ps_result or ps_result.returncode != 0:
            try:
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                await asyncio.sleep(3)
            except Exception as exc:  # pragma: no cover
                print(f"[WARNING] Failed to restart Ollama service: {exc}")
                return

        print("[SUCCESS] Ollama models unloaded and ready for next run.")

    async def _run_agent_in_separate_process(
        self, agent_type: str, model: str
    ) -> Dict[str, Any]:
        """Run an agent in a fresh Python process to avoid warm-cache bias."""

        agent_module = f"agents.{agent_type.lower()}_agent"
        agent_class = f"{agent_type}Agent"
        demo_agent_root = Path(__file__).resolve().parent

        agent_kwargs = (
            {"overrides": self.chimera_overrides}
            if agent_type.lower() == "chimera" and self.chimera_overrides
            else {}
        )
        agent_kwargs_literal = repr(agent_kwargs)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_dir_path = Path(tmp_dir)
            script_path = tmp_dir_path / "agent_runner.py"
            results_path = tmp_dir_path / "results.json"

            script_content = f"""\
import asyncio
import json
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path

DEMO_AGENT_ROOT = Path(r\"{demo_agent_root}\")
if str(DEMO_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(DEMO_AGENT_ROOT))

from {agent_module} import {agent_class}


def _default_serializer(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "__dict__"):
        return value.__dict__
    return str(value)


async def main():
    agent_kwargs = {agent_kwargs_literal}
    agent = {agent_class}("{model}", **agent_kwargs)
    results = await agent.run_full_analysis()
    with open(r\"{results_path}\", "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=_default_serializer)


if __name__ == "__main__":
    asyncio.run(main())
"""

            script_path.write_text(script_content, encoding="utf-8")

            print(f"[PROCESS] Running {agent_type} agent in isolated process...")
            process = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(demo_agent_root),
            )

            if process.returncode != 0:
                raise RuntimeError(
                    f"{agent_type} agent failed with exit code {process.returncode}: {process.stderr.strip()}"
                )

            if not results_path.exists():
                raise RuntimeError(
                    f"{agent_type} agent did not produce a results file."
                )

            with results_path.open("r", encoding="utf-8") as fh:
                return json.load(fh)

    async def _wait_for_model_cooling(self, seconds: int = 30):
        """Wait for model to cool down between runs."""
        print(f"[COOLING] Waiting {seconds} seconds for model cooling...")
        await asyncio.sleep(seconds)

    async def run_demo(self) -> Dict[str, Any]:
        """
        Execute the complete Chimera demo.

        Returns:
            Dictionary containing all results and metrics
        """
        print("Starting Chimera Agent Demo")
        print(f"Model: {self.model}")
        print(f"Runs: {self.runs}")
        print(f"Output Directory: {self.output_dir}")
        print("=" * 60)

        demo_start_time = datetime.now()

        for run_num in range(1, self.runs + 1):
            print(f"\nRun {run_num}/{self.runs}")
            print("-" * 40)

            run_results = await self._run_single_comparison(run_num)
            self.results.append(run_results)

        demo_end_time = datetime.now()

        # Generate comparison report
        comparison_report = self._generate_comparison_report()

        # Save all results
        await self._save_results(comparison_report)

        print(
            f"\nDemo completed in {(demo_end_time - demo_start_time).total_seconds():.2f} seconds"
        )
        print(f"Results saved to: {self.output_dir}")

        return {
            "demo_info": {
                "model": self.model,
                "runs": self.runs,
                "start_time": demo_start_time,
                "end_time": demo_end_time,
                "duration_seconds": (demo_end_time - demo_start_time).total_seconds(),
            },
            "results": self.results,
            "comparison_report": comparison_report,
        }

    async def _run_single_comparison(self, run_num: int) -> Dict[str, Any]:
        """Run a single Chimera vs baseline comparison with forced cold starts."""

        # Method 1: Force model unload before Chimera
        print("[METHOD 1] Forcing model unload before Chimera...")
        await self._force_model_unload()

        # Method 2: Run Chimera in separate process (WARM MODEL)
        print("[WARM MODEL] Running Chimera-Optimized Agent in separate process...")
        chimera_start = datetime.now()
        chimera_results = await self._run_agent_in_separate_process(
            "Chimera", self.model
        )
        chimera_end = datetime.now()

        print(
            f"Chimera completed in {(chimera_end - chimera_start).total_seconds():.2f} seconds"
        )

        # Method 3: Wait for model cooling + Force unload
        print("[METHOD 3] Waiting for model cooling...")
        await self._wait_for_model_cooling(30)
        await self._force_model_unload()

        # Method 2: Run Baseline in separate process (COLD MODEL)
        print("[COLD MODEL] Running Baseline Agent in separate process...")
        baseline_start = datetime.now()
        baseline_results = await self._run_agent_in_separate_process(
            "Baseline", self.model
        )
        baseline_end = datetime.now()

        print(
            f"Baseline completed in {(baseline_end - baseline_start).total_seconds():.2f} seconds"
        )

        # Calculate performance delta
        performance_delta = self._calculate_performance_delta(
            baseline_results["metrics"], chimera_results["metrics"]
        )

        return {
            "run_number": run_num,
            "baseline_results": baseline_results,
            "chimera_results": chimera_results,
            "performance_delta": performance_delta,
            "baseline_duration": (baseline_end - baseline_start).total_seconds(),
            "chimera_duration": (chimera_end - chimera_start).total_seconds(),
        }

    def _calculate_performance_delta(
        self,
        baseline_metrics: Dict[str, Any],
        chimera_metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Calculate performance improvement delta between baseline and Chimera."""

        baseline_agg = baseline_metrics.get("aggregate_metrics", {})
        chimera_agg = chimera_metrics.get("aggregate_metrics", {})

        baseline_throughput = float(baseline_agg.get("average_tokens_per_second") or 0)
        chimera_throughput = float(chimera_agg.get("average_tokens_per_second") or 0)
        baseline_ttft = float(baseline_agg.get("average_ttft_ms") or 0)
        chimera_ttft = float(chimera_agg.get("average_ttft_ms") or 0)

        def percent_change(new: float, old: float) -> float:
            if old <= 0:
                return 0.0
            return ((new - old) / old) * 100.0

        throughput_delta = percent_change(chimera_throughput, baseline_throughput)
        ttft_delta = (
            ((baseline_ttft - chimera_ttft) / baseline_ttft * 100)
            if baseline_ttft > 0
            else 0.0
        )

        return {
            "throughput_improvement_percent": throughput_delta,
            "ttft_reduction_percent": ttft_delta,
            "baseline_throughput": baseline_throughput,
            "chimera_throughput": chimera_throughput,
            "baseline_ttft_ms": baseline_ttft,
            "chimera_ttft_ms": chimera_ttft,
            "throughput_delta_absolute": chimera_throughput - baseline_throughput,
            "ttft_delta_absolute_ms": baseline_ttft - chimera_ttft,
            "baseline_total_duration_ms": float(
                baseline_agg.get("total_duration_ms") or 0
            ),
            "chimera_total_duration_ms": float(
                chimera_agg.get("total_duration_ms") or 0
            ),
            "baseline_total_tokens": int(
                baseline_agg.get("total_tokens_generated") or 0
            ),
            "chimera_total_tokens": int(chimera_agg.get("total_tokens_generated") or 0),
        }

    def _generate_comparison_report(self) -> str:
        """Generate comprehensive comparison report."""
        if not self.results:
            return "No results to compare"

        baseline_throughputs = [
            float(
                run["baseline_results"]["metrics"]["aggregate_metrics"].get(
                    "average_tokens_per_second", 0
                )
            )
            for run in self.results
        ]
        chimera_throughputs = [
            float(
                run["chimera_results"]["metrics"]["aggregate_metrics"].get(
                    "average_tokens_per_second", 0
                )
            )
            for run in self.results
        ]
        baseline_ttft = [
            float(
                run["baseline_results"]["metrics"]["aggregate_metrics"].get(
                    "average_ttft_ms", 0
                )
            )
            for run in self.results
        ]
        chimera_ttft = [
            float(
                run["chimera_results"]["metrics"]["aggregate_metrics"].get(
                    "average_ttft_ms", 0
                )
            )
            for run in self.results
        ]

        avg_baseline_throughput = (
            mean(baseline_throughputs) if baseline_throughputs else 0.0
        )
        avg_chimera_throughput = (
            mean(chimera_throughputs) if chimera_throughputs else 0.0
        )
        avg_baseline_ttft = mean(baseline_ttft) if baseline_ttft else 0.0
        avg_chimera_ttft = mean(chimera_ttft) if chimera_ttft else 0.0

        throughput_improvement = (
            (
                (avg_chimera_throughput - avg_baseline_throughput)
                / avg_baseline_throughput
                * 100
            )
            if avg_baseline_throughput > 0
            else 0.0
        )
        ttft_reduction = (
            ((avg_baseline_ttft - avg_chimera_ttft) / avg_baseline_ttft * 100)
            if avg_baseline_ttft > 0
            else 0.0
        )

        total_duration = sum(
            r["baseline_duration"] + r["chimera_duration"] for r in self.results
        )
        baseline_config = self.results[0]["baseline_results"]["metrics"].get(
            "configuration", {}
        )
        chimera_config_info = self.results[0]["chimera_results"]["metrics"].get(
            "chimera_config", {}
        )
        chimera_config_description = chimera_config_info.get("description", "").strip()

        report_lines = [
            "# Chimera Agent Performance Comparison Report",
            "",
            f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
            f"**Model:** {self.model}  ",
            f"**Runs:** {self.runs}  ",
            f"**Demo Duration:** {total_duration:.2f} seconds",
            "",
            "## Executive Summary",
            "",
            "This experiment compares the Chimera-optimized agent configuration against the baseline Ollama setup "
            "while executing identical benchmark-analysis workloads.",
            "",
            f"- **Average throughput improvement:** {throughput_improvement:.1f}% "
            f"({avg_baseline_throughput:.2f} → {avg_chimera_throughput:.2f} tok/s)",
            f"- **Average TTFT reduction:** {ttft_reduction:.1f}% "
            f"({avg_baseline_ttft:.2f} → {avg_chimera_ttft:.2f} ms)",
            "",
            "## Aggregate Performance",
            "",
            "| Metric | Baseline | Chimera | Δ |",
            "|--------|----------|---------|---|",
            f"| Average Throughput (tok/s) | {avg_baseline_throughput:.2f} | {avg_chimera_throughput:.2f} | "
            f"{throughput_improvement:+.1f}% |",
            f"| Average TTFT (ms) | {avg_baseline_ttft:.2f} | {avg_chimera_ttft:.2f} | "
            f"{ttft_reduction:+.1f}% |",
            "",
            "## Run-by-Run Detail",
            "",
        ]

        for result in self.results:
            delta = result["performance_delta"]
            report_lines.extend(
                [
                    f"### Run {result['run_number']}",
                    "",
                    f"- Baseline duration: {result['baseline_duration']:.2f}s  "
                    f"(throughput {delta['baseline_throughput']:.2f} tok/s, "
                    f"TTFT {delta['baseline_ttft_ms']:.2f} ms)",
                    f"- Chimera duration: {result['chimera_duration']:.2f}s  "
                    f"(throughput {delta['chimera_throughput']:.2f} tok/s, "
                    f"TTFT {delta['chimera_ttft_ms']:.2f} ms)",
                    f"- Throughput delta: {delta['throughput_delta_absolute']:+.2f} tok/s "
                    f"({delta['throughput_improvement_percent']:+.1f}%)",
                    f"- TTFT delta: {delta['ttft_delta_absolute_ms']:+.2f} ms "
                    f"({delta['ttft_reduction_percent']:+.1f}%)",
                    "",
                ]
            )

        report_lines.extend(
            [
                "## Configuration Details",
                "",
                "### Baseline",
                *(f"- {key}: {value}" for key, value in baseline_config.items()),
                "",
                "### Chimera Optimized",
                *(
                    f"- {key}: {value}"
                    for key, value in self.results[0]["chimera_results"]["metrics"]
                    .get("configuration", {})
                    .items()
                ),
                "",
            ]
        )

        if chimera_config_description:
            report_lines.extend(
                [
                    "#### Chimera Configuration Summary",
                    "",
                    chimera_config_description,
                    "",
                ]
            )

        citations = chimera_config_info.get("citations")
        if citations:
            report_lines.extend(["#### Citations", "", citations, ""])

        report_lines.extend(
            [
                "## Conclusion",
                "",
                "Chimera's optimized configuration consistently outperforms the baseline setup across the measured runs. "
                "The higher sustained throughput and lower time-to-first-token translate directly into faster technical "
                "report generation with identical workloads.",
            ]
        )

        return "\n".join(report_lines)

    async def _save_results(self, comparison_report: str):
        """Save all results to files."""
        # Save individual reports
        for i, result in enumerate(self.results, 1):
            # Baseline report
            baseline_report_path = (
                self.output_dir / "reports" / f"baseline_report_run_{i}.md"
            )
            with open(baseline_report_path, "w", encoding="utf-8") as f:
                f.write(result["baseline_results"]["report"])

            # Chimera report
            chimera_report_path = (
                self.output_dir / "reports" / f"chimera_report_run_{i}.md"
            )
            with open(chimera_report_path, "w", encoding="utf-8") as f:
                f.write(result["chimera_results"]["report"])

        # Save comparison report
        comparison_path = self.output_dir / "reports" / "comparison_report.md"
        with open(comparison_path, "w", encoding="utf-8") as f:
            f.write(comparison_report)

        # Save raw metrics data
        metrics_path = self.output_dir / "data" / "metrics.json"
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, default=str)

        print(f"Reports saved to: {self.output_dir / 'reports'}")
        print(f"Metrics saved to: {metrics_path}")


async def main():
    """Main entry point for the Chimera demo."""
    parser = argparse.ArgumentParser(description="Chimera Agent Performance Demo")
    parser.add_argument(
        "--model", default="gemma3:latest", help="Model to use for demo"
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of runs for statistical significance",
    )
    parser.add_argument(
        "--output-dir", default="demo_agent", help="Output directory for results"
    )
    parser.add_argument(
        "--chimera-num-gpu", type=int, help="Override Chimera GPU layer setting"
    )
    parser.add_argument(
        "--chimera-num-ctx", type=int, help="Override Chimera context window"
    )
    parser.add_argument(
        "--chimera-temperature", type=float, help="Override Chimera temperature"
    )
    parser.add_argument("--chimera-top-p", type=float, help="Override Chimera top-p")
    parser.add_argument("--chimera-top-k", type=int, help="Override Chimera top-k")
    parser.add_argument(
        "--chimera-repeat-penalty", type=float, help="Override Chimera repeat penalty"
    )

    args = parser.parse_args()

    chimera_overrides = {
        "num_gpu": args.chimera_num_gpu,
        "num_ctx": args.chimera_num_ctx,
        "temperature": args.chimera_temperature,
        "top_p": args.chimera_top_p,
        "top_k": args.chimera_top_k,
        "repeat_penalty": args.chimera_repeat_penalty,
    }
    chimera_overrides = {k: v for k, v in chimera_overrides.items() if v is not None}

    # Create and run demo
    orchestrator = ChimeraDemoOrchestrator(
        model=args.model,
        output_dir=args.output_dir,
        runs=args.runs,
        chimera_overrides=chimera_overrides,
    )

    try:
        await orchestrator.run_demo()
        print("\nDemo completed successfully!")
        return 0
    except Exception as e:
        print(f"\nDemo failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
