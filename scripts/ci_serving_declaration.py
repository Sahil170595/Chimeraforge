"""Real declaration CLI/API/config receivers, without any engine or model execution."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, localcontext
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from chimeraforge.serving_declaration import ServingDeclaration


def _accept_budget(
    cwd: Path, env: dict, flags: list[str], native: dict, artifact: ServingDeclaration
) -> dict:
    from chimeraforge import api
    from chimeraforge.planner import cloudprice
    from ci_installed_acceptance import run_cli

    with localcontext() as context:
        context.prec = 80
        monthly = Decimal(str(native["offer"]["price_per_hour"])) * 2 * 720
        exact = format(monthly.normalize(), "f")
        below = format((monthly - Decimal("0.000001")).normalize(), "f")
    observed = []
    for cap, limit, fresh_exit in ((exact, 90, 0), (below, 90, 5), (exact, 0, 0)):
        child = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-m",
                "chimeraforge",
                "serving",
                "quote",
                *flags,
                "--max-monthly-usd",
                cap,
                "--max-price-age-days",
                str(limit),
                "--json",
            ],
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=30,
        )
        body = json.loads(child.stdout)
        stale = body["age_days"] > limit
        code = 4 if stale else fresh_exit
        assert child.returncode == body["exit_code"] == code
        assert body["schema_version"] == 2 and body["captured_at"] == native["captured_at"]
        assert body["instance_count"] == 2 and body["hours_per_month"] == 720
        assert body["feasibility"] is body["deployment_ready"] is None
        assert body["budget"]["quoted_monthly_usd"] == exact
        assert body["budget"]["status"] == {0: "within_budget", 4: "stale", 5: "above_budget"}[code]
        assert body["budget"]["max_monthly_usd"] == cap
        observed.append({"age_days": body["age_days"], "limit": limit, "exit_code": code})
    refused = json.loads(
        run_cli(["serving", "quote", *flags, "--max-monthly-usd", "NaN", "--json"], cwd, env, 1)
    )
    assert refused["exit_code"] == 1 and "budget" not in refused
    unknown = json.loads(
        run_cli(["serving", "quote", *flags[:2], "--max-monthly-usd", exact, "--json"], cwd, env, 4)
    )
    assert unknown["budget"]["reason"] == "no_billing_target"
    assert unknown["budget"]["quoted_monthly_usd"] is None and unknown["exit_code"] == 4

    captured = date.fromisoformat(native["captured_at"])
    controlled = []
    for age, limit, cap, code in ((7, 7, exact, 0), (7, 7, below, 5), (8, 7, exact, 4)):
        with patch.object(cloudprice, "_today", return_value=captured + timedelta(days=age)):
            report = api.quote_serving(
                artifact,
                cloud=native["cloud"],
                instance=native["instance"],
                region=native["region"],
                budget_policy=api.ServingQuoteBudgetPolicy(cap, limit),
            )
        assert (
            report.exit_code == code and report.to_dict()["budget"]["quoted_monthly_usd"] == exact
        )
        controlled.append(code)
    return {
        "bundled_native_monthly_usd": exact,
        "actual_cli_observed_snapshot_age": observed,
        "controlled_api_exit_codes": controlled,
        "malformed_cli_exit": 1,
        "unknown_cli_exit": 4,
    }


def accept(cwd: Path, env: dict) -> dict:
    from chimeraforge import api
    from chimeraforge import serving_declaration, serving_export, serving_quote
    from chimeraforge.kubernetes_options import KubernetesOptions
    from ci_installed_acceptance import run_cli

    api_origin = api.__file__
    assert api_origin is not None
    for module in (serving_declaration, serving_export, serving_quote):
        origin = module.__file__
        assert origin is not None and Path(origin).parent == Path(api_origin).parent
    directory = cwd / "serving-declaration"
    directory.mkdir()
    source = directory / "operator.serving.json"
    declared = json.loads(
        run_cli(
            [
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
                str(source),
                "--json",
            ],
            cwd,
            env,
        )
    )
    original = source.read_bytes()
    artifact = api.load_serving_declaration(source)
    assert declared["logical_gpu_slots"] == 12 and declared["deployment_ready"] is None
    assert all(value is None for value in artifact.to_dict()["claims"].values())
    quote_flags = [
        "--declaration",
        str(source),
        "--cloud",
        "aws",
        "--instance",
        "p5.48xlarge",
        "--region",
        "us-east-1",
    ]
    cli_quote = json.loads(run_cli(["serving", "quote", *quote_flags, "--json"], cwd, env))
    direct_quote = api.quote_serving(
        artifact, cloud="aws", instance="p5.48xlarge", region="us-east-1"
    ).to_dict()
    assert {k: v for k, v in cli_quote.items() if k != "created_at"} == {
        k: v for k, v in direct_quote.items() if k != "created_at"
    }
    assert cli_quote["instance_count"] == 2 and cli_quote["billed_gpus"] == 16
    assert cli_quote["idle_billed_gpus"] == 4 and cli_quote["feasibility"] is None
    assert cli_quote["schema_version"] == 1 and "budget" not in cli_quote
    quote_budget = _accept_budget(cwd, env, quote_flags, cli_quote, artifact)
    groups = [[str(4 * r + i) for i in range(4)] for r in range(3)]
    ports = [9001, 9002, 9003]
    profiles = {}
    for format in ("launch", "compose", "kubernetes"):
        output = directory / (format + ".json")
        flags = ["--declaration", str(source), "--format", format]
        if format != "kubernetes":
            flags += [item for group in groups for item in ("--replica-devices", ",".join(group))]
            flags += [item for port in ports for item in ("--replica-port", str(port))]
        else:
            flags += ["--namespace", "ci-serving", "--name-prefix", "operator"]
        group_options = groups if format != "kubernetes" else None
        port_options = ports if format != "kubernetes" else None
        kube_options = (
            KubernetesOptions("ci-serving", "operator") if format == "kubernetes" else None
        )
        run_cli(["serving", "export", *flags, "--out", str(output), "--json"], cwd, env)
        direct = api.export_serving_declaration(
            artifact,
            format=format,
            replica_gpu_devices=group_options,
            replica_host_ports=port_options,
            kubernetes=kube_options,
        )
        assert output.read_bytes() == direct.content.encode("utf-8")
        cli = json.loads(
            run_cli(["serving", "verify", *flags, "--config", str(output), "--json"], cwd, env)
        )
        report = api.verify_serving_declaration(
            artifact,
            output,
            format=format,
            replica_gpu_devices=group_options,
            replica_host_ports=port_options,
            kubernetes=kube_options,
        )
        assert cli["exit_code"] == report.exit_code == 0
        data = json.loads(output.read_bytes())
        if format == "launch":
            assert len(data["replicas"]) == 3
            assert sum(row["logical_gpu_slots"] for row in data["replicas"]) == 12
            data["replicas"][0]["argv"].append("--altered-control")
        elif format == "compose":
            assert len(data["services"]) == 3
            data["services"].pop("inference-3")
        else:
            assert len(data["items"]) == 6
            data["items"][0]["spec"]["template"]["spec"]["containers"][0]["resources"]["limits"][
                "nvidia.com/gpu"
            ] = "3"
        output.write_text(json.dumps(data), encoding="utf-8")
        changed = json.loads(
            run_cli(["serving", "verify", *flags, "--config", str(output), "--json"], cwd, env, 5)
        )
        assert changed["change_count"] > 0
        profiles[format] = {
            "match_exit": 0,
            "mutation_exit": 5,
            "replicas": 3,
            "logical_gpu_slots": 12,
            "objects": 6 if format == "kubernetes" else 3,
        }
    run_cli(
        [
            "serving",
            "export",
            "--declaration",
            str(source),
            "--format",
            "compose",
            "--out",
            str(source),
            "--json",
        ],
        cwd,
        env,
        1,
    )
    invalid = directory / "refused.json"
    run_cli(
        [
            "serving",
            "export",
            "--declaration",
            str(source),
            "--format",
            "compose",
            "--out",
            str(invalid),
            "--replica-devices",
            "0,1,2,3",
            "--replica-devices",
            "0,5,6,7",
            "--replica-devices",
            "8,9,10,11",
            "--replica-port",
            "9001",
            "--replica-port",
            "9002",
            "--replica-port",
            "9003",
            "--json",
        ],
        cwd,
        env,
        1,
    )
    assert not invalid.exists() and source.read_bytes() == original
    try:
        api.check_plan(source)
    except api.PlanError:
        pass
    else:
        raise AssertionError("operator declaration became optimizer evidence")
    return {
        "scope": (
            "Actual CLI/API operator declaration and native config-only receivers; "
            "no engine, image, model, GPU or host execution."
        ),
        "logical_gpu_slots": 12,
        "replicas": 3,
        "profiles": profiles,
        "quote_budget": quote_budget,
        "quote": {
            "instance_count": 2,
            "billed_gpus": 16,
            "idle_billed_gpus": 4,
            "captured_at": cli_quote["captured_at"],
            "age_days": cli_quote["age_days"],
            "stale": cli_quote["stale"],
            "snapshot_object_sha256": cli_quote["snapshot_object_sha256"],
        },
        "aliases_and_invalid_layout_refused": True,
        "optimizer_misuse_refused": True,
        "source_sha256": hashlib.sha256(original).hexdigest(),
        "source_bytes_held": True,
        "owned_CLI_children_joined": True,
        "deployment_ready": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="cf-serving-") as folder:
        actual = accept(Path(folder), dict(os.environ))
    from chimeraforge import __version__

    actual["tool_version"] = __version__
    actual["recorded_at"] = datetime.now(timezone.utc).isoformat()
    actual["source_hash_basis"] = "Actual current RAW source files on the recording host."
    root = Path(__file__).resolve().parents[1]
    paths = [
        *root.glob("src/chimeraforge/serving*.py"),
        root / "src/chimeraforge/commands/serving.py",
        *[
            root / p
            for p in (
                "src/chimeraforge/api.py",
                "src/chimeraforge/cli.py",
                "src/chimeraforge/deploy.py",
                "src/chimeraforge/deployment_verify.py",
                "src/chimeraforge/kubernetes_export.py",
                "src/chimeraforge/planner/cloudprice.py",
                "src/chimeraforge/planner/data/cloud_prices.json",
                "scripts/ci_serving_declaration.py",
                "scripts/ci_installed_acceptance.py",
                "tests/test_serving_declaration.py",
                "tests/test_ci_serving_declaration.py",
                ".github/workflows/ci.yml",
                "pyproject.toml",
                "uv.lock",
                "server.json",
            )
        ],
    ]
    actual["current_source_sha256"] = {
        str(path.relative_to(root)).replace("\\", "/"): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(paths)
    }
    with args.record.open("x", encoding="utf-8") as output:
        output.write(json.dumps(actual, indent=2) + "\n")
    print(json.dumps({"profiles": actual["profiles"], "source_bytes_held": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
