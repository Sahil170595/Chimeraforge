"""Operator-authored serving intent must not fabricate optimizer evidence."""

import json
import os
import subprocess
import sys
from dataclasses import replace
import copy
import datetime as dt

import pytest

from chimeraforge import api


def request(**changes):
    return replace(
        api.ServingRequest(
            model="Qwen/Qwen2.5-1.5B-Instruct",
            revision="a" * 40,
            backend="vllm",
            image="vllm/vllm-openai:v0.30.0",
            replicas=3,
            tensor_parallel=2,
            pipeline_parallel=2,
            context_length=8192,
            batch_size=8,
        ),
        **changes,
    )


def layout():
    return {
        "replica_gpu_devices": [[str(4 * r + i) for i in range(4)] for r in range(3)],
        "replica_host_ports": [9001, 9002, 9003],
    }


def fingerprinted_declaration(data):
    import hashlib

    body = {key: value for key, value in data.items() if key != "fingerprint"}
    data["fingerprint"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    return data


def test_existing_native_quote_export_and_configuration_receiver(tmp_path):
    from chimeraforge.deploy import export_deployment
    from chimeraforge.planner.cloudprice import fleet_hourly_cost, offers_for

    offer = next(row for row in offers_for("aws", "H100 80GB") if row.instance == "p5.48xlarge")
    cost, selected, count = fleet_hourly_cost([offer], 3, 4)
    assert count == 2 and selected == offer and cost == 2 * offer.price_per_hour
    assert count * offer.gpus == 16
    saved = api.plan(
        api.PlanRequest(
            models=["qwen2.5-1.5b"],
            hardware="RTX 4090 24GB",
            platform="linux",
            request_rate=0.1,
            latency_slo=10000,
            quality_target=0,
            budget=1e8,
            allow_network=False,
        )
    )
    index = next(
        i
        for i, row in enumerate(saved.to_dict()["result"]["candidates"])
        if row["backend"] == "vllm" and row["quant"] == "FP16"
    )
    assert saved.candidate(index).n_agents == 1
    image = "vllm/vllm-openai:v0.30.0"
    model = "Qwen/Qwen2.5-1.5B-Instruct"
    rendered = export_deployment(
        saved, format="compose", image=image, model=model, candidate_index=index
    )
    path = tmp_path / "native-compose.json"
    path.write_text(rendered.content, encoding="utf-8")
    checked = api.verify_deployment(saved, path, image=image, model=model, candidate_index=index)
    assert checked.exit_code == 0


def test_operator_declaration_public_workflow(tmp_path):
    declaration = api.declare_serving(
        api.ServingRequest(
            model="Qwen/Qwen2.5-1.5B-Instruct",
            revision="a" * 40,
            backend="vllm",
            image="vllm/vllm-openai:v0.30.0",
            replicas=3,
            tensor_parallel=2,
            pipeline_parallel=2,
            context_length=8192,
            batch_size=8,
        )
    )
    path = tmp_path / "operator.serving.json"
    declaration.save(path)
    loaded = api.load_serving_declaration(path)
    assert loaded.to_dict() == declaration.to_dict()
    quote = api.quote_serving(loaded, cloud="aws", instance="p5.48xlarge", region="us-east-1")
    assert quote.to_dict()["instance_count"] == 2
    assert quote.to_dict()["feasibility"] is None
    groups = [[str(4 * member + offset) for offset in range(4)] for member in range(3)]
    rendered = api.export_serving_declaration(
        loaded, format="compose", replica_gpu_devices=groups, replica_host_ports=[9001, 9002, 9003]
    )
    assert len(json.loads(rendered.content)["services"]) == 3


def test_operator_declaration_actual_cli_workflow(tmp_path):
    path = tmp_path / "operator.serving.json"
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-m",
            "chimeraforge.cli",
            "serving",
            "declare",
            "--model",
            "Qwen/Qwen2.5-1.5B-Instruct",
            "--revision",
            "a" * 40,
            "--backend",
            "vllm",
            "--image",
            "vllm/vllm-openai:v0.30.0",
            "--replicas",
            "3",
            "--tp",
            "2",
            "--pp",
            "2",
            "--context",
            "8192",
            "--batch",
            "8",
            "--out",
            str(path),
            "--json",
        ],
        cwd=tmp_path,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    assert path.is_file()


