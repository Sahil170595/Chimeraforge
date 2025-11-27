"""
TR117 Phase 1: Python MRI (Loop Instrumentation)

This script extends the standard multi-agent runner to instrument:
1. Event Loop Lag (ms)
2. Chunk-level metrics (bytes, gap, parse time)
3. HTTPX buffer size A/B testing

Located in experiments/TR117/scripts/ to avoid modifying core code.
"""

import asyncio
import time
import json
import logging
import csv
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import argparse
import httpx

# Add src/python to sys.path to import banterhearts modules
# Assuming this script is in experiments/TR117/scripts/
# We need to go up 3 levels to get to root, then into src/python
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(PROJECT_ROOT / "src" / "python"))

try:
    from banterhearts.demo_multiagent.run_multiagent_demo import (
        build_options,
        extract_metrics,
        ResourceCoordinator,
        build_prompts,
    )
except ImportError:
    # Fallback if running from a different CWD
    print(f"Could not import banterhearts. Added path: {PROJECT_ROOT / 'src' / 'python'}")
    raise

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("profiler")

class LoopLagMonitor:
    def __init__(self, log_path: Path, interval: float = 0.1):
        self.log_path = log_path
        self.interval = interval
        self.running = False
        self.task = None
        self._csv_file = None
        self._csv_writer = None

    async def start(self):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._csv_file = open(self.log_path, "w", newline="")
        self._csv_writer = csv.writer(self._csv_file)
        self._csv_writer.writerow(["timestamp", "lag_ms"])
        self.running = True
        self.task = asyncio.create_task(self._monitor())

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        if self._csv_file:
            self._csv_file.close()

    async def _monitor(self):
        while self.running:
            start = time.perf_counter()
            await asyncio.sleep(self.interval)
            now = time.perf_counter()
            # Lag is the difference between actual sleep time and requested sleep time
            lag = (now - start) - self.interval
            lag_ms = lag * 1000
            
            if self._csv_writer:
                self._csv_writer.writerow([now, f"{lag_ms:.4f}"])
                self._csv_file.flush()
            
            if lag_ms > 10:
                # logger.warning(f"Loop Stall Detected: {lag_ms:.2f}ms")
                pass

class ChunkProfiler:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.file = open(self.log_path, "w", newline="")
        self.writer = csv.writer(self.file)
        self.writer.writerow(["timestamp", "agent_id", "chunk_index", "bytes", "gap_ms", "parse_ms"])
        self.last_chunk_time = {}

    def log(self, agent_id: str, chunk_idx: int, num_bytes: int, parse_ms: float):
        now = time.perf_counter()
        last = self.last_chunk_time.get(agent_id, now)
        gap_ms = (now - last) * 1000
        self.last_chunk_time[agent_id] = now
        
        self.writer.writerow([now, agent_id, chunk_idx, num_bytes, f"{gap_ms:.4f}", f"{parse_ms:.4f}"])
        self.file.flush()

    def close(self):
        self.file.close()

async def instrumented_call_ollama(
    client: httpx.AsyncClient,
    base_url: str,
    model: str,
    prompt: str,
    options: Dict[str, Any],
    agent_id: str,
    profiler: ChunkProfiler,
) -> Dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,  # Force streaming for chunk profiling
        "options": options,
    }
    
    full_response = ""
    eval_count = 0
    start_time = time.perf_counter()
    first_token_time = None
    final_data = {}
    
    chunk_idx = 0
    
    # We manually handle the request to instrument chunk processing
    async with client.stream("POST", f"{base_url}/api/generate", json=payload, timeout=120.0) as response:
        response.raise_for_status()
        async for chunk in response.aiter_bytes():
            t0 = time.perf_counter()
            # Measure JSON parse time
            try:
                text_chunk = chunk.decode("utf-8")
                for line in text_chunk.splitlines():
                    if not line: continue
                    data = json.loads(line)
                    
                    if not first_token_time and not data.get("done"):
                        first_token_time = time.perf_counter()
                        
                    if "response" in data:
                        full_response += data["response"]
                        eval_count += 1
                    
                    if data.get("done"):
                        final_data = data
            except Exception as e:
                logger.error(f"Parse error: {e}")
                continue
                
            t1 = time.perf_counter()
            parse_ms = (t1 - t0) * 1000
            
            profiler.log(agent_id, chunk_idx, len(chunk), parse_ms)
            chunk_idx += 1

    total_time = time.perf_counter() - start_time
    ttft = (first_token_time - start_time) * 1000 if first_token_time else 0
    
    # Reconstruct a "metrics" dict similar to non-streaming
    metrics = {
        "tokens_generated": eval_count,
        "throughput_tokens_per_sec": eval_count / total_time if total_time > 0 else 0,
        "ttft_ms": ttft,
        "total_duration_ms": total_time * 1000,
        "eval_count": eval_count, 
        "eval_duration": final_data.get("eval_duration", 0),
        "prompt_eval_duration": final_data.get("prompt_eval_duration", 0),
    }
    
    return {"response": full_response, "metrics": metrics}

