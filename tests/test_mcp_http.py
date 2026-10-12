"""Real SDK transport, admission, and server-owned HTTP policy regressions."""

from __future__ import annotations

import asyncio
import json
import socket
import sys
import threading
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
import anyio

pytest.importorskip("mcp", reason="optional [mcp] extra not installed")
import uvicorn
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

from chimeraforge import __version__
from chimeraforge.mcp_server import build_server
from chimeraforge.mcp_transport import DEFAULT_TOOL_TIMEOUT

TOOLS = {
    "chimeraforge_plan",
    "chimeraforge_resolve_model",
    "chimeraforge_list_hardware",
    "chimeraforge_compare_api",
    "chimeraforge_suggest",
}
ROOT = Path(__file__).resolve().parents[1]
HTTP_RESPONSE_MARGIN_SECONDS = 5


@asynccontextmanager
async def serving(**options):
    from chimeraforge.mcp_transport import MCPHTTPSettings

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = build_server(http_settings=MCPHTTPSettings(port=port, **options))
    runner = uvicorn.Server(uvicorn.Config(server.streamable_http_app(), log_level="error"))
    task = asyncio.create_task(runner.serve(sockets=[sock]))
    try:
        with anyio.fail_after(5):
            while not runner.started:
                if task.done():
                    await task
                await asyncio.sleep(0.01)
        yield server, f"http://127.0.0.1:{port}/mcp"
    finally:
        runner.should_exit = True
        await asyncio.wait_for(task, 5)
        sock.close()


@asynccontextmanager
async def connected(url, *, timeout=3):
    async with streamable_http_client(url) as (read, write, _):
        async with ClientSession(
            read, write, read_timeout_seconds=timedelta(seconds=timeout)
        ) as session:
            initialized = await session.initialize()
            yield session, initialized


def payload(result):
    assert not result.isError, result.content
    return result.structuredContent or json.loads(result.content[0].text)


@pytest.mark.asyncio
async def test_http_sdk_client_five_tools_real_offline_plan(monkeypatch):
    import chimeraforge.mcp_server as tools

    consumed = []
    original = tools.run_plan

    def capture(**kwargs):
        consumed.append(kwargs["allow_network"])
        return original(**kwargs)

    monkeypatch.setattr(tools, "run_plan", capture)
    # Receive the server's bounded response even when coverage slows real CPU planning.
    async with (
        serving() as (_, url),
        connected(url, timeout=DEFAULT_TOOL_TIMEOUT + HTTP_RESPONSE_MARGIN_SECONDS) as (
            client,
            initialized,
        ),
    ):
        assert initialized.serverInfo.version == __version__
        assert {item.name for item in (await client.list_tools()).tools} == TOOLS
        result = payload(
            await client.call_tool(
                "chimeraforge_plan",
                {
                    "hardware": "RTX 4090 24GB",
                    "model": "llama3.2-3b",
                    "quality_target": 0,
                },
            )
        )
        assert result["recommended"]["provenance"]
        assert consumed == [False]  # omitted SDK True default must not enable network
        assert payload(
            await client.call_tool("chimeraforge_resolve_model", {"model": "llama3.2-3b"})
        )["ok"]
        assert payload(await client.call_tool("chimeraforge_list_hardware", {}))["count"] > 0
        assert payload(
            await client.call_tool("chimeraforge_compare_api", {"hardware": "RTX 4090 24GB"})
        )["ok"]
        assert payload(
            await client.call_tool("chimeraforge_suggest", {"hardware": "RTX 4090 24GB"})
        )["ok"]


@pytest.mark.asyncio
async def test_stdio_real_sdk_preserves_five_tools_and_version():
    parameters = StdioServerParameters(
        command=sys.executable, args=["-m", "chimeraforge", "mcp"], cwd=ROOT
    )
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as client:
            initialized = await client.initialize()
            assert initialized.serverInfo.version == __version__
            assert {item.name for item in (await client.list_tools()).tools} == TOOLS
            assert payload(
                await client.call_tool(
                    "chimeraforge_resolve_model",
                    {
                        "model": "llama3.2-3b",
                        "allow_network": False,
                    },
                )
            )["ok"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,arguments",
    [
        (
            "chimeraforge_plan",
            {"hardware": "RTX 4090 24GB", "quality_from": "/private/scores.json"},
        ),
        ("chimeraforge_plan", {"hardware": "RTX 4090 24GB", "allow_network": False}),
        ("chimeraforge_resolve_model", {"model": "ollama:secret-model"}),
        ("chimeraforge_resolve_model", {"model": "https://private.invalid/model"}),
        (
            "chimeraforge_suggest",
            {"hardware": "RTX 4090 24GB", "ollama_url": "http://private.invalid"},
        ),
        ("chimeraforge_suggest", {"hardware": "RTX 4090 24GB", "source": "hf"}),
        ("chimeraforge_suggest", {"hardware": "RTX 4090 24GB", "source": "ollama"}),
    ],
)
async def test_http_forbidden_options_rejected_before_tool(name, arguments):
    async with serving() as (_, url), connected(url) as (client, _):
        result = await client.call_tool(name, arguments)
        assert result.isError
        assert "/private" not in str(result.content) and "private.invalid" not in str(
            result.content
        )