@pytest.mark.parametrize("backend", ["vllm", "sglang"])
@pytest.mark.parametrize("format", ["launch", "compose", "kubernetes"])
def test_complete_operator_population_export_and_native_verification(tmp_path, backend, format):
    declaration = api.declare_serving(
        request(backend=backend, image=f"example/{backend}:explicit-tag")
    )
    source = tmp_path / "operator.serving.json"
    declaration.save(source)
    original = source.read_bytes()
    options = {} if format == "kubernetes" else layout()
    rendered = api.export_serving_declaration(source, format=format, **options)
    data = json.loads(rendered.content)
    if format == "launch":
        entries = data["replicas"]
        assert len(entries) == 3
        assert [row["host_port"] for row in entries] == [9001, 9002, 9003]
        assert [row["environment"]["CUDA_VISIBLE_DEVICES"] for row in entries] == [
            "0,1,2,3",
            "4,5,6,7",
            "8,9,10,11",
        ]
        argv = [row["argv"] for row in entries]
        assert sum(row["logical_gpu_slots"] for row in entries) == 12
    elif format == "compose":
        entries = list(data["services"].values())
        assert len(entries) == 3
        assert all("org.chimeraforge.plan-fingerprint" not in row["labels"] for row in entries)
        assert all(
            row["labels"]["org.chimeraforge.declaration-fingerprint"] == declaration.fingerprint
            for row in entries
        )
        assert (
            sum(
                len(row["deploy"]["resources"]["reservations"]["devices"][0]["device_ids"])
                for row in entries
            )
            == 12
        )
        argv = [row["entrypoint"] + row["command"] for row in entries]
    else:
        assert len(data["items"]) == 6
        entries = [row for row in data["items"] if row["kind"] == "Deployment"]
        assert len(entries) == 3
        assert (
            sum(
                int(
                    row["spec"]["template"]["spec"]["containers"][0]["resources"]["requests"][
                        "nvidia.com/gpu"
                    ]
                )
                for row in entries
            )
            == 12
        )
        assert all(
            "org.chimeraforge/plan-fingerprint" not in row["metadata"]["annotations"]
            and "org.chimeraforge/candidate-index" not in row["metadata"]["annotations"]
            for row in data["items"]
        )
        argv = [
            row["spec"]["template"]["spec"]["containers"][0]["command"]
            + row["spec"]["template"]["spec"]["containers"][0]["args"]
            for row in entries
        ]
    for command in argv:
        assert command[command.index("--revision") + 1] == "a" * 40
        context_flag = "--max-model-len" if backend == "vllm" else "--context-length"
        batch_flag = "--max-num-seqs" if backend == "vllm" else "--max-running-requests"
        assert command[command.index(context_flag) + 1] == "8192"
        assert command[command.index(batch_flag) + 1] == "8"
    config = tmp_path / f"{format}.json"
    config.write_text(rendered.content, encoding="utf-8")
    report = api.verify_serving_declaration(source, config, format=format, **options)
    assert report.exit_code == 0 and report.change_count == 0
    assert "declaration_sha256" in report.to_dict() and "plan_sha256" not in report.to_dict()
    if format == "launch":
        data["replicas"][0]["argv"].append("--unexpected-control")
    elif format == "compose":
        data["services"]["inference-1"]["image"] = "different/image:tag"
    else:
        data["items"][0]["spec"]["template"]["spec"]["containers"][0]["resources"]["limits"][
            "nvidia.com/gpu"
        ] = "3"
    config.write_text(json.dumps(data), encoding="utf-8")
    changed = api.verify_serving_declaration(source, config, format=format, **options)
    assert changed.exit_code == 5 and changed.change_count > 0
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "name,value",
    [
        ("replicas", True),
        ("replicas", 0),
        ("replicas", 17),
        ("tensor_parallel", 0),
        ("tensor_parallel", 65),
        ("pipeline_parallel", 64),
        ("context_length", 0),
        ("context_length", True),
        ("batch_size", 0),
        ("batch_size", 1 << 21),
        ("revision", "main"),
        ("revision", "A" * 40),
        ("model", "size-class"),
        ("backend", "ollama"),
        ("backend", "tgi"),
        ("dtype", "AWQ"),
        ("kv_quant", "q4"),
        ("prefix_caching", 1),
        ("image", "image:latest"),
        ("image", "image"),
        ("image", "image:tag\n"),
        ("max_num_batched_tokens", True),
        ("max_num_batched_tokens", 127),
    ],
)
def test_closed_typed_serving_settings_refuse(name, value):
    with pytest.raises(api.ServingDeclarationError):
        api.declare_serving(request(**{name: value}))


