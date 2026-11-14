"""Public CLI admission precedes connections and protects every held input."""

from __future__ import annotations

from dataclasses import asdict
import json
import os
import stat

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


LANES = ("ordinary", "plan", "serial-campaign", "fleet", "fleet-campaign")


def _receipt_arguments(native_fleet, tmp_path, lane):
    fleet_args, sources = arguments(native_fleet, tmp_path)
    plan, work, _ = sources
    single = [str(work), "--base-url", endpoints()[0].url, "--json"]
    if lane == "fleet":
        return fleet_args, sources
    if lane == "fleet-campaign":
        return ["trace-fleet-campaign", *fleet_args[1:], "--executions", "2"], sources
    if lane == "plan":
        return [
            "trace",
            *single,
            "--from-plan",
            str(plan),
            "--candidate-index",
            str(native_fleet[1]["vllm"]),
        ], sources
    if lane == "serial-campaign":
        return [
            "trace-campaign",
            *single,
            "--backend",
            "vllm",
            "--model",
            "controlled",
            "--replicates",
            "2",
        ], sources
    return ["trace", *single, "--backend", "vllm", "--model", "controlled"], sources


@pytest.mark.parametrize(
    "lane,shape",
    [
        *((lane, "directory") for lane in LANES),
        *((lane, "parent_file") for lane in LANES),
        *((lane, "missing_parent") for lane in LANES[:-1]),
    ],
)
def test_unusable_receipt_destination_refuses_before_backend(
    native_fleet, scene, tmp_path, lane, shape
):
    args, sources = _receipt_arguments(native_fleet, tmp_path, lane)
    before = [path.read_bytes() for path in sources]
    anchor = tmp_path / "output-anchor"
    if shape == "directory":
        anchor.mkdir()
        output = anchor
    else:
        if shape == "parent_file":
            anchor.write_bytes(b"protected parent file")
        output = anchor / "new-subdirectory" / "receipt.json"
    result = CliRunner().invoke(app, [*args, "--out", str(output)])
    assert not scene.created, "backend factory ran before refusing the destination"
    assert result.exit_code == 2 and "receipt output" in json.loads(result.stdout)["error"]
    assert [path.read_bytes() for path in sources] == before
    if shape == "directory":
        assert anchor.is_dir() and not list(anchor.iterdir())
    elif shape == "parent_file":
        assert anchor.read_bytes() == b"protected parent file"
    else:
        assert not anchor.exists()


def test_special_receipt_destination_refuses_before_backend(native_fleet, scene, tmp_path):
    args, _ = _receipt_arguments(native_fleet, tmp_path, "ordinary")
    if os.name == "nt":
        output = tmp_path / "COM1.json"
    else:
        output = tmp_path / "fifo"
        os.mkfifo(output)
    result = CliRunner().invoke(app, [*args, "--out", str(output)])
    assert not scene.created
    assert result.exit_code == 2 and "receipt output" in json.loads(result.stdout)["error"]
    if os.name != "nt":
        assert stat.S_ISFIFO(output.lstat().st_mode)


def test_fleet_campaign_preserves_native_parent_creation_after_replay(
    native_fleet, scene, tmp_path, monkeypatch
):
    from chimeraforge.bench import trace

    args, sources = _receipt_arguments(native_fleet, tmp_path, "fleet-campaign")
    before = [path.read_bytes() for path in sources]
    parent = tmp_path / "created-by-writer"
    output = parent / "nested" / "campaign.json"

    def factory(*a, **kw):
        assert not parent.exists()
        return scene.factory(*a, **kw)

    monkeypatch.setattr(trace, "get_backend", factory)
    result = CliRunner().invoke(app, [*args, "--out", str(output)])
    assert result.exit_code == 0, result.output
    assert result.stdout.encode() == output.read_bytes()
    assert len(scene.created) == 6 and all(node.closed for node in scene.created)
    assert [path.read_bytes() for path in sources] == before


def test_fleet_campaign_refuses_dangling_parent_link(native_fleet, scene, tmp_path):
    args, _ = _receipt_arguments(native_fleet, tmp_path, "fleet-campaign")
    missing = tmp_path / "missing-target"
    parent = tmp_path / "parent-link"
    try:
        parent.symlink_to(missing, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation unavailable")
    output = parent / "nested" / "receipt.json"
    result = CliRunner().invoke(app, [*args, "--out", str(output)])
    assert result.exit_code == 2 and "receipt output" in json.loads(result.stdout)["error"]
    assert not scene.created and parent.is_symlink() and not missing.exists()


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
