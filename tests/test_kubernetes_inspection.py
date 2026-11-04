"""Original declarations precede bounded read-only controller observations."""

from __future__ import annotations

import json
import asyncio
from dataclasses import asdict, fields, replace
import os
from pathlib import Path
import sys

import pytest

from chimeraforge import api, deploy
from test_kubernetes_export import native_plans as native_plans


@pytest.fixture
def protocol(monkeypatch, native_plans, tmp_path):
    """Controlled responses use real owned Python pipes; not native kubectl proof."""
    from chimeraforge import kubernetes_inspection_process as process
    from chimeraforge import kubernetes_inspection as inspection
    from chimeraforge.kubernetes_inspection import CA_PATHS, USER_PATHS, PROVIDER_TEMPLATE
    from test_kubernetes_inspection_intent import defaulted

    native_which = inspection.shutil.which
    client = tmp_path / "controlled-native-client.exe"
    client.write_bytes(b"fictional-native-client-not-a-real-binary")
    client.chmod(0o700)
    monkeypatch.setattr(
        inspection.shutil,
        "which",
        lambda command: str(client) if command == "kubectl" else native_which(command),
    )
    saved, index, options = original_intent(native_plans)
    objects = json.loads(
        deploy.export_deployment(
            saved,
            format="kubernetes",
            candidate_index=index,
            image="example/engine:1",
            model="org/manual-fleet",
            kubernetes=options,
        ).content
    )["items"]
    scenario = {
        "provider": b"provider_absent",
        "ca": [],
        "files": [],
        "calls": [],
        "objects": {obj["metadata"]["name"] + obj["kind"]: defaulted(obj) for obj in objects},
        "pending": False,
        "started": asyncio.Event(),
        "processes": [],
        "created": [],
        "client_version": "v1.37.1",
        "server_version": "v1.37.0",
        "first_launch": None,
    }
    native_launch = asyncio.create_subprocess_exec

    async def launch(*argv, **kwargs):
        if scenario["first_launch"] is not None:
            callback, scenario["first_launch"] = scenario["first_launch"], None
            callback()
        scenario["calls"].append(list(argv))
        scenario["created"].append(dict(kwargs["env"]))
        code, payload = 0, b""
        held = False
        if "version" in argv:
            data = {"clientVersion": {"gitVersion": scenario["client_version"]}}
            if "--client=true" not in argv:
                data["serverVersion"] = {"gitVersion": scenario["server_version"]}
            payload = json.dumps(data).encode()
        elif "view" in argv:
            expression = argv[argv.index("--template") + 1]
            if expression == PROVIDER_TEMPLATE:
                payload = scenario["provider"]
            else:
                assert expression in (CA_PATHS, USER_PATHS)
                value = scenario["ca"] if expression == CA_PATHS else scenario["files"]
                payload = value if isinstance(value, bytes) else json.dumps(value).encode()
        else:
            assert "get" in argv
            name = argv[argv.index("get") + 2]
            kind = "Deployment" if "deployments.apps" in argv else "Service"
            observed = scenario["objects"][name + kind]
            if isinstance(observed, bytes):
                payload = observed
            elif observed is None:
                payload = b""
            elif observed == "failure":
                code, payload = 1, b"private-config-canary"
            else:
                payload = json.dumps(observed).encode()
            held = scenario["pending"]
        script = (
            "import sys,time;sys.stdout.buffer.write("
            + repr(payload)
            + ");sys.stdout.flush();"
            + ("time.sleep(30)" if held else f"sys.exit({code})")
        )
        child = await native_launch(sys.executable, "-I", "-c", script, **kwargs)
        scenario["processes"].append(child)
        if held:
            scenario["started"].set()
        return child

    monkeypatch.setattr(process.asyncio, "create_subprocess_exec", launch)
    return scenario


