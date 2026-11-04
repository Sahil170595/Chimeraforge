"""Regenerable installed inspection protocol controls; pinned native kind proof is separate."""

from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
from dataclasses import asdict, fields, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any
from unittest.mock import patch
from xml.etree import ElementTree as ET

from ci_installed_acceptance import assert_installed_modules

IMAGE = "example/inspection:1"
PRIVATE = "inspection-private-canary"
SOURCE_FILES = (
    "src/chimeraforge/kubernetes_inspection.py",
    "src/chimeraforge/kubernetes_inspection_process.py",
    "src/chimeraforge/kubernetes_inspection_intent.py",
    "src/chimeraforge/kubernetes_inspection_types.py",
    "src/chimeraforge/kubernetes_inspection_output.py",
    "src/chimeraforge/commands/deploy_inspect.py",
    "src/chimeraforge/kubernetes_options.py",
    "src/chimeraforge/kubernetes_export.py",
    "src/chimeraforge/api.py",
    "scripts/ci_kubernetes_inspection.py",
    "scripts/ci_kubernetes_inspection_native.py",
    "scripts/ci_secure_monitor.py",
    "scripts/ci_kubernetes_admission.py",
    "scripts/ci_installed_acceptance.py",
    "src/chimeraforge/cli.py",
)


def observed(expected: dict) -> dict:
    """Controlled native-shaped status facts, never a real readiness observation."""
    actual = deepcopy(expected)
    actual["metadata"].update(generation=1, uid="fixture", resourceVersion="1")
    if actual["kind"] == "Deployment":
        actual["status"] = {
            "observedGeneration": 1,
            "updatedReplicas": 1,
            "replicas": 1,
            "availableReplicas": 1,
        }
    return actual


