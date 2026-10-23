"""Explicit GPU visibility is a declaration, never observed topology or rank mapping."""

import json

import pytest
from typer.testing import CliRunner

from chimeraforge import api, deploy
from chimeraforge.cli import app
from test_deploy import artifact

UUID_A = "GPU-ad2367dd-a40e-6b86-6fc3-c44a2cc92c7e"
UUID_B = "GPU-16a23983-e73e-0945-2095-cdeb50696982"


@pytest.fixture
def native_two_gpu():
    saved = api.plan(
        api.PlanRequest(
            models=["ci/manual-placement"],
            overrides={"params_b": 3.0, "n_layers": 28, "n_kv_heads": 8, "d_head": 128},
            hardware="RTX 4090 24GB",
            platform="linux",
            tensor_parallel=2,
            request_rate=0.01,
            latency_slo=10000,
            quality_target=0,
            budget=1e8,
            allow_network=False,
        )
    )
    index = next(
        i
        for i, row in enumerate(saved.to_dict()["result"]["candidates"])
        if row["backend"] == "vllm" and row["quant"] == "FP16" and row["n_agents"] == 1
    )
    assert saved.candidate(index).gpus_total == saved.candidate(index).tensor_parallel == 2
    return saved, index


def render(saved, index, **options):
    return deploy.export_deployment(
        saved, candidate_index=index, model="org/manual-placement", **options
    )


@pytest.mark.parametrize("devices", [["7", "3"], [UUID_B, UUID_A.upper()]])
def test_real_two_gpu_compose_ids_replace_count_without_host_ordinal_cuda_mapping(
    native_two_gpu, devices
):
    saved, index = native_two_gpu
    before = saved.to_dict()
    result = render(
        saved,
        index,
        format="compose",
        image="example/engine:1",
        gpu_devices=devices,
        host_port=9001,
    )
    service = json.loads(result.content)["services"]["inference"]
    expected = [d if d.isascii() and d.isdecimal() else "GPU-" + d[4:].lower() for d in devices]
    assert service["deploy"]["resources"]["reservations"]["devices"] == [
        {"driver": "nvidia", "device_ids": expected, "capabilities": ["gpu"]}
    ]
    assert "CUDA_VISIBLE_DEVICES" not in service.get("environment", {})
    assert service["ports"] == ["127.0.0.1:9001:8000"]
    assert service["command"][service["command"].index("--tensor-parallel-size") + 1] == "2"
    assert saved.to_dict() == before
    assert any("not verified" in note for note in result.notes)
    assert any("ordering" in note and "declaration" in note for note in result.notes)


@pytest.mark.parametrize("devices", [["7", "3"], [UUID_B, UUID_A.upper()]])
def test_systemd_application_device_order_is_explicit(native_two_gpu, devices):
    saved, index = native_two_gpu
    result = render(saved, index, format="systemd", executable="/usr/bin/true", gpu_devices=devices)
    expected = [d if d.isascii() and d.isdecimal() else "GPU-" + d[4:].lower() for d in devices]
    assert 'Environment="CUDA_VISIBLE_DEVICES=' + ",".join(expected) + '"' in result.content


@pytest.mark.parametrize(
    "devices",
    [
        [],
        ["0"],
        ["0", "1", "2"],
        "0,1",
        ("0", "1"),
        [0, 1],
        [False, "1"],
        ["00", "1"],
        ["+1", "2"],
        ["-1", "2"],
        [" 1", "2"],
        ["1 ", "2"],
        ["\u0661", "2"],
        ["0,1", "2"],
        ["1\n", "2"],
        ["0", "0"],
        [UUID_A, UUID_A.upper()],
        [UUID_A, "1"],
        ["GPU-ad2367dd", UUID_B],
        ["MIG-" + UUID_A[4:], UUID_B],
        ["GPU-zz2367dd-a40e-6b86-6fc3-c44a2cc92c7e", UUID_B],
        [None, "1"],
        True,
        ["1" * 41, "2"],
    ],
)
def test_invalid_device_selections_refuse(native_two_gpu, devices):
    saved, index = native_two_gpu
    with pytest.raises(deploy.DeploymentError, match="GPU|device"):
        render(saved, index, format="compose", image="example/engine:1", gpu_devices=devices)


