"""TR129 core: N-agent closed-loop async executor.

Each agent runs a closed loop: send request → wait for response → optional
think time → send next request.  Maximum concurrency = N (not open-loop).

Key design:
- in_flight tracked via mutable [0] list (safe in single-threaded asyncio)
- Each request uses its own httpx.AsyncClient to avoid connection pool contention
- Ollama timing extracted in nanoseconds, converted to ms
- TWO throughput metrics:
    * gpu_tokens_per_s = completion_tokens / eval_ms   (GPU-side, constant across N)
    * effective_tps    = completion_tokens / wall_ms    (user-perceived, degrades with N)
  The distinction matters: eval_ms measures GPU decode time only (no queue wait),
  so gpu_tokens_per_s stays flat as N grows.  effective_tps captures the REAL
  throughput degradation including contention.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import time

import httpx

log = logging.getLogger("tr129.agent_executor")


@dataclass
class AgentConfig:
    """Configuration for a single agent in the N-agent test."""

    agent_id: int
    model: str  # Ollama tag (e.g., "llama3.2:1b")
    n_requests: int
    prompts: list[str]
    think_time_ms: float = 0.0


@dataclass
class AgentRequestResult:
    """Result from a single agent request.

    Two throughput metrics:
    - gpu_tokens_per_s:  completion_tokens / eval_ms  (GPU-side only, no queue wait)
    - effective_tps:     completion_tokens / wall_ms   (user-perceived, includes queue wait)

    For N-agent scaling analysis, effective_tps is the PRIMARY metric because
    it captures the throughput degradation agents actually experience.
    gpu_tokens_per_s is reported for completeness / cross-validation.
    """

    agent_id: int = 0
    request_id: int = 0
    request_sequence: int = 0
    in_flight_at_submit: int = 0
    submit_time_s: float = 0.0
    complete_time_s: float = 0.0
    wall_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    prompt_eval_ms: float = 0.0
    eval_ms: float = 0.0
    total_duration_ms: float = 0.0
    load_duration_ms: float = 0.0
    gpu_tokens_per_s: float = 0.0  # GPU-side: completion_tokens / eval_ms
    effective_tps: float = 0.0  # User-perceived: completion_tokens / wall_ms
    status: str = "ok"


def _extract_ollama_timing(data: dict) -> dict:
    """Extract Ollama native timing (nanoseconds → ms)."""
    ns_to_ms = 1e-6
    return {
        "prompt_tokens": data.get("prompt_eval_count", 0),
        "completion_tokens": data.get("eval_count", 0),
        "prompt_eval_ms": data.get("prompt_eval_duration", 0) * ns_to_ms,
        "eval_ms": data.get("eval_duration", 0) * ns_to_ms,
        "total_duration_ms": data.get("total_duration", 0) * ns_to_ms,
        "load_duration_ms": data.get("load_duration", 0) * ns_to_ms,
    }


async def _agent_loop(
    agent: AgentConfig,
    url: str,
    max_tokens: int,
    timeout: float,
    in_flight: list[int],
    t0: float,
    global_request_id: list[int],
) -> list[AgentRequestResult]:
    """Single agent's closed loop: send → wait → think → send."""
    results: list[AgentRequestResult] = []

    for seq in range(agent.n_requests):
        prompt = agent.prompts[seq % len(agent.prompts)]

        # Record in-flight count at submit
        depth = in_flight[0]
        in_flight[0] += 1
        submit_time = time.perf_counter() - t0

        req_id = global_request_id[0]
        global_request_id[0] += 1

        result = AgentRequestResult(
            agent_id=agent.agent_id,
            request_id=req_id,
            request_sequence=seq,
            in_flight_at_submit=depth,
            submit_time_s=round(submit_time, 4),
        )

        payload = {
            "model": agent.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.0,
                "seed": 42,
            },
        }

        t_req = time.perf_counter()
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{url}/api/generate",
                    json=payload,
                    timeout=timeout,
                )
                result.wall_ms = (time.perf_counter() - t_req) * 1000.0
                resp.raise_for_status()
                data = resp.json()

                timing = _extract_ollama_timing(data)
                result.prompt_tokens = timing["prompt_tokens"]
                result.completion_tokens = timing["completion_tokens"]
                result.prompt_eval_ms = timing["prompt_eval_ms"]
                result.eval_ms = timing["eval_ms"]
                result.total_duration_ms = timing["total_duration_ms"]
                result.load_duration_ms = timing["load_duration_ms"]

                # GPU-side throughput (eval_ms = GPU decode time only)
                if result.eval_ms > 0 and result.completion_tokens > 0:
                    result.gpu_tokens_per_s = result.completion_tokens / (
                        result.eval_ms / 1000.0
                    )

                # Effective throughput (wall_ms = queue wait + decode + overhead)
                if result.wall_ms > 0 and result.completion_tokens > 0:
                    result.effective_tps = result.completion_tokens / (
                        result.wall_ms / 1000.0
                    )

        except httpx.TimeoutException:
            result.wall_ms = (time.perf_counter() - t_req) * 1000.0
            result.status = "timeout"
        except Exception as exc:
            result.wall_ms = (time.perf_counter() - t_req) * 1000.0
            result.status = f"error: {exc}"
            log.warning(
                "Agent %d seq %d failed: %s",
                agent.agent_id,
                seq,
                exc,
            )
        finally:
            in_flight[0] -= 1

        result.complete_time_s = round(time.perf_counter() - t0, 4)
        results.append(result)

        # Think time between requests (skip after last)
        if seq < agent.n_requests - 1 and agent.think_time_ms > 0:
            await asyncio.sleep(agent.think_time_ms / 1000.0)

    return results


