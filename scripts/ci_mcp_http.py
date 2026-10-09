"""Exercise a candidate CLI's native MCP HTTP transport with the real SDK client."""

from __future__ import annotations

import asyncio
import socket
import subprocess
import time
from datetime import timedelta

import httpx

from probe_mcp_stdio import EXPECTED_TOOLS, tool_payload

DEFAULT_PROBE_TIMEOUT = 60.0
PROCESS_CLOSE_TIMEOUT = 10
READINESS_POLL_SECONDS = 0.05


async def exercise(url: str, process: subprocess.Popen, timeout: float) -> dict:
    """Initialize, discover, plan offline, and reject caller policy replacement."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    deadline = time.monotonic() + timeout
    async with httpx.AsyncClient(timeout=1) as http:
        while True:
            if process.poll() is not None:
                raise RuntimeError("candidate MCP HTTP process exited before listening")
            try:
                await http.get(url)
                break
            except httpx.TransportError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("candidate MCP HTTP process did not listen before deadline")
                await asyncio.sleep(READINESS_POLL_SECONDS)
    async with streamable_http_client(url) as (read, write, _):
        async with ClientSession(
            read, write, read_timeout_seconds=timedelta(seconds=timeout)
        ) as client:
            initialized = await client.initialize()
            assert "HTTP network policy: offline." in initialized.instructions
            names = [item.name for item in (await client.list_tools()).tools]
            assert set(names) == EXPECTED_TOOLS, names
            hardware = tool_payload(await client.call_tool("chimeraforge_list_hardware", {}))
            assert hardware["ok"] and hardware["count"] > 0
            model = tool_payload(
                await client.call_tool("chimeraforge_resolve_model", {"model": "llama3.2-3b"})
            )
            assert model["ok"] and model["params_b"] > 0
            result = tool_payload(
                await client.call_tool(
                    "chimeraforge_plan",
                    {
                        "hardware": "RTX 4080 12GB",
                        "model_size": "3b",
                        "request_rate": 0.01,
                    },
                )
            )
            assert result["ok"] and result["recommended"]["provenance"]
            assert result["recommended"]["total_throughput_tps"] > 0
            forbidden = await client.call_tool(
                "chimeraforge_resolve_model",
                {
                    "model": "llama3.2-3b",
                    "allow_network": True,
                },
            )
            assert forbidden.isError, "caller replaced the server-owned offline policy"
            await client.send_ping()
            return {
                "serverInfo": initialized.serverInfo.model_dump(),
                "tools": names,
                "transport": "streamable-http",
                "offline_default_plan": "passed",
                "caller_network_override": "rejected",
            }


def probe(
    command: list[str], *, cwd=None, env=None, timeout: float = DEFAULT_PROBE_TIMEOUT
) -> dict:
    """Own and close the CLI process; bound the entire real HTTP conversation."""
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    process = subprocess.Popen(
        [*command, "--transport", "streamable-http", "--port", str(port)],
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        receipt = asyncio.run(
            asyncio.wait_for(exercise(f"http://127.0.0.1:{port}/mcp", process, timeout), timeout)
        )
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.communicate(timeout=PROCESS_CLOSE_TIMEOUT)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=PROCESS_CLOSE_TIMEOUT)
    receipt["owned_process"] = "closed"
    return receipt
