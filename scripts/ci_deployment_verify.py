"""Installed verifier acceptance using the original native fleet and saved intent."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


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