@pytest.mark.asyncio
async def test_http_server_owns_opt_in_network(monkeypatch):
    import chimeraforge.mcp_server as tools

    seen = []

    def resolve(model: str, allow_network: bool = True) -> dict:
        seen.append(allow_network)
        return {"ok": True}

    monkeypatch.setattr(tools, "resolve_model", resolve)
    async with serving(allow_network=True) as (_, url), connected(url) as (client, _):
        assert payload(
            await client.call_tool("chimeraforge_resolve_model", {"model": "org/model"})
        )["ok"]
        assert seen == [True]
        assert (
            await client.call_tool(
                "chimeraforge_resolve_model", {"model": "org/model", "allow_network": True}
            )
        ).isError


@pytest.mark.asyncio
async def test_sdk_http_native_body_host_origin_guards():
    async with serving(max_body_bytes=1024) as (_, url), httpx.AsyncClient() as client:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        oversized = " " * 2048
        assert (await client.post(url, content=oversized, headers=headers)).status_code == 413

        async def chunks():
            yield b" " * 700
            yield b" " * 700

        assert (await client.post(url, content=chunks(), headers=headers)).status_code == 413
        assert (
            await client.post(url, content="{}", headers={**headers, "Host": "evil.invalid"})
        ).status_code == 421
        assert (
            await client.post(
                url, content="{}", headers={**headers, "Origin": "https://evil.invalid"}
            )
        ).status_code == 403
        # Even local browser-origin requests are not enabled on this loopback API.
        assert (
            await client.post(
                url, content="{}", headers={**headers, "Origin": url.rsplit("/", 1)[0]}
            )
        ).status_code == 403


@pytest.mark.asyncio
async def test_tool_timeout_retains_worker_capacity_and_control_is_responsive(monkeypatch):
    import chimeraforge.mcp_server as tools

    entered, release = threading.Event(), threading.Event()

    def blocked(model: str, allow_network: bool = True) -> dict:
        entered.set()
        assert release.wait(2)
        return {"ok": True}

    monkeypatch.setattr(tools, "resolve_model", blocked)
    try:
        async with (
            serving(tool_timeout=0.03, max_workers=1) as (_, url),
            connected(url) as (client, _),
        ):
            result = await client.call_tool("chimeraforge_resolve_model", {"model": "llama3.2-3b"})
            assert entered.is_set() and result.isError
            assert "timeout" in str(result.content).lower()
            with anyio.fail_after(0.5):
                await client.send_ping()
                assert {item.name for item in (await client.list_tools()).tools} == TOOLS
            busy = await client.call_tool("chimeraforge_list_hardware", {})
            assert busy.isError and "busy" in str(busy.content).lower()
            release.set()
            with anyio.fail_after(1):
                while True:
                    result = await client.call_tool("chimeraforge_list_hardware", {})
                    if not result.isError:
                        break
                    await asyncio.sleep(0.01)
            assert payload(result)["count"] > 0
    finally:
        release.set()


@pytest.mark.asyncio
async def test_client_cancellation_does_not_admit_another_worker(monkeypatch):
    import chimeraforge.mcp_server as tools

    entered, release = threading.Event(), threading.Event()

    def blocked(model: str, allow_network: bool = True) -> dict:
        entered.set()
        assert release.wait(2)
        return {"ok": True}

    monkeypatch.setattr(tools, "resolve_model", blocked)
    try:
        async with (
            serving(tool_timeout=1, max_workers=1) as (_, url),
            connected(url) as (client, _),
        ):
            task = asyncio.create_task(
                client.call_tool("chimeraforge_resolve_model", {"model": "llama3.2-3b"})
            )
            with anyio.fail_after(1):
                while not entered.is_set():
                    await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            busy = await client.call_tool("chimeraforge_list_hardware", {})
            assert busy.isError and "busy" in str(busy.content).lower()
            await client.send_ping()
            release.set()
    finally:
        release.set()


