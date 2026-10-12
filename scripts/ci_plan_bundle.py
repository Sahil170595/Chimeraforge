"""Installed CLI handoff: synthetic bound inputs, producer removal, foreign-host reuse."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def validate(report: dict, raw_plan: bytes, directory: Path) -> None:
    """Require content binding and relocation, never a performance/authenticity claim."""
    data = json.loads(raw_plan)
    assert report["fingerprint"] == data["fingerprint"]
    assert report["exit_code"] == 0 and report["comparison"]["changed"] is False
    assert report["performance"]["state"] == "unverified"
    assert report["bundle"]["source_authentication"] == "unverified"
    for role in ("corpus", "quality"):
        receipt = report["bundle"]["relocations"][role]
        assert receipt["state"] == "verified_content"
        assert receipt["producer"] == data["result"]["replay_context"][role]["input"]
        assert receipt["local"]["path"] == str((directory / f"{role}.json").resolve())
        assert receipt["producer"]["path"] != receipt["local"]["path"]
        assert receipt["local"]["sha256"] == receipt["producer"]["sha256"]
        assert report["components"][role]["state"] == "unchanged"
        assert report["components"][role]["before"] != report["components"][role]["after"]
    assert "private_payload" not in json.dumps(report["bundle"])


def _check_absent_producers(data: dict) -> None:
    from chimeraforge.plan_check import _local_file

    for role in ("corpus", "quality"):
        binding = data["result"]["replay_context"][role]["input"]
        source = _local_file(binding)
        assert source is None or not source.exists(), "producer inputs remain available"


def produce(directory: Path, checkout: Path) -> dict:
    """Generate via isolated installed CLI; only aggregate bundle bytes are retained."""
    from ci_installed_acceptance import assert_installed_origin, run_cli

    directory = directory.resolve()
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    with tempfile.TemporaryDirectory(prefix="chimeraforge-bundle-producer-") as temporary:
        work = Path(temporary).resolve()
        env["CHIMERAFORGE_CACHE"] = str(work / "cache")
        origin = subprocess.run(
            [sys.executable, "-I", "-c", "import chimeraforge; print(chimeraforge.__file__)"],
            cwd=work,
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        ).stdout.strip()
        assert_installed_origin(origin, checkout)
        corpus, harness, plan = (
            work / "coefficients.json",
            work / "harness.json",
            work / "original-plan.json",
        )
        corpus.write_text(json.dumps({"vram": {"overhead_factor": 1.123}}), encoding="utf-8")
        harness.write_text(
            json.dumps(
                {
                    "results": {"mmlu": {"acc,none": 0.83}},
                    "n-samples": {"mmlu": 5000},
                    "config": {"private_payload": "synthetic privacy sentinel"},
                }
            ),
            encoding="utf-8",
        )
        run_cli(
            [
                "plan",
                "--model",
                "ci/bundle-fixture",
                "--params-b",
                "3",
                "--n-layers",
                "28",
                "--n-kv-heads",
                "8",
                "--d-head",
                "128",
                "--hardware",
                "RTX 4080 12GB",
                "--platform",
                "linux",
                "--request-rate",
                "0.01",
                "--latency-slo",
                "5000",
                "--budget",
                "100000",
                "--quality-target",
                "0.8",
                "--no-network",
                "--json",
                "--models-path",
                str(corpus),
                "--quality-from",
                str(harness),
                "--save",
                str(plan),
            ],
            work,
            env,
        )
        original = plan.read_bytes()
        run_cli(["bundle", "create", str(plan), "--out", str(directory), "--json"], work, env)
        assert original == plan.read_bytes() == (directory / "plan.json").read_bytes()
    data = json.loads(original)
    _check_absent_producers(data)
    report = json.loads(
        run_cli(["bundle", "check", str(directory), "--json"], directory.parent, env)
    )
    validate(report, original, directory)
    return {
        "origin": origin,
        "plan_sha256": hashlib.sha256(original).hexdigest(),
        "fingerprint": data["fingerprint"],
        "producer_paths_absent": True,
        "producer_path_flavor": data["result"]["replay_context"]["quality"]["input"]["path_flavor"],
        "scope": "synthetic coefficient/harness fixture, actual installed CLI",
    }


def accept(cwd: Path, env: dict, checkout: Path, *, handoff: Path | None = None) -> dict:
    from ci_installed_acceptance import run_cli

    local = produce(cwd / "local-bundle", checkout)
    receipts = {"same_host": local}
    if handoff is not None:
        destination = cwd / "foreign-bundle"
        # Copy only a previously uploaded fixed-membership bundle; verify rejects extras/links.
        from chimeraforge.api import verify_plan_bundle

        verify_plan_bundle(handoff)
        shutil.copytree(handoff, destination)
        original = (destination / "plan.json").read_bytes()
        data = json.loads(original)
        _check_absent_producers(data)
        verified = json.loads(run_cli(["bundle", "verify", str(destination), "--json"], cwd, env))
        report = json.loads(run_cli(["bundle", "check", str(destination), "--json"], cwd, env))
        validate(report, original, destination)
        assert original == (destination / "plan.json").read_bytes()
        assert verified["fingerprint"] == data["fingerprint"]
        producer_flavor = data["result"]["replay_context"]["quality"]["input"]["path_flavor"]
        assert producer_flavor == "posix", "hosted producer must be actual Linux"
        if sys.platform == "win32":
            assert report["bundle"]["relocations"]["quality"]["local"]["path_flavor"] == "windows"
        receipts["linux_producer_handoff"] = {
            "plan_sha256": hashlib.sha256(original).hexdigest(),
            "fingerprint": data["fingerprint"],
            "producer_path_flavor": producer_flavor,
            "consumer_platform": sys.platform,
            "producer_paths_absent": True,
            "original_bytes_unchanged": True,
            "installed_cli_create_verify_check": "passed",
            "source_authentication": "unverified",
            "performance": "unverified",
        }
    return receipts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--produce", required=True, type=Path)
    parser.add_argument("--checkout", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(produce(args.produce, args.checkout), indent=2))


if __name__ == "__main__":
    main()
