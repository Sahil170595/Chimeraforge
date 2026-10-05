import json
import math

import pytest
from typer.testing import CliRunner

from chimeraforge.cli import app


def test_public_plan_and_snapshot_roundtrip(tmp_path):
    from chimeraforge.api import PlanRequest, plan, load_plan

    artifact = plan(PlanRequest(allow_network=False))
    payload = artifact.to_dict()
    assert payload["schema_version"] == 1
    assert payload["inputs"]["request_rate"] == 1.0
    assert payload["result"]["candidates"][0]["provenance"]
    assert payload["result"]["platform"] == "linux"
    path = tmp_path / "plan.json"
    artifact.save(path)
    assert load_plan(path).to_dict() == payload
    assert artifact.candidate().model == payload["result"]["candidates"][0]["model"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"request_rate": -1},
        {"budget": math.nan},
        {"avg_tokens": True},
        {"models": "llama"},
        {"quality_target": 2},
        {"tensor_parallel": 0},
        {"workload_cv2": -1},
        {"session_turns": 0},
        {"platform": "amiga"},
    ],
)
def test_sdk_rejects_invalid_inputs_before_search(kwargs):
    from chimeraforge.api import PlanRequest, plan, PlanError

    with pytest.raises(PlanError):
        plan(PlanRequest(**kwargs))


def test_snapshot_redacts_credentials_and_detects_tampering(tmp_path):
    from chimeraforge.api import PlanRequest, plan, load_plan, PlanError

    artifact = plan(PlanRequest(hf_token="private-token", allow_network=False))
    path = tmp_path / "plan.json"
    artifact.save(path)
    assert "private-token" not in path.read_text()
    payload = json.loads(path.read_text())
    payload["inputs"]["request_rate"] = 99
    path.write_text(json.dumps(payload))
    with pytest.raises(PlanError, match="fingerprint"):
        load_plan(path)


def test_plan_save_keeps_existing_stdout_contract(tmp_path):
    path = tmp_path / "plan.json"
    result = CliRunner().invoke(app, ["plan", "--no-network", "--json", "--save", str(path)])
    assert result.exit_code == 0, result.output
    candidates = json.loads(result.stdout)
    payload = json.loads(path.read_text())
    assert payload["result"]["candidates"] == candidates


def test_snapshot_rejects_unknown_schema_and_duplicate_keys(tmp_path):
    from chimeraforge.api import load_plan, PlanError

    path = tmp_path / "plan.json"
    for text in ['{"schema_version":99}', '{"schema_version":1,"schema_version":1}']:
        path.write_text(text)
        with pytest.raises(PlanError):
            load_plan(path)


def test_public_request_matches_shared_core_defaults():
    import inspect
    from dataclasses import fields
    from chimeraforge.api import PlanRequest
    from chimeraforge.planner.service import run_plan

    request = PlanRequest()
    parameters = inspect.signature(run_plan).parameters
    assert {f.name for f in fields(request)} == set(parameters)
    for name, parameter in parameters.items():
        assert getattr(request, name) == parameter.default


def test_artifact_failures_are_actionable(tmp_path):
    from chimeraforge.api import PlanRequest, plan, load_plan, PlanError, artifact_from_dict
    import hashlib

    artifact = plan(PlanRequest(allow_network=False))
    with pytest.raises(PlanError, match="index"):
        artifact.candidate(-1)
    with pytest.raises(PlanError, match="cannot save"):
        artifact.save(tmp_path / "absent" / "plan.json")
    with pytest.raises(PlanError, match="invalid saved plan"):
        load_plan(tmp_path / "missing")
    data = artifact.to_dict()
    data["result"]["candidates"][0]["effective_batch"] = "two"
    body = {k: v for k, v in data.items() if k != "fingerprint"}
    data["fingerprint"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with pytest.raises(PlanError, match="effective_batch"):
        artifact_from_dict(data)


def test_url_credentials_are_removed():
    from chimeraforge.api import PlanRequest, plan

    artifact = plan(
        PlanRequest(
            allow_network=False, ollama_url="http://user:secret@localhost:11434/?token=secret"
        )
    )
    data = artifact.to_dict()
    assert data["inputs"]["ollama_url"] == "http://localhost:11434/"
    data["inputs"]["request_rate"] = 999
    assert artifact.to_dict()["inputs"]["request_rate"] == 1