def test_unsupported_sglang_kv_and_chunk_controls_refuse():
    with pytest.raises(api.ServingDeclarationError):
        api.declare_serving(request(backend="sglang", dtype="BF16", kv_quant="fp16"))
    with pytest.raises(api.ServingDeclarationError):
        api.declare_serving(request(backend="sglang", max_num_batched_tokens=1024))


def test_declaration_never_resolves_or_plans_and_never_becomes_optimizer_evidence(monkeypatch):
    from chimeraforge.planner import models, service, resolver

    def forbidden(*args, **kwargs):
        raise AssertionError("declaration invoked an optimizer/model/corpus lookup")

    monkeypatch.setattr(service, "run_plan", forbidden)
    monkeypatch.setattr(models, "load_effective_models", forbidden)
    monkeypatch.setattr(resolver, "resolve_spec", forbidden)
    declaration = api.declare_serving(request())
    assert "result" not in declaration.to_dict() and "corpus_sha256" not in declaration.to_dict()
    assert all(value is None for value in declaration.to_dict()["claims"].values())
    api.export_serving_declaration(declaration, format="compose", **layout())
    for call in (
        lambda: api.plan(declaration),
        lambda: api.check_plan(declaration),
        lambda: api.artifact_from_dict(declaration.to_dict()),
    ):
        with pytest.raises(api.PlanError):
            call()


@pytest.mark.parametrize(
    "change", ["missing_group", "same_device", "same_port", "short_group", "mixed_options"]
)
def test_explicit_multireplica_alias_or_incomplete_layout_refuses(change):
    options = layout()
    if change == "missing_group":
        options["replica_gpu_devices"].pop()
    elif change == "same_device":
        options["replica_gpu_devices"][1][0] = "0"
    elif change == "same_port":
        options["replica_host_ports"][1] = 9001
    elif change == "short_group":
        options["replica_gpu_devices"][1].pop()
    else:
        options["gpu_devices"] = ["0", "1", "2", "3"]
    with pytest.raises(api.ServingDeclarationError):
        api.export_serving_declaration(api.declare_serving(request()), format="compose", **options)


def test_quote_target_region_and_whole_instance_unknowns():
    declaration = api.declare_serving(request())
    unknown = api.quote_serving(declaration).to_dict()
    assert unknown["status"] == "unknown" and unknown["price_per_hour"] is None
    actual = api.quote_serving(
        declaration, cloud="aws", instance="p5.48xlarge", region="us-east-1"
    ).to_dict()
    assert actual["instance_count"] == 2 and actual["billed_gpus"] == 16
    assert actual["logical_gpu_slots"] == 12 and actual["idle_billed_gpus"] == 4
    assert actual["captured_at"] == "2026-10-01" and actual["hours_per_month"] == 720
    assert actual["price_per_hour"] == 2 * actual["offer"]["price_per_hour"]
    assert actual["monthly_cost"] == actual["price_per_hour"] * 720
    assert actual["feasibility"] is None and actual["cost_per_token"] is None
    other = api.quote_serving(
        declaration, cloud="aws", instance="p5.48xlarge", region="us-west-2"
    ).to_dict()
    assert other["status"] == "unknown" and other["reason"] == "offer_unavailable"
    large = api.declare_serving(request(tensor_parallel=16, pipeline_parallel=1))
    nofit = api.quote_serving(
        large, cloud="aws", instance="p5.48xlarge", region="us-east-1"
    ).to_dict()
    assert nofit["reason"] == "group_does_not_fit_instance" and nofit["price_per_hour"] is None
    with pytest.raises(api.ServingDeclarationError):
        api.quote_serving(declaration, cloud="aws")