async def inspect_fixture(native_plans, tmp_path, **kwargs):
    saved, index, options = original_intent(native_plans)
    config = tmp_path / "private-config-canary"
    config.write_text("private-config-canary", encoding="utf-8")
    return await api.inspect_kubernetes_deployment(
        saved,
        candidate_index=index,
        model="org/manual-fleet",
        image="example/engine:1",
        kubernetes=options,
        kubeconfig=config,
        context="private-context-canary",
        timeout_s=5,
        **kwargs,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("type", 1),
        ("status", False),
        ("reason", ["ProgressDeadlineExceeded"]),
        ("message", {"private-condition-canary": "not-a-string"}),
    ],
)
async def test_public_inspection_rejects_malformed_native_condition_strings(
    native_plans, tmp_path, protocol, field, value
):
    observed = next(iter(protocol["objects"].values()))
    observed["status"]["conditions"] = [{"type": "Progressing", field: value}]
    result = await inspect_fixture(native_plans, tmp_path)
    assert result.exit_code == 4, result.to_dict()
    assert result.resources[0]["intent"]["state"] == "match"
    assert result.resources[0]["rollout"] == {
        "state": "unknown",
        "reason": "native_rollout_invalid",
    }
    assert len(result.resources) == 6
    assert result._data["cleanup"]["owned_processes"] == 11
    assert result._data["cleanup"]["closed_processes"] == 11
    assert "private-condition-canary" not in json.dumps(result.to_dict())
    assert all(child.returncode is not None for child in protocol["processes"])


@pytest.mark.asyncio
@pytest.mark.parametrize("family", ["generation", "replicas"])
@pytest.mark.parametrize("overflow", [False, True])
async def test_public_inspection_native_integer_width_boundary(
    native_plans, tmp_path, protocol, family, overflow
):
    observed = next(iter(protocol["objects"].values()))
    width = 63 if family == "generation" else 31
    value = (1 << width) - 1 + int(overflow)
    if family == "generation":
        observed["metadata"]["generation"] = value
        observed["status"]["observedGeneration"] = value
    else:
        for field in ("updatedReplicas", "replicas", "availableReplicas"):
            observed["status"][field] = value
    result = await inspect_fixture(native_plans, tmp_path)
    assert result.exit_code == (4 if overflow else 0), result.to_dict()
    assert result.resources[0]["rollout"]["state"] == ("unknown" if overflow else "complete")
    assert len(result.resources) == 6
    assert result._data["cleanup"]["owned_processes"] == 11
    assert result._data["cleanup"]["closed_processes"] == 11
    assert all(child.returncode is not None for child in protocol["processes"])


@pytest.mark.asyncio
@pytest.mark.parametrize("condition", [{}, {"type": "Progressing"}])
async def test_public_inspection_keeps_omitted_optional_condition_fields(
    native_plans, tmp_path, protocol, condition
):
    observed = next(iter(protocol["objects"].values()))
    observed["status"]["conditions"] = [condition]
    result = await inspect_fixture(native_plans, tmp_path)
    assert result.exit_code == 0
    assert result.resources[0]["rollout"]["state"] == "complete"


def original_intent(native_plans):
    saved, indices = native_plans[3]
    options = api.KubernetesOptions(namespace="inspection", name_prefix="original")
    declaration = json.loads(
        deploy.export_deployment(
            saved,
            format="kubernetes",
            candidate_index=indices["vllm"],
            image="example/engine:1",
            model="org/manual-fleet",
            kubernetes=options,
        ).content
    )
    assert len(declaration["items"]) == 6
    assert [row["kind"] for row in declaration["items"]] == ["Deployment", "Service"] * 3
    assert all(
        row["spec"]["replicas"] == 1
        and row["spec"]["template"]["spec"]["containers"][0]["resources"]["limits"][
            "nvidia.com/gpu"
        ]
        == "2"
        for row in declaration["items"]
        if row["kind"] == "Deployment"
    )
    return saved, indices["vllm"], options


