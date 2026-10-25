"""A native homogeneous fleet remains N complete replicas with explicit placement."""

import copy
import json

import pytest
from typer.testing import CliRunner

from chimeraforge import api, deploy
from chimeraforge.cli import app
from test_deploy import artifact

GROUPS = [["7", "3"], ["9", "2"], ["8", "4"]]
PORTS = [9001, 9002, 9003]


@pytest.fixture
def native_fleet():
    saved = api.plan(
        api.PlanRequest(
            models=["ci/manual-fleet"],
            overrides={"params_b": 3.0, "n_layers": 28, "n_kv_heads": 8, "d_head": 128},
            hardware="RTX 4090 24GB",
            platform="linux",
            tensor_parallel=2,
            request_rate=128,
            latency_slo=10000,
            quality_target=0,
            budget=1e8,
            allow_network=False,
        )
    )
    indices = {
        row["backend"]: i
        for i, row in enumerate(saved.to_dict()["result"]["candidates"])
        if row["backend"] in ("vllm", "sglang")
        and row["quant"] == "FP16"
        and row["n_agents"] == 3
        and row["gpus_total"] == 6
    }
    assert set(indices) == {"vllm", "sglang"}
    return saved, indices


def render(saved, index, **options):
    return deploy.export_deployment(
        saved, candidate_index=index, model="org/manual-fleet", **options
    )


@pytest.mark.parametrize("backend", ["vllm", "sglang"])
def test_real_native_three_replica_population_preserves_original_geometry(
    native_fleet, backend, monkeypatch
):
    saved, indices = native_fleet
    before = saved.to_dict()
    candidate = saved.candidate(indices[backend])
    original = deploy._validate_fidelity
    observed = []

    def admit(row, *args):
        observed.append((row.n_agents, row.gpus_total, row.effective_batch))
        return original(row, *args)

    monkeypatch.setattr(deploy, "_validate_fidelity", admit)
    result = render(
        saved,
        indices[backend],
        format="compose",
        image="example/engine:1",
        replica_gpu_devices=GROUPS,
        replica_host_ports=PORTS,
    )
    assert observed == [(3, 6, candidate.effective_batch)]
    services = json.loads(result.content)["services"]
    assert list(services) == ["inference-1", "inference-2", "inference-3"]
    tpflag, batchflag, port = (
        ("--tensor-parallel-size", "--max-num-seqs", 8000)
        if backend == "vllm"
        else ("--tp-size", "--max-running-requests", 30000)
    )
    for offset, service in enumerate(services.values()):
        assert service["image"] == "example/engine:1"
        assert service["ports"] == [f"127.0.0.1:{PORTS[offset]}:{port}"]
        assert service["deploy"]["resources"]["reservations"]["devices"] == [
            {"driver": "nvidia", "device_ids": GROUPS[offset], "capabilities": ["gpu"]}
        ]
        assert "CUDA_VISIBLE_DEVICES" not in service.get("environment", {})
        command = service["command"]
        assert command[command.index(tpflag) + 1] == "2"
        assert command[command.index(batchflag) + 1] == str(candidate.effective_batch)
        assert (
            command[0 if backend == "vllm" else command.index("--model-path") + 1]
            == "org/manual-fleet"
        )
        assert service["labels"]["org.chimeraforge.plan-fingerprint"] == before["fingerprint"]
        assert service["labels"]["org.chimeraforge.replica-index"] == str(offset + 1)
        assert service["labels"]["org.chimeraforge.replica-count"] == "3"
        assert "replicas" not in service["deploy"]
    assert saved.to_dict() == before and not result.files
    assert any("router" in note and "not" in note for note in result.notes)


@pytest.mark.parametrize(
    "invalid",
    [
        "missing-groups",
        "missing-ports",
        "empty-groups",
        "empty-ports",
        "group-count",
        "group-size",
        "overlap",
        "duplicate-port",
        "bad-port",
        "bool-port",
        "mixed-namespace",
        "outer-string",
        "ports-tuple",
    ],
)
def test_invalid_fleet_layout_refuses_before_render(native_fleet, invalid):
    saved, indices = native_fleet
    groups, ports = copy.deepcopy(GROUPS), PORTS[:]
    if invalid == "missing-groups":
        groups = None
    elif invalid == "missing-ports":
        ports = None
    elif invalid == "empty-groups":
        groups = []
    elif invalid == "empty-ports":
        ports = []
    elif invalid == "group-count":
        groups.pop()
    elif invalid == "group-size":
        groups[0].pop()
    elif invalid == "overlap":
        groups[1][0] = groups[0][1]
    elif invalid == "duplicate-port":
        ports[1] = ports[0]
    elif invalid == "bad-port":
        ports[0] = 65536
    elif invalid == "bool-port":
        ports[0] = True
    elif invalid == "mixed-namespace":
        groups[1] = [
            "GPU-ad2367dd-a40e-6b86-6fc3-c44a2cc92c7e",
            "GPU-16a23983-e73e-0945-2095-cdeb50696982",
        ]
    elif invalid == "outer-string":
        groups = "7,3;9,2;8,4"
    else:
        ports = tuple(ports)
    with pytest.raises(deploy.DeploymentError, match="replica|GPU|port|device"):
        render(
            saved,
            indices["vllm"],
            format="compose",
            image="example/engine:1",
            replica_gpu_devices=groups,
            replica_host_ports=ports,
        )


