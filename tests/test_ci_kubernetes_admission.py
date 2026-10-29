"""Native admission evidence and owned-cluster exceptional paths, without Docker."""

from __future__ import annotations

import copy
import json

import pytest

from test_ci_acceptance import load_script


def test_server_response_checks_every_original_object_and_native_field():
    module = load_script("ci_kubernetes_admission")
    expected = {
        "apiVersion": "v1",
        "kind": "List",
        "items": [
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": "m1", "namespace": "default"},
                "spec": {
                    "replicas": 1,
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": "inference",
                                    "args": ["$$(TOKEN)"],
                                    "resources": {"limits": {"nvidia.com/gpu": "2"}},
                                }
                            ]
                        }
                    },
                },
            },
            {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {"name": "m1", "namespace": "default"},
                "spec": {"type": "ClusterIP"},
            },
        ],
    }
    actual = copy.deepcopy(expected)
    actual["items"].reverse()
    actual["items"][0]["spec"]["clusterIP"] = "10.0.0.1"
    module.validate_response(expected, actual)
    changed = copy.deepcopy(actual)
    changed["items"][1]["spec"]["template"]["spec"]["containers"][0]["args"] = ["expanded"]
    with pytest.raises(AssertionError):
        module.validate_response(expected, changed)
    for items in (actual["items"][:1], [actual["items"][0]] * 2):
        with pytest.raises(AssertionError):
            module.validate_response(expected, {**actual, "items": items})


@pytest.mark.parametrize("failure", ["partial_create", "callback", None])
def test_owned_cluster_always_deletes_exact_owned_resources(tmp_path, monkeypatch, failure):
    module = load_script("ci_kubernetes_admission")
    calls = []
    deleted = False
    label = "fixture-owner"

    def run(argv, env, *, timeout=60, negative=False):
        nonlocal deleted
        calls.append(argv)
        if argv[0] == "kind" and argv[1:3] == ["get", "clusters"]:
            return "" if not deleted else ""
        if argv[:3] == ["docker", "network", "ls"]:
            return ""
        if argv[:3] == ["docker", "network", "create"]:
            return "owned-network-id\n"
        if argv[:3] == ["docker", "network", "inspect"]:
            return json.dumps(
                [
                    {
                        "Id": "owned-network-id",
                        "Name": "kind",
                        "Labels": {module.OWNER_LABEL: label},
                        "Containers": {},
                    }
                ]
            )
        if argv[:3] == ["kind", "create", "cluster"]:
            if failure == "partial_create":
                raise RuntimeError("controlled-create")
            return ""
        if argv[:3] == ["kind", "delete", "cluster"]:
            deleted = True
            return ""
        if argv[:2] == ["docker", "ps"]:
            return ""
        if argv[:3] == ["docker", "network", "rm"]:
            assert deleted and argv[-1] == "owned-network-id"
            return "owned-network-id"
        raise AssertionError(argv)

    monkeypatch.setattr(module, "run", run)
    monkeypatch.setattr(module.uuid, "uuid4", lambda: label)
    receipt = {}

    def check(kubectl, env):
        assert "--kubeconfig" in kubectl and "--context" in kubectl
        assert env["KUBECONFIG"] == str(tmp_path / "kubeconfig")
        if failure == "callback":
            raise RuntimeError("controlled-callback")
        receipt["admitted"] = True

    if failure:
        with pytest.raises(RuntimeError, match="controlled"):
            module.owned_cluster(tmp_path, {}, "kind", "kubectl", receipt, check)
    else:
        module.owned_cluster(tmp_path, {}, "kind", "kubectl", receipt, check)
    assert deleted and receipt["cleanup"]["state"] == "completed"
    assert [row for row in calls if row[:3] == ["docker", "network", "rm"]] == [
        ["docker", "network", "rm", "owned-network-id"]
    ]


@pytest.mark.parametrize("existing", ["cluster", "duplicate_network"])
def test_preexisting_resources_are_not_adopted_or_deleted(tmp_path, monkeypatch, existing):
    module = load_script("ci_kubernetes_admission")
    calls = []

    def run(argv, env, **kwargs):
        calls.append(argv)
        if argv[:3] == ["kind", "get", "clusters"]:
            return "cf-admission\n" if existing == "cluster" else ""
        if argv[:3] == ["docker", "network", "ls"]:
            return "id1\nid2\n"
        raise AssertionError(argv)

    monkeypatch.setattr(module, "run", run)
    with pytest.raises(RuntimeError):
        module.owned_cluster(tmp_path, {}, "kind", "kubectl", {}, lambda *_: None)
    assert not any("delete" in row or "rm" in row or "create" in row for row in calls)