@pytest.mark.asyncio
@pytest.mark.parametrize("alias", [False, True])
@pytest.mark.parametrize("paired", [False, True])
async def test_native_client_file_is_protected_by_public_delayed_writers(
    native_plans, tmp_path, protocol, alias, paired
):
    client = tmp_path / "client-canary.exe"
    original = b"fictional-native-client-not-a-real-binary"
    client.write_bytes(original)
    client.chmod(0o700)
    target = tmp_path / "client-alias.exe" if alias else client
    if alias:
        os.link(client, target)
    result = await inspect_fixture(native_plans, tmp_path, kubectl=client)
    assert result.exit_code == 0
    output = tmp_path / "paired.json"
    with pytest.raises(api.KubernetesInspectionError):
        if paired:
            api.write_kubernetes_inspection(result, out=output, junit=target)
        else:
            result.save(target)
    assert client.read_bytes() == target.read_bytes() == original
    assert not output.exists()


@pytest.mark.parametrize("alias", [False, True])
@pytest.mark.parametrize("sink", ["--out", "--junit"])
def test_cli_native_client_output_alias_refuses_before_launch(
    native_plans, tmp_path, protocol, alias, sink
):
    from typer.testing import CliRunner
    from chimeraforge.cli import app

    saved, index, _ = original_intent(native_plans)
    source, config, client = (tmp_path / name for name in ("source.json", "config", "client.exe"))
    saved.save(source)
    config.write_bytes(b"fictional-config")
    original = b"fictional-native-client-not-a-real-binary"
    client.write_bytes(original)
    client.chmod(0o700)
    target = tmp_path / "alias.exe" if alias else client
    if alias:
        os.link(client, target)
    response = CliRunner().invoke(
        app,
        [
            "deploy-inspect",
            "--plan",
            str(source),
            "--image",
            "example/engine:1",
            "--model",
            "org/manual-fleet",
            "--candidate-index",
            str(index),
            "--namespace",
            "inspection",
            "--name-prefix",
            "original",
            "--kubeconfig",
            str(config),
            "--context",
            "fixture",
            "--kubectl",
            str(client),
            sink,
            str(target),
            "--json",
        ],
    )
    assert response.exit_code == 2, response.output
    assert protocol["calls"] == []
    assert client.read_bytes() == target.read_bytes() == original


@pytest.mark.asyncio
@pytest.mark.parametrize("bare", [False, True])
async def test_selected_native_client_is_held_before_await_and_cwd_path_changes(
    native_plans, tmp_path, protocol, monkeypatch, bare
):
    from chimeraforge import kubernetes_inspection as inspection

    tools, later = tmp_path / "tools", tmp_path / "later"
    tools.mkdir()
    later.mkdir()
    client = tools / "held-native-client.exe"
    original = b"fictional-selected-native-client"
    client.write_bytes(original)
    client.chmod(0o700)
    (later / client.name).write_bytes(b"fictional-other-client")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", str(tools))
    supplied = client.name if bare else str(Path("tools") / client.name)
    calls = []
    native_which = inspection.shutil.which

    def choose(value):
        calls.append(value)
        return native_which(value)

    def change_environment():
        monkeypatch.chdir(later)
        monkeypatch.setenv("PATH", str(later))

    monkeypatch.setattr(inspection.shutil, "which", choose)
    protocol["first_launch"] = change_environment
    result = await inspect_fixture(native_plans, tmp_path, kubectl=supplied)
    assert result.exit_code == 0
    assert calls == [supplied]
    assert len(protocol["calls"]) == 11
    assert all(call[0] == str(client) for call in protocol["calls"])
    for receipt in (result, replace(result)):
        with pytest.raises(api.KubernetesInspectionError):
            receipt.save(client)
    assert client.read_bytes() == original
    assert str(client) not in json.dumps(asdict(result))


