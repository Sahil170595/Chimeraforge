"""Installed CLI/API inventory arithmetic on owned protocol children, never GPU qualification."""

from __future__ import annotations

import asyncio
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile


def accept(
    cwd: Path, env: dict, saved: Path, index: int, *, hosted_native_absence: bool = True
) -> dict:
    from typer.testing import CliRunner

    from chimeraforge import api, inventory_process
    from chimeraforge.cli import app
    from ci_installed_acceptance import run_cli

    assert Path(api.__file__).parent == Path(inventory_process.__file__).parent
    original = saved.read_bytes()
    groups = [["7", "3"], ["9", "2"], ["8", "4"]]
    arguments = ["inventory-check", "--plan", str(saved), "--candidate-index", str(index), "--json"]
    arguments += [arg for group in groups for arg in ("--replica-devices", ",".join(group))]
    candidate = json.loads(original)["result"]["candidates"][index]
    assert candidate["n_agents"] == 3 and candidate["gpus_total"] == 6
    native_absence = None
    # This path is reserved for the actual hosted CPU consumer, never a local GPU probe.
    if hosted_native_absence and os.environ.get("GITHUB_ACTIONS") == "true":
        native_absence = json.loads(run_cli(arguments, cwd, env, 4))
        assert native_absence["deployment_ready"] is None
        assert len(native_absence["slots"]) == 6
    outcomes = {}
    command = inventory_process.COMMAND
    try:
        for label, expected in (
            ("complete", 0),
            ("unavailable_free", 4),
            ("shortfall", 5),
            ("malformed", 4),
            ("missing", 5),
        ):
            free = (
                "N/A" if label == "unavailable_free" else "0" if label == "shortfall" else "100000"
            )
            raw = "".join(
                f"{value}, GPU-{int(value):08x}-1111-2222-3333-444444444444, "
                f"protocol fixture, 100000, {free}, "
                f"595.00, {'Enabled' if offset % 2 else 'N/A'}\n"
                for offset, value in enumerate(value for group in groups for value in group)
                if label != "missing" or value != "7"
            )
            if label == "malformed":
                raw += "truncated row\n"
            inventory_process.COMMAND = (
                sys.executable,
                "-B",
                "-c",
                f"import sys;sys.stdout.buffer.write({raw.encode()!r})",
            )
            direct = asyncio.run(
                api.check_inventory(saved, candidate_index=index, replica_gpu_devices=groups)
            )
            cli = CliRunner().invoke(app, arguments)
            assert direct.exit_code == cli.exit_code == expected, (
                label,
                direct.to_dict(),
                cli.output,
            )
            public = json.loads(cli.stdout)
            assert public["deployment_ready"] is None and len(public["slots"]) == 6
            assert [slot["selector"] for slot in public["slots"]] == [
                value for group in groups for value in group
            ]
            outcomes[label] = {"api": direct.to_dict(), "cli": public}
    finally:
        inventory_process.COMMAND = command
    assert saved.read_bytes() == original
    return {
        "scope": "synthetic subprocess protocol and saved B1 arithmetic only",
        "controls": outcomes,
        "hosted_cpu_native_absence": native_absence,
        "original_plan_sha256": hashlib.sha256(original).hexdigest(),
        "source_bytes_unchanged": True,
        "gpu_execution": "unverified",
        "physical_independence": "unverified",
        "deployment_ready": None,
    }


def main() -> int:
    """Regenerate only controlled source-protocol evidence, without native GPU contact."""
    from chimeraforge import api, __version__

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="chimeraforge-inventory-record-") as temporary:
        cwd = Path(temporary)
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
        index = next(
            i
            for i, row in enumerate(saved.to_dict()["result"]["candidates"])
            if row["backend"] == "vllm"
            and row["quant"] == "FP16"
            and row["n_agents"] == 3
            and row["gpus_total"] == 6
        )
        path = cwd / "saved.json"
        saved.save(path)
        actual = accept(cwd, dict(os.environ), path, index, hosted_native_absence=False)
    root = Path(__file__).resolve().parents[1]
    record = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "version": __version__,
        "evidence": (
            "source CLI/API on owned Python subprocess fixtures; "
            "no installed-distribution or GPU qualification"
        ),
        "population": {
            "replicas": 3,
            "tensor_parallel": 2,
            "pipeline_parallel": 1,
            "declared_slots": 6,
            "ordered_groups": [["7", "3"], ["9", "2"], ["8", "4"]],
        },
        "baseline": actual["controls"]["complete"]["api"]["baseline"],
        "controls": {
            key: {
                "api_exit": value["api"]["exit_code"],
                "cli_exit": value["cli"]["exit_code"],
                "declared_coverage": value["api"]["declared_coverage"],
                "deployment_ready": None,
            }
            for key, value in actual["controls"].items()
        },
        "source_bytes_unchanged": actual["source_bytes_unchanged"],
        "deployment_ready": None,
        "unassessed": actual["controls"]["complete"]["api"]["unassessed"],
        "hardware_queries": 0,
        "source_sha256": {
            str(path.relative_to(root)).replace("\\", "/"): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted((root / "src/chimeraforge").glob("inventory*.py"))
        },
    }
    args.record.parent.mkdir(parents=True, exist_ok=True)
    args.record.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record["controls"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