def test_budget_quote_exact_boundary_ignores_binary_and_ambient_decimal(monkeypatch):
    from decimal import Inexact, localcontext

    from chimeraforge.planner import cloudprice

    snapshot = copy.deepcopy(cloudprice.load_cloud_prices())
    offer = next(row for row in snapshot["offers"] if row["instance"] == "p5.48xlarge")
    offer["price_per_hour"] = 0.07
    captured = dt.date.fromisoformat(snapshot["captured_at"])
    monkeypatch.setattr(cloudprice, "load_cloud_prices", lambda: snapshot)
    monkeypatch.setattr(cloudprice, "_today", lambda: captured)
    declaration = api.declare_serving(request())
    target = dict(cloud="aws", instance="p5.48xlarge", region="us-east-1")
    default = api.quote_serving(declaration, **target).to_dict()
    assert default["schema_version"] == 1 and default["monthly_cost"] > 100.8
    with localcontext() as context:
        context.prec = 1
        context.traps[Inexact] = True
        report = api.quote_serving(
            declaration, **target, budget_policy=api.ServingQuoteBudgetPolicy("100.800000")
        )
    data = report.to_dict()
    assert report.exit_code == data["exit_code"] == 0
    assert data["schema_version"] == 2
    assert data["budget"]["quoted_monthly_usd"] == data["budget"]["max_monthly_usd"] == "100.8"
    assert data["budget"]["status"] == "within_budget"
    assert data["instance_count"] == 2 and data["billed_gpus"] == 16
    assert data["monthly_cost"] == default["monthly_cost"]
    assert data["feasibility"] is data["deployment_ready"] is None