@pytest.mark.asyncio
async def test_missing_native_tool_keeps_every_original_resource_unavailable(
    native_plans, tmp_path
):
    saved, index, options = original_intent(native_plans)
    config = tmp_path / "private.cfg"
    config.write_text(json.dumps({"apiVersion": "v1", "kind": "Config"}), encoding="utf-8")
    result = await api.inspect_kubernetes_deployment(
        saved,
        image="example/engine:1",
        candidate_index=index,
        model="org/manual-fleet",
        kubernetes=options,
        kubeconfig=config,
        context="fixture",
        kubectl=tmp_path / "nonexistent-kubectl",
        timeout_s=2,
    )
    data = result.to_dict()
    assert result.exit_code == 4 and len(data["resources"]) == 6
    assert all(row["intent"]["state"] == "unknown" for row in data["resources"])
    assert data["cleanup"]["state"] == "completed"


def test_inspection_cli_has_a_native_unavailable_receipt_not_usage_failure(native_plans, tmp_path):
    from typer.testing import CliRunner
    from chimeraforge.cli import app

    saved, index, _ = original_intent(native_plans)
    source, config = tmp_path / "plan.json", tmp_path / "private.cfg"
    saved.save(source)
    config.write_text(json.dumps({"apiVersion": "v1", "kind": "Config"}), encoding="utf-8")
    result = CliRunner().invoke(
        app,
        [
            "deploy-inspect",
            "--plan",
            str(source),
            "--image",
            "example/engine:1",
            "--model",
            "org/manual-fleet",
            "--candidate-index",
            str(index),
            "--namespace",
            "inspection",
            "--name-prefix",
            "original",
            "--kubeconfig",
            str(config),
            "--context",
            "fixture",
            "--kubectl",
            str(tmp_path / "nonexistent-kubectl"),
            "--timeout",
            "2",
            "--json",
        ],
    )
    assert result.exit_code == 4, result.output
    assert len(json.loads(result.stdout)["resources"]) == 6


@pytest.mark.asyncio
async def test_owned_fixture_retains_population_and_excludes_private_state(
    native_plans, tmp_path, protocol, monkeypatch
):
    monkeypatch.setenv("KUBERC", "off")
    monkeypatch.setenv("KUBECTL_KUBERC", "false")
    original_home = os.environ.get("HOME")
    result = await inspect_fixture(native_plans, tmp_path)
    data = result.to_dict()
    assert result.exit_code == 0 and len(result.resources) == 6
    assert all(row["intent"]["state"] == "match" for row in data["resources"])
    assert data["cleanup"]["closed_processes"] == data["cleanup"]["owned_processes"] == 11
    assert data["cleanup"]["runtime_files_closed"]
    assert len(protocol["calls"]) == 11
    assert all(
        call[call.index("--context") + 1] == "private-context-canary" for call in protocol["calls"]
    )
    assert all(call[call.index("--namespace") + 1] == "inspection" for call in protocol["calls"])
    assert all(
        env["KUBECTL_KUBERC"] == "true" and "KUBERC" not in env and "HOMEPATH" not in env
        for env in protocol["created"]
    )
    assert all(not Path(env["HOME"]).exists() for env in protocol["created"])
    assert os.environ["KUBERC"] == "off" and os.environ.get("HOME") == original_home
    assert all(child.returncode is not None for child in protocol["processes"])
    assert {field.name for field in fields(result)} == {"_data"}
    assert "private-config-canary" not in json.dumps(asdict(result))
    assert "private-context-canary" not in result.json_bytes().decode()
    assert replace(result)._input_paths == result._input_paths
    for copy in (result, replace(result)):
        with pytest.raises(api.KubernetesInspectionError):
            copy.save(tmp_path / "private-config-canary")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response", [b"provider_present", b"private-config-canary", b"provider_absent\n"]
)
async def test_unsupported_or_malformed_provider_projection_blocks_every_server_contact(
    native_plans, tmp_path, protocol, response
):
    protocol["provider"] = response
    result = await inspect_fixture(native_plans, tmp_path)
    assert result.exit_code == 4 and len(result.resources) == 6
    assert len(protocol["calls"]) == 2
    assert not any("get" in call for call in protocol["calls"])
    assert all(row["observation"]["state"] == "unstarted" for row in result.resources)
    assert "private-config-canary" not in result.json_bytes().decode()


