"""Closed JUnit projection of one finalized ordinary or whole-fleet envelope."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from xml.etree import ElementTree as ET

import pytest
from typer.testing import CliRunner

from chimeraforge import api
from chimeraforge.bench.gate import RegressionGate
from chimeraforge.cli import app
from chimeraforge.planner.replay import digest
from test_fleet_trace_envelope import population as population, produce
from test_trace_envelope import assess, declarations, finish, pack, reseal, uniform


def xml_cases(result, tmp_path):
    path = tmp_path / "assessment.xml"
    api.write_trace_envelope(result, junit=path)
    suite = ET.fromstring(path.read_bytes())
    return suite, {case.attrib["name"]: case for case in suite}


def breached_campaign():
    high = uniform(0.05)
    row = high["replicas"][2]["receipt"]["requests"][1]
    row["times"]["terminal_s"] = row["times"]["scheduled_s"] + 3.0
    return pack(high)


def test_finalized_ordinary_envelope_writes_native_json_and_closed_junit(tmp_path):
    result = assess()
    expected = result.to_dict()
    out, junit = tmp_path / "assessment.json", tmp_path / "assessment.xml"
    api.write_trace_envelope(result, out=out, junit=junit)
    assert json.loads(out.read_bytes()) == expected == result.to_dict()
    suite = ET.fromstring(junit.read_bytes())
    assert suite.attrib["tests"] == "9"
    assert suite.attrib["errors"] == suite.attrib["failures"] == "0"
    assert [case.attrib["name"] for case in suite] == [
        "overall",
        "cell-0",
        "cell-0.execution-0",
        "cell-0.execution-1",
        "cell-0.execution-2",
        "cell-1",
        "cell-1.execution-0",
        "cell-1.execution-1",
        "cell-1.execution-2",
    ]
    assert b"PRIVATE" not in junit.read_bytes() and b"slow" not in junit.read_bytes()


def test_missing_higher_cell_keeps_lower_passing_cases(tmp_path):
    result = assess({"slow": uniform()})
    junit = tmp_path / "assessment.xml"
    api.write_trace_envelope(result, junit=junit)
    suite = ET.fromstring(junit.read_bytes())
    assert result.to_dict()["exit_code"] == 3
    cases = {case.attrib["name"]: case for case in suite}
    assert cases["overall"].find("error") is not None
    assert cases["cell-0"].find("error") is None
    assert all(cases[f"cell-0.execution-{index}"].find("error") is None for index in range(3))
    assert cases["cell-1"].find("error") is not None


def test_cli_junit_is_optional_and_keeps_native_stdout(tmp_path):
    cases, policy = declarations()
    inputs = {"cases": cases, "policy": policy, "slow": uniform(), "fast": uniform(0.05)}
    paths = {name: tmp_path / f"{name}.json" for name in inputs}
    for name, value in inputs.items():
        paths[name].write_text(json.dumps(value), encoding="utf-8")
    junit = tmp_path / "assessment.xml"
    args = [
        "trace-envelope",
        "--cases",
        str(paths["cases"]),
        "--policy",
        str(paths["policy"]),
        "--campaign",
        f"slow={paths['slow']}",
        "--campaign",
        f"fast={paths['fast']}",
        "--json",
    ]
    legacy = CliRunner().invoke(app, args)
    current = CliRunner().invoke(app, [*args, "--junit", str(junit)])
    assert legacy.exit_code == current.exit_code == 0, current.output
    left, right = json.loads(legacy.stdout), json.loads(current.stdout)
    left.pop("created_at")
    left.pop("fingerprint")
    right.pop("created_at")
    right.pop("fingerprint")
    assert left == right and ET.fromstring(junit.read_bytes()).attrib["tests"] == "9"


def test_known_breach_keeps_complete_sibling_execution_passing(tmp_path):
    result = assess({"slow": uniform(), "fast": breached_campaign()})
    suite, cases = xml_cases(result, tmp_path)
    assert suite.attrib["failures"] == "3" and suite.attrib["errors"] == "0"
    assert cases["overall"].find("failure") is not None
    assert cases["cell-1"].find("failure") is not None
    for index in (0, 1):
        assert cases[f"cell-1.execution-{index}"].find("failure") is None
        assert cases[f"cell-1.execution-{index}"].find("error") is None
    assert cases["cell-1.execution-2"].find("failure") is not None


def test_known_breach_survives_simultaneous_missing_clock(tmp_path):
    high = breached_campaign()
    for slot in high["replicas"]:
        slot["receipt"]["clock"]["origin"] = None
        slot["receipt"]["execution"]["elapsed_seconds"] = None
        finish(slot["receipt"])
    reseal(high)
    result = assess({"slow": uniform(), "fast": high})
    suite, cases = xml_cases(result, tmp_path)
    assert suite.attrib["failures"] == "3" and suite.attrib["errors"] == "5"
    assert cases["cell-1.execution-2"].find("failure") is not None
    assert cases["cell-1.execution-2"].find("error") is not None
    assert cases["cell-0"].find("error") is None


@pytest.mark.parametrize("required", [False, True])
def test_unknown_control_only_blocks_when_required(tmp_path, required):
    low = uniform()
    for slot in low["replicas"]:
        for phase in ("serving_before", "serving_after"):
            slot["receipt"][phase]["context_length"] = None
    pack(low)
    _, policy = declarations()
    policy["fixed_controls"] = {"context_length": 2048} if required else {}
    result = assess({"slow": low, "fast": uniform(0.05)}, policy=policy)
    suite, cases = xml_cases(result, tmp_path)
    assert int(suite.attrib["errors"]) == (5 if required else 0)
    assert cases["cell-1"].find("error") is None


def test_global_incompatibility_prevents_execution_passes(tmp_path):
    high = uniform(0.05)
    for slot in high["replicas"]:
        slot["receipt"]["serving_after"]["context_length"] = 4096
    pack(high)
    suite, _ = xml_cases(assess({"slow": uniform(), "fast": high}), tmp_path)
    assert suite.attrib["errors"] == "9"


def test_cell_names_with_colons_never_become_xml_identifiers_or_global_blocks(tmp_path):
    cases, policy = declarations()
    names = ["PRIVATE:low<>&", "PRIVATE:high<>&"]
    for cell, name in zip(cases["cells"], names):
        cell["name"] = name
    result = assess({names[0]: uniform()}, cases=cases, policy=policy)
    _, nodes = xml_cases(result, tmp_path)
    assert nodes["cell-0"].find("error") is None
    assert b"PRIVATE" not in (tmp_path / "assessment.xml").read_bytes()


def test_whole_fleet_json_retains_all_members_and_rows(population, tmp_path):
    plan, index, cases, policy, campaigns = population
    result = api.assess_fleet_trace_envelope(
        plan, cases, campaigns, policy=policy, candidate_index=index
    )
    original = result.to_dict()
    out, junit = tmp_path / "fleet.json", tmp_path / "fleet.xml"
    api.write_trace_envelope(result, out=out, junit=junit)
    assert json.loads(out.read_bytes()) == original == result.to_dict()
    assert all(
        len(slot["members"]) == 3 and len(slot["rows"]) == 6
        for cell in original["cells"]
        for slot in cell["executions"]
    )
    suite = ET.fromstring(junit.read_bytes())
    assert (
        suite.attrib["tests"] == "7" and suite.attrib["errors"] == suite.attrib["failures"] == "0"
    )
    assert not any(
        value.encode() in junit.read_bytes()
        for value in (str(plan), "member-0", ".invalid", "lower", "higher")
    )


def test_fleet_missing_higher_preserves_lower_execution_passes(population, tmp_path):
    plan, index, cases, policy, campaigns = population
    result = api.assess_fleet_trace_envelope(
        plan, cases, {"lower": campaigns["lower"]}, policy=policy, candidate_index=index
    )
    suite, nodes = xml_cases(result, tmp_path)
    assert suite.attrib["errors"] == "4"
    assert all(
        nodes[name].find("error") is None
        for name in ("cell-0", "cell-0.execution-0", "cell-0.execution-1")
    )


def test_incomplete_fleet_still_validates_member_blocker_shape(population, tmp_path):
    plan, index, cases, policy, campaigns = population
    data = api.assess_fleet_trace_envelope(
        plan, cases, {"lower": campaigns["lower"]}, policy=policy, candidate_index=index
    ).to_dict()
    data["cells"][1]["executions"][0]["members"][0]["blockers"] = "PRIVATE-invalid-shape"
    data["fingerprint"] = digest(
        {key: value for key, value in data.items() if key != "fingerprint"}
    )
    with pytest.raises(api.PlanError):
        api.write_trace_envelope(RegressionGate(data), junit=tmp_path / "assessment.xml")
    assert not (tmp_path / "assessment.xml").exists()


@pytest.mark.parametrize("incomplete", [False, True])
def test_fleet_known_breach_does_not_fail_sibling_execution(
    population, tmp_path, monkeypatch, incomplete
):
    from test_fleet_trace import Node

    plan, index, cases, policy, campaigns = population
    generate = Node.generate_observed
    nodes = []

    async def mixed(node, *args):
        if node not in nodes:
            nodes.append(node)
        value = await generate(node, *args)
        if nodes.index(node) >= cases["original_replicas"]:
            value.native["eval_duration_ms"] = 2000 * (value.native["tokens_generated"] - 1)
            value.native["throughput_tps"] = 0.5
            return replace(value, mean_tpot_ms=2000)
        return value

    monkeypatch.setattr(Node, "generate_observed", mixed)
    high = produce(
        population,
        "controlled-mixed",
        facts_sequence={"version": [None, "controlled-source"]} if incomplete else None,
    )
    result = api.assess_fleet_trace_envelope(
        plan,
        cases,
        {"lower": campaigns["lower"], "higher": high},
        policy=policy,
        candidate_index=index,
    )
    suite, nodes = xml_cases(result, tmp_path)
    assert result.to_dict()["exit_code"] == (3 if incomplete else 1)
    assert suite.attrib["failures"] == "3"
    assert suite.attrib["errors"] == ("4" if incomplete else "0")
    assert nodes["cell-1.execution-0"].find("failure") is None
    assert nodes["cell-1.execution-1"].find("failure") is not None
    assert (nodes["cell-1.execution-1"].find("error") is not None) == incomplete
    assert nodes["cell-0"].find("error") is None


@pytest.mark.parametrize(
    "mutation", ["fingerprint", "kind", "shape", "boolean", "target", "nonfinite"]
)
@pytest.mark.parametrize("junit_requested", [False, True])
def test_invalid_finalized_assessment_refuses_before_either_write(
    tmp_path, mutation, junit_requested
):
    data = assess().to_dict()
    if mutation == "fingerprint":
        data["fingerprint"] = "0" * 64
    else:
        if mutation == "kind":
            data["kind"] = "PRIVATE-other-decision"
        elif mutation == "shape":
            data["cells"][0]["replicas"].pop()
        elif mutation == "boolean":
            data["exit_code"] = False
        elif mutation == "target":
            data["policy"]["targets"]["PRIVATE-target"] = 2
        else:
            data["cells"][0]["nominal_rate_rps"] = float("inf")
        if mutation != "nonfinite":
            data["fingerprint"] = digest(
                {key: value for key, value in data.items() if key != "fingerprint"}
            )
    out, junit = tmp_path / "output.json", tmp_path / "output.xml"
    out.write_bytes(b"original-json")
    junit.write_bytes(b"original-xml")
    with pytest.raises(api.PlanError, match="complete trace envelope") as error:
        api.write_trace_envelope(
            RegressionGate(data), out=out, junit=junit if junit_requested else None
        )
    assert "PRIVATE" not in str(error.value)
    assert out.read_bytes() == b"original-json" and junit.read_bytes() == b"original-xml"


def test_xml_cap_admits_complete_buffer_before_any_publication(tmp_path, monkeypatch):
    from chimeraforge.bench import trace_envelope_output

    monkeypatch.setattr(trace_envelope_output, "MAX_JUNIT_BYTES", 100)
    out = tmp_path / "assessment.json"
    with pytest.raises(api.PlanError):
        api.write_trace_envelope(assess(), out=out, junit=tmp_path / "assessment.xml")
    assert not out.exists()


def large_native_envelope():
    cases, policy = declarations()
    cases["expected_replicates"] = 16
    cases["cells"] = [
        {"name": f"private-cell-{index}", "arrival_interval_seconds": 0.1 / (index + 1)}
        for index in range(16)
    ]
    durations = tuple(0.12 + index * 0.001 for index in range(16))
    campaigns = {
        cell["name"]: uniform(cell["arrival_interval_seconds"], durations=durations)
        for cell in cases["cells"]
    }
    result = assess(campaigns, cases=cases, policy=policy)
    assert result.to_dict()["exit_code"] == 0
    return result


def test_json_only_large_population_does_not_materialize_unrequested_xml(tmp_path, monkeypatch):
    from chimeraforge.bench import trace_envelope_output

    result = large_native_envelope()
    expected = result.to_dict()
    original_element = trace_envelope_output.ET.Element
    created_xml = []

    def track_xml(*args, **kwargs):
        created_xml.append(1)
        return original_element(*args, **kwargs)

    monkeypatch.setattr(trace_envelope_output.ET, "Element", track_xml)
    out = tmp_path / "assessment.json"
    api.write_trace_envelope(result, out=out)
    assert json.loads(out.read_bytes()) == expected == result.to_dict()
    assert out.read_bytes() == (json.dumps(expected, indent=2, allow_nan=False) + "\n").encode()
    assert not created_xml and not list(tmp_path.glob("*.xml"))


def test_real_complete_xml_limit_refuses_without_losing_population(tmp_path, monkeypatch):
    from chimeraforge.bench import trace_envelope_output

    result = large_native_envelope()
    out, junit = tmp_path / "assessment.json", tmp_path / "assessment.xml"
    out.write_bytes(b"original-json")
    junit.write_bytes(b"original-xml")
    with pytest.raises(api.PlanError):
        api.write_trace_envelope(result, out=out, junit=junit)
    assert out.read_bytes() == b"original-json" and junit.read_bytes() == b"original-xml"
    monkeypatch.setattr(trace_envelope_output, "MAX_JUNIT_BYTES", 128 * 1024)
    _, complete = trace_envelope_output.materialize(result)
    assert len(complete) > 64 * 1024
    assert ET.fromstring(complete).attrib["tests"] == "273"


def test_second_file_failure_keeps_first_file_atomic_and_existing_directory(tmp_path):
    out, junit = tmp_path / "assessment.json", tmp_path / "existing-directory"
    junit.mkdir()
    result = assess()
    with pytest.raises(api.PlanError):
        api.write_trace_envelope(result, out=out, junit=junit)
    assert json.loads(out.read_bytes()) == result.to_dict()
    assert junit.is_dir() and not list(tmp_path.glob("*.tmp"))


def test_writer_requires_finalized_type_and_destination(tmp_path):
    with pytest.raises(api.PlanError):
        api.write_trace_envelope(assess())
    with pytest.raises(api.PlanError):
        api.write_trace_envelope(api.PlanArtifact(assess().to_dict()), junit=tmp_path / "out.xml")
    with pytest.raises(api.PlanError):
        api.write_trace_envelope(api.PlanArtifact(assess().to_dict()), out=tmp_path / "out.json")


@pytest.mark.parametrize("hardlink", [False, True])
def test_mutual_output_alias_refuses_without_overwriting(tmp_path, hardlink):
    out = tmp_path / "assessment.json"
    out.write_bytes(b"original")
    junit = tmp_path / "assessment.xml" if hardlink else out
    if hardlink:
        os.link(out, junit)
    with pytest.raises(api.PlanError):
        api.write_trace_envelope(assess(), out=out, junit=junit)
    assert out.read_bytes() == junit.read_bytes() == b"original"


@pytest.mark.parametrize("destination", ["out", "junit"])
def test_late_consumed_input_guard_refuses_source_alias(tmp_path, destination):
    cases, policy = declarations()
    source = tmp_path / "campaign.json"
    source.write_text(json.dumps(uniform()), encoding="utf-8")
    original = source.read_bytes()
    result = api.assess_trace_envelope(
        cases, {"slow": source, "fast": uniform(0.05)}, policy=policy
    )
    with pytest.raises(api.PlanError):
        api.write_trace_envelope(result, **{destination: source})
    assert source.read_bytes() == original


def test_cli_guards_declared_input_before_assessment_and_assesses_once(tmp_path, monkeypatch):
    result = assess()
    calls = []

    def assess_once(*args, **kwargs):
        calls.append(1)
        return result

    monkeypatch.setattr(api, "assess_trace_envelope", assess_once)
    source = tmp_path / "declared.json"
    source.write_bytes(b"held")
    args = ["trace-envelope", "--cases", str(source), "--policy", str(source), "--json"]
    refused = CliRunner().invoke(app, [*args, "--junit", str(source)])
    assert refused.exit_code == 2 and not calls and source.read_bytes() == b"held"
    accepted = CliRunner().invoke(app, [*args, "--junit", str(tmp_path / "out.xml")])
    assert accepted.exit_code == 0 and calls == [1]
