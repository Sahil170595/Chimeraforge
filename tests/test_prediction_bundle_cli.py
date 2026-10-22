"""CLI admission and private handoff messaging; core/installed validation is separate."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from chimeraforge import api
from chimeraforge.cli import app


def test_prediction_bundle_public_api_exports_concrete_defensive_types():
    from typing import get_type_hints

    assert get_type_hints(api.create_prediction_bundle)["return"] is api.PredictionBundle
    assert get_type_hints(api.verify_prediction_bundle)["return"] is api.PredictionBundle
    assert get_type_hints(api.score_prediction_bundle)["return"] is api.PredictionScorecard


@pytest.mark.parametrize("receipts", [[], ["first.json", "second.json", "first.json"]])
def test_prediction_create_keeps_explicit_receipt_population_and_private_warning(
    receipts, monkeypatch
):
    calls = []

    class Bundle:
        def to_dict(self):
            return {
                "kind": "chimeraforge.prediction-bundle-verification",
                "status": "verified_content",
                "plan_fingerprint": "a" * 64,
                "receipt_count": len(receipts),
                "private_handoff": True,
                "limits": "Private handoff; raw receipts may contain prompts/options.",
            }

    def create(saved, benchmark_paths, *, policy, outdir):
        calls.append((saved, benchmark_paths, policy, outdir))
        return Bundle()

    monkeypatch.setattr(api, "create_prediction_bundle", create, raising=False)
    argv = [
        "bundle",
        "prediction-create",
        "plan.json",
        "--policy",
        "policy.json",
        "--out",
        "private",
    ]
    for receipt in receipts:
        argv.extend(["--benchmark", receipt])
    result = CliRunner().invoke(app, [*argv, "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["receipt_count"] == len(receipts)
    assert calls == [
        (Path("plan.json"), list(map(Path, receipts)), Path("policy.json"), Path("private"))
    ]
    human = CliRunner().invoke(app, argv)
    assert human.exit_code == 0, human.output
    assert "Private handoff" in human.stdout


@pytest.mark.parametrize("command", ["prediction-create", "prediction-verify", "prediction-score"])
def test_prediction_bundle_domain_errors_are_bounded_json(command, monkeypatch):
    def refuse(*args, **kwargs):
        raise api.PlanError("invalid prediction bundle input")

    names = {
        "prediction-create": "create_prediction_bundle",
        "prediction-verify": "verify_prediction_bundle",
        "prediction-score": "score_prediction_bundle",
    }
    monkeypatch.setattr(api, names[command], refuse, raising=False)
    argv = ["bundle", command, "source", "--json"]
    if command == "prediction-create":
        argv.extend(["--policy", "policy.json", "--out", "private"])
    result = CliRunner().invoke(app, argv)
    assert result.exit_code == 2, result.output
    assert json.loads(result.stdout) == {"error": "invalid prediction bundle input"}


def test_prediction_score_protects_bundle_root_before_consumption(tmp_path, monkeypatch):
    bundle = tmp_path / "private"
    bundle.mkdir()

    def score(*args, **kwargs):
        raise AssertionError("output aliases reached bundle consumption")

    monkeypatch.setattr(api, "score_prediction_bundle", score, raising=False)
    result = CliRunner().invoke(
        app, ["bundle", "prediction-score", str(bundle), "--out", str(bundle), "--json"]
    )
    assert result.exit_code == 2, result.output
    assert "cannot replace" in json.loads(result.stdout)["error"]


def test_prediction_score_save_failure_preserves_previous_output(tmp_path, monkeypatch):
    output = tmp_path / "score.json"
    output.write_bytes(b"prior score")

    class Score:
        def save(self, path):
            assert path == output
            raise api.PlanError("invalid prediction score output")

        def to_dict(self):
            raise AssertionError("failed save emitted a successful score")

    monkeypatch.setattr(api, "score_prediction_bundle", lambda *_: Score(), raising=False)
    result = CliRunner().invoke(
        app,
        ["bundle", "prediction-score", str(tmp_path / "private"), "--out", str(output), "--json"],
    )
    assert result.exit_code == 2, result.output
    assert json.loads(result.stdout) == {"error": "invalid prediction score output"}
    assert output.read_bytes() == b"prior score"