def test_existing_network_id_is_preserved_on_partial_cluster_failure(tmp_path, monkeypatch):
    module = load_script("ci_kubernetes_admission")
    calls = []

    def run(argv, env, **kwargs):
        calls.append(argv)
        if argv[:3] == ["kind", "get", "clusters"]:
            return ""
        if argv[:3] == ["docker", "network", "ls"]:
            return "existing-id"
        if argv[:3] == ["docker", "network", "inspect"]:
            assert argv[-1] == "existing-id"
            return json.dumps([{"Id": "existing-id", "Name": "kind"}])
        if argv[:3] == ["kind", "create", "cluster"]:
            raise RuntimeError("controlled-primary")
        if argv[:3] == ["kind", "delete", "cluster"]:
            raise OSError("controlled-delete")
        if argv[:2] == ["docker", "ps"]:
            return ""
        raise AssertionError(argv)

    monkeypatch.setattr(module, "run", run)
    receipt = {}
    with pytest.raises(RuntimeError, match="controlled-primary"):
        module.owned_cluster(tmp_path, {}, "kind", "kubectl", receipt, lambda *_: None)
    assert receipt["cleanup"]["state"] == "incomplete"
    assert receipt["cleanup"]["errors"] == ["cluster-delete:OSError"]
    assert receipt["network"]["preexisting_id"] == "existing-id"
    assert not any(
        row[:3] in (["docker", "network", "rm"], ["docker", "network", "create"]) for row in calls
    )


def test_real_offline_checkpoint_fixture_produces_all_four_native_geometries(tmp_path, monkeypatch):
    from typer.testing import CliRunner
    from chimeraforge.cli import app

    module = load_script("ci_kubernetes_admission")
    load_script("ci_checkpoint_identity")
    load_script("ci_kubernetes_export")
    installed = load_script("ci_installed_acceptance")
    monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path / "cache"))

    def source_cli(arguments, cwd, env, expected_code=0):
        result = CliRunner().invoke(app, arguments, env=env)
        assert result.exit_code == expected_code, result.output
        return result.stdout

    monkeypatch.setattr(installed, "run_cli", source_cli)
    cases = module.fixtures(tmp_path, {})
    assert [(row["n"], row["backend"]) for row in cases] == [
        (1, "vllm"),
        (1, "sglang"),
        (3, "vllm"),
        (3, "sglang"),
    ]
    assert all(len(row["manifest"]["items"]) == 2 * row["n"] for row in cases)
    assert all(row["saved"].read_bytes() == row["source"] for row in cases)


@pytest.mark.parametrize("provider", ["podman", "nerdctl"])
def test_provider_bound_refusal_never_adopts_a_foreign_docker_cluster(
    tmp_path, monkeypatch, provider
):
    module = load_script("ci_kubernetes_admission")
    calls = []

    def run(argv, env, **kwargs):
        calls.append((argv, dict(env)))
        if argv[:3] == ["kind", "get", "clusters"]:
            return "cf-admission\n" if env.get("KIND_EXPERIMENTAL_PROVIDER") == "docker" else ""
        if argv[:3] == ["docker", "network", "ls"]:
            return "existing-network"
        if argv[:3] == ["docker", "network", "inspect"]:
            return json.dumps([{"Id": "existing-network", "Name": "kind"}])
        if argv[:3] == ["kind", "create", "cluster"]:
            raise RuntimeError("controlled native foreign cluster already exists")
        if argv[:3] == ["kind", "delete", "cluster"] or argv[:2] == ["docker", "ps"]:
            return ""
        raise AssertionError(argv)

    monkeypatch.setattr(module, "run", run)
    inherited = {
        "KIND_EXPERIMENTAL_PROVIDER": provider,
        "KUBECONFIG": "foreign-config",
        "KIND_EXPERIMENTAL_DOCKER_NETWORK": "foreign-network",
    }
    original = dict(inherited)
    with pytest.raises(RuntimeError) as error:
        module.owned_cluster(tmp_path, inherited, "kind", "kubectl", {}, lambda *_: None)
    assert "refusing preexisting" in str(error.value)
    assert len(calls) == 1 and calls[0][0] == ["kind", "get", "clusters"]
    assert calls[0][1]["KIND_EXPERIMENTAL_PROVIDER"] == "docker"
    assert calls[0][1]["KUBECONFIG"] == str(tmp_path / "kubeconfig")
    assert "KIND_EXPERIMENTAL_DOCKER_NETWORK" not in calls[0][1]
    assert inherited == original
