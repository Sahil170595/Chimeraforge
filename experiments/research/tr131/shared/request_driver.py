"""HTTP request driver for Ollama — runs OUTSIDE the nsys profiling session.

Sends N concurrent request streams to a running Ollama instance.
Reuses the closed-loop pattern from TR129/TR130.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import time

import httpx

log = logging.getLogger("tr131.request_driver")

OLLAMA_URL = "http://localhost:11434"


@dataclass
class RequestResult:
    """Single request result."""

    agent_id: int
    request_seq: int
    wall_ms: float
    prompt_tokens: int
    completion_tokens: int
    effective_tps: float
    eval_ms: float | None = None
    prompt_eval_ms: float | None = None
    status: str = "ok"


async def _agent_loop(
    agent_id: int,
    model_tag: str,
    prompts: list[str],
    max_tokens: int,
    results: list[RequestResult],
    in_flight: list[int],
) -> None:
    """Single agent loop — send requests serially."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        for seq, prompt in enumerate(prompts):
            in_flight[0] += 1
            t0 = time.perf_counter()
            try:
                resp = await client.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={
                        "model": model_tag,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "num_predict": max_tokens,
                            "temperature": 0.0,
                            "seed": 42,
                        },
                    },
                )
                wall_ms = (time.perf_counter() - t0) * 1000
                data = resp.json()

                comp_tokens = data.get("eval_count", 0)
                prompt_tokens = data.get("prompt_eval_count", 0)
                eval_ns = data.get("eval_duration", 0)
                prompt_eval_ns = data.get("prompt_eval_duration", 0)

                results.append(
                    RequestResult(
                        agent_id=agent_id,
                        request_seq=seq,
                        wall_ms=wall_ms,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=comp_tokens,
                        effective_tps=(
                            comp_tokens / wall_ms * 1000 if wall_ms > 0 else 0
                        ),
                        eval_ms=eval_ns / 1e6 if eval_ns else None,
                        prompt_eval_ms=prompt_eval_ns / 1e6 if prompt_eval_ns else None,
                        status="ok",
                    )
                )
            except Exception as e:
                wall_ms = (time.perf_counter() - t0) * 1000
                log.warning("Agent %d req %d failed: %s", agent_id, seq, e)
                results.append(
                    RequestResult(
                        agent_id=agent_id,
                        request_seq=seq,
                        wall_ms=wall_ms,
                        prompt_tokens=0,
                        completion_tokens=0,
                        effective_tps=0.0,
                        status=f"error: {e}",
                    )
                )
            finally:
                in_flight[0] -= 1


async def _run_agents(
    n_agents: int,
    model_tag: str,
    prompts_per_agent: list[list[str]],
    max_tokens: int,
) -> list[RequestResult]:
    """Launch N concurrent agents."""
    results: list[RequestResult] = []
    in_flight = [0]

    tasks = []
    for i in range(n_agents):
        tasks.append(
            _agent_loop(
                i, model_tag, prompts_per_agent[i], max_tokens, results, in_flight
            )
        )
    await asyncio.gather(*tasks)
    return results


def send_requests(
    n_agents: int,
    requests_per_agent: int,
    model_tag: str,
    prompts: list[str],
    max_tokens: int = 128,
) -> list[RequestResult]:
    """Send N concurrent request streams to Ollama.

    Returns list of RequestResult, one per request.
    """
    # Distribute prompts across agents (round-robin)
    prompts_per_agent = [[] for _ in range(n_agents)]
    for i in range(n_agents):
        for j in range(requests_per_agent):
            idx = (i * requests_per_agent + j) % len(prompts)
            prompts_per_agent[i].append(prompts[idx])

    return asyncio.run(_run_agents(n_agents, model_tag, prompts_per_agent, max_tokens))


def warmup(model_tag: str, n: int = 3, max_tokens: int = 32) -> bool:
    """Send warmup requests to Ollama. Returns True if successful."""
    from .utils import generate_prompt

    prompt = generate_prompt(50)

    async def _warmup():
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            for i in range(n):
                try:
                    resp = await client.post(
                        f"{OLLAMA_URL}/api/generate",
                        json={
                            "model": model_tag,
                            "prompt": prompt,
                            "stream": False,
                            "options": {"num_predict": max_tokens},
                        },
                    )
                    if resp.status_code == 200:
                        log.debug("Warmup %d/%d ok", i + 1, n)
                except Exception as e:
                    log.warning("Warmup %d failed: %s", i + 1, e)
                    return False
        return True

    return asyncio.run(_warmup())


def wait_ollama_ready(timeout_s: int = 60) -> bool:
    """Poll Ollama until it responds."""
    import urllib.request

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            resp = urllib.request.urlopen(
                f"{OLLAMA_URL}/api/tags",
                timeout=3,
            )
            if resp.status == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False