@pytest.mark.asyncio
async def test_known_missing_and_drift_take_priority_over_other_unknown_and_pending(
    native_plans, tmp_path, protocol
):
    names = list(protocol["objects"])
    protocol["objects"][names[0]]["spec"]["template"]["spec"]["containers"][0]["image"] = (
        "private-live-value"
    )
    protocol["objects"][names[1]] = None
    protocol["objects"][names[2]] = b"{invalid private-live-value"
    protocol["objects"][names[4]]["status"]["availableReplicas"] = 0
    result = await inspect_fixture(native_plans, tmp_path)
    assert result.exit_code == 5
    assert [row["intent"]["state"] for row in result.resources] == [
        "drift",
        "missing",
        "unknown",
        "match",
        "match",
        "match",
    ]
    assert result.resources[4]["rollout"]["state"] == "pending"
    assert "private-live-value" not in result.json_bytes().decode()
    from chimeraforge.kubernetes_inspection_output import materialize
    from xml.etree import ElementTree as ET

    _, xml = materialize(result)
    suite = ET.fromstring(xml)
    assert suite.get("tests") == "10" and len(suite.findall("testcase")) == 10
    assert int(suite.get("failures")) == 2 and int(suite.get("errors")) >= 3


@pytest.mark.asyncio
async def test_relative_private_paths_use_lexical_config_parent_and_guard_later_writer(
    native_plans, tmp_path, protocol
):
    protocol["files"] = ["relative.key"]
    original = tmp_path / "relative.key"
    original.write_bytes(b"private-key-canary")
    result = await inspect_fixture(native_plans, tmp_path)
    assert original in result._input_paths
    output = tmp_path / "safe.json"
    with pytest.raises(api.KubernetesInspectionError):
        api.write_kubernetes_inspection(result, out=output, junit=original)
    assert not output.exists() and original.read_bytes() == b"private-key-canary"
    assert "private-key-canary" not in result.json_bytes().decode()


@pytest.mark.asyncio
async def test_repeated_public_cancellation_joins_real_children_before_runtime_files_close(
    native_plans, tmp_path, protocol, monkeypatch
):
    from chimeraforge.kubernetes_inspection_process import ProcessOwner

    protocol["pending"] = True
    closing, release = asyncio.Event(), asyncio.Event()
    native_close = ProcessOwner._close_child

    async def held_close(self, child):
        closing.set()
        await release.wait()
        return await native_close(self, child)

    monkeypatch.setattr(ProcessOwner, "_close_child", held_close)
    task = asyncio.create_task(inspect_fixture(native_plans, tmp_path))
    try:
        await asyncio.wait_for(protocol["started"].wait(), 5)
        task.cancel()
        await asyncio.wait_for(closing.wait(), 5)
        task.cancel()
        done, _ = await asyncio.wait({task}, timeout=0.05)
        assert not done and all(Path(env["HOME"]).exists() for env in protocol["created"])
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert task.cancelled()
    assert all(child.returncode is not None for child in protocol["processes"])
    assert all(not Path(env["HOME"]).exists() for env in protocol["created"])


@pytest.mark.asyncio
@pytest.mark.parametrize("version,expected_calls", [("client_version", 1), ("server_version", 5)])
async def test_unsupported_native_versions_never_fall_back(
    native_plans, tmp_path, protocol, version, expected_calls
):
    protocol[version] = "v0.private-version-canary"
    result = await inspect_fixture(native_plans, tmp_path)
    assert result.exit_code == 4 and len(protocol["calls"]) == expected_calls
    assert all(row["observation"]["state"] == "unstarted" for row in result.resources)
    assert "private-version-canary" not in result.json_bytes().decode()


