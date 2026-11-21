"""Closed outputs preserve native inventory arithmetic and all declared slots."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import subprocess
import sys
from xml.etree import ElementTree as ET

import pytest
from typer.testing import CliRunner

from chimeraforge import api
from chimeraforge.cli import app
from test_deploy import artifact
from test_inventory_check import csv_row, uuid
from test_inventory_selected_batch import native_qwen


def supplied_result(tmp_path, *, total="4096", free="2048"):
    saved = artifact(candidate_changes={"vram_gb": 1.0})
    plan, capture = tmp_path / "PRIVATE-plan.json", tmp_path / "PRIVATE-inventory.csv"
    saved.save(plan)
    capture.write_text(csv_row(total=total, free=free), encoding="utf-8")
    result = asyncio.run(api.check_inventory(plan, gpu_devices=[uuid(0)], inventory_file=capture))
    return result, plan, capture


def test_writer_retains_native_json_and_closed_total_unknown_pass(tmp_path):
    result, _, _ = supplied_result(tmp_path, total="N/A")
    assert result.exit_code == 0 and result.slots[0].reasons
    native = result.to_dict()
    out, junit = tmp_path / "inventory.json", tmp_path / "inventory.xml"
    api.write_inventory_check(result, out=out, junit=junit)
    assert json.loads(out.read_bytes()) == json.loads(json.dumps(native))
    assert result.to_dict() == native
    suite = ET.fromstring(junit.read_bytes())
    assert suite.attrib["tests"] == "4"
    assert suite.attrib["errors"] == suite.attrib["failures"] == "0"
    assert [case.attrib["name"] for case in suite] == [
        "overall",
        "observation",
        "replica-0",
        "replica-0.device-0",
    ]
    assert not any(value in junit.read_bytes() for value in (b"PRIVATE", b"GPU-", b"NVIDIA"))


def test_private_roles_survive_replace_without_dataclass_serialization(tmp_path):
    result, plan, capture = supplied_result(tmp_path)
    public = result.to_dict()
    assert result._protected_paths == (plan, capture)
    assert result._declared_population == (1, 1, 1)
    copied = replace(result)
    assert asdict(copied) == asdict(result) and copied.to_dict() == public
    assert all(not key.startswith("_") for key in asdict(result))
    assert str(plan) not in json.dumps(asdict(result))
    assert str(capture) not in json.dumps(result.to_dict())
    original = capture.read_bytes()
    with pytest.raises(api.PlanError):
        api.write_inventory_check(copied, out=capture)
    assert capture.read_bytes() == original


@pytest.mark.parametrize("output_json", [False, True])
def test_cli_optional_outputs_keep_default_stdout_and_exit(tmp_path, output_json):
    native, plan, capture = supplied_result(tmp_path)
    args = [
        "inventory-check",
        "--plan",
        str(plan),
        "--gpu-device",
        uuid(0),
        "--inventory-file",
        str(capture),
    ]
    if output_json:
        args.append("--json")
    legacy = CliRunner().invoke(app, args)
    out, junit = tmp_path / "inventory.json", tmp_path / "inventory.xml"
    current = CliRunner().invoke(app, [*args, "--out", str(out), "--junit", str(junit)])
    assert legacy.exit_code == current.exit_code == 0, current.output
    assert legacy.stdout == current.stdout
    assert json.loads(out.read_bytes()) == json.loads(json.dumps(native.to_dict()))
    if output_json:
        assert json.loads(current.stdout) == json.loads(out.read_bytes())
    assert ET.fromstring(junit.read_bytes()).attrib["errors"] == "0"


def fleet_result(tmp_path, *, basis="batch-one", scenario="complete"):
    saved, index, plan = native_qwen(tmp_path, rate=128)
    assert saved.candidate(index).n_agents == 3
    capture = tmp_path / "PRIVATE-fleet.csv"
    rows = []
    for i in range(6):
        if scenario == "missing" and i == 5:
            continue
        free = (
            "0"
            if scenario in ("shortfall", "mixed") and i == 0
            else "N/A"
            if (scenario == "unknown" and i == 0 or scenario == "mixed" and i == 1)
            else "100000"
        )
        rows.append(csv_row(i, free=free, total="N/A" if scenario == "total_unknown" else "100000"))
    capture.write_text(
        "".join(rows) + ("PRIVATE-seventh-row\n" if scenario == "late_invalid" else ""),
        encoding="utf-8",
    )
    groups = [[str(2 * i), str(2 * i + 1)] for i in range(3)]
    result = asyncio.run(
        api.check_inventory(
            plan,
            candidate_index=index,
            replica_gpu_devices=groups,
            memory_basis=basis,
            inventory_file=capture,
        )
    )
    return result, plan, capture, index, groups


@pytest.mark.parametrize("basis", ["batch-one", "selected-batch"])
@pytest.mark.parametrize(
    "scenario,code,errors,failures",
    [
        ("complete", 0, 0, 0),
        ("late_invalid", 4, 11, 0),
        ("missing", 5, 0, 3),
        ("shortfall", 5, 0, 3),
        ("unknown", 4, 3, 0),
        ("mixed", 5, 3, 3),
        ("total_unknown", 0, 0, 0),
    ],
)
def test_original_six_slot_census_native_priority_and_actual_cli(
    tmp_path, basis, scenario, code, errors, failures
):
    result, plan, capture, index, groups = fleet_result(tmp_path, basis=basis, scenario=scenario)
    held = {path: path.read_bytes() for path in (plan, capture)}
    assert result.exit_code == code and result._declared_population == (3, 2, 1)
    out, junit = tmp_path / "result.json", tmp_path / "result.xml"
    api.write_inventory_check(result, out=out, junit=junit)
    suite = ET.fromstring(junit.read_bytes())
    assert suite.attrib["tests"] == "11"
    assert (int(suite.attrib["errors"]), int(suite.attrib["failures"])) == (errors, failures)
    assert len(result.slots) == 6
    assert [slot.selector for slot in result.slots] == list("012345")
    if scenario == "late_invalid":
        assert all(slot.selector_state == "unknown" for slot in result.slots)
        assert not result.observation.devices
    if scenario == "total_unknown":
        assert all(slot.reasons and slot.total_comparison == "unknown" for slot in result.slots)
    args = [
        "inventory-check",
        "--plan",
        str(plan),
        "--candidate-index",
        str(index),
        "--inventory-file",
        str(capture),
        "--memory-basis",
        basis,
        "--json",
    ]
    for group in groups:
        args += ["--replica-devices", ",".join(group)]
    cli_json, cli_xml = tmp_path / "cli.json", tmp_path / "cli.xml"
    run = subprocess.run(
        [
            sys.executable,
            "-I",
            "-m",
            "chimeraforge.cli",
            *args,
            "--out",
            str(cli_json),
            "--junit",
            str(cli_xml),
        ],
        cwd=tmp_path,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )
    assert run.returncode == code and not run.stderr
    assert (
        json.loads(run.stdout) == json.loads(out.read_bytes()) == json.loads(cli_json.read_bytes())
    )
    assert cli_xml.read_bytes() == junit.read_bytes()
    assert all(path.read_bytes() == raw for path, raw in held.items())
    assert not any(
        value in junit.read_bytes()
        for value in (b"PRIVATE", b"GPU-", b"NVIDIA", b"595.00", b"reason", str(tmp_path).encode())
    )


def test_live_cleanup_priority_preserves_known_failure(tmp_path, monkeypatch):
    from chimeraforge import inventory_process
    from test_inventory_check import process_fixture

    process_fixture(monkeypatch, csv_row(free="0").encode())
    result = asyncio.run(
        api.check_inventory(artifact(candidate_changes={"vram_gb": 1.0}), gpu_devices=["0"])
    )
    assert result.exit_code == 5 and result.observation.cleanup_state == "completed"
    incomplete = replace(result, observation=replace(result.observation, cleanup_state="failed"))
    assert incomplete.exit_code == 4 and incomplete._protected_paths == ()
    junit = tmp_path / "live.xml"
    api.write_inventory_check(incomplete, junit=junit)
    suite = ET.fromstring(junit.read_bytes())
    assert suite.attrib["errors"] == "4" and suite.attrib["failures"] == "3"
    assert (
        b"sys.stdout" not in junit.read_bytes()
        and inventory_process.COMMAND[0].encode() not in junit.read_bytes()
    )


def test_object_source_never_invents_saved_plan_path(tmp_path):
    _, plan, capture = supplied_result(tmp_path)
    result = asyncio.run(
        api.check_inventory(api.load_plan(plan), gpu_devices=["0"], inventory_file=capture)
    )
    assert result._protected_paths == (capture,)
    assert asdict(replace(result)) == asdict(result)


@pytest.mark.parametrize(
    "mutation", ["truncated", "reordered", "ordinal", "dimensions", "schema", "basis"]
)
@pytest.mark.parametrize("xml", [False, True])
def test_invalid_frozen_population_refuses_requested_outputs(tmp_path, mutation, xml):
    result, _, _, _, _ = fleet_result(tmp_path)
    if mutation == "truncated":
        result = replace(result, slots=result.slots[:-1])
    elif mutation == "reordered":
        result = replace(result, slots=tuple(reversed(result.slots)))
    elif mutation == "ordinal":
        result = replace(
            result, slots=(replace(result.slots[0], device_index=False), *result.slots[1:])
        )
    elif mutation == "dimensions":
        result = replace(result, _population=(3, 1, 1))
    elif mutation == "schema":
        result = replace(result, schema_version=True)
    else:
        result = replace(
            result,
            slots=(
                replace(result.slots[0], free_comparison="at_least_selected_batch_estimate"),
                *result.slots[1:],
            ),
        )
    out, junit = tmp_path / "out.json", tmp_path / "out.xml"
    out.write_bytes(b"old-json")
    junit.write_bytes(b"old-xml")
    with pytest.raises(api.PlanError):
        api.write_inventory_check(result, out=out, junit=junit if xml else None)
    assert out.read_bytes() == b"old-json" and junit.read_bytes() == b"old-xml"


@pytest.mark.parametrize("source", ["plan", "capture"])
@pytest.mark.parametrize("hardlink", [False, True])
@pytest.mark.parametrize("destination", ["out", "junit"])
def test_replaced_sdk_result_preserves_actual_input_alias_guards(
    tmp_path, source, hardlink, destination
):
    result, plan, capture = supplied_result(tmp_path)
    source_path = plan if source == "plan" else capture
    sink = tmp_path / "alias" if hardlink else source_path
    if hardlink:
        os.link(source_path, sink)
    held = source_path.read_bytes()
    with pytest.raises(api.PlanError):
        api.write_inventory_check(replace(result), **{destination: sink})
    assert source_path.read_bytes() == held


@pytest.mark.parametrize(
    "kind", ["plan", "capture", "directory", "parent_file", "mutual", "hardlink"]
)
def test_cli_invalid_sink_precedes_asyncio_run(tmp_path, monkeypatch, kind):
    from chimeraforge.commands import inventory_check as command

    _, plan, capture = supplied_result(tmp_path)
    held = {path: path.read_bytes() for path in (plan, capture)}
    out = tmp_path / "out.json"
    if kind == "plan":
        out = plan
    elif kind == "capture":
        out = capture
    elif kind == "directory":
        out = tmp_path
    elif kind == "parent_file":
        out = capture / "out.json"
    elif kind == "hardlink":
        os.link(plan, out)
    calls = []

    def forbid_run(*args, **kwargs):
        calls.append(1)
        if args:
            args[0].close()
        raise AssertionError("observation must not start")

    monkeypatch.setattr(command.asyncio, "run", forbid_run)
    args = [
        "inventory-check",
        "--plan",
        str(plan),
        "--inventory-file",
        str(capture),
        "--gpu-device",
        "0",
        "--json",
        "--out",
        str(out),
    ]
    if kind == "mutual":
        args += ["--junit", str(out)]
    run = CliRunner().invoke(app, args)
    assert run.exit_code == 1 and not calls
    assert json.loads(run.stdout)["exit_code"] == 1
    assert all(path.read_bytes() == raw for path, raw in held.items())


def test_requested_xml_cap_and_json_only_generation(tmp_path, monkeypatch):
    from chimeraforge import inventory_output

    result, _, _ = supplied_result(tmp_path)
    monkeypatch.setattr(inventory_output, "MAX_JUNIT_BYTES", 1)
    out, junit = tmp_path / "out.json", tmp_path / "out.xml"
    out.write_bytes(b"old-json")
    junit.write_bytes(b"old-xml")
    with pytest.raises(api.PlanError):
        api.write_inventory_check(result, out=out, junit=junit)
    assert out.read_bytes() == b"old-json" and junit.read_bytes() == b"old-xml"

    def forbid_xml(*args, **kwargs):
        raise AssertionError("unrequested XML")

    monkeypatch.setattr(inventory_output.ET, "Element", forbid_xml)
    api.write_inventory_check(result, out=out)
    assert json.loads(out.read_bytes()) == json.loads(json.dumps(result.to_dict()))


def test_late_second_write_failure_keeps_native_sources_and_atomic_first(tmp_path, monkeypatch):
    result, plan, capture = supplied_result(tmp_path)
    held = {path: path.read_bytes() for path in (plan, capture)}
    out, junit = tmp_path / "out.json", tmp_path / "out.xml"
    junit.write_bytes(b"old-xml")
    native_replace = Path.replace

    def fail_xml(path, target):
        if Path(target) == junit:
            raise OSError("PRIVATE late failure")
        return native_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_xml)
    with pytest.raises(api.PlanError) as error:
        api.write_inventory_check(result, out=out, junit=junit)
    assert "PRIVATE" not in str(error.value)
    assert json.loads(out.read_bytes()) == json.loads(json.dumps(result.to_dict()))
    assert junit.read_bytes() == b"old-xml" and not list(tmp_path.glob("*.tmp"))
    assert all(path.read_bytes() == raw for path, raw in held.items())


@pytest.mark.parametrize("hardlink", [False, True])
def test_sdk_mutual_alias_refuses_without_overwrite(tmp_path, hardlink):
    result, _, _ = supplied_result(tmp_path)
    out = tmp_path / "same.json"
    out.write_bytes(b"old")
    junit = tmp_path / "same.xml" if hardlink else out
    if hardlink:
        os.link(out, junit)
    with pytest.raises(api.PlanError):
        api.write_inventory_check(result, out=out, junit=junit)
    assert out.read_bytes() == junit.read_bytes() == b"old"


def test_existing_installed_capture_consumer_exercises_both_bases_and_closed_outputs(tmp_path):
    from test_ci_acceptance import load_script

    _, plan, capture, index, groups = fleet_result(tmp_path)
    held = plan.read_bytes()
    load_script("ci_installed_acceptance")
    script = load_script("ci_inventory_check")
    args = ["inventory-check", "--plan", str(plan), "--candidate-index", str(index)]
    for group in groups:
        args += ["--replica-devices", ",".join(group)]
    result = script._accept_captured_inventory(
        tmp_path, dict(os.environ), args, capture.read_text()
    )
    assert len(result) == 14 and plan.read_bytes() == held
    assert {row["exit_code"] for row in result.values()} == {0, 4, 5}
    assert all(row["original_slots"] == 6 and row["junit_cases"] == 11 for row in result.values())


@pytest.mark.parametrize("n,tp,pp", [(2, 2, 3), (16, 8, 8)])
def test_native_admitted_tp_pp_population_and_real_xml_cap(tmp_path, monkeypatch, n, tp, pp):
    from chimeraforge import inventory_output

    saved = artifact(
        candidate_changes={
            "n_agents": n,
            "tensor_parallel": tp,
            "pipeline_parallel": pp,
            "gpus_total": n * tp * pp,
            "vram_gb": 1.0,
        }
    )
    groups = [[str(replica * tp * pp + index) for index in range(tp * pp)] for replica in range(n)]
    capture = tmp_path / "large.csv"
    capture.write_text(
        "".join(csv_row(i, total="100000", free="100000") for i in range(n * tp * pp)),
        encoding="utf-8",
    )
    result = asyncio.run(
        api.check_inventory(saved, replica_gpu_devices=groups, inventory_file=capture)
    )
    assert result._declared_population == (n, tp, pp)
    assert len(result.slots) == n * tp * pp
    assert [slot.selector for slot in result.slots] == [
        value for group in groups for value in group
    ]
    assert result.exit_code in (0, 4)
    out, junit = tmp_path / "out.json", tmp_path / "out.xml"
    if n == 16:
        out.write_bytes(b"old-json")
        junit.write_bytes(b"old-xml")
        with pytest.raises(api.PlanError):
            api.write_inventory_check(result, out=out, junit=junit)
        assert out.read_bytes() == b"old-json" and junit.read_bytes() == b"old-xml"
        monkeypatch.setattr(inventory_output, "MAX_JUNIT_BYTES", 1024 * 1024)
    _, xml = inventory_output._materialize(result, want_json=False, want_junit=True)
    suite = ET.fromstring(xml)
    assert int(suite.attrib["tests"]) == 2 + n + n * tp * pp
    if n == 16:
        assert len(xml) > 64 * 1024
    api.write_inventory_check(result, out=out)
    assert json.loads(out.read_bytes()) == json.loads(json.dumps(result.to_dict()))


def test_empty_manual_report_retains_native_unknown_and_writer_type_guards(tmp_path):
    result, _, _ = supplied_result(tmp_path)
    empty = replace(result, slots=(), _population=None)
    assert empty.exit_code == 4
    junit = tmp_path / "empty.xml"
    api.write_inventory_check(empty, junit=junit)
    suite = ET.fromstring(junit.read_bytes())
    assert suite.attrib["tests"] == "2" and suite.attrib["errors"] == "1"
    with pytest.raises(api.PlanError):
        api.write_inventory_check(result)
    with pytest.raises(api.PlanError):
        api.write_inventory_check(result.to_dict(), out=tmp_path / "invalid.json")