async def run_instrumented_pair(
    client: httpx.AsyncClient,
    scenario: str,
    model: str,
    collector_url: str,
    insight_url: str,
    chimera_opts: Dict[str, Any],
    chimera2_opts: Dict[str, Any],
    coordinator: ResourceCoordinator,
    chunk_profiler: ChunkProfiler,
) -> Dict[str, Any]:
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
        async with coordinator:
            # Use instrumented call
            result = await instrumented_call_ollama(
                client, base_url, model, prompt, opts, agent_id, chunk_profiler
            )
            return {
                "id": agent_id,
                "base_url": base_url,
                "options": opts,
                "response": result["response"],
                "metrics": result["metrics"],
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
    
    return {
        "run_number": None,
        "scenario": scenario,
        "collector": agent_a,
        "insight": agent_b,
        "concurrent_wall_time_ms": wall_ms,
        "concurrency_speedup": speedup,
        "efficiency_percent": efficiency,
    }

def parse_args():
    parser = argparse.ArgumentParser(description="TR117 Python MRI Profiler")
    
    parser.add_argument("--model", default="gemma3:latest")
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--scenario", default="chimera_homo")
    parser.add_argument("--output-dir", default="experiments/TR117/results/phase1")
    parser.add_argument("--collector-ollama-url", default="http://localhost:11434")
    parser.add_argument("--insight-ollama-url", default="http://localhost:11435")
    
    # TR117 specific
    parser.add_argument("--read-buffer-size", type=int, default=None, help="httpx read buffer size in bytes")
    
    # Chimera opts (simplified for this exp)
    parser.add_argument("--chimera-num-gpu", type=int, default=80)
    parser.add_argument("--chimera-num-ctx", type=int, default=512)
    parser.add_argument("--chimera-temperature", type=float, default=1.0)
    parser.add_argument("--chimera-top-p", type=float, default=None)
    parser.add_argument("--chimera-top-k", type=int, default=None)
    parser.add_argument("--chimera-repeat-penalty", type=float, default=None)
    
    return parser.parse_args()

async def main():
    args = parse_args()
    output_root = Path(args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    
    # Setup Loop Monitor
    loop_monitor = LoopLagMonitor(output_root / "loop_lag.csv")
    await loop_monitor.start()
    
    # Setup Chunk Profiler
    chunk_profiler = ChunkProfiler(output_root / "chunk_metrics.csv")
    
    # Coordinator
    coordinator = ResourceCoordinator(permits=2)
    
    # Chimera opts
    chimera_opts = {
        "num_gpu": args.chimera_num_gpu,
        "num_ctx": args.chimera_num_ctx,
        "temperature": args.chimera_temperature,
        "top_p": args.chimera_top_p,
        "top_k": args.chimera_top_k,
        "repeat_penalty": args.chimera_repeat_penalty,
    }
    # Filter None
    chimera_opts = {k: v for k, v in chimera_opts.items() if v is not None}
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        runs = []
        for i in range(1, args.runs + 1):
            logger.info(f"Starting Run {i}...")
            run = await run_instrumented_pair(
                client,
                args.scenario,
                args.model,
                args.collector_ollama_url,
                args.insight_ollama_url,
                chimera_opts,
                chimera_opts, # homo for now
                coordinator,
                chunk_profiler,
            )
            run["run_number"] = i
            runs.append(run)
            logger.info(f"Run {i} Complete. Efficiency: {run['efficiency_percent']:.2f}%")
            
            # Dump run metrics
            (output_root / f"run_{i}.json").write_text(json.dumps(run, indent=2), encoding="utf-8")

    await loop_monitor.stop()
    chunk_profiler.close()
    
    # Aggregate results for quick view
    avg_eff = sum(r["efficiency_percent"] for r in runs) / len(runs)
    logger.info(f"Average Efficiency: {avg_eff:.2f}%")

if __name__ == "__main__":
    asyncio.run(main())
