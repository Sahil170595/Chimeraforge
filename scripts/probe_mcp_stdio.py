"""Exercise a real MCP stdio server using the supported MCP client SDK."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import timedelta

EXPECTED_TOOLS = {
    "chimeraforge_plan",
    "chimeraforge_resolve_model",
    "chimeraforge_list_hardware",
    "chimeraforge_compare_api",
    "chimeraforge_suggest",
}


def tool_payload(result) -> dict:
    """Accept SDK structured results or their JSON text representation."""
    assert not result.isError, f"MCP tool failed: {result.content}"
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured
    text = [block.text for block in result.content if block.type == "text"]
    assert len(text) == 1, f"expected one JSON result, got {result.content}"
    payload = json.loads(text[0])
    assert isinstance(payload, dict), f"expected a result object, got {payload!r}"
    return payload


async def exercise(
    command: list[str], timeout: float, cwd=None, env=None, checkpoint_request: dict | None = None
) -> tuple[dict, list[str]]:
    """Initialize, discover, invoke, and reject invalid requests over stdio."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    parameters = StdioServerParameters(command=command[0], args=command[1:], cwd=cwd, env=env)
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(
            read, write, read_timeout_seconds=timedelta(seconds=timeout)
        ) as session:
            initialized = await session.initialize()
            tools = [tool.name for tool in (await session.list_tools()).tools]
            assert EXPECTED_TOOLS <= set(tools), f"missing MCP tools: {EXPECTED_TOOLS - set(tools)}"
            hardware = tool_payload(await session.call_tool("chimeraforge_list_hardware", {}))
            assert hardware["ok"] and hardware["count"] == len(hardware["gpus"]) > 0
            assert any(row["name"] == "RTX 4080 12GB" for row in hardware["gpus"])
            model = tool_payload(
                await session.call_tool(
                    "chimeraforge_resolve_model", {"model": "llama3.2-3b", "allow_network": False}
                )
            )
            assert model["ok"] and model["params_b"] > 0 and model["n_layers"] > 0
            plan = tool_payload(
                await session.call_tool(
                    "chimeraforge_plan",
                    {
                        "hardware": "RTX 4080 12GB",
                        "model_size": "3b",
                        "request_rate": 0.01,
                        "allow_network": False,
                    },
                )
            )
            assert plan["ok"] and plan["recommended"] and plan["recommended"]["provenance"]
            assert plan["recommended"]["total_throughput_tps"] > 0
            if checkpoint_request is not None:
                repo, commit = checkpoint_request["repo"], checkpoint_request["commit"]
                bound = tool_payload(
                    await session.call_tool(
                        "chimeraforge_plan",
                        {
                            "hardware": "RTX 4080 12GB",
                            "model": repo,
                            "model_revisions": {repo: commit},
                            "allow_network": False,
                            "quality_target": 0,
                            "request_rate": 0.01,
                        },
                    )
                )
                assert bound["ok"] and bound["recommended"]
                assert bound["model_checkpoints"][repo]["resolved_revision"] == commit
                assert bound["model_checkpoints"][repo]["weight_bytes_verified"] is False
                resolved = tool_payload(
                    await session.call_tool(
                        "chimeraforge_resolve_model",
                        {
                            "model": repo,
                            "hf_revision": commit,
                            "allow_network": False,
                        },
                    )
                )
                assert resolved["ok"] and resolved["checkpoint"]["resolved_revision"] == commit
            error = tool_payload(
                await session.call_tool(
                    "chimeraforge_plan",
                    {
                        "hardware": "ci-unknown-gpu",
                        "allow_network": False,
                    },
                )
            )
            assert error["ok"] is False and "unknown GPU" in error["error"]
            invalid = await session.call_tool("chimeraforge_plan", {})
            assert invalid.isError, "missing required hardware unexpectedly succeeded"
            unknown = await session.call_tool("ci_nonexistent_tool", {})
            assert unknown.isError, "unknown MCP tool unexpectedly succeeded"
            return initialized.serverInfo.model_dump(), tools


def probe(
    command: list[str],
    timeout: float = 120,
    *,
    cwd=None,
    env=None,
    checkpoint_request: dict | None = None,
) -> tuple[dict, list[str]]:
    """Bound the entire client/server conversation, including silent servers."""

    async def bounded():
        return await asyncio.wait_for(
            exercise(command, timeout, cwd, env, checkpoint_request), timeout=timeout
        )

    return asyncio.run(bounded())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect-version")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("give the server command after --")
    info, tools = probe(command, args.timeout)
    if args.expect_version:
        assert info.get("version") == args.expect_version, (info, args.expect_version)
    print(json.dumps({"serverInfo": info, "tools": tools, "tool_calls": "passed"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
