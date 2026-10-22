"""Envelope CLI admission protects named input populations before assessment."""

import json

import pytest
from typer.testing import CliRunner

from chimeraforge import api
from chimeraforge.cli import app


def test_public_envelope_api_has_a_concrete_defensive_result():
    from typing import get_type_hints

    assert get_type_hints(api.assess_trace_envelope)["return"] is api.RegressionGate


@pytest.mark.parametrize("assignments", [["cell"], ["=file.json"], ["cell="], ["cell=a", "cell=b"]])
def test_campaign_assignments_refuse_malformed_or_duplicate_names(assignments, monkeypatch):
    def assess(*args, **kwargs):
        raise AssertionError("invalid campaign assignments reached assessment")

    monkeypatch.setattr(api, "assess_trace_envelope", assess, raising=False)
    arguments = ["trace-envelope", "--cases", "cases.json", "--policy", "policy.json", "--json"]
    for value in assignments:
        arguments.extend(["--campaign", value])
    result = CliRunner().invoke(app, arguments)
    assert result.exit_code == 2, result.output
    assert json.loads(result.stdout)["error"]


@pytest.mark.parametrize("role", ["cases", "policy", "campaign"])
def test_output_cannot_replace_any_named_input(tmp_path, role, monkeypatch):
    paths = {name: tmp_path / f"{name}.json" for name in ("cases", "policy", "campaign")}
    for name, path in paths.items():
        path.write_bytes(f"PRIVATE INVALID {name}".encode())
    original = {path: path.read_bytes() for path in paths.values()}

    def assess(*args, **kwargs):
        raise AssertionError("output alias reached assessment")

    monkeypatch.setattr(api, "assess_trace_envelope", assess, raising=False)
    result = CliRunner().invoke(
        app,
        [
            "trace-envelope",
            "--cases",
            str(paths["cases"]),
            "--policy",
            str(paths["policy"]),
            "--campaign",
            f"observed={paths['campaign']}",
            "--out",
            str(paths[role]),
            "--json",
        ],
    )
    assert result.exit_code == 2, result.output
    assert "cannot replace" in json.loads(result.stdout)["error"]
    assert all(path.read_bytes() == raw for path, raw in original.items())


def test_campaign_path_may_contain_equals_and_empty_population_is_preserved(monkeypatch):
    seen = []

    class Decision:
        def to_dict(self):
            return {"outcome": "inconclusive", "exit_code": 3, "limits": "missing cells"}

    def assess(cases, campaigns, *, policy):
        seen.append((cases, campaigns, policy))
        return Decision()

    monkeypatch.setattr(api, "assess_trace_envelope", assess, raising=False)
    for arguments in ([], ["--campaign", "observed=file=part.json"]):
        result = CliRunner().invoke(
            app,
            [
                "trace-envelope",
                "--cases",
                "cases.json",
                "--policy",
                "policy.json",
                "--json",
                *arguments,
            ],
        )
        assert result.exit_code == 3, result.output
        assert json.loads(result.stdout)["outcome"] == "inconclusive"
    assert seen[0][1] == {}
    assert str(seen[1][1]["observed"]) == "file=part.json"