@pytest.mark.parametrize("port", [0, -1, 65536, True, False, "9000", 9000.0])
def test_host_port_requires_an_actual_bounded_integer(port):
    with pytest.raises(deploy.DeploymentError, match="port"):
        deploy.export_deployment(
            artifact(), format="compose", image="example/engine:1", host_port=port
        )


@pytest.mark.parametrize(
    "backend,container,default", [("vllm", 8000, 8000), ("sglang", 30000, 30000), ("tgi", 80, 8080)]
)
@pytest.mark.parametrize("port", [1, 65535])
def test_port_override_changes_only_loopback_host_mapping(backend, container, default, port):
    saved = artifact(backend=backend)
    before = json.loads(
        deploy.export_deployment(saved, format="compose", image="example/engine:1").content
    )
    after = json.loads(
        deploy.export_deployment(
            saved, format="compose", image="example/engine:1", host_port=port
        ).content
    )
    assert before["services"]["inference"]["ports"] == [f"127.0.0.1:{default}:{container}"]
    assert after["services"]["inference"]["ports"] == [f"127.0.0.1:{port}:{container}"]
    after["services"]["inference"]["ports"] = before["services"]["inference"]["ports"]
    assert after == before


@pytest.mark.parametrize(
    "format,options",
    [
        ("launchd", {"gpu_devices": ["0"]}),
        ("modelfile", {"gpu_devices": ["0"]}),
        ("systemd", {"host_port": 9000}),
        ("launchd", {"host_port": 9000}),
        ("modelfile", {"host_port": 9000}),
    ],
)
def test_options_are_not_silently_ignored_by_unsupported_formats(format, options):
    with pytest.raises(deploy.DeploymentError, match="only"):
        deploy.export_deployment(artifact(), format=format, **options)


def test_unbounded_native_gpu_count_is_refused_before_default_device_iteration(monkeypatch):
    saved = artifact(candidate_changes={"gpus_total": 10**12, "tensor_parallel": 10**12})
    monkeypatch.setattr(
        deploy, "range", lambda *args: pytest.fail("unbounded GPU iteration"), raising=False
    )
    with pytest.raises(deploy.DeploymentError, match="GPU.*64|64.*GPU"):
        deploy.export_deployment(saved, format="systemd", executable="/usr/bin/true")


def test_oversize_and_custom_lists_refuse_before_element_traversal(native_two_gpu):
    class CustomList(list):
        def __iter__(self):
            pytest.fail("custom list traversed")

    saved, index = native_two_gpu
    for devices in ([object()] * 65, CustomList(["0", "1"])):
        with pytest.raises(deploy.DeploymentError, match="device|GPU"):
            render(saved, index, format="compose", image="example/engine:1", gpu_devices=devices)


def test_export_bound_accepts_exactly_sixty_four_devices():
    saved = artifact(candidate_changes={"gpus_total": 64, "tensor_parallel": 64})
    devices = [str(index) for index in range(64)]
    exported = deploy.export_deployment(
        saved, format="compose", image="example/engine:1", gpu_devices=devices
    )
    reservation = json.loads(exported.content)["services"]["inference"]["deploy"]["resources"][
        "reservations"
    ]["devices"][0]
    assert reservation["device_ids"] == devices and "count" not in reservation


