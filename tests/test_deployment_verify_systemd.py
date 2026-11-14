"""Systemd verification compares exact native bytes with independent intent."""

import hashlib
import json
import os
import subprocess
import sys

import pytest
from typer.testing import CliRunner

from chimeraforge import api
from chimeraforge.cli import app
from chimeraforge.deploy import export_deployment
from chimeraforge.deployment_verify import DeploymentVerificationError
from chimeraforge.planner.resolver import SOURCE_OLLAMA
from test_deploy import artifact


def written(tmp_path, saved=None, **options):
    saved = saved or artifact()
    plan = tmp_path / "original.json"
    saved.save(plan)
    unit = tmp_path / "inference.service"
    rendered = export_deployment(saved, format="systemd", executable="/usr/bin/true", **options)
    unit.write_bytes(rendered.content.encode("utf-8"))
    for name, content in rendered.files.items():
        (tmp_path / name).write_bytes(content.encode("utf-8"))
    return saved, plan, unit


def test_public_systemd_verifier_matches_native_unit_without_writes(tmp_path):
    saved, plan, unit = written(tmp_path, gpu_devices=["7"])
    source, raw = plan.read_bytes(), unit.read_bytes()
    checked = api.verify_systemd_deployment(
        plan, unit, executable="/usr/bin/true", gpu_devices=["7"]
    )
    assert checked.status == "match" and checked.exit_code == 0
    assert checked.plan_sha256 == hashlib.sha256(source).hexdigest()
    assert (
        checked.config_sha256 == checked.expected_config_sha256 == hashlib.sha256(raw).hexdigest()
    )
    assert checked.changes == checked.companions == ()
    assert (
        api.verify_systemd_deployment(
            saved, unit, executable="/usr/bin/true", gpu_devices=["7"]
        ).source_kind
        == "artifact_snapshot"
    )
    assert plan.read_bytes() == source and unit.read_bytes() == raw