@pytest.mark.asyncio
async def test_initial_stop_retains_all_rows_without_a_native_launch(
    native_plans, tmp_path, protocol
):
    stopped = asyncio.Event()
    stopped.set()
    result = await inspect_fixture(native_plans, tmp_path, stop_event=stopped)
    assert result.exit_code == 4 and result._data["budget"]["termination"] == "caller_stop"
    assert len(result.resources) == 6 and not protocol["calls"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "control,value",
    [
        ("request_timeout_s", 0),
        ("concurrency", True),
        ("request_timeout_s", 0.00001),
        ("concurrency", 5),
        ("cleanup_timeout_s", float("nan")),
    ],
)
async def test_invalid_control_admission_precedes_every_process(
    native_plans, tmp_path, protocol, control, value
):
    with pytest.raises(api.KubernetesInspectionError):
        await inspect_fixture(native_plans, tmp_path, **{control: value})
    assert not protocol["calls"]


@pytest.mark.asyncio
async def test_paired_export_preflights_both_complete_encodings(
    native_plans, tmp_path, protocol, monkeypatch
):
    from chimeraforge import kubernetes_inspection_output as output
    from chimeraforge import kubernetes_inspection_types as types

    result = await inspect_fixture(native_plans, tmp_path)
    out, junit = tmp_path / "out.json", tmp_path / "junit.xml"
    out.write_bytes(b"prior-json")
    junit.write_bytes(b"prior-xml")
    monkeypatch.setattr(output, "MAX_JUNIT_BYTES", 10)
    with pytest.raises(api.KubernetesInspectionError):
        api.write_kubernetes_inspection(result, out=out, junit=junit)
    assert out.read_bytes() == b"prior-json" and junit.read_bytes() == b"prior-xml"
    monkeypatch.setattr(output, "MAX_JUNIT_BYTES", 64 * 1024)
    monkeypatch.setattr(types, "MAX_REPORT_BYTES", 10)
    with pytest.raises(api.KubernetesInspectionError):
        result.to_dict()
    assert len(result.resources) == 6 and result.exit_code == 0
    with pytest.raises(api.KubernetesInspectionError):
        api.write_kubernetes_inspection(result, out=out, junit=junit)
    assert out.read_bytes() == b"prior-json" and junit.read_bytes() == b"prior-xml"


@pytest.mark.asyncio
async def test_hardlink_private_input_alias_and_paired_alias_do_not_clobber(
    native_plans, tmp_path, protocol
):
    key = tmp_path / "key.pem"
    key.write_bytes(b"private-key-canary")
    alias = tmp_path / "key-alias.pem"
    os.link(key, alias)
    protocol["files"] = [str(key)]
    result = await inspect_fixture(native_plans, tmp_path)
    with pytest.raises(api.KubernetesInspectionError):
        api.write_kubernetes_inspection(result, out=alias)
    assert key.read_bytes() == alias.read_bytes() == b"private-key-canary"
    destination = tmp_path / "paired.json"
    with pytest.raises(api.KubernetesInspectionError):
        api.write_kubernetes_inspection(result, out=destination, junit=destination)
    assert not destination.exists()


