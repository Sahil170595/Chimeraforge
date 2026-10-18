"""CLI dispatch, output admission and bounded failures for the signed native gate."""

import json
from pathlib import Path
from typing import get_type_hints

import pytest
from typer.testing import CliRunner

from chimeraforge import api
from chimeraforge.cli import app
from chimeraforge.contrib import ContribError


def argv(output="decision.json"):
    return [
        "contribute",
        "gate",
        "--baseline",
        "first.json",
        "--baseline",
        "first.json",
        "--candidate",
        "second.json",
        "--trusted-key",
        "receiver.pub",
        "--policy",
        "policy.json",
        "--out",
        str(output),
        "--json",
    ]


def test_signed_gate_public_api_returns_existing_receipt_type():
    assert get_type_hints(api.gate_signed_contributions)["return"] is api.SignedContributionReceipt


@pytest.mark.parametrize("code", [0, 1, 3])
def test_gate_preserves_order_repeats_explicit_keys_and_result(code, tmp_path, monkeypatch):
    calls = []
    output = tmp_path / "decision.json"

    def gate(baseline, candidate, *, trusted_keys, policy):
        calls.append((baseline, candidate, trusted_keys, policy))
        return api.SignedContributionReceipt({"status": "conditional_pass", "exit_code": code})

    monkeypatch.setattr(api, "gate_signed_contributions", gate, raising=False)
    result = CliRunner().invoke(app, argv(output))
    assert result.exit_code == code, result.output
    assert calls == [
        (
            [Path("first.json"), Path("first.json")],
            [Path("second.json")],
            (Path("receiver.pub"),),
            Path("policy.json"),
        )
    ]
    assert json.loads(result.stdout)["exit_code"] == code
    assert json.loads(output.read_text())["exit_code"] == code


@pytest.mark.parametrize("protected", ["first.json", "second.json", "receiver.pub", "policy.json"])
def test_gate_protects_all_declared_paths_before_consumption(protected, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("aliased output reached consumption")

    monkeypatch.setattr(api, "gate_signed_contributions", refuse, raising=False)
    result = CliRunner().invoke(app, argv(protected))
    assert result.exit_code == 2, result.output
    assert "cannot replace" in json.loads(result.stdout)["error"]


def test_gate_refuses_private_domain_error_without_reflecting_input(monkeypatch):
    def refuse(*args, **kwargs):
        raise ContribError("PRIVATE payload and provider contents")

    monkeypatch.setattr(api, "gate_signed_contributions", refuse, raising=False)
    result = CliRunner().invoke(app, argv())
    assert result.exit_code == 2, result.output
    assert json.loads(result.stdout) == {
        "error": "invalid signed gate input, policy or trusted key"
    }
    assert "PRIVATE" not in result.output


def test_gate_failed_save_cannot_emit_success(tmp_path, monkeypatch):
    output = tmp_path / "decision.json"
    output.write_bytes(b"prior")

    class Receipt:
        def save(self, path):
            raise ContribError("PRIVATE filesystem detail")

        def to_dict(self):
            raise AssertionError("success emitted after failed save")

    monkeypatch.setattr(api, "gate_signed_contributions", lambda *a, **kw: Receipt(), raising=False)
    result = CliRunner().invoke(app, argv(output))
    assert result.exit_code == 2, result.output
    assert json.loads(result.stdout) == {"error": "signed contribution output failed"}
    assert output.read_bytes() == b"prior"
