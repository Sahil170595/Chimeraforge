"""
TR117 One-Shot Orchestrator

Runs the key TR117 pathways sequentially with defaults tuned to the 25-run plan:
- MRI (loop lag + chunk metrics) for Gemma with two buffer settings (5 runs each) -> 10 runs
- Hardware (dmon) for Gemma and Qwen (5 runs each) if a command template is provided -> 10 runs
- Throttle A/B (60 tok/s) for Gemma (5 runs) -> 5 runs

Total: 25 runs when defaults are used and a hardware command template is supplied.
"""

import argparse
import subprocess
from pathlib import Path
import sys
import re

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def run_cmd(cmd: list[str]) -> int:
    print(f"==> Running: {' '.join(cmd)}")
    return subprocess.call(cmd)


def slugify(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", model).strip("_")


def main():
    parser = argparse.ArgumentParser(description="Run TR117 suite in one shot")
    parser.add_argument("--mri-models", nargs="+", default=["gemma3:latest"], help="Models for MRI runs")
    parser.add_argument("--hardware-models", nargs="+", default=["gemma3:latest", "qwen2.5:7b"], help="Models for hardware (dmon) runs")
    parser.add_argument("--throttle-models", nargs="+", default=["gemma3:latest"], help="Models for throttle tests")
    parser.add_argument("--runs", type=int, default=5, help="Runs per config")
    parser.add_argument("--buffers", nargs="+", type=int, default=[-1, 8192], help="Read buffer sizes; use -1 for default")
    parser.add_argument("--throttle-rates", nargs="+", type=float, default=[60.0], help="Token/sec caps for throttle tests")
    parser.add_argument("--scenario", default="chimera_homo", help="Scenario passed to MRI/throttle scripts")
    parser.add_argument("--collector-url", default="http://localhost:11434")
    parser.add_argument("--insight-url", default="http://localhost:11435")
    parser.add_argument("--output-root", default="experiments/TR117_multiagent/results/suite_run", help="Root output directory")
    parser.add_argument("--run-tokenizer-bench", action="store_true", help="Run tokenizer bench as part of suite")
    parser.add_argument("--allow-download-tokenizers", action="store_true", help="Allow HF downloads in tokenizer bench")
    parser.add_argument(
        "--hardware-cmd-template",
        help="Optional command template for hardware runs; include {model} and optionally {slug}. Example: \"my_rust_bench --model {model}\"",
    )
    parser.add_argument(
        "--hardware-bin",
        default=str(PROJECT_ROOT / "src" / "rust" / "demo_multiagent" / "target" / "release" / "Demo_rust_multiagent.exe"),
        help="Path to rust multi-agent binary (used if no template is provided).",
    )
    args = parser.parse_args()

    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    failures = 0
    total_runs = 0

    # MRI runs (per model, per buffer size)
    for model in args.mri_models:
        for buf in args.buffers:
            buf_label = "default" if buf == -1 else f"buf{buf}"
            out_dir = output_root / "phase1" / slugify(model) / buf_label
            cmd = [
                sys.executable,
                str(PROJECT_ROOT / "experiments" / "TR117" / "scripts" / "profiler_agent.py"),
                "--model",
                model,
                "--runs",
                str(args.runs),
                "--scenario",
                args.scenario,
                "--collector-ollama-url",
                args.collector_url,
                "--insight-ollama-url",
                args.insight_url,
                "--output-dir",
                str(out_dir),
            ]
            if buf != -1:
                cmd.extend(["--read-buffer-size", str(buf)])
            failures += run_cmd(cmd)
            total_runs += args.runs

    # Throttle runs (per model, per throttle rate)
    for model in args.throttle_models:
        for rate in args.throttle_rates:
            out_dir = output_root / "phase3" / slugify(model) / f"{int(rate)}tps"
            cmd = [
                sys.executable,
                str(PROJECT_ROOT / "experiments" / "TR117" / "scripts" / "throttled_agent.py"),
                "--model",
                model,
                "--runs",
                str(args.runs),
                "--scenario",
                args.scenario,
                "--collector-ollama-url",
                args.collector_url,
                "--insight-ollama-url",
                args.insight_url,
                "--throttle-rate",
                str(rate),
                "--output-dir",
                str(out_dir),
            ]
            failures += run_cmd(cmd)
            total_runs += args.runs

    # Hardware runs via dmon (optional; uses template if provided, otherwise rust binary)
    dmon_script = PROJECT_ROOT / "experiments" / "TR117" / "scripts" / "dmon_wrapper.py"
    for model in args.hardware_models:
        slug = slugify(model)
        out_dir = output_root / "phase2" / slug
        if args.hardware_cmd_template:
            filled = args.hardware_cmd_template.format(model=model, slug=slug)
            cmd_parts = filled.split()
        else:
            cmd_parts = [
                args.hardware_bin,
                "--model",
                model,
                "--runs",
                str(args.runs),
                "--scenario",
                "chimera-homo",
                "--collector-ollama-url",
                args.collector_url,
                "--insight-ollama-url",
                args.insight_url,
                "--chimera-num-gpu",
                "80",
                "--chimera-num-ctx",
                "512",
                "--chimera-temperature",
                "1.0",
                "--output-dir",
                str(out_dir / "agent_output"),
            ]
        cmd = [sys.executable, str(dmon_script), "--output-dir", str(out_dir), "--"] + cmd_parts
        failures += run_cmd(cmd)
        total_runs += args.runs

    # Tokenizer bench (optional)
    if args.run_tokenizer_bench:
        out_dir = output_root / "phase2" / "tokenizers"
        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "experiments" / "TR117" / "scripts" / "bench_tokenizer.py"),
            "--output-dir",
            str(out_dir),
        ]
        if args.allow_download_tokenizers:
            cmd.append("--allow-download")
        failures += run_cmd(cmd)

    print(f"Planned runs executed (excluding tokenizer): {total_runs}")
    if failures:
        print(f"Suite completed with {failures} non-zero exits.")
        sys.exit(1)
    else:
        print("Suite completed successfully.")


if __name__ == "__main__":
    main()