def test_cli_private_reference_output_alias_is_refused_before_server_contact(
    native_plans, tmp_path, protocol
):
    from chimeraforge.cli import app
    from typer.testing import CliRunner

    saved, index, _ = original_intent(native_plans)
    source, config, key = (tmp_path / name for name in ("plan.json", "config", "private.key"))
    saved.save(source)
    config.write_text("private-config-canary", encoding="utf-8")
    key.write_bytes(b"private-key-canary")
    protocol["files"] = ["private.key"]
    result = CliRunner().invoke(
        app,
        [
            "deploy-inspect",
            "--plan",
            str(source),
            "--image",
            "example/engine:1",
            "--model",
            "org/manual-fleet",
            "--candidate-index",
            str(index),
            "--namespace",
            "inspection",
            "--name-prefix",
            "original",
            "--kubeconfig",
            str(config),
            "--context",
            "fixture",
            "--out",
            str(key),
            "--json",
        ],
    )
    assert result.exit_code == 2 and len(protocol["calls"]) == 4
    assert json.loads(result.stdout)["exit_code"] == 2
    assert "resources" not in result.stdout and "private-key-canary" not in result.stdout
    assert key.read_bytes() == b"private-key-canary"
    assert not any("get" in call for call in protocol["calls"])


@pytest.mark.asyncio
async def test_tiny_native_request_duration_is_never_zero(native_plans, tmp_path, protocol):
    result = await inspect_fixture(native_plans, tmp_path, request_timeout_s=0.001)
    assert result.exit_code == 0
    assert all(
        float(
            next(arg.split("=", 1)[1][:-1] for arg in call if arg.startswith("--request-timeout="))
        )
        > 0
        for call in protocol["calls"]
    )


@pytest.mark.asyncio
async def test_missing_client_cannot_publish_over_an_unenumerated_config_reference(
    native_plans, tmp_path
):
    saved, index, options = original_intent(native_plans)
    key, config = tmp_path / "credential", tmp_path / "config"
    key.write_bytes(b"private-input-canary")
    config.write_text(
        json.dumps(
            {
                "apiVersion": "v1",
                "kind": "Config",
                "clusters": [{"name": "fixture", "cluster": {"server": "https://127.0.0.1:1"}}],
                "users": [{"name": "fixture", "user": {"tokenFile": "credential"}}],
                "contexts": [
                    {"name": "fixture", "context": {"cluster": "fixture", "user": "fixture"}}
                ],
                "current-context": "fixture",
            }
        ),
        encoding="utf-8",
    )
    result = await api.inspect_kubernetes_deployment(
        saved,
        image="example/engine:1",
        candidate_index=index,
        model="org/manual-fleet",
        kubernetes=options,
        kubeconfig=config,
        context="fixture",
        kubectl=tmp_path / "absent-client",
    )
    out = tmp_path / "out.json"
    with pytest.raises(api.KubernetesInspectionError):
        api.write_kubernetes_inspection(result, out=out, junit=key)
    assert not out.exists() and key.read_bytes() == b"private-input-canary"
    assert result.exit_code == 4 and len(result.to_dict()["resources"]) == 6
    result._data["preflight"]["private_projection_complete"] = True
    for copied in (result, replace(result)):
        assert copied._can_publish_files is False
        with pytest.raises(api.KubernetesInspectionError):
            copied.save(key)
    assert key.read_bytes() == b"private-input-canary"


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["provider", "late_projection"])
async def test_incomplete_private_inventory_cannot_publish_any_paired_file(
    native_plans, tmp_path, protocol, phase
):
    key = tmp_path / "credential"
    key.write_bytes(b"private-input-canary")
    if phase == "provider":
        protocol["provider"] = b"provider_present"
    else:
        protocol["ca"] = [str(key)]
        protocol["files"] = b"invalid-private-projection"
    result = await inspect_fixture(native_plans, tmp_path)
    assert result.exit_code == 4 and not result._data["preflight"]["private_projection_complete"]
    out = tmp_path / "out.json"
    with pytest.raises(api.KubernetesInspectionError):
        api.write_kubernetes_inspection(result, out=out, junit=key)
    assert not out.exists() and key.read_bytes() == b"private-input-canary"
    assert not any("get" in call for call in protocol["calls"])


