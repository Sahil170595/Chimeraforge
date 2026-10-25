"""Installed offline device/port declarations from a real native two-GPU candidate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

DEVICES = ["7", "3"]
UUIDS = ["GPU-16a23983-e73e-0945-2095-cdeb50696982", "GPU-ad2367dd-a40e-6b86-6fc3-c44a2cc92c7e"]
HOST_PORT = 9001


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
    }
