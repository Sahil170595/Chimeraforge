"""
CLI entrypoint for running Python multi-agent benchmarks.

Supports three scenarios:
- baseline_vs_chimera: baseline agent vs chimera-optimized agent
- chimera_hetero: two chimera agents with distinct overrides
- chimera_homo: two chimera agents sharing the same overrides
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, Tuple

import httpx

from .coordinator import ResourceCoordinator
from .orchestrator import aggregate_runs, build_prompts


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for the multi-agent benchmark demo.

    Returns:
        argparse.Namespace: Parsed command-line arguments including:
            - model: Ollama model to use (default: "gemma3:latest")
            - runs: Number of benchmark repetitions (default: 3)
            - scenario: Execution scenario type
            - output-dir: Output directory for results
            - collector-ollama-url: Ollama URL for collector agent
            - insight-ollama-url: Ollama URL for insight agent
            - chimera-*: Override options for first Chimera agent
            - chimera2-*: Override options for second Chimera agent (hetero scenario)
    """
    parser = argparse.ArgumentParser(description="Python multi-agent benchmark demo")
    parser.add_argument("--model", default="gemma3:latest", help="Model to use")
    parser.add_argument("--runs", type=int, default=3, help="Number of repetitions")
    parser.add_argument(
        "--scenario",
        choices=["baseline_vs_chimera", "chimera_hetero", "chimera_homo"],
        default="baseline_vs_chimera",
        help="Execution scenario",
    )
    parser.add_argument(
        "--output-dir",
        default="experiments/TR116/results/multi/python",
        help="Output root",
    )
    parser.add_argument(
        "--collector-ollama-url",
        default="http://localhost:11434",
        help="Ollama base URL for agent A",
    )
    parser.add_argument(
        "--insight-ollama-url",
        default="http://localhost:11435",
        help="Ollama base URL for agent B",
    )
    # Chimera agent 1 overrides
    parser.add_argument("--chimera-num-gpu", type=int)
    parser.add_argument("--chimera-num-ctx", type=int)
    parser.add_argument("--chimera-temperature", type=float)
    parser.add_argument("--chimera-top-p", type=float)
    parser.add_argument("--chimera-top-k", type=int)
    parser.add_argument("--chimera-repeat-penalty", type=float)
    # Chimera agent 2 overrides (hetero)
    parser.add_argument("--chimera2-num-gpu", type=int)
    parser.add_argument("--chimera2-num-ctx", type=int)
    parser.add_argument("--chimera2-temperature", type=float)
    parser.add_argument("--chimera2-top-p", type=float)
    parser.add_argument("--chimera2-top-k", type=int)
    parser.add_argument("--chimera2-repeat-penalty", type=float)
    return parser.parse_args()


def build_options(prefix: str, args: argparse.Namespace) -> Dict[str, Any]:
    """
    Build a dictionary of Ollama options from command-line arguments.

    Extracts options with the given prefix from args and filters out None values.
    Used to construct Chimera configuration overrides.

    Args:
        prefix: Prefix to match argument names (e.g., "chimera_" or "chimera2_")
        args: Parsed command-line arguments

    Returns:
        Dict[str, Any]: Dictionary of Ollama options with None values filtered out.
            Keys include: num_gpu, num_ctx, temperature, top_p, top_k, repeat_penalty
    """
    options = {
        "num_gpu": getattr(args, f"{prefix}num_gpu"),
        "num_ctx": getattr(args, f"{prefix}num_ctx"),
        "temperature": getattr(args, f"{prefix}temperature"),
        "top_p": getattr(args, f"{prefix}top_p"),
        "top_k": getattr(args, f"{prefix}top_k"),
        "repeat_penalty": getattr(args, f"{prefix}repeat_penalty"),
    }
    return {k: v for k, v in options.items() if v is not None}