@pytest.mark.asyncio
async def test_caller_stop_during_cleanup_retains_completed_rows_but_is_not_pass(
    native_plans, tmp_path, protocol, monkeypatch
):
    from chimeraforge.kubernetes_inspection_process import ProcessOwner

    stop, closing, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    native_close = ProcessOwner._close_child

    async def held_close(self, child):
        closing.set()
        await release.wait()
        return await native_close(self, child)

    monkeypatch.setattr(ProcessOwner, "_close_child", held_close)
    task = asyncio.create_task(inspect_fixture(native_plans, tmp_path, stop_event=stop))
    try:
        await asyncio.wait_for(closing.wait(), 5)
        stop.set()
    finally:
        release.set()
        result = await task
    assert result.exit_code == 4 and result._data["budget"]["termination"] == "caller_stop"
    assert result._data["cleanup"]["state"] == "completed"
    assert all(row["intent"]["state"] == "match" for row in result.resources)
    assert all(row["observation"]["state"] == "complete" for row in result.resources)


@pytest.mark.asyncio
@pytest.mark.parametrize("late_observation", [False, True])
async def test_controlled_clock_separates_observation_and_cleanup_budgets(
    native_plans, tmp_path, protocol, monkeypatch, late_observation
):
    from types import SimpleNamespace
    from chimeraforge import kubernetes_inspection as inspection
    from chimeraforge import kubernetes_inspection_process as process

    clock = [0.0]
    synthetic = SimpleNamespace(perf_counter=lambda: clock[0])
    monkeypatch.setattr(inspection, "time", synthetic)
    monkeypatch.setattr(process, "time", synthetic)
    native_compare, native_close = inspection.compare_intent, process.ProcessOwner._close_child
    compared = 0

    def complete_response(expected, actual):
        nonlocal compared
        result = native_compare(expected, actual)
        compared += 1
        if compared == 6:
            clock[0] = 5.25 if late_observation else 4.5
        return result

    async def close(self, child):
        if not late_observation:
            clock[0] = 5.5
        return await native_close(self, child)

    monkeypatch.setattr(inspection, "compare_intent", complete_response)
    monkeypatch.setattr(process.ProcessOwner, "_close_child", close)
    result = await inspect_fixture(native_plans, tmp_path)
    assert compared == 6 and all(row["intent"]["state"] == "match" for row in result.resources)
    assert result._data["cleanup"]["state"] == "completed"
    assert result.exit_code == (4 if late_observation else 0)
    assert result._data["budget"]["termination"] == (
        "observation_deadline" if late_observation else None
    )
    assert result._data["budget"]["elapsed_seconds"] > 5


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["vllm", "sglang"])
async def test_original_n1_uses_two_resources_and_four_cases(
    native_plans, tmp_path, protocol, backend
):
    from test_kubernetes_inspection_intent import defaulted
    from chimeraforge.kubernetes_inspection_output import materialize
    from xml.etree import ElementTree as ET

    saved, indices = native_plans[1]
    options = api.KubernetesOptions(namespace="inspection", name_prefix="original")
    manifest = json.loads(
        deploy.export_deployment(
            saved,
            format="kubernetes",
            image="example/engine:1",
            model="org/manual-fleet",
            candidate_index=indices[backend],
            kubernetes=options,
        ).content
    )
    protocol["objects"] = {
        row["metadata"]["name"] + row["kind"]: defaulted(row) for row in manifest["items"]
    }
    config = tmp_path / "config"
    config.write_text("controlled", encoding="utf-8")
    result = await api.inspect_kubernetes_deployment(
        saved,
        image="example/engine:1",
        model="org/manual-fleet",
        candidate_index=indices[backend],
        kubernetes=options,
        kubeconfig=config,
        context="fixture",
    )
    assert result.exit_code == 0 and len(result.resources) == 2
    assert result._data["budget"]["processes"] == 7
    _, xml = materialize(result)
    assert len(ET.fromstring(xml).findall("testcase")) == 4