@pytest.mark.parametrize("singular", [{"gpu_devices": ["7", "3"]}, {"host_port": 9001}])
def test_singular_and_replica_options_do_not_mix(native_fleet, singular):
    saved, indices = native_fleet
    with pytest.raises(deploy.DeploymentError, match="mix|singular|replica"):
        render(
            saved,
            indices["vllm"],
            format="compose",
            image="example/engine:1",
            replica_gpu_devices=GROUPS,
            replica_host_ports=PORTS,
            **singular,
        )


def test_uuid_group_order_is_canonical_and_case_aliases_are_disjoint():
    uuids = [
        [f"GPU-00000000-0000-0000-0000-{i:012x}" for i in (2, 1)],
        [f"GPU-00000000-0000-0000-0000-{i:012x}" for i in (4, 3)],
    ]
    saved = artifact(candidate_changes={"n_agents": 2, "tensor_parallel": 2, "gpus_total": 4})
    result = deploy.export_deployment(
        saved,
        format="compose",
        image="example/engine:1",
        replica_gpu_devices=uuids,
        replica_host_ports=[9001, 9002],
    )
    services = json.loads(result.content)["services"]
    assert [
        s["deploy"]["resources"]["reservations"]["devices"][0]["device_ids"]
        for s in services.values()
    ] == uuids
    uuids[1][0] = uuids[0][0].upper()
    with pytest.raises(deploy.DeploymentError, match="duplicate|overlap|disjoint"):
        deploy.export_deployment(
            saved,
            format="compose",
            image="example/engine:1",
            replica_gpu_devices=uuids,
            replica_host_ports=[9001, 9002],
        )


def test_fleet_total_can_exceed_single_replica_export_bound():
    saved = artifact(candidate_changes={"n_agents": 16, "tensor_parallel": 8, "gpus_total": 128})
    groups = [[str(8 * n + i) for i in range(8)] for n in range(16)]
    result = deploy.export_deployment(
        saved,
        format="compose",
        image="example/engine:1",
        replica_gpu_devices=groups,
        replica_host_ports=list(range(9000, 9016)),
    )
    assert len(json.loads(result.content)["services"]) == 16


@pytest.mark.parametrize(
    "changes",
    [
        {"n_agents": 17, "gpus_total": 17},
        {"n_agents": 3, "gpus_total": 5},
        {"n_agents": 2, "tensor_parallel": 65, "gpus_total": 130},
    ],
)
def test_invalid_original_population_or_per_replica_geometry_refuses(changes, monkeypatch):
    monkeypatch.setattr(
        deploy,
        "_replica_layout",
        lambda *args: pytest.fail("invalid original geometry reached layout traversal"),
    )
    with pytest.raises(deploy.DeploymentError, match="GPU|replica"):
        deploy.export_deployment(
            artifact(candidate_changes=changes),
            format="compose",
            image="example/engine:1",
            replica_gpu_devices=GROUPS,
            replica_host_ports=PORTS,
        )


@pytest.mark.parametrize(
    "format,backend,changes,inputs",
    [
        ("systemd", "vllm", {}, {}),
        ("compose", "tgi", {}, {}),
        ("compose", "ollama", {}, {}),
        ("compose", "vllm", {"mode": "batch"}, {"mode": "batch"}),
        ("compose", "vllm", {"offload_fraction": 0.1}, {}),
        ("compose", "vllm", {"lora_adapters": 1}, {}),
        ("compose", "vllm", {}, {"kv_quant": "q4"}),
    ],
)
def test_fleet_does_not_bypass_format_backend_mode_and_fidelity(format, backend, changes, inputs):
    saved = artifact(
        backend=backend,
        candidate_changes={"n_agents": 3, "gpus_total": 3, **changes},
        inputs=inputs,
    )
    with pytest.raises(deploy.DeploymentError):
        deploy.export_deployment(
            saved,
            format=format,
            image="example/engine:1" if format == "compose" else None,
            executable="/usr/bin/true" if format == "systemd" else None,
            replica_gpu_devices=[["7"], ["3"], ["9"]],
            replica_host_ports=PORTS,
        )


def test_single_candidate_rejects_replica_matrix_options():
    with pytest.raises(deploy.DeploymentError, match="replica"):
        deploy.export_deployment(
            artifact(),
            format="compose",
            image="example/engine:1",
            replica_gpu_devices=[["7"]],
            replica_host_ports=[9001],
        )


