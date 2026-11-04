"""Offline drift compares independent intent with fully admitted held files."""

import hashlib
import json
import os
import traceback
from pathlib import Path

import pytest
from typer.testing import CliRunner

from chimeraforge.api import PlanArtifact
from chimeraforge.cli import app
from chimeraforge.deploy import export_deployment
from chimeraforge.planner.resolver import SOURCE_OLLAMA
from test_deploy import artifact
import test_deploy_fleets as fleet_fixtures
from test_deploy_fleets import GROUPS, PORTS

native_fleet = fleet_fixtures.native_fleet
native_hf_fleet = fleet_fixtures.native_hf_fleet

CANARY = "PRIVATE_CANARY_DO_NOT_DISCLOSE"


def verifier():
    from chimeraforge import deployment_verify

    return deployment_verify


def written(tmp_path, saved=None, **intent):
    saved = saved or artifact()
    intent = {"image": "example/engine:1", **intent}
    exported = export_deployment(saved, format="compose", **intent)
    config = tmp_path / "compose.json"
    config.write_text(exported.content, encoding="utf-8")
    for name, value in exported.files.items():
        (tmp_path / name).write_bytes(value.encode())
    return saved, config, intent


def check(saved, config, **intent):
    return verifier().verify_deployment(saved, config, **intent)


@pytest.mark.parametrize("backend", ["vllm", "sglang", "tgi", "ollama"])
def test_all_native_compose_backends_match_without_writes(tmp_path, backend):
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
    saved, path, intent = written(tmp_path, saved)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    result = check(saved, path, **intent)
    assert result.exit_code == 0 and result.status == "match"
    assert result.change_count == 0 and not result.changes
    assert result.config_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result.renderer_version
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
    assert len(result.companions) == (1 if backend == "ollama" else 0)


@pytest.mark.parametrize("backend", ["vllm", "sglang"])
def test_actual_native_fleet_holds_all_original_replicas(tmp_path, native_fleet, backend):
    saved, indices = native_fleet
    before = saved.to_dict()
    saved, path, intent = written(
        tmp_path,
        saved,
        candidate_index=indices[backend],
        model="org/manual-fleet",
        replica_gpu_devices=GROUPS,
        replica_host_ports=PORTS,
    )
    assert check(saved, path, **intent).exit_code == 0
    data = json.loads(path.read_text())
    del data["services"]["inference-3"]
    path.write_text(json.dumps(data))
    result = check(saved, path, **intent)
    assert result.exit_code == 5 and result.change_count
    assert saved.to_dict() == before


@pytest.mark.parametrize("devices", [["7"], ["GPU-16a23983-e73e-0945-2095-cdeb50696982"]])
def test_explicit_single_layout_and_independent_changed_intent(tmp_path, devices):
    saved, path, intent = written(tmp_path, gpu_devices=devices, host_port=9001)
    assert check(saved, path, **intent).exit_code == 0
    assert check(saved, path, **{**intent, "host_port": 9002}).exit_code == 5
    assert check(saved, path, **{**intent, "image": "example/engine:2"}).exit_code == 5


def test_key_order_and_whitespace_ignored_but_arrays_ordered(tmp_path):
    saved, path, intent = written(tmp_path)
    data = json.loads(path.read_text())
    path.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")))
    assert check(saved, path, **intent).exit_code == 0
    data["services"]["inference"]["command"].reverse()
    path.write_text(json.dumps(data))
    assert check(saved, path, **intent).exit_code == 5


@pytest.mark.parametrize("field,value", [("init", 1), ("init", 1.0), ("restart", True)])
def test_scalar_types_are_exact(tmp_path, field, value):
    saved, path, intent = written(tmp_path)
    data = json.loads(path.read_text())
    data["services"]["inference"][field] = value
    path.write_text(json.dumps(data))
    result = check(saved, path, **intent)
    assert result.exit_code == 5 and any(c.category == "type" for c in result.changes)


@pytest.mark.parametrize("value", [True, 1.0])
def test_native_integer_count_does_not_equal_bool_or_float(tmp_path, value):
    saved, path, intent = written(tmp_path)
    data = json.loads(path.read_text())
    data["services"]["inference"]["deploy"]["resources"]["reservations"]["devices"][0]["count"] = (
        value
    )
    path.write_text(json.dumps(data))
    assert check(saved, path, **intent).exit_code == 5


