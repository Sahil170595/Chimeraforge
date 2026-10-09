"""Loopback MCP settings, server-owned policy, and bounded synchronous execution."""

from __future__ import annotations

import asyncio
import logging
import math
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import wraps
from typing import Callable

from chimeraforge.planner.discovery import DEFAULT_HF_LIMIT
from chimeraforge.rest_server import LOCAL_HOSTS, LOCAL_ONLY_OPTIONS, MAX_BODY_BYTES, MAX_MODELS

log = logging.getLogger(__name__)
DEFAULT_MCP_PORT = 8766
DEFAULT_TOOL_TIMEOUT = 30.0
# Fixed admission capacity, with no executor submission queue beyond running work.
DEFAULT_WORKERS = 2
MAX_WORKERS = 16
DEFAULT_MAX_SESSIONS = 32
DEFAULT_SESSION_IDLE_TIMEOUT = 300.0
NETWORK_TOOLS = {"chimeraforge_plan", "chimeraforge_resolve_model", "chimeraforge_compare_api"}


@dataclass(frozen=True)
class MCPHTTPSettings:
    """Operator-owned settings; HTTP clients cannot replace this network policy."""

    host: str = "127.0.0.1"
    port: int = DEFAULT_MCP_PORT
    allow_network: bool = False
    max_body_bytes: int = MAX_BODY_BYTES
    max_sessions: int = DEFAULT_MAX_SESSIONS
    session_idle_timeout: float = DEFAULT_SESSION_IDLE_TIMEOUT
    max_workers: int = DEFAULT_WORKERS
    tool_timeout: float = DEFAULT_TOOL_TIMEOUT

    def __post_init__(self) -> None:
        if type(self.host) is not str or self.host not in LOCAL_HOSTS:
            raise ValueError("the MCP HTTP server binds to loopback only")
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        if type(self.allow_network) is not bool:
            raise ValueError("allow_network must be boolean")
        for field in ("max_body_bytes", "max_sessions", "max_workers"):
            value = getattr(self, field)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{field} must be a positive integer")
        if self.max_workers > MAX_WORKERS:
            raise ValueError(f"max_workers must be at most {MAX_WORKERS}")
        for field in ("session_idle_timeout", "tool_timeout"):
            value = getattr(self, field)
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{field} must be positive and finite")


def http_arguments(name: str, arguments: dict, settings: MCPHTTPSettings) -> dict:
    """Guard raw arguments before the SDK injects function defaults."""
    forbidden = LOCAL_ONLY_OPTIONS.intersection(arguments)
    if forbidden:
        raise ValueError(
            "options are configured by the server, not HTTP: " + ", ".join(sorted(forbidden))
        )
    model = arguments.get("model")
    if isinstance(model, str) and (
        ":" in model or model.startswith(("/", "\\", ".")) or "\\" in model
    ):
        raise ValueError(
            "local paths, URLs, and Ollama endpoint resolution are not exposed over MCP HTTP"
        )
    if name == "chimeraforge_suggest":
        hf_limit = arguments.get("hf_limit", DEFAULT_HF_LIMIT)
        if type(hf_limit) is not int or not 1 <= hf_limit <= MAX_MODELS:
            raise ValueError(f"HTTP hf_limit must be an integer between 1 and {MAX_MODELS}")
        source = arguments.get("source", "catalog")
        if isinstance(source, str):
            sources = {item.strip().lower() for item in source.split(",")}
            if "ollama" in sources:
                raise ValueError("Ollama endpoint discovery is not exposed over MCP HTTP")
            if "hf" in sources and not settings.allow_network:
                raise ValueError("network discovery is disabled by the server")
    effective = dict(arguments)
    if name in NETWORK_TOOLS:
        effective["allow_network"] = settings.allow_network
    return effective


class ToolExecutor:
    """Keep ownership until synchronous work ends, even after client cancellation."""

    def __init__(self, settings: MCPHTTPSettings) -> None:
        self._timeout = settings.tool_timeout
        self._pool = ThreadPoolExecutor(
            max_workers=settings.max_workers, thread_name_prefix="chimeraforge-mcp"
        )
        self._slots = threading.BoundedSemaphore(settings.max_workers)
        self._lock = threading.RLock()
        self._pending: set[Future] = set()
        self._closing = False

    def wrap(self, function: Callable) -> Callable:
        """Retain the public tool signature and schema on an asynchronous wrapper."""

        @wraps(function)
        async def execute(**kwargs):
            with self._lock:
                if self._closing or not self._slots.acquire(blocking=False):
                    raise RuntimeError(
                        "MCP server busy; synchronous work still owns all worker slots"
                    )
                try:
                    future = self._pool.submit(function, **kwargs)
                except RuntimeError:
                    self._slots.release()
                    raise
                self._pending.add(future)
                future.add_done_callback(self._completed)
            waiter = asyncio.wrap_future(future)
            waiter.add_done_callback(self._consume_exception)
            try:
                return await asyncio.wait_for(asyncio.shield(waiter), timeout=self._timeout)
            except asyncio.TimeoutError as exc:
                log.info("MCP tool response timed out; worker remains owned until completion")
                raise RuntimeError(
                    "MCP tool timeout; work retains its worker slot until completion"
                ) from exc

        return execute

    @staticmethod
    def _consume_exception(future: asyncio.Future) -> None:
        if not future.cancelled() and future.exception() is not None:
            # Do not log model identifiers, file paths, endpoint tokens, or exception text.
            log.debug(
                "MCP synchronous tool completed with an error: %s",
                type(future.exception()).__name__,
            )

    def _completed(self, future: Future) -> None:
        with self._lock:
            self._pending.discard(future)
            self._slots.release()

    async def aclose(self) -> None:
        """Stop admission and drain the fixed owned workers before releasing the server."""
        with self._lock:
            self._closing = True
            pending = tuple(self._pending)
        if pending:
            await asyncio.gather(
                *(asyncio.wrap_future(item) for item in pending), return_exceptions=True
            )
        self._pool.shutdown(wait=True)


def build_http_server(*, instructions: str, settings: MCPHTTPSettings):
    """Use native SDK transport/session/security guards and its public tool seam."""
    import anyio
    from mcp.server.fastmcp import FastMCP
    from mcp.server.transport_security import TransportSecuritySettings

    executor = ToolExecutor(settings)

    class HTTPMCP(FastMCP):
        async def call_tool(self, name: str, arguments: dict):
            return await super().call_tool(name, http_arguments(name, arguments, settings))

        def streamable_http_app(self):
            app = super().streamable_http_app()
            sdk_lifespan = app.router.lifespan_context

            @asynccontextmanager
            async def lifespan(application):
                try:
                    async with sdk_lifespan(application) as state:
                        yield state
                finally:
                    # SDK session cancellation must not abandon owned synchronous jobs.
                    with anyio.CancelScope(shield=True):
                        await executor.aclose()

            app.router.lifespan_context = lifespan
            return app

    policy = "operator-enabled" if settings.allow_network else "offline"
    server = HTTPMCP(
        "chimeraforge",
        instructions=(
            instructions + f" HTTP network policy: {policy}. "
            "Callers cannot override this policy or supply local paths/endpoints."
        ),
        host=settings.host,
        port=settings.port,
        streamable_http_path="/mcp",
        json_response=False,
        stateless_http=False,
        max_request_body_size=settings.max_body_bytes,
        max_sessions=settings.max_sessions,
        session_idle_timeout=settings.session_idle_timeout,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[f"{host}:{settings.port}" for host in LOCAL_HOSTS],
            allowed_origins=[],
        ),
    )
    return server, executor