async def _run_agents(
    agents: list[AgentConfig],
    url: str,
    max_tokens: int = 128,
    timeout: float = 120.0,
) -> list[AgentRequestResult]:
    """Launch all agent loops concurrently via asyncio."""
    in_flight: list[int] = [0]
    global_request_id: list[int] = [0]
    t0 = time.perf_counter()

    tasks = [
        asyncio.create_task(
            _agent_loop(
                agent, url, max_tokens, timeout, in_flight, t0, global_request_id
            ),
        )
        for agent in agents
    ]

    all_results: list[AgentRequestResult] = []
    for completed in await asyncio.gather(*tasks, return_exceptions=True):
        if isinstance(completed, Exception):
            log.error("Agent task failed: %s", completed)
            continue
        all_results.extend(completed)

    all_results.sort(key=lambda r: r.submit_time_s)

    n_ok = sum(1 for r in all_results if r.status == "ok")
    log.info(
        "N-agent test: %d agents, %d/%d ok, max in_flight=%d",
        len(agents),
        n_ok,
        len(all_results),
        max((r.in_flight_at_submit for r in all_results), default=0) + 1,
    )
    return all_results


async def run_n_agent_test(
    url: str,
    model: str,
    n_agents: int,
    requests_per_agent: int,
    prompts: list[str],
    think_time_ms: float = 0.0,
    max_tokens: int = 128,
    timeout: float = 120.0,
) -> list[AgentRequestResult]:
    """Homogeneous test: N agents all using the same model."""
    agents = []
    for i in range(n_agents):
        # Each agent gets a different slice of prompts for variety
        start = (i * requests_per_agent) % len(prompts)
        agent_prompts = []
        for j in range(requests_per_agent):
            idx = (start + j) % len(prompts)
            agent_prompts.append(prompts[idx])

        agents.append(
            AgentConfig(
                agent_id=i,
                model=model,
                n_requests=requests_per_agent,
                prompts=agent_prompts,
                think_time_ms=think_time_ms,
            )
        )

    log.info(
        "Running N=%d agents, model=%s, %d req/agent, think=%dms",
        n_agents,
        model,
        requests_per_agent,
        think_time_ms,
    )
    return await _run_agents(agents, url, max_tokens, timeout)


async def run_heterogeneous_test(
    agents: list[AgentConfig],
    url: str,
    max_tokens: int = 128,
    timeout: float = 120.0,
) -> list[AgentRequestResult]:
    """Heterogeneous test: agents with different model assignments."""
    models = {a.model for a in agents}
    log.info(
        "Running heterogeneous test: %d agents, models=%s",
        len(agents),
        sorted(models),
    )
    return await _run_agents(agents, url, max_tokens, timeout)
