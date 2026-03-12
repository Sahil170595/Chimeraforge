"""TR130 core: backend-agnostic N-agent closed-loop async executor.

Adapted from TR129. Key difference: calls backend.generate() instead of raw
Ollama HTTP — works identically for Ollama, vLLM, and TGI.

Each agent runs a closed loop: send request → wait for response → optional
think time → send next request.  Maximum concurrency = N (not open-loop).

in_flight tracked via mutable [0] list (safe in single-threaded asyncio).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import time

from research.tr130.shared.backends import (
    ServingBackend,
)

log = logging.getLogger("tr130.agent_executor")


@dataclass
class AgentConfig:
    """Configuration for a single agent in the N-agent test."""

    agent_id: int
    n_requests: int
    prompts: list[str]
    think_time_ms: float = 0.0


@dataclass
class AgentRequestResult:
    """Result from a single agent request.

    effective_tps = completion_tokens / wall_ms * 1000  (user-perceived)
    gpu_tokens_per_s = completion_tokens / decode_ms * 1000 (Ollama/TGI only)
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
    prefill_ms: float | None = None
    decode_ms: float | None = None
    effective_tps: float = 0.0
    gpu_tokens_per_s: float | None = None
    ttft_ms: float | None = None
    status: str = "ok"


async def _agent_loop(
    agent: AgentConfig,
    backend: ServingBackend,
    max_tokens: int,
    in_flight: list[int],
    t0: float,
    global_request_id: list[int],
    stream: bool = False,
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

        try:
            if stream:
                br = await backend.generate_stream(prompt=prompt, max_tokens=max_tokens)
                result.ttft_ms = br.ttft_ms
            else:
                br = await backend.generate(prompt=prompt, max_tokens=max_tokens)

            result.wall_ms = br.wall_ms
            result.prompt_tokens = br.prompt_tokens
            result.completion_tokens = br.completion_tokens
            result.prefill_ms = br.prefill_ms
            result.decode_ms = br.decode_ms
            result.effective_tps = br.effective_tps
            result.gpu_tokens_per_s = br.gpu_tokens_per_s
            result.status = br.status

        except Exception as exc:
            result.wall_ms = (time.perf_counter() - (t0 + submit_time)) * 1000
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
    backend: ServingBackend,
    max_tokens: int = 128,
    stream: bool = False,
) -> list[AgentRequestResult]:
    """Launch all agent loops concurrently via asyncio."""
    in_flight: list[int] = [0]
    global_request_id: list[int] = [0]
    t0 = time.perf_counter()

    tasks = [
        asyncio.create_task(
            _agent_loop(
                agent,
                backend,
                max_tokens,
                in_flight,
                t0,
                global_request_id,
                stream=stream,
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
    backend: ServingBackend,
    n_agents: int,
    requests_per_agent: int,
    prompts: list[str],
    think_time_ms: float = 0.0,
    max_tokens: int = 128,
    stream: bool = False,
) -> list[AgentRequestResult]:
    """Homogeneous test: N agents all using the same backend."""
    agents = []
    for i in range(n_agents):
        start = (i * requests_per_agent) % len(prompts)
        agent_prompts = []
        for j in range(requests_per_agent):
            idx = (start + j) % len(prompts)
            agent_prompts.append(prompts[idx])

        agents.append(
            AgentConfig(
                agent_id=i,
                n_requests=requests_per_agent,
                prompts=agent_prompts,
                think_time_ms=think_time_ms,
            )
        )

    log.info(
        "Running N=%d agents, backend=%s, %d req/agent, think=%dms",
        n_agents,
        backend.name,
        requests_per_agent,
        think_time_ms,
    )
    return await _run_agents(agents, backend, max_tokens, stream=stream)