def test_budget_quote_cli_within_above_and_native_unknown_exits(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from chimeraforge.cli import app
    from chimeraforge.planner import cloudprice

    captured = dt.date.fromisoformat(cloudprice.load_cloud_prices()["captured_at"])
    monkeypatch.setattr(cloudprice, "_today", lambda: captured)
    path = tmp_path / "operator.json"
    api.declare_serving(request()).save(path)
    held = path.read_bytes()
    command = ["serving", "quote", "--declaration", str(path), "--json"]
    target = ["--cloud", "aws", "--instance", "p5.48xlarge", "--region", "us-east-1"]
    for arguments, cap, expected, status in (
        (target, "79257.6", 0, "within_budget"),
        (target, "79257.599999", 5, "above_budget"),
        ([], "1", 4, "unknown"),
    ):
        result = CliRunner().invoke(app, [*command, *arguments, "--max-monthly-usd", cap])
        assert result.exit_code == expected, result.output
        data = json.loads(result.stdout)
        assert data["exit_code"] == expected and data["budget"]["status"] == status
    assert path.read_bytes() == held


@pytest.mark.parametrize(
    "age,limit,state,code,native_stale",
    [
        (0, 0, "within_budget", 0, False),
        (7, 7, "within_budget", 0, False),
        (8, 7, "stale", 4, False),
        (90, 90, "within_budget", 0, False),
        (91, 90, "stale", 4, True),
    ],
)
def test_budget_quote_preserves_native_quote_but_enforces_policy_age(
    monkeypatch, age, limit, state, code, native_stale
):
    from chimeraforge.planner import cloudprice

    captured = dt.date.fromisoformat(cloudprice.load_cloud_prices()["captured_at"])
    monkeypatch.setattr(cloudprice, "_today", lambda: captured + dt.timedelta(days=age))
    target = dict(cloud="aws", instance="p5.48xlarge", region="us-east-1")
    declaration = api.declare_serving(request())
    default = api.quote_serving(declaration, **target)
    actual = api.quote_serving(
        declaration, **target, budget_policy=api.ServingQuoteBudgetPolicy("79257.6", limit)
    )
    data = actual.to_dict()
    assert actual.exit_code == code and data["budget"]["status"] == state
    assert data["budget"]["quoted_monthly_usd"] == "79257.6"
    assert data["stale"] is native_stale and data["age_days"] == age
    assert default.exit_code == 0
    legacy = default.to_dict()
    assert legacy["schema_version"] == 1 and "exit_code" not in legacy and "budget" not in legacy
    for name in legacy.keys() - {"created_at", "schema_version"}:
        assert data[name] == legacy[name]


@pytest.mark.parametrize(
    "policy",
    [
        {"max_monthly_usd": "1"},
        *(
            (bad, 90)
            for bad in (
                True,
                0.01,
                "",
                "NaN",
                "Infinity",
                "-0",
                "1e3",
                " 1",
                "01",
                "\u0661",
                "1000000000000",
                "0.0000001",
                "1" * 1000,
            )
        ),
        *(("1", bad) for bad in (True, 7.0, -1, 91)),
    ],
)
def test_invalid_budget_refuses_before_loading_billing_snapshot(monkeypatch, policy):
    from chimeraforge.planner import cloudprice

    def unexpected():
        pytest.fail("malformed policy reached the native snapshot")

    monkeypatch.setattr(cloudprice, "load_cloud_prices", unexpected)
    if isinstance(policy, tuple):
        policy = api.ServingQuoteBudgetPolicy(*policy)
    with pytest.raises(api.ServingDeclarationError, match="invalid serving quote budget policy"):
        api.quote_serving(
            api.declare_serving(request()),
            cloud="aws",
            instance="p5.48xlarge",
            region="us-east-1",
            budget_policy=policy,
        )


def test_budget_quote_invalid_age_alone_and_unavailable_offer_cli(tmp_path):
    from typer.testing import CliRunner

    from chimeraforge.cli import app

    path = tmp_path / "operator.json"
    api.declare_serving(request()).save(path)
    command = ["serving", "quote", "--declaration", str(path), "--json"]
    result = CliRunner().invoke(app, [*command, "--max-price-age-days", "5"])
    assert result.exit_code == 1 and json.loads(result.stdout)["exit_code"] == 1
    result = CliRunner().invoke(
        app,
        [
            *command,
            "--cloud",
            "aws",
            "--instance",
            "p5.48xlarge",
            "--region",
            "us-west-2",
            "--max-monthly-usd",
            "0",
        ],
    )
    assert result.exit_code == 4
    body = json.loads(result.stdout)
    assert body["reason"] == body["budget"]["reason"] == "offer_unavailable"
    assert body["budget"]["status"] == "unknown" and body["budget"]["quoted_monthly_usd"] is None


@pytest.mark.parametrize("days", [90, 91])
def test_quote_carries_native_snapshot_age_and_stale_boundary(monkeypatch, days):
    from chimeraforge.planner import cloudprice

    captured = dt.date.fromisoformat(cloudprice.load_cloud_prices()["captured_at"])
    monkeypatch.setattr(cloudprice, "_today", lambda: captured + dt.timedelta(days=days))
    quote = api.quote_serving(
        api.declare_serving(request()), cloud="aws", instance="p5.48xlarge", region="us-east-1"
    ).to_dict()
    assert quote["age_days"] == days and quote["stale"] is (days > 90)
    assert quote["status"] == "estimated" and quote["feasibility"] is None


@pytest.mark.parametrize("change", ["zero_price", "duplicate", "foreign_cheaper"])
def test_quote_refuses_unknown_or_ambiguous_price_and_never_chooses_foreign_region(
    monkeypatch, change
):
    from chimeraforge.planner import cloudprice

    snapshot = copy.deepcopy(cloudprice.load_cloud_prices())
    offer = next(row for row in snapshot["offers"] if row["instance"] == "p5.48xlarge")
    original_price = offer["price_per_hour"]
    if change == "zero_price":
        offer["price_per_hour"] = 0
    else:
        alternative = copy.deepcopy(offer)
        if change == "foreign_cheaper":
            alternative.update(region="elsewhere", price_per_hour=0.01)
        snapshot["offers"].append(alternative)
    monkeypatch.setattr(cloudprice, "load_cloud_prices", lambda: snapshot)
    quote = api.quote_serving(
        api.declare_serving(request()), cloud="aws", instance="p5.48xlarge", region="us-east-1"
    ).to_dict()
    if change == "foreign_cheaper":
        assert quote["region"] == "us-east-1" and quote["price_per_hour"] == 2 * original_price
    else:
        assert quote["status"] == "unknown" and quote["monthly_cost"] is None
        assert quote["reason"] == ("price_unknown" if change == "zero_price" else "offer_ambiguous")


@pytest.mark.parametrize(
    "backend,dtype,kv", [("vllm", "BF16", "fp16"), ("vllm", "FP16", "q8"), ("sglang", "BF16", "q8")]
)
def test_explicit_supported_native_dtype_cache_controls(backend, dtype, kv):
    declaration = api.declare_serving(
        request(backend=backend, dtype=dtype, kv_quant=kv, prefix_caching=True)
    )
    rendered = api.export_serving_declaration(declaration, format="compose", **layout())
    row = json.loads(rendered.content)["services"]["inference-1"]
    command = row["entrypoint"] + row["command"]
    assert command[command.index("--dtype") + 1] == ("bfloat16" if dtype == "BF16" else "float16")
    if kv == "q8":
        assert command[command.index("--kv-cache-dtype") + 1] == (
            "fp8" if backend == "vllm" else "fp8_e5m2"
        )


def test_fingerprint_does_not_authorize_fabricated_claims_and_source_output_alias(tmp_path):
    declaration = api.declare_serving(request())
    source = tmp_path / "operator.serving.json"
    declaration.save(source)
    original = source.read_bytes()
    with pytest.raises(api.ServingDeclarationError):
        declaration.save(source)
    assert source.read_bytes() == original
    for field, value in (
        ("claims", {**declaration.to_dict()["claims"], "feasibility": True}),
        ("argv_profile", "foreign-profile"),
    ):
        data = declaration.to_dict()
        data[field] = value
        changed = tmp_path / (field + ".json")
        changed.write_text(json.dumps(fingerprinted_declaration(data)), encoding="utf-8")
        with pytest.raises(api.ServingDeclarationError):
            api.load_serving_declaration(changed)
    with pytest.raises(api.ServingDeclarationError):
        api.verify_serving_declaration(source, source, **layout())
    assert source.read_bytes() == original


@pytest.mark.parametrize("route", ["save", "quote", "export", "verify"])
def test_mutated_typed_declaration_is_admitted_before_copy_or_encode(tmp_path, route):
    from chimeraforge.serving_declaration import MAX_DECLARATION_BYTES

    copied = []

    class CopyTrap:
        def __deepcopy__(self, memo):
            copied.append(True)
            raise RuntimeError("typed receiver copied before admission")

    declaration = api.declare_serving(request())
    config = tmp_path / "expected.json"
    config.write_text(
        api.export_serving_declaration(declaration, format="compose", **layout()).content,
        encoding="utf-8",
    )
    declaration._data["unexpected"] = {
        "oversized": "x" * (MAX_DECLARATION_BYTES + 1),
        "copy_trap": CopyTrap(),
    }
    calls = {
        "save": lambda: declaration.save(tmp_path / "refused.json"),
        "quote": lambda: api.quote_serving(declaration),
        "export": lambda: api.export_serving_declaration(declaration, format="compose", **layout()),
        "verify": lambda: api.verify_serving_declaration(declaration, config, **layout()),
    }
    with pytest.raises(api.ServingDeclarationError):
        calls[route]()
    assert copied == []
    assert not (tmp_path / "refused.json").exists()


def test_namespace_only_keeps_declaration_default_name_not_candidate_identity():
    from chimeraforge.kubernetes_options import KubernetesOptions

    declaration = api.declare_serving(request())
    exported = api.export_serving_declaration(
        declaration, format="kubernetes", kubernetes=KubernetesOptions(namespace="operators")
    )
    rows = json.loads(exported.content)["items"]
    assert len(rows) == 6
    assert all("-serving-" in row["metadata"]["name"] for row in rows)
    assert all(row["metadata"]["namespace"] == "operators" for row in rows)
