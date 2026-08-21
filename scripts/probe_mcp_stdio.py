"""Probe an MCP stdio server and assert it answers introspection.

Building an image proves it installs. This proves it actually *serves*: an MCP
image is only useful if a client can initialize and list tools over stdio. Kept as
a committed script rather than inline CI YAML so it is readable, reusable against
any command, and not a nested-heredoc puzzle.

    python scripts/probe_mcp_stdio.py -- docker run --rm -i chimeraforge:ci
    python scripts/probe_mcp_stdio.py -- chimeraforge mcp
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

EXPECTED_TOOLS = {
    "chimeraforge_plan",
    "chimeraforge_resolve_model",
    "chimeraforge_list_hardware",
}
# Minimal client handshake: initialize, acknowledge, then ask what tools exist.
REQUESTS = [
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "chimeraforge-probe", "version": "1"},
        },
    },
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
]


def probe(command: list[str], timeout: float = 120.0) -> tuple[dict, list[str]]:
    """Run `command` as an MCP stdio server; return (serverInfo, tool names)."""
    stdin = "".join(json.dumps(r) + "\n" for r in REQUESTS)
    proc = subprocess.run(command, input=stdin, capture_output=True, text=True, timeout=timeout)
    server_info: dict = {}
    tools: list[str] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        # The server interleaves log lines with JSON-RPC; skip anything not a message.
        if not line.startswith("{"):
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        result = msg.get("result") or {}
        if "serverInfo" in result:
            server_info = result["serverInfo"]
        if "tools" in result:
            tools = [t["name"] for t in result["tools"]]
    if not server_info and not tools:
        sys.stderr.write(proc.stderr[-2000:])
        raise SystemExit(f"no JSON-RPC response from {' '.join(command)} (exit {proc.returncode})")
    return server_info, tools


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--expect-version", help="Assert serverInfo.version equals this.")
    ap.add_argument("command", nargs=argparse.REMAINDER, help="-- <server command>")
    args = ap.parse_args(argv)
    command = [a for a in args.command if a != "--"]
    if not command:
        ap.error("give the server command after --")

    info, tools = probe(command)
    print(f"serverInfo: {info}")
    print(f"tools: {tools}")

    missing = EXPECTED_TOOLS - set(tools)
    if missing:
        print(f"::error::introspection missing tools: {sorted(missing)}")
        return 1
    if args.expect_version and info.get("version") != args.expect_version:
        # A wrong version is worse than none: clients display it as fact.
        print(
            f"::error::serverInfo.version is {info.get('version')!r}, "
            f"expected {args.expect_version!r}"
        )
        return 1
    print("introspection OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