async def call_ollama(
    client: httpx.AsyncClient,
    base_url: str,
    model: str,
    prompt: str,
    options: Dict[str, Any],
) -> Tuple[Dict[str, Any], str]:
    """
    Make an asynchronous call to the Ollama API to generate text.

    Args:
        client: HTTP client for making requests
        base_url: Base URL of the Ollama service (e.g., "http://localhost:11434")
        model: Model name to use for generation
        prompt: Text prompt to send to the model
        options: Dictionary of Ollama generation options (num_gpu, num_ctx, etc.)

    Returns:
        Tuple[Dict[str, Any], str]: A tuple containing:
            - Full response dictionary from Ollama API (includes metrics)
            - Generated text response string

    Raises:
        httpx.HTTPStatusError: If the API request fails
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": options,
    }
    resp = await client.post(f"{base_url}/api/generate", json=payload, timeout=120.0)
    resp.raise_for_status()
    data = resp.json()
    return data, data.get("response", "")


def extract_metrics(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract performance metrics from an Ollama API response.

    Computes derived metrics including throughput and time-to-first-token (TTFT)
    from raw Ollama response data.

    Args:
        result: Raw response dictionary from Ollama API containing:
            - eval_count: Number of tokens generated
            - eval_duration: Generation duration in nanoseconds
            - prompt_eval_duration: Prompt processing duration in nanoseconds

    Returns:
        Dict[str, Any]: Dictionary containing extracted metrics:
            - tokens_generated: Number of tokens generated
            - throughput_tokens_per_sec: Tokens per second throughput
            - ttft_ms: Time-to-first-token in milliseconds
            - total_duration_ms: Total request duration in milliseconds
    """
    eval_count = result.get("eval_count") or 0
    eval_dur_ns = result.get("eval_duration") or 0
    prompt_dur_ns = result.get("prompt_eval_duration") or 0
    total_ns = eval_dur_ns + prompt_dur_ns
    throughput = (
        eval_count / (eval_dur_ns / 1e9) if eval_dur_ns and eval_dur_ns > 0 else 0.0
    )
    ttft_ms = prompt_dur_ns / 1e6 if prompt_dur_ns else 0.0
    total_ms = total_ns / 1e6 if total_ns else 0.0
    return {
        "tokens_generated": eval_count,
        "throughput_tokens_per_sec": throughput,
        "ttft_ms": ttft_ms,
        "total_duration_ms": total_ms,
    }


async def run_pair(
    client: httpx.AsyncClient,
    scenario: str,
    model: str,
    collector_url: str,
    insight_url: str,
    chimera_opts: Dict[str, Any],
    chimera2_opts: Dict[str, Any],
    coordinator: ResourceCoordinator,
) -> Dict[str, Any]:
    """
    Execute a single concurrent pair of agents and collect performance metrics.

    Runs two agents (collector and insight) concurrently using asyncio.gather,
    then calculates concurrency metrics including speedup and efficiency.

    Args:
        client: HTTP client for making Ollama requests
        scenario: Execution scenario ("baseline_vs_chimera", "chimera_hetero", "chimera_homo")
        model: Model name to use for both agents
        collector_url: Ollama base URL for the collector agent
        insight_url: Ollama base URL for the insight agent
        chimera_opts: Configuration options for the first Chimera agent
        chimera2_opts: Configuration options for the second Chimera agent (hetero scenario)
        coordinator: Resource coordinator for managing concurrent access

    Returns:
        Dict[str, Any]: Dictionary containing:
            - run_number: Will be set by caller
            - scenario: Execution scenario used
            - collector: Results from collector agent (id, base_url, options, response, metrics)
            - insight: Results from insight agent (id, base_url, options, response, metrics)
            - concurrent_wall_time_ms: Wall-clock time for concurrent execution
            - sequential_estimate_ms: Estimated time if run sequentially
            - concurrency_speedup: Speedup factor (sequential / concurrent)
            - efficiency_percent: Efficiency percentage (speedup / num_agents * 100)
            - throughput_delta: Difference in throughput between agents
            - ttft_delta_ms: Difference in TTFT between agents
    """
    prompts = build_prompts()

    def options_for(agent_role: str) -> Dict[str, Any]:
        if scenario == "baseline_vs_chimera":
            return {} if agent_role == "collector" else chimera_opts
        if scenario == "chimera_homo":
            return chimera_opts
        if scenario == "chimera_hetero":
            return chimera_opts if agent_role == "collector" else chimera2_opts
        return {}

    async def run_agent(agent_id: str, base_url: str, prompt: str, opts: Dict[str, Any]):
        """
        Run a single agent with resource coordination.

        Args:
            agent_id: Identifier for the agent ("collector" or "insight")
            base_url: Ollama base URL for this agent
            prompt: Prompt to send to the agent
            opts: Ollama configuration options

        Returns:
            Dict containing agent results with id, base_url, options, response, and metrics
        """
        async with coordinator:
            start = time.perf_counter()
            result, response = await call_ollama(client, base_url, model, prompt, opts)
            end = time.perf_counter()
            metrics = extract_metrics(result)
            metrics["wall_clock_ms"] = (end - start) * 1000
            return {
                "id": agent_id,
                "base_url": base_url,
                "options": opts,
                "response": response,
                "metrics": metrics,
            }

    start = time.perf_counter()
    a_task = asyncio.create_task(
        run_agent("collector", collector_url, prompts["collector"], options_for("collector"))
    )
    b_task = asyncio.create_task(
        run_agent("insight", insight_url, prompts["insight"], options_for("insight"))
    )
    agent_a, agent_b = await asyncio.gather(a_task, b_task)
    end = time.perf_counter()

    wall_ms = (end - start) * 1000
    seq_ms = agent_a["metrics"]["total_duration_ms"] + agent_b["metrics"]["total_duration_ms"]
    speedup = seq_ms / wall_ms if wall_ms else 0.0
    efficiency = (speedup / 2) * 100
    throughput_delta = agent_b["metrics"]["throughput_tokens_per_sec"] - agent_a["metrics"]["throughput_tokens_per_sec"]
    ttft_delta = agent_b["metrics"]["ttft_ms"] - agent_a["metrics"]["ttft_ms"]

    return {
        "run_number": None,  # filled by caller
        "scenario": scenario,
        "collector": agent_a,
        "insight": agent_b,
        "concurrent_wall_time_ms": wall_ms,
        "sequential_estimate_ms": seq_ms,
        "concurrency_speedup": speedup,
        "efficiency_percent": efficiency,
        "throughput_delta": throughput_delta,
        "ttft_delta_ms": ttft_delta,
    }