@pytest.mark.parametrize(
    "kind", ["image", "batch", "port", "device", "environment", "mount", "extra-service"]
)
def test_real_config_drift_never_discloses_actual_values_or_unknown_keys(tmp_path, kind):
    saved, path, intent = written(tmp_path)
    data = json.loads(path.read_text())
    service = data["services"]["inference"]
    if kind == "image":
        service["image"] = CANARY
    elif kind == "batch":
        service["command"][service["command"].index("--max-num-seqs") + 1] = CANARY
    elif kind == "port":
        service["ports"] = [CANARY]
    elif kind == "device":
        service["deploy"]["resources"]["reservations"]["devices"][0]["count"] = CANARY
    elif kind == "environment":
        service["environment"] = {CANARY: CANARY}
    elif kind == "mount":
        service["volumes"] = [CANARY]
    else:
        data["services"][CANARY] = {CANARY: CANARY}
    path.write_text(json.dumps(data))
    result = check(saved, path, **intent)
    assert result.exit_code == 5 and CANARY not in json.dumps(result.to_dict())


@pytest.mark.parametrize(
    "raw",
    [
        b"{} garbage",
        b"[]",
        b'{"x":NaN}',
        b'{"x":1e999}',
        b'"\xff"',
        ('{"' + CANARY + '":1,"' + CANARY + '":2}').encode(),
    ],
)
def test_malformed_actual_is_invalid_with_sanitized_errors(tmp_path, raw):
    saved, path, intent = written(tmp_path)
    path.write_bytes(raw)
    with pytest.raises(verifier().DeploymentVerificationError) as exc:
        check(saved, path, **intent)
    assert CANARY not in str(exc.value)


def test_private_native_domain_error_is_suppressed_in_public_traceback(tmp_path):
    from chimeraforge.api import _digest

    saved, path, intent = written(tmp_path)
    data = saved.to_dict()
    data["inputs"]["gpu_overrides"] = {CANARY: 1}
    data["fingerprint"] = _digest({k: v for k, v in data.items() if k != "fingerprint"})
    with pytest.raises(verifier().DeploymentVerificationError) as caught:
        check(PlanArtifact(data), path, **intent)
    assert CANARY not in "".join(traceback.format_exception(caught.value))


def test_full_admission_precedes_diagnostic_cap(tmp_path, monkeypatch):
    saved, path, intent = written(tmp_path)
    module = verifier()
    monkeypatch.setattr(module, "MAX_CHANGES", 1)
    data = json.loads(path.read_text())
    data["services"]["inference"]["image"] = CANARY
    data["late-invalid"] = [float("inf")]
    path.write_text(json.dumps(data))
    with pytest.raises(module.DeploymentVerificationError):
        check(saved, path, **intent)
    data["late-invalid"] = [0] * 10
    path.write_text(json.dumps(data))
    result = check(saved, path, **intent)
    assert result.exit_code == 5 and len(result.changes) == 1 and result.changes_truncated


@pytest.mark.parametrize(
    "kind", ["config-size", "nodes", "depth", "total", "intent", "cycle", "huge-list"]
)
def test_named_limits_refuse_before_diff_or_copy(tmp_path, monkeypatch, kind):
    saved, path, intent = written(tmp_path)
    module = verifier()
    if kind == "config-size":
        monkeypatch.setattr(module, "MAX_CONFIG_BYTES", 2)
    elif kind == "nodes":
        monkeypatch.setattr(module, "MAX_JSON_NODES", 2)
    elif kind == "depth":
        monkeypatch.setattr(module, "MAX_JSON_DEPTH", 2)
    elif kind == "total":
        monkeypatch.setattr(module, "MAX_TOTAL_BYTES", 2)
    elif kind == "intent":
        intent["image"] = "x" * (module.MAX_INTENT_CHARS + 1)
    elif kind == "cycle":
        data = {}
        data["cycle"] = data
        saved = PlanArtifact(data)
    else:
        saved = PlanArtifact({"huge": [0] * (module.MAX_JSON_NODES + 1)})
    with pytest.raises(module.DeploymentVerificationError):
        check(saved, path, **intent)