def test_fleet_cli_validates_complete_layout_before_new_output(native_fleet, tmp_path):
    saved, indices = native_fleet
    path, out = tmp_path / "plan.json", tmp_path / "fleet.json"
    saved.save(path)
    original = path.read_bytes()
    args = [
        "deploy",
        "--plan",
        str(path),
        "--candidate-index",
        str(indices["vllm"]),
        "--model",
        "org/manual-fleet",
        "--format",
        "compose",
        "--image",
        "example/engine:1",
        "--out",
        str(out),
    ]
    layout = []
    for group, port in zip(GROUPS, PORTS):
        layout += ["--replica-devices", ",".join(group), "--replica-port", str(port)]
    for invalid in (
        layout[:-2],
        [*layout, "--gpu-device", "7"],
        ["--replica-devices", " 7,3", "--replica-port", "9001"],
    ):
        result = CliRunner().invoke(app, [*args, *invalid])
        assert result.exit_code != 0 and not out.exists(), result.output
    result = CliRunner().invoke(app, [*args, *layout])
    assert result.exit_code == 0, result.output
    content = out.read_bytes()
    assert len(json.loads(content)["services"]) == 3
    assert CliRunner().invoke(app, [*args, *layout]).exit_code != 0
    assert out.read_bytes() == content and path.read_bytes() == original


def test_cli_group_input_is_bounded_before_split(native_fleet, tmp_path):
    saved, indices = native_fleet
    path = tmp_path / "plan.json"
    saved.save(path)
    out = tmp_path / "fleet.json"
    args = [
        "deploy",
        "--plan",
        str(path),
        "--candidate-index",
        str(indices["vllm"]),
        "--model",
        "org/manual-fleet",
        "--format",
        "compose",
        "--image",
        "example/engine:1",
        "--out",
        str(out),
    ]
    result = CliRunner().invoke(
        app, [*args, "--replica-devices", "1" * 3000, "--replica-port", "9001"]
    )
    assert result.exit_code != 0 and "bound" in result.output.lower() and not out.exists()


@pytest.fixture
def native_hf_fleet(tmp_path, monkeypatch):
    from test_ci_acceptance import load_script

    monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path / "cache"))
    observation = load_script("ci_checkpoint_identity").seed(live=False)
    saved = api.plan(
        api.PlanRequest(
            models=[observation["repo"]],
            model_revisions={observation["repo"]: observation["commit"]},
            hardware="RTX 4090 24GB",
            platform="linux",
            tensor_parallel=2,
            request_rate=2048,
            quality_target=0,
            budget=1e8,
            allow_network=False,
        )
    )
    index = next(
        i
        for i, c in enumerate(saved.to_dict()["result"]["candidates"])
        if c["backend"] == "vllm"
        and c["quant"] == "FP16"
        and c["n_agents"] == 3
        and c["gpus_total"] == 6
    )
    return saved, index


@pytest.mark.parametrize(
    "invalid",
    [
        "lost-service",
        "aggregate-batch",
        "lost-revision",
        "overlap",
        "port-alias",
        "host-cuda",
        "tp",
        "replica-label",
        "model",
    ],
)
def test_installed_fleet_validator_refuses_missing_population_or_native_drift(
    native_hf_fleet, invalid
):
    from test_ci_acceptance import load_script

    saved, index = native_hf_fleet
    script = load_script("ci_deploy_placement")
    compose = json.loads(
        deploy.export_deployment(
            saved,
            format="compose",
            candidate_index=index,
            image="example/engine:1",
            replica_gpu_devices=GROUPS,
            replica_host_ports=PORTS,
        ).content
    )
    script.validate_fleet(saved.to_dict(), index, compose)
    services = compose["services"]
    first = services["inference-1"]
    last = services["inference-3"]
    if invalid == "lost-service":
        services.pop("inference-3")
    elif invalid == "aggregate-batch":
        last["command"][last["command"].index("--max-num-seqs") + 1] = str(
            saved.candidate(index).effective_batch * 3
        )
    elif invalid == "lost-revision":
        last["command"].remove("--revision")
    elif invalid == "overlap":
        last["deploy"]["resources"]["reservations"]["devices"][0]["device_ids"] = GROUPS[0]
    elif invalid == "port-alias":
        last["ports"] = first["ports"]
    elif invalid == "host-cuda":
        last["environment"] = {"CUDA_VISIBLE_DEVICES": "8,4"}
    elif invalid == "tp":
        last["command"][last["command"].index("--tensor-parallel-size") + 1] = "1"
    elif invalid == "replica-label":
        last["labels"]["org.chimeraforge.replica-count"] = "1"
    else:
        last["command"][0] = "org/different-model"
    with pytest.raises(AssertionError):
        script.validate_fleet(saved.to_dict(), index, compose)
