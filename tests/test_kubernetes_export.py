"""Native original geometry in declarations; no cluster or inference is executed."""

from __future__ import annotations

import json

import pytest

from chimeraforge import api, deploy


@pytest.fixture(scope="module")
def native_plans():
    results = {}
    for n, rate in ((1, 10), (3, 128)):
        saved = api.plan(
            api.PlanRequest(
                models=["ci/manual-fleet"],
                overrides={"params_b": 3.0, "n_layers": 28, "n_kv_heads": 8, "d_head": 128},
                hardware="RTX 4090 24GB",
                platform="linux",
                tensor_parallel=2,
                request_rate=rate,
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
            and row["n_agents"] == n
            and row["tensor_parallel"] == 2
            and row["pipeline_parallel"] == 1
        }
        assert set(indices) == {"vllm", "sglang"}
        results[n] = saved, indices
    return results


@pytest.mark.parametrize("n", [1, 3])
@pytest.mark.parametrize("backend", ["vllm", "sglang"])
def test_native_original_members_and_controls_are_complete(native_plans, n, backend):
    saved, indices = native_plans[n]
    index = indices[backend]
    original = saved.to_dict()
    selected = original["result"]["candidates"][index]
    prefix = f"native-{backend}-n{n}"
    result = deploy.export_deployment(
        saved,
        format="kubernetes",
        candidate_index=index,
        image="example/engine:1",
        model="org/manual-fleet",
        kubernetes=api.KubernetesOptions(
            name_prefix=prefix, node_selector={"accelerator": "declared"}
        ),
    )
    assert result.format == "kubernetes" and result.backend == backend and result.files == {}
    data = json.loads(result.content)
    assert data["apiVersion"] == "v1" and data["kind"] == "List"
    assert len(data["items"]) == 2 * n
    assert [row["kind"] for row in data["items"]] == [
        kind for _ in range(n) for kind in ("Deployment", "Service")
    ]
    selectors = []
    for i in range(n):
        deployment, service = data["items"][2 * i : 2 * i + 2]
        name = f"{prefix}-m{i + 1}"
        assert deployment["apiVersion"] == "apps/v1" and service["apiVersion"] == "v1"
        for item in (deployment, service):
            assert item["metadata"]["name"] == name and item["metadata"]["namespace"] == "default"
            annotations = item["metadata"]["annotations"]
            assert annotations["org.chimeraforge/plan-fingerprint"] == original["fingerprint"]
            assert annotations["org.chimeraforge/candidate-index"] == str(index)
            assert annotations["org.chimeraforge/replica-index"] == str(i + 1)
            assert annotations["org.chimeraforge/replica-count"] == str(n)
        spec = deployment["spec"]
        assert spec["replicas"] == 1 and spec["strategy"] == {"type": "Recreate"}
        selector = spec["selector"]["matchLabels"]
        assert selector == service["spec"]["selector"]
        assert selector.items() <= spec["template"]["metadata"]["labels"].items()
        selectors.append(selector)
        pod = spec["template"]["spec"]
        assert pod["nodeSelector"] == {"kubernetes.io/os": "linux", "accelerator": "declared"}
        assert not any(k in pod for k in ("hostNetwork", "hostPID", "hostIPC"))
        assert len(pod["containers"]) == 1
        container = pod["containers"][0]
        assert container["image"] == "example/engine:1"
        quantity = str(selected["tensor_parallel"] * selected["pipeline_parallel"])
        assert container["resources"] == {
            "requests": {"nvidia.com/gpu": quantity},
            "limits": {"nvidia.com/gpu": quantity},
        }
        port = 8000 if backend == "vllm" else 30000
        assert container["ports"][0]["containerPort"] == port
        assert service["spec"]["type"] == "ClusterIP"
        assert (
            service["spec"]["ports"][0]["port"] == service["spec"]["ports"][0]["targetPort"] == port
        )
        argv = container["command"] + container["args"]
        tp, batch, context = (
            ("--tensor-parallel-size", "--max-num-seqs", "--max-model-len")
            if backend == "vllm"
            else ("--tp-size", "--max-running-requests", "--context-length")
        )
        assert argv[argv.index(tp) + 1] == "2"
        assert argv[argv.index(batch) + 1] == str(selected["effective_batch"])
        assert argv[argv.index(context) + 1] == str(original["inputs"]["context_length"])
        assert argv[argv.index("--host") + 1] == "0.0.0.0"
        assert argv[argv.index("--dtype") + 1] == "float16"
        assert {v["emptyDir"]["sizeLimit"] for v in pod["volumes"]} == {"1Gi"}
        assert not any("hostPath" in v for v in pod["volumes"])
        assert not any(k in container for k in ("env", "securityContext"))
    assert len({json.dumps(v, sort_keys=True) for v in selectors}) == n
    assert saved.to_dict() == original


@pytest.mark.parametrize(
    "literal,encoded",
    [
        ("org/$", "org/$$"),
        ("org/$(TOKEN)", "org/$$(TOKEN)"),
        ("org/$$(TOKEN)", "org/$$$$(TOKEN)"),
        ("/models/$broken(", "/models/$$broken("),
        ("/models/$a tail", "/models/$$a tail"),
        ("/models/emoji-\u2603", "/models/emoji-\u2603"),
    ],
)
@pytest.mark.parametrize("backend", ["vllm", "sglang"])
def test_kubernetes_encodes_each_native_dollar_once_without_shell_quoting(
    native_plans, backend, literal, encoded
):
    saved, indices = native_plans[1]
    result = deploy.export_deployment(
        saved,
        format="kubernetes",
        image="example/engine:1",
        candidate_index=indices[backend],
        model=literal,
    )
    container = json.loads(result.content)["items"][0]["spec"]["template"]["spec"]["containers"][0]
    argv = container["command"] + container["args"]
    assert encoded in argv and "'" not in container["args"][0]


@pytest.mark.parametrize(
    "options",
    [
        {"namespace": "Upper"},
        {"namespace": "bad/namespace"},
        {"name_prefix": "a" * 41},
        {"node_selector": {"kubernetes.io/os": "windows"}},
        {"node_selector": {"key": "PRIVATE VALUE!"}},
        {"node_selector": {"bad/key/more": "x"}},
        {"node_selector": {f"key{i}": "x" for i in range(17)}},
    ],
)
def test_invalid_kubernetes_options_fail_before_render_without_echoing_values(
    native_plans, options
):
    saved, indices = native_plans[1]
    with pytest.raises(deploy.DeploymentError) as error:
        deploy.export_deployment(
            saved,
            format="kubernetes",
            image="example/engine:1",
            candidate_index=indices["vllm"],
            model="org/manual-fleet",
            kubernetes=api.KubernetesOptions(**options),
        )
    assert "PRIVATE" not in str(error.value)


def test_encoded_argv_byte_limit_includes_dollar_expansion(native_plans):
    saved, indices = native_plans[1]
    with pytest.raises(deploy.DeploymentError, match="encoded argv"):
        deploy.export_deployment(
            saved,
            format="kubernetes",
            image="example/engine:1",
            candidate_index=indices["vllm"],
            model="org/" + "$" * 2048,
        )


@pytest.mark.parametrize(
    "option",
    [
        {"gpu_devices": ["0", "1"]},
        {"host_port": 8000},
        {"replica_gpu_devices": [["0", "1"]]},
        {"replica_host_ports": [8000]},
        {"executable": "/bin/python"},
    ],
)
def test_host_and_device_options_are_refused_for_kubernetes(native_plans, option):
    saved, indices = native_plans[1]
    with pytest.raises(deploy.DeploymentError):
        deploy.export_deployment(
            saved,
            format="kubernetes",
            image="example/engine:1",
            candidate_index=indices["vllm"],
            model="org/manual-fleet",
            **option,
        )


@pytest.mark.parametrize("n", [1, 3])
@pytest.mark.parametrize("backend", ["vllm", "sglang"])
def test_independent_api_verifier_preserves_match_drift_and_source_bytes(
    native_plans, tmp_path, n, backend
):
    saved, indices = native_plans[n]
    options = api.KubernetesOptions(
        namespace="default",
        name_prefix=f"verify-{backend}-{n}",
        node_selector={"operator.example/accelerator": "declared"},
    )
    intent = {
        "format": "kubernetes",
        "image": "example/engine:1",
        "model": "org/manual-fleet",
        "candidate_index": indices[backend],
        "kubernetes": options,
    }
    original = saved.to_dict()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(deploy.export_deployment(saved, **intent).content, encoding="utf-8")
    raw = manifest.read_bytes()
    matched = api.verify_deployment(saved, manifest, **intent)
    assert matched.exit_code == 0 and matched.status == "match" and not matched.changes
    assert manifest.read_bytes() == raw and saved.to_dict() == original
    data = json.loads(raw)
    data["items"][0]["spec"]["template"]["spec"]["containers"][0]["image"] = (
        "private-canary/changed:1"
    )
    data["items"][0]["PRIVATE-KEY-CANARY"] = "private-value"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    drift = api.verify_deployment(saved, manifest, **intent)
    assert drift.exit_code == 5 and drift.status == "drift" and drift.change_count >= 2
    report = json.dumps(drift.to_dict())
    assert "private" not in report.lower() and "CANARY" not in report
    assert saved.to_dict() == original


def test_full_kubernetes_cli_export_and_verify_with_independent_options(native_plans, tmp_path):
    from typer.testing import CliRunner
    from chimeraforge.cli import app

    saved, indices = native_plans[3]
    plan, manifest = tmp_path / "saved.json", tmp_path / "manifest.json"
    saved.save(plan)
    original = plan.read_bytes()
    common = [
        "--format",
        "kubernetes",
        "--plan",
        str(plan),
        "--image",
        "example/engine:1",
        "--model",
        "org/manual-fleet",
        "--candidate-index",
        str(indices["vllm"]),
        "--namespace",
        "default",
        "--name-prefix",
        "cli-original",
        "--node-selector",
        "accelerator=declared",
    ]
    runner = CliRunner()
    exported = runner.invoke(app, ["deploy", *common, "--out", str(manifest)])
    assert exported.exit_code == 0, exported.output
    result = runner.invoke(app, ["deploy-verify", *common, "--config", str(manifest), "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["status"] == "match"
    changed = runner.invoke(
        app,
        ["deploy-verify", *common, "--name-prefix", "other", "--config", str(manifest), "--json"],
    )
    assert changed.exit_code == 5 and json.loads(changed.stdout)["status"] == "drift"
    before = manifest.read_bytes()
    duplicate = runner.invoke(app, ["deploy", *common, "--out", str(manifest)])
    assert duplicate.exit_code == 1 and manifest.read_bytes() == before
    assert plan.read_bytes() == original


@pytest.mark.parametrize(
    "changes",
    [
        {"backend": "tgi"},
        {"backend": "ollama"},
        {"platform": "macos"},
        {"candidate_changes": {"mode": "batch"}, "inputs": {"mode": "batch"}},
        {"candidate_changes": {"offload_fraction": 0.1}},
        {"candidate_changes": {"offload_fraction": None}},
        {"candidate_changes": {"lora_adapters": 1}},
        {"inputs": {"kv_quant": "q4"}},
        {"spec_changes": {"recurrent_state_bytes_per_seq": 8192.0}},
        {"backend": "sglang", "inputs": {"max_num_batched_tokens": 512}},
    ],
)
def test_single_replica_never_bypasses_backend_mode_platform_or_native_fidelity(changes):
    from test_deploy import artifact

    with pytest.raises(deploy.DeploymentError):
        deploy.export_deployment(artifact(**changes), format="kubernetes", image="example/engine:1")


def test_sixteen_members_keep_all_resources_and_per_replica_gpu_limits():
    from test_deploy import artifact

    saved = artifact(candidate_changes={"n_agents": 16, "tensor_parallel": 8, "gpus_total": 128})
    result = deploy.export_deployment(saved, format="kubernetes", image="example/engine:1")
    items = json.loads(result.content)["items"]
    assert len(items) == 32
    assert (
        sum(
            int(
                row["spec"]["template"]["spec"]["containers"][0]["resources"]["limits"][
                    "nvidia.com/gpu"
                ]
            )
            for row in items
            if row["kind"] == "Deployment"
        )
        == 128
    )
    assert all(len(row["metadata"]["name"]) <= 63 for row in items)


def test_options_are_defensively_held_before_render(native_plans, monkeypatch):
    from chimeraforge import kubernetes_export

    saved, indices = native_plans[1]
    labels = {"accelerator": "held"}
    options = api.KubernetesOptions(node_selector=labels)
    original = kubernetes_export.render

    def alter_caller(*args):
        labels["accelerator"] = "changed"
        return original(*args)

    monkeypatch.setattr(kubernetes_export, "render", alter_caller)
    result = deploy.export_deployment(
        saved,
        format="kubernetes",
        image="example/engine:1",
        model="org/manual-fleet",
        candidate_index=indices["vllm"],
        kubernetes=options,
    )
    assert (
        json.loads(result.content)["items"][0]["spec"]["template"]["spec"]["nodeSelector"][
            "accelerator"
        ]
        == "held"
    )


@pytest.mark.parametrize("fault", ["kind", "api", "objects", "duplicate", "nan", "source_alias"])
def test_kubernetes_receiver_refuses_outside_scope_and_unsafe_json(native_plans, tmp_path, fault):
    from chimeraforge.deployment_verify import DeploymentVerificationError

    saved, indices = native_plans[1]
    source, config = tmp_path / "source.json", tmp_path / "manifest.json"
    saved.save(source)
    intent = {
        "format": "kubernetes",
        "image": "example/engine:1",
        "model": "org/manual-fleet",
        "candidate_index": indices["vllm"],
    }
    raw = deploy.export_deployment(saved, **intent).content
    data = json.loads(raw)
    if fault == "kind":
        data["items"][0]["kind"] = "Secret"
    elif fault == "api":
        data["apiVersion"] = "private-canary"
    elif fault == "objects":
        data["items"] *= 17
    elif fault == "source_alias":
        config = source
    if fault != "source_alias":
        content = json.dumps(data)
        if fault == "duplicate":
            content = content.replace('"kind": "List"', '"kind": "List", "kind": "List"', 1)
        if fault == "nan":
            content = content.replace('"replicas": 1', '"replicas": NaN', 1)
        config.write_text(content, encoding="utf-8")
    original = source.read_bytes()
    with pytest.raises(DeploymentVerificationError) as error:
        api.verify_deployment(source, config, **intent)
    assert "private" not in str(error.value).lower() and source.read_bytes() == original


def test_installed_kubernetes_consumer_calls_actual_cli_api_and_preserves_source(
    native_plans, tmp_path, monkeypatch
):
    from test_ci_acceptance import load_script
    from typer.testing import CliRunner
    from chimeraforge.cli import app

    script = load_script("ci_kubernetes_export")
    parent = load_script("ci_installed_acceptance")

    def source_cli(arguments, cwd, env, expected_code=0):
        result = CliRunner().invoke(app, arguments, env=env)
        assert result.exit_code == expected_code, result.output
        return result.stdout

    monkeypatch.setattr(parent, "run_cli", source_cli)
    saved, _ = native_plans[3]
    source = tmp_path / "source.json"
    saved.save(source)
    result = script.accept(tmp_path, {}, source, replicas=3)
    assert len(result["controls"]) == 2 and result["source_bytes_unchanged"]
    assert all(
        row["api_exit"] == row["cli_exit"] == 0 and row["drift_exit"] == 5
        for row in result["controls"]
    )


@pytest.mark.parametrize("backend", ["vllm", "sglang"])
def test_genuine_pipeline_plan_preserves_native_parallel_flags(backend):
    saved = api.plan(
        api.PlanRequest(
            models=["ci/pipeline"],
            overrides={"params_b": 3.0, "n_layers": 28, "n_kv_heads": 8, "d_head": 128},
            hardware="RTX 4090 24GB",
            platform="linux",
            tensor_parallel=1,
            pipeline_parallel=2,
            request_rate=10,
            latency_slo=10000,
            quality_target=0,
            budget=1e8,
            allow_network=False,
        )
    )
    index = next(
        i
        for i, row in enumerate(saved.to_dict()["result"]["candidates"])
        if row["backend"] == backend and row["quant"] == "FP16"
    )
    candidate = saved.candidate(index)
    assert candidate.pipeline_parallel == 2 and candidate.tensor_parallel == 1
    data = json.loads(
        deploy.export_deployment(
            saved,
            format="kubernetes",
            image="example/engine:1",
            model="org/pipeline",
            candidate_index=index,
        ).content
    )
    for item in data["items"][::2]:
        container = item["spec"]["template"]["spec"]["containers"][0]
        argv = container["command"] + container["args"]
        flag = "--pipeline-parallel-size" if backend == "vllm" else "--pp-size"
        assert argv[argv.index(flag) + 1] == "2"
        assert container["resources"]["requests"] == {"nvidia.com/gpu": "2"}


def test_final_utf8_json_bound_refuses_before_output_creation(native_plans, tmp_path, monkeypatch):
    from chimeraforge import deployment_verify
    from chimeraforge.cli import app
    from typer.testing import CliRunner

    saved, indices = native_plans[1]
    source, output = tmp_path / "source.json", tmp_path / "new.json"
    saved.save(source)
    original = source.read_bytes()
    monkeypatch.setattr(deployment_verify, "MAX_CONFIG_BYTES", 200)
    result = CliRunner().invoke(
        app,
        [
            "deploy",
            "--plan",
            str(source),
            "--format",
            "kubernetes",
            "--image",
            "example/engine:1",
            "--model",
            "org/model",
            "--candidate-index",
            str(indices["vllm"]),
            "--out",
            str(output),
        ],
    )
    assert result.exit_code == 1 and not output.exists() and source.read_bytes() == original