@pytest.mark.parametrize("kind", ["missing", "edited", "crlf"])
def test_required_companion_exact_bytes_are_drift(tmp_path, kind):
    saved = artifact(
        backend="ollama",
        source=SOURCE_OLLAMA,
        model="ollama:llama3.1:8b",
        quant="Q4_K_M",
        native_quant="Q4_K_M",
    )
    saved, path, intent = written(tmp_path, saved)
    companion = tmp_path / "Modelfile"
    if kind == "missing":
        companion.unlink()
    elif kind == "edited":
        companion.write_bytes(CANARY.encode())
    else:
        companion.write_bytes(companion.read_bytes().replace(b"\n", b"\r\n"))
    result = check(saved, path, **intent)
    assert result.exit_code == 5 and result.companions[0].state != "match"
    assert CANARY not in json.dumps(result.to_dict())


def test_top_missing_and_input_alias_invalid(tmp_path):
    saved, path, intent = written(tmp_path)
    with pytest.raises(verifier().DeploymentVerificationError):
        check(saved, tmp_path / "missing", **intent)
    source = tmp_path / "plan.json"
    saved.save(source)
    with pytest.raises(verifier().DeploymentVerificationError):
        check(source, source, **intent)
    assert check(source, path, **intent).exit_code == 0


def test_source_hash_basis_distinguishes_original_file_from_object_snapshot(tmp_path):
    saved, path, intent = written(tmp_path)
    source = tmp_path / "plan.json"
    saved.save(source)
    from_file, from_object = check(source, path, **intent), check(saved, path, **intent)
    assert from_file.source_kind == "file_bytes"
    assert from_object.source_kind == "artifact_snapshot"
    assert from_file.plan_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert from_file.expected_config_sha256 == from_object.expected_config_sha256


def test_saved_identity_is_bounded_before_renderer(tmp_path, monkeypatch):
    module = verifier()
    saved, path, intent = written(tmp_path)
    oversized = artifact(model="org/" + "x" * module.MAX_INTENT_CHARS)

    def forbidden(*args, **kwargs):
        pytest.fail("oversized derived identity reached renderer")

    monkeypatch.setattr(module, "export_deployment", forbidden)
    with pytest.raises(module.DeploymentVerificationError):
        check(oversized, path, **intent)


def test_full_sixteen_by_sixty_four_export_shape_fits_admission(tmp_path):
    # A legacy-shaped saved row exercises verifier limits, not physical/planner feasibility.
    saved = artifact(candidate_changes={"n_agents": 16, "tensor_parallel": 64, "gpus_total": 1024})
    groups = [[str(i * 64 + j) for j in range(64)] for i in range(16)]
    saved, path, intent = written(
        tmp_path, saved, replica_gpu_devices=groups, replica_host_ports=list(range(9000, 9016))
    )
    assert check(saved, path, **intent).exit_code == 0


def test_actual_bound_revision_drift_and_cli_fleet_layout(tmp_path, native_hf_fleet):
    saved, index = native_hf_fleet
    saved, path, intent = written(
        tmp_path, saved, candidate_index=index, replica_gpu_devices=GROUPS, replica_host_ports=PORTS
    )
    source = tmp_path / "plan.json"
    saved.save(source)
    layout = [
        item
        for group, port in zip(GROUPS, PORTS)
        for item in ("--replica-devices", ",".join(group), "--replica-port", str(port))
    ]
    args = [
        "deploy-verify",
        "--plan",
        str(source),
        "--config",
        str(path),
        "--candidate-index",
        str(index),
        "--image",
        intent["image"],
        *layout,
        "--json",
    ]
    assert CliRunner().invoke(app, args).exit_code == 0
    data = json.loads(path.read_text())
    argv = data["services"]["inference-3"]["command"]
    assert "--revision" in argv
    argv[argv.index("--revision") + 1] = "0" * 40
    path.write_text(json.dumps(data))
    assert check(saved, path, **intent).exit_code == 5
    assert CliRunner().invoke(app, args).exit_code == 5


def test_shared_dag_references_are_counted_before_source_serialization(tmp_path):
    saved, path, intent = written(tmp_path)
    shared = [0]
    for _ in range(17):
        shared = [shared, shared]
    with pytest.raises(verifier().DeploymentVerificationError):
        check(PlanArtifact({"expanded": shared}), path, **intent)


