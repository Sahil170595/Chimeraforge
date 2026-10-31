"""Installed consumer composition uses actual source producers, not a native cluster."""

from __future__ import annotations

import os
import json
from pathlib import Path

import pytest

from test_ci_acceptance import load_script
from test_kubernetes_export import native_plans as native_plans


def test_source_consumer_runs_both_engines_and_complete_junit(native_plans, tmp_path):
    script = load_script("ci_kubernetes_inspection")
    source = tmp_path / "source.json"
    native_plans[3][0].save(source)
    result = script.accept(tmp_path, dict(os.environ), source)
    assert len(result["controls"]) == 18
    assert {row["api_exit"] for row in result["controls"]} == {0, 4, 5}
    assert all(row["resources"] == 6 and row["junit_cases"] == 10 for row in result["controls"])
    assert result["raw_cli_byte_parity"] and result["owned_processes_closed"]
    assert result["source_unchanged"]
    assert result["loaded_modules_before"] is result["loaded_modules_after"] is None


def test_native_inspection_fixture_loads_saved_plan_before_native_render(tmp_path, monkeypatch):
    from typer.testing import CliRunner
    from chimeraforge import api, deploy
    from chimeraforge.cli import app

    admission = load_script("ci_kubernetes_admission")
    load_script("ci_checkpoint_identity")
    load_script("ci_kubernetes_export")
    installed = load_script("ci_installed_acceptance")
    native = load_script("ci_kubernetes_inspection_native")
    monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path / "cache"))

    def source_cli(arguments, cwd, env, expected_code=0):
        response = CliRunner().invoke(app, arguments, env=env)
        assert response.exit_code == expected_code, response.output
        return response.stdout

    monkeypatch.setattr(installed, "run_cli", source_cli)
    fixture_work, work = tmp_path / "fixtures", tmp_path / "native"
    fixture_work.mkdir()
    work.mkdir()
    cases = admission.fixtures(fixture_work, {})
    config = work / "private.cfg"
    config.write_text('{"apiVersion":"v1","kind":"Config"}', encoding="utf-8")
    rendered, namespace, deleted, observations = [], {}, [], []
    native_render = deploy.export_deployment

    class ReachedInspectionBoundary(RuntimeError):
        pass

    def render(artifact, **kwargs):
        output = native_render(artifact, **kwargs)
        rendered.append((artifact, json.loads(output.content)))
        return output

    async def observe(saved, **kwargs):
        observations.append(saved)
        raise ReachedInspectionBoundary("controlled boundary; no cluster contacted")

    def admin(argv, env, **kwargs):
        if "apply" in argv:
            value = json.loads(Path(argv[argv.index("-f") + 1]).read_text(encoding="utf-8"))
            assert value["kind"] == "Namespace"
            namespace.update(value)
            return ""
        if "delete" in argv:
            deleted.append(argv)
            return ""
        assert "get" in argv and "namespace" in argv
        return json.dumps(namespace) if argv[-1] == "json" else ""

    monkeypatch.setattr(deploy, "export_deployment", render)
    monkeypatch.setattr(api, "inspect_kubernetes_deployment", observe)
    receipt = {}
    with pytest.raises(ReachedInspectionBoundary):
        native.accept(
            ["kubectl", "--kubeconfig", str(config), "--context", "owned"],
            {},
            cases,
            work,
            admin,
            receipt,
        )
    assert len(rendered) == len(observations) == len(deleted) == 1
    artifact, manifest = rendered[0]
    assert isinstance(artifact, api.PlanArtifact) and len(manifest["items"]) == 6
    assert all(
        row["spec"]["template"]["spec"]["containers"][0]["resources"]["limits"]
        == {"nvidia.com/gpu": "2"}
        for row in manifest["items"]
        if row["kind"] == "Deployment"
    )
    assert receipt["cleanup"] == {"state": "completed", "owned_namespace_deleted": True}
    assert all(case["saved"].read_bytes() == case["source"] for case in cases)
