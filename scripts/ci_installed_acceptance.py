"""Accept the candidate wheel outside the source checkout, without network resolution."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from probe_mcp_stdio import probe
from ci_mcp_http import probe as probe_http

CLI_TIMEOUT_SECONDS = 90
RESOURCE_FILES = (
    "fitted_models.json",
    "hardware.json",
    "engine_support.json",
    "api_pricing.json",
    "model_catalog.json",
    "carbon_intensity.json",
)


def assert_installed_origin(origin: str | Path, checkout: str | Path) -> None:
    """A checkout or editable install cannot supply artifact acceptance evidence."""
    origin, checkout = Path(origin).resolve(), Path(checkout).resolve()
    assert not origin.is_relative_to(checkout), f"import came from checkout: {origin}"
    assert any(part in {"site-packages", "dist-packages"} for part in origin.parts), (
        f"import did not come from site-packages: {origin}"
    )


def run_cli(
    arguments: list[str], cwd: Path, env: dict, expected_code: int | tuple[int, ...] = 0
) -> str:
    """Invoke the installed module with checkout and PYTHONPATH isolation."""
    result = subprocess.run(
        [sys.executable, "-I", "-m", "chimeraforge", *arguments],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=CLI_TIMEOUT_SECONDS,
    )
    allowed = expected_code if isinstance(expected_code, tuple) else (expected_code,)
    assert result.returncode in allowed, (
        arguments,
        result.returncode,
        result.stdout,
        result.stderr,
    )
    assert "Traceback (most recent call last)" not in result.stdout + result.stderr
    return result.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect-version", required=True)
    parser.add_argument("--checkout", required=True, type=Path)
    parser.add_argument("--plan-handoff", type=Path)
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="chimeraforge-installed-") as work:
        cwd = Path(work).resolve()
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env.update({"CHIMERAFORGE_CACHE": str(cwd / "cache"), "NO_COLOR": "1"})
        inspect_code = (
            "import importlib.metadata as m, importlib.resources as r, json, chimeraforge; "
            "print(json.dumps({'origin':chimeraforge.__file__, 'version':chimeraforge.__version__, "
            "'distribution_version':m.version('chimeraforge'), "
            "'resources':{name:json.loads(r.files('chimeraforge.planner')"
            ".joinpath('data',name).read_text()) "
            f"for name in {RESOURCE_FILES!r}" + "}}))"
        )
        result = subprocess.run(
            [sys.executable, "-I", "-c", inspect_code],
            cwd=cwd,
            env=env,
            check=True,
            text=True,
            capture_output=True,
            timeout=CLI_TIMEOUT_SECONDS,
        )
        installed = json.loads(result.stdout)
        assert_installed_origin(installed["origin"], args.checkout)
        assert installed["version"] == installed["distribution_version"] == args.expect_version
        assert all(installed["resources"].values()), "empty bundled data resource"
        assert args.expect_version in run_cli(["--version"], cwd, env)
        assert "RTX 4080" in run_cli(["plan", "--list-hardware"], cwd, env)
        common = ["--hardware", "RTX 4080 12GB", "--request-rate", "0.01", "--no-network", "--json"]
        registered = json.loads(run_cli(["plan", "--model-size", "3b", *common], cwd, env))
        assert (
            registered and registered[0]["provenance"] and registered[0]["total_throughput_tps"] > 0
        )
        snapshot_path = cwd / "saved-plan.json"
        saved_candidates = json.loads(
            run_cli(["plan", "--model-size", "3b", *common, "--save", str(snapshot_path)], cwd, env)
        )
        from chimeraforge.api import load_plan, PlanRequest, plan as public_plan

        saved = load_plan(snapshot_path)
        assert saved.to_dict()["result"]["candidates"] == saved_candidates
        assert public_plan(PlanRequest(allow_network=False)).candidate().provenance
        manual = json.loads(
            run_cli(
                [
                    "plan",
                    "--model",
                    "ci/manual-3b",
                    "--params-b",
                    "3",
                    "--n-layers",
                    "28",
                    "--n-kv-heads",
                    "8",
                    "--d-head",
                    "128",
                    *common,
                ],
                cwd,
                env,
            )
        )
        assert manual and manual[0]["model_source"] == "manual"
        from ci_checkpoint_identity import accept as accept_checkpoint

        checkpoint_receipt = accept_checkpoint(cwd, env, args.checkout)
        from ci_plan_bundle import accept as accept_bundle

        bundle_receipt = accept_bundle(cwd, env, args.checkout, handoff=args.plan_handoff)
        default_bundle = cwd / "bundled-coefficient-handoff"
        original_default = snapshot_path.read_bytes()
        run_cli(
            [
                "bundle",
                "create",
                str(snapshot_path),
                "--out",
                str(default_bundle),
                "--json",
            ],
            cwd,
            env,
        )
        default_check = json.loads(
            run_cli(
                [
                    "bundle",
                    "check",
                    str(default_bundle),
                    "--json",
                ],
                cwd,
                env,
            )
        )
        assert default_check["components"]["installed_bundled_corpus"]["state"] == "unchanged"
        assert default_check["bundle"]["relocations"]["corpus"]["producer"]["kind"] == "bundled"
        assert (
            original_default
            == snapshot_path.read_bytes()
            == (default_bundle / "plan.json").read_bytes()
        )
        bundle_receipt["bundled_coefficients"] = {
            "fingerprint": saved.to_dict()["fingerprint"],
            "installed_cli_create_check": "passed",
            "original_bytes_unchanged": True,
            "current_installed_corpus": "unchanged",
            "source_authentication": "unverified",
        }
        from ci_plan_study import accept as accept_study

        study_bundle = cwd / ("foreign-bundle" if args.plan_handoff is not None else "local-bundle")
        study_receipt = accept_study(cwd, env, args.checkout, snapshot_path, study_bundle)
        from ci_regression_gate import accept as accept_gate

        gate_receipt = accept_gate(cwd, env, args.checkout)
        error = json.loads(run_cli(["plan", "--hardware", "ci-unknown-gpu", "--json"], cwd, env, 1))
        assert error["error"], "invalid hardware did not produce a machine-readable error"
        info, tools = probe(
            [sys.executable, "-I", "-m", "chimeraforge", "mcp"],
            cwd=cwd,
            env=env,
            checkpoint_request=checkpoint_receipt,
        )
        checkpoint_receipt["installed_mcp_revision"] = "passed"
        assert info["version"] == args.expect_version
        http_receipt = probe_http(
            [sys.executable, "-I", "-m", "chimeraforge", "mcp"], cwd=cwd, env=env
        )
        assert http_receipt["serverInfo"]["version"] == args.expect_version
        print(
            json.dumps(
                {
                    "version": args.expect_version,
                    "origin": installed["origin"],
                    "resources": list(installed["resources"]),
                    "checkpoint_identity": checkpoint_receipt,
                    "portable_plan_bundle": bundle_receipt,
                    "plan_sensitivity": study_receipt,
                    "regression_gate": gate_receipt,
                    "mcp_tools": tools,
                    "mcp_http": http_receipt,
                    "cli_and_mcp_acceptance": "passed",
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
