"""
TR117 Phase 3: Flow Dynamics (Tortoise & Hare)

This script implements an agent with an artificial "Token Bucket" throttler
to limit generation speed (e.g., to 60 tok/s) to test if slower models
improve Python event loop efficiency.

Located in experiments/TR117/scripts/ to avoid modifying core code.
"""

import asyncio
import time
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import argparse
import httpx

# Add src/python to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(PROJECT_ROOT / "src" / "python"))

try:
    from banterhearts.demo_multiagent.run_multiagent_demo import (
        ResourceCoordinator,
        build_prompts,
        extract_metrics,
    )
except ImportError:
    print(f"Could not import banterhearts. Added path: {PROJECT_ROOT / 'src' / 'python'}")
    raise

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("throttler")

class TokenBucket:
    def __init__(self, rate_tokens_per_sec: float):
        self.rate = rate_tokens_per_sec
        self.tokens = 0.0
        self.last_update = time.perf_counter()
        self.lock = asyncio.Lock()
        
    async def acquire(self, amount: int = 1):
        if self.rate <= 0: return # No limit
        
        async with self.lock:
            while True:
                now = time.perf_counter()
                elapsed = now - self.last_update
                self.last_update = now
                
                # Refill
                self.tokens += elapsed * self.rate
                # Cap bucket at 1 second worth of burst (optional, keeping it tight for smoothing)
                if self.tokens > self.rate:
                    self.tokens = self.rate
                
                if self.tokens >= amount:
                    self.tokens -= amount
                    return
                
                # Wait for enough tokens
                missing = amount - self.tokens
                wait_time = missing / self.rate
                await asyncio.sleep(wait_time)

async def throttled_call_ollama(
    client: httpx.AsyncClient,
    base_url: str,
    model: str,
    prompt: str,
    options: Dict[str, Any],
    throttle_rate: float,
) -> Dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": options,
    }
    
    bucket = TokenBucket(throttle_rate)
    full_response = ""
    eval_count = 0
    start_time = time.perf_counter()
    first_token_time = None
    final_data = {}
    
    # We must stream to throttle token-by-token (or chunk-by-chunk)
    async with client.stream("POST", f"{base_url}/api/generate", json=payload, timeout=120.0) as response:
        response.raise_for_status()
        async for chunk in response.aiter_bytes():
            # Throttle based on estimated token count or just chunk count?
            # Chunks are bytes. We don't know exact token count without tokenizing.
            # Approximation: 1 token ~= 4 bytes. 
            # Or better: Just throttle the *read* loop. 
            # If we want 60 tok/s, and we get a chunk, we parse it to find token count if possible.
            # Ollama sends JSON objects. Each "response" field is a token (usually).
            
            # Let's parse first, then throttle.
            try:
                text_chunk = chunk.decode("utf-8")
                token_count_in_chunk = 0
                for line in text_chunk.splitlines():
                    if not line: continue
                    data = json.loads(line)
                    
                    if not first_token_time and not data.get("done"):
                        first_token_time = time.perf_counter()
                        
                    if "response" in data:
                        full_response += data["response"]
                        token_count_in_chunk += 1
                        eval_count += 1
                    
                    if data.get("done"):
                        final_data = data
                
                # Throttle now
                if throttle_rate > 0 and token_count_in_chunk > 0:
                    await bucket.acquire(token_count_in_chunk)
                    
            except Exception as e:
                logger.error(f"Parse error: {e}")
                continue

    total_time = time.perf_counter() - start_time
    ttft = (first_token_time - start_time) * 1000 if first_token_time else 0
    
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

async def run_throttled_pair(
    client: httpx.AsyncClient,
    scenario: str,
    model: str,
    collector_url: str,
    insight_url: str,
    chimera_opts: Dict[str, Any],
    chimera2_opts: Dict[str, Any],
    coordinator: ResourceCoordinator,
    throttle_rate: float,
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
            # Apply throttling ONLY to the "insight" agent (Agent B) or both?
            # To test "Slower Models", we should throttle both if we want to simulate a slower model architecture.
            # Or just the one being measured. 
            # Let's throttle BOTH to simulate "Using Llama instead of Gemma".
            
            result = await throttled_call_ollama(
                client, base_url, model, prompt, opts, throttle_rate
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
        "throttle_rate": throttle_rate
    }

def parse_args():
    parser = argparse.ArgumentParser(description="TR117 Phase 3 Throttled Agent")
    parser.add_argument("--model", default="gemma3:latest")
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--scenario", default="chimera_homo")
    parser.add_argument("--output-dir", default="experiments/TR117/results/phase3")
    parser.add_argument("--collector-ollama-url", default="http://localhost:11434")
    parser.add_argument("--insight-ollama-url", default="http://localhost:11435")
    
    # TR117 Phase 3 specific
    parser.add_argument("--throttle-rate", type=float, default=0.0, help="Max tokens/sec (0 = unlimited)")
    
    # Chimera opts
    parser.add_argument("--chimera-num-gpu", type=int, default=80)
    parser.add_argument("--chimera-num-ctx", type=int, default=512)
    parser.add_argument("--chimera-temperature", type=float, default=1.0)
    
    return parser.parse_args()

async def main():
    args = parse_args()
    output_root = Path(args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    
    coordinator = ResourceCoordinator(permits=2)
    
    chimera_opts = {
        "num_gpu": args.chimera_num_gpu,
        "num_ctx": args.chimera_num_ctx,
        "temperature": args.chimera_temperature,
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        runs = []
        for i in range(1, args.runs + 1):
            logger.info(f"Starting Run {i} (Throttle: {args.throttle_rate} tok/s)...")
            run = await run_throttled_pair(
                client,
                args.scenario,
                args.model,
                args.collector_ollama_url,
                args.insight_ollama_url,
                chimera_opts,
                chimera_opts,
                coordinator,
                args.throttle_rate,
            )
            run["run_number"] = i
            runs.append(run)
            logger.info(f"Run {i} Complete. Efficiency: {run['efficiency_percent']:.2f}%")
            
            (output_root / f"run_{i}.json").write_text(json.dumps(run, indent=2), encoding="utf-8")

    avg_eff = sum(r["efficiency_percent"] for r in runs) / len(runs)
    logger.info(f"Average Efficiency: {avg_eff:.2f}%")

if __name__ == "__main__":
    asyncio.run(main())