def test_actual_cli_verifies_systemd_without_image(tmp_path):
    _, plan, unit = written(tmp_path)
    command = [
        sys.executable,
        "-B",
        "-m",
        "chimeraforge",
        "deploy-verify",
        "--plan",
        str(plan),
        "--config",
        str(unit),
        "--format",
        "systemd",
        "--executable",
        "/usr/bin/true",
        "--json",
    ]
    completed = subprocess.run(
        command,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout)["status"] == "match"
    original = plan.read_bytes()
    for raw, code, status in [
        (unit.read_bytes() + b"# PRIVATE_UNIT_VALUE\n", 5, "drift"),
        (b"invalid\0PRIVATE_UNIT_VALUE", 1, "invalid"),
    ]:
        unit.write_bytes(raw)
        changed = subprocess.run(
            command,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert changed.returncode == code, changed.stdout + changed.stderr
        assert json.loads(changed.stdout)["status"] == status
        assert "PRIVATE_UNIT_VALUE" not in changed.stdout + changed.stderr
        assert plan.read_bytes() == original


@pytest.mark.parametrize("backend", ["vllm", "sglang", "ollama"])
def test_supported_native_backends_and_companions(tmp_path, backend):
    saved = (
        artifact(backend=backend)
        if backend != "ollama"
        else artifact(
            backend="ollama",
            source=SOURCE_OLLAMA,
            model="ollama:llama3.1:8b",
            quant="Q4_K_M",
            native_quant="Q4_K_M",
        )
    )
    _, plan, unit = written(tmp_path, saved)
    result = api.verify_systemd_deployment(plan, unit, executable="/usr/bin/true")
    assert result.exit_code == 0
    if backend == "ollama":
        companion = tmp_path / "Modelfile"
        companion.unlink()
        result = api.verify_systemd_deployment(plan, unit, executable="/usr/bin/true")
        assert result.exit_code == 5 and result.companions[0].state == "missing"
        companion.write_bytes(b"PRIVATE_NATIVE_COMPANION")
        result = api.verify_systemd_deployment(plan, unit, executable="/usr/bin/true")
        assert result.exit_code == 5 and result.companions[0].state == "drift"
        assert "PRIVATE_NATIVE_COMPANION" not in json.dumps(result.to_dict())


@pytest.mark.parametrize("change", ["argv", "environment", "comment", "crlf", "append"])
def test_any_valid_unit_byte_drift_is_categorical(tmp_path, change):
    _, plan, unit = written(tmp_path)
    raw = unit.read_bytes()
    altered = {
        "argv": raw.replace(b"/usr/bin/true", b"/PRIVATE_ENGINE"),
        "environment": raw.replace(b"CUDA_VISIBLE_DEVICES=0", b"CUDA_VISIBLE_DEVICES=PRIVATE"),
        "comment": raw.replace(b"Saved plan", b"PRIVATE_PLAN"),
        "crlf": raw.replace(b"\n", b"\r\n"),
        "append": raw + b"PrivateDirective=PRIVATE_VALUE\n",
    }[change]
    assert altered != raw
    unit.write_bytes(altered)
    result = api.verify_systemd_deployment(plan, unit, executable="/usr/bin/true")
    assert result.exit_code == 5 and result.change_count == 1
    assert [(item.path, item.category) for item in result.changes] == [("/unit", "content")]
    assert result.config_sha256 == hashlib.sha256(altered).hexdigest()
    assert result.expected_config_sha256 == hashlib.sha256(raw).hexdigest()
    public = json.dumps(result.to_dict())
    assert "PRIVATE" not in public and str(tmp_path) not in public and "/usr/bin/true" not in public


def test_independent_executable_and_gpu_order_do_not_follow_unit(tmp_path):
    _, plan, unit = written(tmp_path, gpu_devices=["7"])
    assert (
        api.verify_systemd_deployment(
            plan, unit, executable="/opt/other/engine", gpu_devices=["7"]
        ).exit_code
        == 5
    )
    assert (
        api.verify_systemd_deployment(
            plan, unit, executable="/usr/bin/true", gpu_devices=["3"]
        ).exit_code
        == 5
    )
    with pytest.raises(DeploymentVerificationError):
        api.verify_systemd_deployment(plan, unit, executable="/usr/bin/true", model="private/other")


@pytest.mark.parametrize("raw", [b"", b"invalid\x00unit", b"\xff\xfe"])
def test_empty_nul_and_non_utf8_units_are_invalid(tmp_path, raw):
    _, plan, unit = written(tmp_path)
    unit.write_bytes(raw)
    with pytest.raises(DeploymentVerificationError):
        api.verify_systemd_deployment(plan, unit, executable="/usr/bin/true")


def test_exact_byte_bound_and_source_aliases(tmp_path, monkeypatch):
    from chimeraforge import deployment_verify

    _, plan, unit = written(tmp_path)
    raw = unit.read_bytes()
    monkeypatch.setattr(deployment_verify, "MAX_CONFIG_BYTES", len(raw))
    assert api.verify_systemd_deployment(plan, unit, executable="/usr/bin/true").exit_code == 0
    unit.write_bytes(raw + b"\n")
    with pytest.raises(DeploymentVerificationError):
        api.verify_systemd_deployment(plan, unit, executable="/usr/bin/true")
    with pytest.raises(DeploymentVerificationError):
        api.verify_systemd_deployment(plan, plan, executable="/usr/bin/true")
    with pytest.raises(DeploymentVerificationError):
        api.verify_systemd_deployment(plan, tmp_path, executable="/usr/bin/true")


@pytest.mark.parametrize(
    "executable", ["relative/private", "", "/bad\nPRIVATE", "C:\\private.exe", True]
)
def test_native_executable_refusals_are_sanitized(tmp_path, executable):
    _, plan, unit = written(tmp_path)
    with pytest.raises(DeploymentVerificationError) as caught:
        api.verify_systemd_deployment(plan, unit, executable=executable)
    assert "PRIVATE" not in str(caught.value)


@pytest.mark.parametrize(
    "options",
    [
        {"backend": "tgi"},
        {"platform": "macos"},
        {"inputs": {"kv_quant": "q4"}},
        {"candidate_changes": {"n_agents": 2}},
    ],
)
def test_native_fidelity_and_original_population_refusals(tmp_path, options):
    saved = artifact(**options)
    unit = tmp_path / "untrusted.service"
    unit.write_bytes(b"[Service]\nExecStart=/usr/bin/true\n")
    with pytest.raises(DeploymentVerificationError):
        api.verify_systemd_deployment(saved, unit, executable="/usr/bin/true")


@pytest.mark.parametrize(
    "extra",
    [
        ["--image", "example/engine:1"],
        ["--host-port", "8000"],
        ["--replica-devices", "0"],
        ["--replica-port", "8000"],
        ["--namespace", "default"],
        ["--name-prefix", "private"],
        ["--node-selector", "private=value"],
    ],
)
def test_cli_incompatible_systemd_controls_refuse_before_source_read(tmp_path, monkeypatch, extra):
    from chimeraforge import deployment_verify

    calls = []

    def forbidden(*args, **kwargs):
        calls.append(1)
        raise AssertionError("source read before intent admission")

    monkeypatch.setattr(deployment_verify, "_source", forbidden)
    result = CliRunner().invoke(
        app,
        [
            "deploy-verify",
            "--plan",
            str(tmp_path / "private.json"),
            "--config",
            str(tmp_path / "private.service"),
            "--format",
            "systemd",
            "--executable",
            "/usr/bin/true",
            "--json",
            *extra,
        ],
    )
    assert result.exit_code == 1 and json.loads(result.output)["status"] == "invalid"
    assert calls == [] and "private" not in result.output


def test_cli_required_controls_and_native_usage(tmp_path):
    _, plan, unit = written(tmp_path)
    common = ["deploy-verify", "--plan", str(plan), "--config", str(unit)]
    assert CliRunner().invoke(app, common).exit_code == 2
    assert CliRunner().invoke(app, [*common, "--format", "systemd", "--json"]).exit_code == 1
    assert (
        CliRunner()
        .invoke(
            app, [*common, "--image", "example/engine:1", "--executable", "/usr/bin/true", "--json"]
        )
        .exit_code
        == 1
    )


def test_verification_starts_no_child_and_preserves_escaped_native_content(tmp_path, monkeypatch):
    saved = artifact(model='org/model${UNSET}%u;"\\quoted')
    _, plan, unit = written(tmp_path, saved)
    original = unit.read_bytes()

    def forbidden(*args, **kwargs):
        raise AssertionError("verification started a process")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    assert api.verify_systemd_deployment(plan, unit, executable="/usr/bin/true").exit_code == 0
    assert unit.read_bytes() == original
