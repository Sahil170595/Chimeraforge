"""`mcp` command - run the MCP server so assistants (Claude/GPT/Cursor) can call
the planner. Heavy/optional `mcp` SDK is imported lazily inside the command."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.markup import escape

from chimeraforge.mcp_transport import (
    DEFAULT_MAX_SESSIONS,
    DEFAULT_MCP_PORT,
    DEFAULT_SESSION_IDLE_TIMEOUT,
    DEFAULT_TOOL_TIMEOUT,
    DEFAULT_WORKERS,
    MAX_BODY_BYTES,
)

console = Console()


def mcp(
    transport: str = typer.Option("stdio", help="stdio or streamable-http."),
    host: str = typer.Option("127.0.0.1", help="HTTP loopback bind host."),
    port: int = typer.Option(DEFAULT_MCP_PORT, help="HTTP bind port; endpoint is /mcp."),
    allow_network: bool = typer.Option(
        False, help="Server-owned HTTP model lookup/discovery permission."
    ),
    max_body_bytes: int = typer.Option(
        MAX_BODY_BYTES, help="Native SDK HTTP request-body cap in bytes."
    ),
    max_sessions: int = typer.Option(
        DEFAULT_MAX_SESSIONS, help="Native SDK concurrent HTTP session cap."
    ),
    session_idle_timeout: float = typer.Option(
        DEFAULT_SESSION_IDLE_TIMEOUT, help="Native SDK HTTP session idle timeout in seconds."
    ),
    max_workers: int = typer.Option(
        DEFAULT_WORKERS, help="Fixed HTTP synchronous-tool admission capacity (1-16)."
    ),
    tool_timeout: float = typer.Option(
        DEFAULT_TOOL_TIMEOUT, help="HTTP tool response timeout; underlying work retains capacity."
    ),
) -> None:
    """Run the ChimeraForge MCP server over stdio or loopback Streamable HTTP.

    Exposes plan / resolve-model / list-hardware tools to any MCP client so an
    assistant answers deployment questions from measured data, not stale guesses.
    Requires the ``mcp`` extra: pip install "chimeraforge[mcp]".
    """
    from chimeraforge.mcp_server import main
    from chimeraforge.mcp_transport import MCPHTTPSettings

    try:
        if transport == "stdio":
            if allow_network:
                raise ValueError("--allow-network configures Streamable HTTP only")
            main()
        elif transport == "streamable-http":
            settings = MCPHTTPSettings(
                host=host,
                port=port,
                allow_network=allow_network,
                max_body_bytes=max_body_bytes,
                max_sessions=max_sessions,
                session_idle_timeout=session_idle_timeout,
                max_workers=max_workers,
                tool_timeout=tool_timeout,
            )
            main(transport=transport, http_settings=settings)
        else:
            raise ValueError("transport must be stdio or streamable-http")
    except (RuntimeError, ValueError) as exc:
        console.print(f"[red]Error:[/] {escape(str(exc))}")
        raise typer.Exit(code=1)
