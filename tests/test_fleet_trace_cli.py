"""Public CLI admission precedes connections and protects every held input."""

from __future__ import annotations

from dataclasses import asdict
import json
import os

import pytest
from typer.testing import CliRunner

from chimeraforge.cli import app
from test_fleet_trace import Node, endpoints, routes, scene as scene, workload
from test_fleet_monitor import native_fleet as native_fleet


def arguments(native_fleet, tmp_path):
    saved, indices = native_fleet
    selected = indices["vllm"]
    requests = workload(saved, selected)
    plan, work, routing = (tmp_path / name for name in ("plan.json", "work.json", "routes.json"))
    saved.save(plan)
    work.write_text(json.dumps([asdict(row) for row in requests]), encoding="utf-8")
    routing.write_text(json.dumps([asdict(row) for row in routes(requests)]), encoding="utf-8")
    args = [
        "trace-fleet",
        str(work),
        "--from-plan",
        str(plan),
        "--candidate-index",
        str(selected),
        "--routes",
        str(routing),
        "--json",
    ]
    for endpoint in endpoints():
        args.extend(["--endpoint", f"{endpoint.id}={endpoint.url}"])
    return args, (plan, work, routing)


def test_complete_cli_uses_same_native_population(native_fleet, scene, tmp_path):
    args, sources = arguments(native_fleet, tmp_path)
    before = [path.read_bytes() for path in sources]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["native_trace"]["execution"]["completed"] == 6
    assert [path.read_bytes() for path in sources] == before
    assert all(node.closed for node in scene.created)


def test_non_json_complete_execution_reports_known_mismatch(
    native_fleet, scene, tmp_path, monkeypatch
):
    original = Node.generate_observed

    async def wrong_tokens(node, *args):
        observed = await original(node, *args)
        observed.native["prompt_tokens"] = 1
        return observed

    monkeypatch.setattr(Node, "generate_observed", wrong_tokens)
    args, _ = arguments(native_fleet, tmp_path)
    args.remove("--json")
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 1, result.output
    assert "Completed 6/6 requests" in result.stdout
    assert "execution=completed" in result.stdout and "configuration=mismatch" in result.stdout
    assert (
        "slo=" in result.stdout
        and "cleanup=completed" in result.stdout
        and "exit=1" in result.stdout
    )
    assert "PRIVATE" not in result.output and all(node.closed for node in scene.created)


@pytest.mark.parametrize("source_index", [0, 1, 2])
def test_cli_output_cannot_replace_actual_inputs(native_fleet, scene, tmp_path, source_index):
    args, sources = arguments(native_fleet, tmp_path)
    before = [path.read_bytes() for path in sources]
    result = CliRunner().invoke(app, args + ["--out", str(sources[source_index])])
    assert result.exit_code == 2, result.output
    assert json.loads(result.stdout) == {"error": "invalid or unavailable original-fleet trace"}
    assert not scene.created and [path.read_bytes() for path in sources] == before


@pytest.mark.parametrize("field", ["--ca-bundle", "--client-cert", "--client-key"])
@pytest.mark.parametrize("hardlink", [False, True])
def test_cli_output_cannot_replace_explicit_tls_inputs(
    native_fleet, scene, tmp_path, field, hardlink
):
    args, _ = arguments(native_fleet, tmp_path)
    private = tmp_path / "PRIVATE_TLS_PATH_CANARY.pem"
    private.write_bytes(b"PRIVATE INPUT BYTES")
    output = private
    if hardlink:
        output = tmp_path / "alias.pem"
        os.link(private, output)
    result = CliRunner().invoke(app, args + [field, f"member-0={private}", "--out", str(output)])
    assert result.exit_code == 2, result.output
    assert json.loads(result.stdout) == {"error": "invalid or unavailable original-fleet trace"}
    assert "PRIVATE" not in result.output and not scene.created
    assert private.read_bytes() == b"PRIVATE INPUT BYTES"
