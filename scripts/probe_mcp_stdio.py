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
import queue
import subprocess
import sys
import threading
import time

TOOLS_REQUEST_ID = 2
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
    {"jsonrpc": "2.0", "id": TOOLS_REQUEST_ID, "method": "tools/list"},
]


def probe(command: list[str], timeout: float = 120.0) -> tuple[dict, list[str]]:
    """Run `command` as an MCP stdio server; return (serverInfo, tool names).

    stdin is held open until the response we asked for arrives. Writing the three
    requests and immediately closing stdin looks like it works -- `initialize` gets
    answered -- but the server sees EOF and shuts down before flushing the
    `tools/list` reply, so the probe reports zero tools against a perfectly healthy
    server. That race is timing-dependent: it passed locally and failed in CI.
    """
    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    lines: queue.Queue[str | None] = queue.Queue()

    def _pump() -> None:
        # A dedicated reader keeps a silent server from blocking us forever: the
        # deadline below is enforced on the queue, not on a blocking readline.
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.put(line)
        lines.put(None)

    reader = threading.Thread(target=_pump, daemon=True)
    reader.start()

    server_info: dict = {}
    tools: list[str] = []
    seen_tools_reply = False
    try:
        assert proc.stdin is not None
        for request in REQUESTS:
            proc.stdin.write(json.dumps(request) + "\n")
            proc.stdin.flush()

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not seen_tools_reply:
            try:
                line = lines.get(timeout=1.0)
            except queue.Empty:
                continue
            if line is None:
                break
            line = line.strip()
            # The server interleaves log lines with JSON-RPC; skip non-messages.
            if not line.startswith("{"):
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            result = msg.get("result") or {}
            if "serverInfo" in result:
                server_info = result["serverInfo"]
            if msg.get("id") == TOOLS_REQUEST_ID:
                tools = [t["name"] for t in result.get("tools", [])]
                seen_tools_reply = True
    finally:
        # Only now is it safe to signal EOF; the server exits on its own.
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
        except OSError:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    if not seen_tools_reply:
        stderr = (proc.stderr.read() if proc.stderr else "") or ""
        sys.stderr.write(stderr[-2000:])
        raise SystemExit(
            f"no tools/list response from {' '.join(command)} within {timeout:.0f}s "
            f"(exit {proc.returncode})"
        )
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
