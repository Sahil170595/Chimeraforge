"""Installed verifier acceptance using the original native fleet and saved intent."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def accept_systemd(
    cwd: Path, env: dict, saved: Path, unit: Path, index: int, devices: list[str]
) -> dict:
    from ci_installed_acceptance import run_cli
    from chimeraforge import api

    source, raw = saved.read_bytes(), unit.read_bytes()
    command = [
        "deploy-verify",
        "--plan",
        str(saved),
        "--candidate-index",
        str(index),
        "--config",
        str(unit),
        "--format",
        "systemd",
        "--executable",
        "/usr/bin/true",
        *[item for device in devices for item in ("--gpu-device", device)],
        "--json",
    ]
    direct = api.verify_systemd_deployment(
        saved,
        unit,
        executable="/usr/bin/true",
        candidate_index=index,
        gpu_devices=devices,
    )
    matched = json.loads(run_cli(command, cwd, env))
    assert matched == json.loads(json.dumps(direct.to_dict())) and direct.exit_code == 0
    assert (
        matched["config_sha256"]
        == matched["expected_config_sha256"]
        == hashlib.sha256(raw).hexdigest()
    )
    drift = cwd / "verification-drift.service"
    drift.write_bytes(raw + b"PrivateDirective=PRIVATE_SYSTEMD_VALUE\n")
    changed = command[:]
    changed[changed.index("--config") + 1] = str(drift)
    output = run_cli(changed, cwd, env, 5)
    receipt = json.loads(output)
    assert receipt["changes"] == [{"path": "/unit", "category": "content", "count": 1}]
    assert "PRIVATE_SYSTEMD_VALUE" not in output and str(cwd) not in output
    drift.write_bytes(b"invalid\0unit")
    assert json.loads(run_cli(changed, cwd, env, 1))["status"] == "invalid"
    assert (
        json.loads(run_cli([*command, "--image", "example/engine:1"], cwd, env, 1))["status"]
        == "invalid"
    )
    assert (
        api.verify_systemd_deployment(
            saved,
            unit,
            executable="/opt/other/engine",
            candidate_index=index,
            gpu_devices=devices,
        ).exit_code
        == 5
    )
    assert saved.read_bytes() == source and unit.read_bytes() == raw
    return {
        "match_exit": 0,
        "drift_exit": 5,
        "invalid_exit": 1,
        "independent_executable_drift_exit": 5,
        "source_and_unit_held": True,
        "installed_api_and_cli": "passed",
        "config_sha256": matched["config_sha256"],
    }


def accept(
    cwd: Path,
    env: dict,
    saved: Path,
    config: Path,
    index: int,
    groups: list[list[str]],
    ports: list[int],
) -> dict:
    from ci_installed_acceptance import run_cli
    from chimeraforge.deployment_verify import verify_deployment

    source_bytes, config_bytes = saved.read_bytes(), config.read_bytes()
    layout = [
        item
        for group, port in zip(groups, ports)
        for item in ("--replica-devices", ",".join(group), "--replica-port", str(port))
    ]
    command = [
        "deploy-verify",
        "--plan",
        str(saved),
        "--candidate-index",
        str(index),
        "--config",
        str(config),
        "--image",
        "example/engine:1",
        *layout,
        "--json",
    ]
    candidate = json.loads(source_bytes)["result"]["candidates"][index]
    assert candidate["n_agents"] == 3 and candidate["gpus_total"] == 6
    original_groups, original_ports = json.dumps(groups), ports[:]
    direct = verify_deployment(
        saved,
        config,
        image="example/engine:1",
        candidate_index=index,
        replica_gpu_devices=groups,
        replica_host_ports=ports,
    )
    matched = json.loads(run_cli(command, cwd, env))
    assert matched == json.loads(json.dumps(direct.to_dict())) and matched["exit_code"] == 0
    drifted = cwd / "fleet-verification-drift.json"
    document = json.loads(config_bytes)
    document["services"]["inference-2"]["image"] = "PRIVATE_ACTUAL_IMAGE_CANARY"
    drifted.write_text(json.dumps(document), encoding="utf-8")
    changed_command = command[:]
    changed_command[changed_command.index("--config") + 1] = str(drifted)
    observed = run_cli(changed_command, cwd, env, 5)
    assert "PRIVATE_ACTUAL_IMAGE_CANARY" not in observed
    assert json.loads(observed)["status"] == "drift"
    assert (
        verify_deployment(
            saved,
            drifted,
            image="example/engine:1",
            candidate_index=index,
            replica_gpu_devices=groups,
            replica_host_ports=ports,
        ).exit_code
        == 5
    )
    different_intent = verify_deployment(
        saved,
        config,
        image="example/engine:2",
        candidate_index=index,
        replica_gpu_devices=groups,
        replica_host_ports=ports,
    )
    assert different_intent.exit_code == 5
    malformed = cwd / "fleet-verification-invalid.json"
    malformed.write_text('{"PRIVATE_UNKNOWN_KEY":1,"PRIVATE_UNKNOWN_KEY":2}', encoding="utf-8")
    changed_command[changed_command.index("--config") + 1] = str(malformed)
    invalid = run_cli(changed_command, cwd, env, 1)
    assert "PRIVATE_UNKNOWN_KEY" not in invalid and json.loads(invalid)["status"] == "invalid"
    assert saved.read_bytes() == source_bytes and config.read_bytes() == config_bytes
    assert json.dumps(groups) == original_groups and ports == original_ports
    return {
        "scope": "current-renderer offline consistency only",
        "renderer_version": matched["renderer_version"],
        "match_exit": matched["exit_code"],
        "drift_exit": 5,
        "invalid_exit": 1,
        "independent_intent_drift_exit": different_intent.exit_code,
        "original_plan_and_config_bytes_unchanged": True,
        "plan_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "native_replicas": candidate["n_agents"],
        "gpus_total": candidate["gpus_total"],
        "installed_cli_and_api": "passed",
        "private_actual_values_and_unknown_keys": "not disclosed",
        "gpu_execution": "unverified",
        "source_authenticity": "unverified",
        "atomic_cross_file_snapshot": "not claimed",
    }
