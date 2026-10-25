"""Installed offline device/port declarations from a real native two-GPU candidate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

DEVICES = ["7", "3"]
UUIDS = ["GPU-16a23983-e73e-0945-2095-cdeb50696982", "GPU-ad2367dd-a40e-6b86-6fc3-c44a2cc92c7e"]
HOST_PORT = 9001
FLEET_DEVICES = [["7", "3"], ["9", "2"], ["8", "4"]]
FLEET_PORTS = [9001, 9002, 9003]
FLEET_REQUEST_RATE = 2048


def validate(data: dict, index: int, compose: dict, unit: str) -> None:
    """Check emitted declarations and native controls, never host/GPU execution."""
    candidate = data["result"]["candidates"][index]
    assert candidate["backend"] == "vllm" and candidate["quant"] == "FP16"
    assert candidate["n_agents"] == candidate["pipeline_parallel"] == 1
    assert candidate["gpus_total"] == candidate["tensor_parallel"] == 2
    assert candidate["platform"] == "linux-cuda" and candidate["offload_fraction"] == 0
    service = compose["services"]["inference"]
    assert service["deploy"]["resources"]["reservations"]["devices"] == [
        {"driver": "nvidia", "device_ids": DEVICES, "capabilities": ["gpu"]}
    ]
    assert "CUDA_VISIBLE_DEVICES" not in service.get("environment", {})
    assert service["ports"] == [f"127.0.0.1:{HOST_PORT}:8000"]
    argv = service["command"]
    assert argv[argv.index("--tensor-parallel-size") + 1] == "2"
    assert argv[argv.index("--pipeline-parallel-size") + 1] == "1"
    assert 'Environment="CUDA_VISIBLE_DEVICES=7,3"' in unit
    assert '"--tensor-parallel-size" "2"' in unit


def validate_fleet(data: dict, index: int, compose: dict) -> None:
    """Keep every original native replica, its batch and immutable HF revision."""
    candidate = data["result"]["candidates"][index]
    assert candidate["backend"] == "vllm" and candidate["quant"] == "FP16"
    assert candidate["n_agents"] == 3 and candidate["gpus_total"] == 6
    assert candidate["tensor_parallel"] == 2 and candidate["pipeline_parallel"] == 1
    assert candidate["platform"] == "linux-cuda" and candidate["offload_fraction"] == 0
    spec = data["result"]["specs"][candidate["model"]]
    assert spec["source"] == "hf" and spec["checkpoint"]
    services = compose["services"]
    assert list(services) == ["inference-1", "inference-2", "inference-3"]
    for offset, service in enumerate(services.values()):
        assert service["deploy"]["resources"]["reservations"]["devices"] == [
            {"driver": "nvidia", "device_ids": FLEET_DEVICES[offset], "capabilities": ["gpu"]}
        ]
        assert "replicas" not in service["deploy"]
        assert service["ports"] == [f"127.0.0.1:{FLEET_PORTS[offset]}:8000"]
        assert "CUDA_VISIBLE_DEVICES" not in service.get("environment", {})
        assert service["labels"] == {
            "org.chimeraforge.plan-fingerprint": data["fingerprint"],
            "org.chimeraforge.replica-index": str(offset + 1),
            "org.chimeraforge.replica-count": "3",
        }
        argv = service["command"]
        assert argv[0] == candidate["model"]
        expected = {
            "--tensor-parallel-size": "2",
            "--pipeline-parallel-size": "1",
            "--max-num-seqs": str(candidate["effective_batch"]),
            "--max-model-len": str(data["inputs"]["context_length"]),
            "--dtype": "float16",
            "--port": "8000",
            "--revision": spec["checkpoint"]["resolved_revision"],
        }
        for flag, value in expected.items():
            assert argv.count(flag) == 1 and argv[argv.index(flag) + 1] == value


def _accept_fleet(cwd: Path, env: dict, checkpoint: dict) -> dict:
    from ci_installed_acceptance import run_cli
    from chimeraforge import api
    from chimeraforge.deploy import export_deployment

    saved, output = cwd / "fleet-plan.json", cwd / "fleet-compose.json"
    run_cli(
        [
            "plan",
            "--model",
            checkpoint["repo"],
            "--revision",
            checkpoint["commit"],
            "--platform",
            "linux",
            "--hardware",
            "RTX 4090 24GB",
            "--tensor-parallel",
            "2",
            "--request-rate",
            str(FLEET_REQUEST_RATE),
            "--quality-target",
            "0",
            "--budget",
            "100000",
            "--no-network",
            "--save",
            str(saved),
            "--json",
        ],
        cwd,
        env,
    )
    original = saved.read_bytes()
    data = json.loads(original)
    index = next(
        i
        for i, row in enumerate(data["result"]["candidates"])
        if row["backend"] == "vllm"
        and row["quant"] == "FP16"
        and row["n_agents"] == 3
        and row["gpus_total"] == 6
        and row["tensor_parallel"] == 2
        and row["pipeline_parallel"] == 1
        and row["offload_fraction"] == 0
    )
    layout = [
        arg
        for group, port in zip(FLEET_DEVICES, FLEET_PORTS)
        for arg in ("--replica-devices", ",".join(group), "--replica-port", str(port))
    ]
    common = [
        "deploy",
        "--plan",
        str(saved),
        "--candidate-index",
        str(index),
        "--format",
        "compose",
        "--image",
        "example/engine:1",
    ]
    run_cli([*common, "--out", str(output), *layout], cwd, env)
    compose = json.loads(output.read_text())
    validate_fleet(data, index, compose)
    public = export_deployment(
        api.load_plan(saved),
        format="compose",
        candidate_index=index,
        image="example/engine:1",
        replica_gpu_devices=FLEET_DEVICES,
        replica_host_ports=FLEET_PORTS,
    )
    assert json.loads(public.content) == compose
    refused = cwd / "fleet-refused.json"
    run_cli([*common, "--out", str(refused), *layout, "--gpu-device", "7"], cwd, env, 1)
    assert not refused.exists() and saved.read_bytes() == original
    from ci_deployment_verify import accept as accept_verification

    verification = accept_verification(cwd, env, saved, output, index, FLEET_DEVICES, FLEET_PORTS)
    return {
        "scope": "offline homogeneous serving declaration",
        "replicas": 3,
        "gpus_total": 6,
        "tensor_parallel_per_replica": 2,
        "pipeline_parallel_per_replica": 1,
        "batch_per_replica": data["result"]["candidates"][index]["effective_batch"],
        "service_names": list(compose["services"]),
        "gpu_groups": FLEET_DEVICES,
        "host_ports": FLEET_PORTS,
        "source_plan_sha256": hashlib.sha256(original).hexdigest(),
        "source_plan_bytes_unchanged": True,
        "installed_cli_and_api": "passed",
        "router": "not provided",
        "scaler": "not provided",
        "gpu_execution": "unverified",
        "device_availability": "unverified",
        "physical_independence": "unverified",
        "deployment_verification": verification,
    }


def accept(cwd: Path, env: dict, checkout: Path, checkpoint: dict) -> dict:
    from ci_installed_acceptance import assert_installed_origin, run_cli
    from chimeraforge import api
    from chimeraforge.deploy import export_deployment

    assert_installed_origin(api.__file__, checkout)
    saved = cwd / "placement-plan.json"
    run_cli(
        [
            "plan",
            "--model",
            checkpoint["repo"],
            "--revision",
            checkpoint["commit"],
            "--platform",
            "linux",
            "--hardware",
            "RTX 4090 24GB",
            "--tensor-parallel",
            "2",
            "--request-rate",
            "0.01",
            "--quality-target",
            "0",
            "--budget",
            "100000",
            "--no-network",
            "--save",
            str(saved),
            "--json",
        ],
        cwd,
        env,
    )
    original = saved.read_bytes()
    data = json.loads(original)
    index = next(
        i
        for i, row in enumerate(data["result"]["candidates"])
        if row["backend"] == "vllm"
        and row["quant"] == "FP16"
        and row["n_agents"] == row["pipeline_parallel"] == 1
        and row["tensor_parallel"] == row["gpus_total"] == 2
        and row["offload_fraction"] == 0
    )
    common = ["deploy", "--plan", str(saved), "--candidate-index", str(index)]
    compose_path, unit_path = cwd / "placement-compose.json", cwd / "placement.service"
    selection = ["--gpu-device", DEVICES[0], "--gpu-device", DEVICES[1]]
    run_cli(
        [
            *common,
            "--format",
            "compose",
            "--image",
            "example/engine:1",
            "--host-port",
            str(HOST_PORT),
            "--out",
            str(compose_path),
            *selection,
        ],
        cwd,
        env,
    )
    run_cli(
        [
            *common,
            "--format",
            "systemd",
            "--executable",
            "/usr/bin/true",
            "--out",
            str(unit_path),
            *selection,
        ],
        cwd,
        env,
    )
    compose, unit = json.loads(compose_path.read_text()), unit_path.read_text()
    validate(data, index, compose, unit)
    argv = compose["services"]["inference"]["command"]
    assert argv[argv.index("--revision") + 1] == checkpoint["commit"]
    public = export_deployment(
        api.load_plan(saved),
        format="compose",
        candidate_index=index,
        image="example/engine:1",
        gpu_devices=DEVICES,
        host_port=HOST_PORT,
    )
    assert json.loads(public.content) == compose
    uuid_path = cwd / "placement-uuid-compose.json"
    run_cli(
        [
            *common,
            "--format",
            "compose",
            "--image",
            "example/engine:1",
            "--out",
            str(uuid_path),
            "--gpu-device",
            UUIDS[0],
            "--gpu-device",
            UUIDS[1].upper(),
        ],
        cwd,
        env,
    )
    uuid_device = json.loads(uuid_path.read_text())["services"]["inference"]["deploy"]["resources"][
        "reservations"
    ]["devices"][0]
    assert uuid_device == {"driver": "nvidia", "device_ids": UUIDS, "capabilities": ["gpu"]}
    refused = cwd / "placement-refused.json"
    run_cli(
        [
            *common,
            "--format",
            "compose",
            "--image",
            "example/engine:1",
            "--out",
            str(refused),
            "--gpu-device",
            "7",
            "--gpu-device",
            "7",
        ],
        cwd,
        env,
        1,
    )
    assert not refused.exists() and saved.read_bytes() == original
    return {
        "scope": "offline declaration only",
        "gpus_per_replica": 2,
        "gpu_devices": DEVICES,
        "gpu_uuids": UUIDS,
        "host_port": HOST_PORT,
        "container_port": 8000,
        "source_plan_sha256": hashlib.sha256(original).hexdigest(),
        "source_plan_bytes_unchanged": True,
        "installed_cli_and_api": "passed",
        "gpu_execution": "unverified",
        "device_availability": "unverified",
        "cuda_rank_mapping": "unverified",
        "topology": "unverified",
        "homogeneous_fleet": _accept_fleet(cwd, env, checkpoint),
    }