async def main():
    """
    Main entry point for the multi-agent benchmark demo.

    Orchestrates multiple benchmark runs, saves results to disk, and generates
    summary reports. Creates output directories organized by model and scenario.
    """
    args = parse_args()
    output_root = Path(args.output_dir) / args.model.replace(":", "_")
    scenario_suffix = args.scenario.replace("_", "-")
    if args.scenario == "baseline_vs_chimera":
        output_root = output_root / f"{scenario_suffix}_gpu80_ctx512_temp10"
    else:
        output_root = output_root / f"{scenario_suffix}_gpu80_ctx512_temp10"
    output_root.mkdir(parents=True, exist_ok=True)

    chimera_opts = build_options("chimera_", args)
    chimera2_opts = build_options("chimera2_", args)
    coordinator = ResourceCoordinator(permits=2)

    async with httpx.AsyncClient(timeout=120.0) as client:
        runs = []
        for i in range(1, args.runs + 1):
            run = await run_pair(
                client,
                args.scenario,
                args.model,
                args.collector_ollama_url,
                args.insight_ollama_url,
                chimera_opts,
                chimera2_opts,
                coordinator,
            )
            run["run_number"] = i
            run_dir = output_root / f"run_{i}"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "metrics.json").write_text(json.dumps(run, indent=2), encoding="utf-8")

            # simple reports
            (run_dir / "collector_report.md").write_text(run["collector"]["response"], encoding="utf-8")
            (run_dir / "insight_report.md").write_text(run["insight"]["response"], encoding="utf-8")
            (run_dir / "combined_report.md").write_text(
                f"# Combined Summary\n\nSpeedup: {run['concurrency_speedup']:.3f}x\nEfficiency: {run['efficiency_percent']:.2f}%",
                encoding="utf-8",
            )
            runs.append(run)

    summary = aggregate_runs(runs)
    (output_root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output_root / "summary.md").write_text(
        f"# Summary\n\nSpeedup (avg): {summary['aggregate']['average_concurrency_speedup']:.3f}x\n"
        f"Efficiency (avg): {summary['aggregate']['average_efficiency']:.2f}%\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    asyncio.run(main())