def accept(work: Path, env: dict, saved: Path, checkout: Path | None = None) -> dict:
    from typer.testing import CliRunner
    from chimeraforge import api, deploy
    from chimeraforge.cli import app
    from chimeraforge.kubernetes_inspection import CA_PATHS, PROVIDER_TEMPLATE
    from chimeraforge.kubernetes_inspection_output import materialize

    before = assert_installed_modules(checkout) if checkout is not None else None
    work.mkdir(parents=True, exist_ok=True)
    original = saved.read_bytes()
    artifact = api.load_plan(saved)
    n = 3
    indices = {
        backend: next(
            i
            for i, candidate in enumerate(artifact._data["result"]["candidates"])
            if candidate["backend"] == backend
            and candidate["quant"] == "FP16"
            and candidate["n_agents"] == n
        )
        for backend in ("vllm", "sglang")
    }
    config = work / "private-config"
    config.write_text(PRIVATE, encoding="utf-8")
    client = work / "controlled-client.exe"
    client_bytes = b"fictional-native-client-not-a-real-binary"
    client.write_bytes(client_bytes)
    client.chmod(0o700)
    controls: list[dict] = []
    native_launch = asyncio.create_subprocess_exec
    total_children = 0
    for backend, index in indices.items():
        options = api.KubernetesOptions(namespace="inspection", name_prefix=f"inspect-{backend}")
        manifest = json.loads(
            deploy.export_deployment(
                artifact,
                format="kubernetes",
                image=IMAGE,
                candidate_index=index,
                model=artifact.candidate(index).model,
                kubernetes=options,
            ).content
        )
        common = [
            "deploy-inspect",
            "--plan",
            str(saved),
            "--image",
            IMAGE,
            "--candidate-index",
            str(index),
            "--model",
            artifact.candidate(index).model,
            "--kubeconfig",
            str(config),
            "--context",
            PRIVATE,
            "--namespace",
            options.namespace,
            "--name-prefix",
            options.name_prefix or "",
            "--json",
            "--kubectl",
            str(client),
        ]
        for fault, code in (
            ("matching_status", 0),
            ("intent_drift", 5),
            ("pending_status", 4),
            ("missing_service", 5),
            ("provider", 4),
            ("wrong_identity", 4),
            ("malformed_condition", 4),
            ("generation_width", 4),
            ("replica_width", 4),
        ):
            objects: dict[str, Any] = {
                row["metadata"]["name"] + row["kind"]: observed(row) for row in manifest["items"]
            }
            first, service = manifest["items"][:2]
            if fault == "intent_drift":
                objects[first["metadata"]["name"] + "Deployment"]["spec"]["template"]["spec"][
                    "containers"
                ][0]["image"] = PRIVATE
            elif fault == "pending_status":
                objects[first["metadata"]["name"] + "Deployment"]["status"]["availableReplicas"] = 0
            elif fault == "missing_service":
                objects[service["metadata"]["name"] + "Service"] = None
            elif fault == "wrong_identity":
                objects[first["metadata"]["name"] + "Deployment"]["metadata"]["name"] = PRIVATE
            elif fault == "malformed_condition":
                objects[first["metadata"]["name"] + "Deployment"]["status"]["conditions"] = [
                    {"type": "Progressing", "reason": ["ProgressDeadlineExceeded"]}
                ]
            elif fault == "generation_width":
                actual = objects[first["metadata"]["name"] + "Deployment"]
                actual["metadata"]["generation"] = 1 << 63
                actual["status"]["observedGeneration"] = 1 << 63
            elif fault == "replica_width":
                actual = objects[first["metadata"]["name"] + "Deployment"]
                for field in ("updatedReplicas", "replicas", "availableReplicas"):
                    actual["status"][field] = 1 << 31
            children: list[asyncio.subprocess.Process] = []

            async def launch(*argv: str, **kwargs: Any) -> asyncio.subprocess.Process:
                if "version" in argv:
                    response = {"clientVersion": {"gitVersion": "v1.37.1"}}
                    if "--client=true" not in argv:
                        response["serverVersion"] = {"gitVersion": "v1.37.0"}
                    payload = json.dumps(response).encode()
                elif "view" in argv:
                    expression = argv[argv.index("--template") + 1]
                    payload = (
                        (b"provider_present" if fault == "provider" else b"provider_absent")
                        if expression == PROVIDER_TEMPLATE
                        else b"[]"
                    )
                    assert (
                        expression == PROVIDER_TEMPLATE
                        or expression == CA_PATHS
                        or "tokenFile" in expression
                    )
                else:
                    assert "get" in argv
                    name = argv[argv.index("get") + 2]
                    kind = "Deployment" if "deployments.apps" in argv else "Service"
                    value = objects[name + kind]
                    payload = b"" if value is None else json.dumps(value).encode()
                child = await native_launch(
                    sys.executable,
                    "-I",
                    "-c",
                    "import sys;sys.stdout.buffer.write(" + repr(payload) + ")",
                    **kwargs,
                )
                children.append(child)
                return child

            with patch("asyncio.create_subprocess_exec", launch):
                result = asyncio.run(
                    api.inspect_kubernetes_deployment(
                        saved,
                        image=IMAGE,
                        candidate_index=index,
                        model=artifact.candidate(index).model,
                        kubernetes=options,
                        kubeconfig=config,
                        context=PRIVATE,
                        kubectl=client,
                        timeout_s=20,
                    )
                )
                cli_out = work / f"{backend}-{fault}-cli.json"
                cli_xml = work / f"{backend}-{fault}-cli.xml"
                arguments = (
                    common
                    if fault == "provider"
                    else [*common, "--out", str(cli_out), "--junit", str(cli_xml)]
                )
                cli = CliRunner().invoke(app, arguments)
                if fault == "provider":
                    refused = CliRunner().invoke(
                        app, [*common, "--out", str(cli_out), "--junit", str(cli_xml)]
                    )
                    assert refused.exit_code == 2 and not cli_out.exists() and not cli_xml.exists()
                if fault == "matching_status":
                    guarded = work / f"{backend}-client-guard.json"
                    try:
                        api.write_kubernetes_inspection(result, out=guarded, junit=client)
                    except api.KubernetesInspectionError:
                        assert not guarded.exists() and client.read_bytes() == client_bytes
                    else:
                        raise AssertionError("native client input was overwritten")
                    count = len(children)
                    refused = CliRunner().invoke(app, [*common, "--out", str(client)])
                    assert refused.exit_code == 2 and len(children) == count
                    assert client.read_bytes() == client_bytes
            assert result.exit_code == cli.exit_code == code, (backend, fault, cli.exit_code)
            cli_data = json.loads(cli.stdout)
            raw, xml = materialize(result)
            assert len(result.resources) == len(cli_data["resources"]) == 2 * n
            assert len(ET.fromstring(xml).findall("testcase")) == 3 * n + 1
            api_out, api_xml = (
                work / f"{backend}-{fault}-api.json",
                work / f"{backend}-{fault}-api.xml",
            )
            if fault == "provider":
                try:
                    api.write_kubernetes_inspection(result, out=api_out, junit=api_xml)
                except api.KubernetesInspectionError:
                    assert not api_out.exists() and not api_xml.exists()
                else:
                    raise AssertionError("unverified private inventory published files")
            else:
                api.write_kubernetes_inspection(result, out=api_out, junit=api_xml)
                assert api_out.read_bytes() == raw and api_xml.read_bytes() == xml
                assert cli_out.read_bytes() == cli.stdout.encode()
                assert len(ET.fromstring(cli_xml.read_bytes()).findall("testcase")) == 3 * n + 1
            assert PRIVATE not in raw.decode() + cli.stdout + xml.decode()
            assert {field.name for field in fields(result)} == {"_data"}
            assert PRIVATE not in json.dumps(asdict(result))
            assert replace(result)._input_paths == result._input_paths
            assert result._data["cleanup"]["state"] == cli_data["cleanup"]["state"] == "completed"
            assert all(child.returncode is not None for child in children)
            total_children += len(children)
            controls.append(
                {
                    "backend": backend,
                    "control": fault,
                    "api_exit": code,
                    "cli_exit": code,
                    "resources": 2 * n,
                    "junit_cases": 3 * n + 1,
                }
            )
        # This is an actual module subprocess/raw stdout byte check, without a native tool.
        missing = work / "absent-native-client"
        output = subprocess.run(
            [sys.executable, "-B", "-I", "-m", "chimeraforge", *common, "--kubectl", str(missing)],
            env=env,
            cwd=work,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=30,
        )
        assert output.returncode == 4 and PRIVATE.encode() not in output.stdout + output.stderr
        decoded = json.loads(output.stdout)
        canonical = (
            json.dumps(decoded, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
        ).encode()
        assert canonical == output.stdout and len(decoded["resources"]) == 2 * n
    assert saved.read_bytes() == original and config.read_text(encoding="utf-8") == PRIVATE
    return {
        "controls": controls,
        "controlled_owned_processes": total_children,
        "protocol_scope": (
            "controlled Python processes/statuses; native kubectl/kind proof separate"
        ),
        "raw_cli_byte_parity": True,
        "complete_api_cli_junit_files": True,
        "unverified_inventory_publication_refused": True,
        "selected_client_input_guard_preserved": True,
        "source_unchanged": True,
        "owned_processes_closed": True,
        "loaded_modules_before": before,
        "loaded_modules_after": assert_installed_modules(checkout)
        if checkout is not None
        else None,
    }


def record(path: Path, checkout: Path) -> None:
    """Refresh only aggregate counts/hashes, never credential/config/resource bodies."""
    import tempfile
    import os
    from chimeraforge import api

    assert api.__file__ is not None and Path(api.__file__).resolve().is_relative_to(
        (checkout / "src" / "chimeraforge").resolve()
    ), "source record requires the selected editable checkout"
    with tempfile.TemporaryDirectory(prefix="cf-inspection-record-") as temporary:
        work = Path(temporary)
        env = dict(os.environ)
        env["CHIMERAFORGE_CACHE"] = str(work / "cache")
        saved = work / "source.json"
        api.plan(
            api.PlanRequest(
                models=["ci/manual-fleet"],
                overrides={"params_b": 3, "n_layers": 28, "n_kv_heads": 8, "d_head": 128},
                hardware="RTX 4090 24GB",
                platform="linux",
                tensor_parallel=2,
                request_rate=128,
                latency_slo=10000,
                quality_target=0,
                budget=1e8,
                allow_network=False,
            )
        ).save(saved)
        result = accept(work, env, saved)
    result.pop("loaded_modules_before")
    result.pop("loaded_modules_after")
    result.update(
        captured_at=datetime.now(timezone.utc).isoformat(),
        source_profile="editable source, not installed or native kubectl qualification",
        method=(
            "actual API/in-process CLI controlled owned Python protocol and raw missing-tool CLI"
        ),
        source_sha256={
            name: hashlib.sha256((checkout / name).read_bytes()).hexdigest()
            for name in SOURCE_FILES
        },
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--checkout", type=Path, required=True)
    arguments = parser.parse_args()
    record(arguments.record, arguments.checkout)