@pytest.mark.parametrize(
    "options",
    [
        {"host": "0.0.0.0"},
        {"max_workers": 0},
        {"tool_timeout": float("nan")},
        {"max_body_bytes": 0},
        {"max_sessions": 0},
        {"session_idle_timeout": 0},
        {"port": True},
        {"port": 0},
        {"allow_network": 1},
    ],
)
def test_http_settings_reject_invalid_or_external_bind(options):
    from chimeraforge.mcp_transport import MCPHTTPSettings

    with pytest.raises(ValueError):
        MCPHTTPSettings(**options)


@pytest.mark.asyncio
async def test_sdk_native_session_cap_delete_and_idle_expiry():
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "session-guard-test", "version": "1"},
        },
    }
    async with (
        serving(max_sessions=1, session_idle_timeout=0.08) as (_, url),
        httpx.AsyncClient() as client,
    ):
        first = await client.post(url, json=initialize, headers=headers)
        assert first.status_code == 200
        session_id = first.headers["mcp-session-id"]
        assert (await client.post(url, json=initialize, headers=headers)).status_code == 503
        await asyncio.sleep(0.15)
        expired = await client.post(
            url,
            json={"jsonrpc": "2.0", "id": 2, "method": "ping"},
            headers={
                **headers,
                "mcp-session-id": session_id,
                "mcp-protocol-version": "2025-11-25",
            },
        )
        assert expired.status_code == 404
        second = await client.post(url, json=initialize, headers=headers)
        assert second.status_code == 200
        deleted = await client.delete(
            url, headers={**headers, "mcp-session-id": second.headers["mcp-session-id"]}
        )
        assert deleted.status_code == 200
        assert (await client.post(url, json=initialize, headers=headers)).status_code == 200


def test_http_cli_passes_typed_operator_settings_and_preserves_stdio(monkeypatch):
    from typer.testing import CliRunner
    from chimeraforge.cli import app
    from chimeraforge.mcp_transport import MCPHTTPSettings

    calls = []
    monkeypatch.setattr("chimeraforge.mcp_server.main", lambda **kwargs: calls.append(kwargs))
    runner = CliRunner()
    assert runner.invoke(app, ["mcp"]).exit_code == 0
    assert calls == [{}]
    result = runner.invoke(
        app, ["mcp", "--transport", "streamable-http", "--port", "9876", "--allow-network"]
    )
    assert result.exit_code == 0, result.output
    assert calls[1]["transport"] == "streamable-http"
    settings = calls[1]["http_settings"]
    assert (
        isinstance(settings, MCPHTTPSettings) and settings.port == 9876 and settings.allow_network
    )
    assert (
        runner.invoke(app, ["mcp", "--transport", "streamable-http", "--host", "0.0.0.0"]).exit_code
        == 1
    )
    assert runner.invoke(app, ["mcp", "--transport", "invalid"]).exit_code == 1


@pytest.mark.asyncio
async def test_shutdown_stops_admission_and_drains_timed_out_owned_worker():
    from chimeraforge.mcp_transport import MCPHTTPSettings, ToolExecutor

    release, finished = threading.Event(), threading.Event()
    executor = ToolExecutor(MCPHTTPSettings(tool_timeout=0.01, max_workers=1))

    def blocked() -> dict:
        try:
            assert release.wait(2)
            return {"ok": True}
        finally:
            finished.set()

    call = executor.wrap(blocked)
    try:
        with pytest.raises(RuntimeError, match="timeout"):
            await call()
        close = asyncio.create_task(executor.aclose())
        await asyncio.sleep(0.03)
        assert not close.done() and not finished.is_set()
        with pytest.raises(RuntimeError, match="busy"):
            await call()
        release.set()
        await asyncio.wait_for(close, 1)
        assert finished.is_set()
        assert not any(item.name.startswith("chimeraforge-mcp") for item in threading.enumerate())
    finally:
        release.set()
        await executor.aclose()


@pytest.mark.asyncio
async def test_http_hf_fanout_is_bounded_before_network_admission(monkeypatch):
    from chimeraforge.rest_server import MAX_MODELS

    seen = []

    def discover(sources, *, ollama_url, hf_limit):
        seen.append(hf_limit)
        return []

    monkeypatch.setattr("chimeraforge.planner.discovery.discover_identifiers", discover)
    async with serving(allow_network=True) as (_, url), connected(url) as (client, _):
        arguments = {"hardware": "RTX 4090 24GB", "source": "hf"}
        for limit in (0, -1, MAX_MODELS + 1, 1000, True, "1000"):
            invalid = await client.call_tool(
                "chimeraforge_suggest", {**arguments, "hf_limit": limit}
            )
            assert invalid.isError and "hf_limit" in str(invalid.content)
        assert seen == []
        valid = await client.call_tool(
            "chimeraforge_suggest", {**arguments, "hf_limit": MAX_MODELS}
        )
        assert payload(valid)["ok"] and seen == [MAX_MODELS]