def test_cli_repeatable_devices_port_and_refusals_preserve_plan_and_existing_output(
    native_two_gpu, tmp_path
):
    saved, index = native_two_gpu
    path, out = tmp_path / "plan.json", tmp_path / "compose.json"
    saved.save(path)
    original = path.read_bytes()
    args = [
        "deploy",
        "--plan",
        str(path),
        "--candidate-index",
        str(index),
        "--model",
        "org/manual-placement",
        "--format",
        "compose",
        "--image",
        "example/engine:1",
        "--out",
        str(out),
    ]
    for invalid in (
        ["--gpu-device", "0"],
        ["--gpu-device", "0", "--gpu-device", "0"],
        ["--host-port", "0"],
    ):
        result = CliRunner().invoke(app, [*args, *invalid])
        assert result.exit_code != 0 and not out.exists(), result.output
    result = CliRunner().invoke(
        app, [*args, "--gpu-device", "7", "--gpu-device", "3", "--host-port", "9001"]
    )
    assert result.exit_code == 0, result.output
    content = out.read_bytes()
    service = json.loads(content)["services"]["inference"]
    assert service["ports"] == ["127.0.0.1:9001:8000"]
    assert service["deploy"]["resources"]["reservations"]["devices"][0]["device_ids"] == ["7", "3"]
    assert CliRunner().invoke(app, [*args, "--host-port", "9002"]).exit_code != 0
    assert out.read_bytes() == content and path.read_bytes() == original


@pytest.mark.parametrize("format", ["compose", "systemd"])
def test_explicit_absence_is_byte_identical_to_legacy_defaults(format):
    kwargs = (
        {"image": "example/engine:1"} if format == "compose" else {"executable": "/usr/bin/true"}
    )
    saved = artifact()
    before = deploy.export_deployment(saved, format=format, **kwargs).to_dict()
    after = deploy.export_deployment(
        saved, format=format, gpu_devices=None, host_port=None, **kwargs
    ).to_dict()
    assert before == after


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"n_agents": 2, "gpus_total": 2}, "replica"),
        ({"offload_fraction": 0.2}, "offload"),
        ({"lora_adapters": 1}, "adapter"),
        ({"tensor_parallel": 2, "gpus_total": 1}, "GPU count"),
    ],
)
def test_placement_does_not_bypass_native_fidelity(changes, message):
    with pytest.raises(deploy.DeploymentError, match=message):
        deploy.export_deployment(
            artifact(candidate_changes=changes),
            format="compose",
            image="example/engine:1",
            gpu_devices=["7"],
            host_port=9001,
        )


@pytest.mark.parametrize(
    "invalid",
    [
        "count",
        "order",
        "host-cuda",
        "capabilities",
        "host-bind",
        "container-port",
        "tp",
        "systemd-order",
    ],
)
def test_installed_validator_requires_actual_placement_and_native_controls(native_two_gpu, invalid):
    from test_ci_acceptance import load_script

    saved, index = native_two_gpu
    script = load_script("ci_deploy_placement")
    compose = json.loads(
        render(
            saved,
            index,
            format="compose",
            image="example/engine:1",
            gpu_devices=["7", "3"],
            host_port=9001,
        ).content
    )
    unit = render(
        saved, index, format="systemd", executable="/usr/bin/true", gpu_devices=["7", "3"]
    ).content
    script.validate(saved.to_dict(), index, compose, unit)
    service = compose["services"]["inference"]
    device = service["deploy"]["resources"]["reservations"]["devices"][0]
    if invalid == "count":
        device["count"] = 2
    elif invalid == "order":
        device["device_ids"] = ["3", "7"]
    elif invalid == "host-cuda":
        service["environment"] = {"CUDA_VISIBLE_DEVICES": "7,3"}
    elif invalid == "capabilities":
        device["capabilities"] = []
    elif invalid == "host-bind":
        service["ports"] = ["0.0.0.0:9001:8000"]
    elif invalid == "container-port":
        service["ports"] = ["127.0.0.1:9001:9001"]
    elif invalid == "tp":
        service["command"][service["command"].index("--tensor-parallel-size") + 1] = "1"
    else:
        unit = unit.replace("CUDA_VISIBLE_DEVICES=7,3", "CUDA_VISIBLE_DEVICES=3,7")
    with pytest.raises(AssertionError):
        script.validate(saved.to_dict(), index, compose, unit)