def test_ollama_uses_only_expected_fixed_companion_and_denies_unreadable(tmp_path, monkeypatch):
    saved = artifact(
        backend="ollama",
        source=SOURCE_OLLAMA,
        model="ollama:llama3.1:8b",
        quant="Q4_K_M",
        native_quant="Q4_K_M",
    )
    saved, path, intent = written(tmp_path, saved)
    data = json.loads(path.read_text())
    data["services"]["inference"]["volumes"][1] = CANARY
    path.write_text(json.dumps(data))
    module = verifier()
    original = module._read
    reads = []

    def observed(p, *args, **kwargs):
        reads.append(p)
        return original(p, *args, **kwargs)

    monkeypatch.setattr(module, "_read", observed)
    assert check(saved, path, **intent).exit_code == 5
    assert reads == [path, tmp_path / "Modelfile"]

    def unreadable(p, *args, **kwargs):
        if p.name == "Modelfile":
            raise PermissionError(CANARY)
        return original(p, *args, **kwargs)

    monkeypatch.setattr(module, "_read", unreadable)
    with pytest.raises(module.DeploymentVerificationError) as caught:
        check(saved, path, **intent)
    assert CANARY not in "".join(traceback.format_exception(caught.value))


@pytest.mark.skipif(os.name != "nt", reason="Windows native extended-prefix alias")
def test_windows_extended_prefix_input_alias_is_invalid(tmp_path):
    saved, path, intent = written(tmp_path)
    source = tmp_path / "plan.json"
    saved.save(source)
    alias = Path("\\\\?\\" + str(source))
    assert source.samefile(alias)
    with pytest.raises(verifier().DeploymentVerificationError):
        check(source, alias, **intent)


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "parent-link", "broken-companion"])
def test_unsafe_files_are_invalid_without_resolving_links(tmp_path, kind):
    saved, path, intent = written(tmp_path)
    try:
        if kind == "symlink":
            linked = tmp_path / "linked"
            linked.symlink_to(path)
            path = linked
        elif kind == "hardlink":
            linked = tmp_path / "linked"
            os.link(path, linked)
            path = linked
        elif kind == "parent-link":
            linked = tmp_path / "directory"
            linked.symlink_to(tmp_path, target_is_directory=True)
            path = linked / path.name
        else:
            saved = artifact(
                backend="ollama",
                source=SOURCE_OLLAMA,
                model="ollama:llama3.1:8b",
                quant="Q4_K_M",
                native_quant="Q4_K_M",
            )
            saved, path, intent = written(tmp_path, saved)
            (tmp_path / "Modelfile").unlink()
            (tmp_path / "Modelfile").symlink_to(tmp_path / "absent")
    except OSError as exc:
        pytest.skip(f"Host cannot create this link fixture: {type(exc).__name__}")
    with pytest.raises(verifier().DeploymentVerificationError):
        check(saved, path, **intent)


def test_dollars_are_preinterpolation_and_actual_mounts_env_files_never_read(tmp_path, monkeypatch):
    saved = artifact(source=None)
    saved, path, intent = written(tmp_path, saved, model="org/$PRIVATE")
    assert "$$PRIVATE" in path.read_text()
    (tmp_path / ".env").write_text(CANARY)
    module = verifier()
    original = module._read
    reads = []

    def observed(p, *args, **kwargs):
        reads.append(p)
        return original(p, *args, **kwargs)

    monkeypatch.setattr(module, "_read", observed)
    assert check(saved, path, **intent).exit_code == 0
    path.write_text(path.read_text().replace("$$PRIVATE", "$PRIVATE"))
    assert check(saved, path, **intent).exit_code == 5
    data = json.loads(path.read_text())
    data["services"]["inference"]["volumes"] = [str(tmp_path / ".env")]
    path.write_text(json.dumps(data))
    assert check(saved, path, **intent).exit_code == 5
    assert reads == [path, path, path]


def test_cli_has_match_drift_invalid_outcomes_and_sanitized_json(tmp_path):
    saved, path, intent = written(tmp_path)
    source = tmp_path / "plan.json"
    saved.save(source)
    args = [
        "deploy-verify",
        "--plan",
        str(source),
        "--config",
        str(path),
        "--image",
        intent["image"],
        "--json",
    ]
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0 and json.loads(result.output)["status"] == "match", result.output
    path.write_text('{"' + CANARY + '":1}')
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 5 and CANARY not in result.output
    path.write_text('{"' + CANARY + '":1,"' + CANARY + '":2}')
    result = CliRunner().invoke(app, args)
    assert (
        result.exit_code == 1
        and json.loads(result.output)["status"] == "invalid"
        and CANARY not in result.output
    )
    assert source.read_bytes() == before[source.name]


def test_cli_preserves_native_typer_usage_exit_two():
    result = CliRunner().invoke(app, ["deploy-verify", "--candidate-index", "not-an-integer"])
    assert result.exit_code == 2
