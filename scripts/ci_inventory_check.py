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


def accept_selected_batch(cwd: Path, env: dict, *, hosted_native_absence: bool) -> dict:
    """Qualify installed producer/receiver arithmetic with declared archived geometry."""
    from typer.testing import CliRunner

    from chimeraforge import api, inventory_process
    from chimeraforge.cli import app
    from ci_installed_acceptance import run_cli

    outcomes = {}
    native_absence = None
    consumed_corpus = None
    original_command = inventory_process.COMMAND
    saved_paths = {}
    source_root = Path(__file__).resolve().parents[1]
    archive = source_root / "tests/fixtures/hybrid_configs/Qwen_Qwen2.5-1.5B-Instruct.json"
    config = json.loads(archive.read_text(encoding="utf-8"))
    assert (
        config["num_hidden_layers"],
        config["num_key_value_heads"],
        config["hidden_size"],
        config["num_attention_heads"],
        config["use_sliding_window"],
    ) == (28, 2, 1536, 12, False)
    try:
        for context, rate, replicas in ((8192, 16, 1), (8193, 16, 1), (8192, 128, 3)):
            # Geometry is from the committed Qwen archive; params_b is a declared fixture.
            # This does not load weights or resolve a Hub revision.
            artifact = api.plan(
                api.PlanRequest(
                    models=["ci/archived-qwen-geometry"],
                    overrides={
                        "params_b": 1.5,
                        "n_layers": config["num_hidden_layers"],
                        "n_kv_heads": config["num_key_value_heads"],
                        "d_head": config["hidden_size"] // config["num_attention_heads"],
                        "hidden_size": config["hidden_size"],
                    },
                    hardware="RTX 4090 24GB",
                    platform="linux",
                    tensor_parallel=2,
                    context_length=context,
                    request_rate=rate,
                    latency_slo=10000,
                    quality_target=0,
                    budget=1e8,
                    allow_network=False,
                )
            )
            produced_corpus = artifact.to_dict()["result"]["replay_context"]["corpus"]
            if consumed_corpus is None:
                consumed_corpus = produced_corpus
            else:
                assert consumed_corpus == produced_corpus
            index = next(
                i
                for i, row in enumerate(artifact.to_dict()["result"]["candidates"])
                if row["backend"] == "vllm" and row["quant"] == "FP16"
            )
            assert artifact.candidate(index).n_agents == replicas
            path = cwd / f"selected-{context}-{replicas}.json"
            artifact.save(path)
            original = path.read_bytes()
            assert api.load_plan(path).to_dict() == artifact.to_dict()
            saved_paths[path] = original
            groups = [[str(2 * i), str(2 * i + 1)] for i in range(replicas)]
            arguments = ["inventory-check", "--plan", str(path), "--candidate-index", str(index)]
            if replicas == 1:
                arguments += [arg for value in groups[0] for arg in ("--gpu-device", value)]
            else:
                arguments += [
                    arg for group in groups for arg in ("--replica-devices", ",".join(group))
                ]
            arguments += ["--memory-basis", "selected-batch", "--json"]
            if context == 8192 and replicas == 1 and hosted_native_absence:
                if os.environ.get("GITHUB_ACTIONS") == "true":
                    public = json.loads(run_cli(arguments, cwd, env, 4))
                    assert public["baseline"]["status"] == "estimated"
                    assert public["deployment_ready"] is None and len(public["slots"]) == 2
                    native_absence = {"exit_code": 4, "slots": 2, "deployment_ready": None}
            cases = (
                (
                    ("selected_pass", "5000", 0),
                    ("selected_shortfall", "4100", 5),
                    ("overlap", "4490", 4),
                    ("free_unavailable", "N/A", 4),
                    ("missing", "5000", 5),
                    ("malformed", "5000", 4),
                )
                if context == 8192 and replicas == 1
                else (("odd_context_pass", "4506.335704", 0),)
                if context == 8193
                else (("all_original_six", "100000", 0),)
            )
            for label, free, expected in cases:
                raw = "".join(
                    f"{value}, GPU-{int(value):08x}-1111-2222-3333-444444444444, "
                    f"protocol fixture, 100000, {free}, 595.00, N/A\n"
                    for group in groups
                    for value in group
                    if label != "missing" or value != "0"
                ) + ("truncated row\n" if label == "malformed" else "")
                inventory_process.COMMAND = (
                    sys.executable,
                    "-B",
                    "-c",
                    f"import sys;sys.stdout.buffer.write({raw.encode()!r})",
                )
                direct = asyncio.run(
                    api.check_inventory(
                        path,
                        candidate_index=index,
                        memory_basis="selected-batch",
                        gpu_devices=groups[0] if replicas == 1 else None,
                        replica_gpu_devices=groups if replicas > 1 else None,
                    )
                )
                cli = CliRunner().invoke(app, arguments)
                assert direct.exit_code == cli.exit_code == expected, (
                    label,
                    direct.to_dict(),
                    cli.output,
                )
                public = json.loads(cli.stdout)
                assert public["schema_version"] == 2 and public["deployment_ready"] is None
                assert len(public["slots"]) == replicas * 2
                assert [slot["selector"] for slot in public["slots"]] == [
                    v for g in groups for v in g
                ]
                assert public["observation"]["cleanup_state"] == "completed"
                assert isinstance(direct.baseline, api.SelectedBatchBaseline)
                if label == "selected_shortfall":
                    b1 = asyncio.run(
                        api.check_inventory(path, candidate_index=index, gpu_devices=groups[0])
                    )
                    assert b1.exit_code == 0
                    assert direct.baseline.saved_effective_batch == 8
                    assert direct.baseline.selected_lower_gib == "4.380625"
                    assert direct.baseline.selected_upper_gib == "4.390625"
                    # Independently specified native archived-geometry B8 minus B1 addition.
                    from fractions import Fraction

                    assert direct.baseline.per_sequence_increment_gib is not None
                    assert Fraction(direct.baseline.per_sequence_increment_gib) * 7 * 1024 == 784
                if context == 8193:
                    assert direct.baseline.per_sequence_increment_gib == "0.1093883514404296875"
                outcomes[label] = {
                    "api_exit": direct.exit_code,
                    "cli_exit": cli.exit_code,
                    "original_slots": replicas * 2,
                    "all_slots_retained": True,
                    "owned_children_closed": direct.observation.cleanup_state == "completed",
                }
        legacy_path = source_root / "tests/fixtures/inventory/legacy086-qwen-b8.json"
        legacy_raw = legacy_path.read_bytes()
        legacy_sha = hashlib.sha256(legacy_raw).hexdigest()
        assert legacy_sha == "33dd39c068be999b66566f336677c489a6af183fc99c3c2d3b0e24035ed57212"
        legacy = api.load_plan(legacy_path)
        legacy_index = next(
            i
            for i, row in enumerate(legacy.to_dict()["result"]["candidates"])
            if row["backend"] == "vllm" and row["quant"] == "FP16"
        )
        default = asyncio.run(
            api.check_inventory(legacy, candidate_index=legacy_index, gpu_devices=["0", "1"])
        )
        explicit = asyncio.run(
            api.check_inventory(
                legacy,
                candidate_index=legacy_index,
                gpu_devices=["0", "1"],
                memory_basis="batch-one",
            )
        )
        assert default.exit_code == explicit.exit_code == 0
        assert default.baseline == explicit.baseline and default.slots == explicit.slots
        assert default.schema_version == explicit.schema_version == 1
        unknown = asyncio.run(
            api.check_inventory(
                legacy,
                candidate_index=legacy_index,
                gpu_devices=["0", "1"],
                memory_basis="selected-batch",
            )
        )
        assert unknown.exit_code == 4 and unknown.observation.state == "not_started"
        assert len(unknown.slots) == 2 and legacy_path.read_bytes() == legacy_raw
        saved_corpus = legacy.to_dict()["result"]["replay_context"]["corpus"]
        assert consumed_corpus is not None
        legacy_check = api.check_plan(legacy).to_dict()
        checked_corpus = legacy_check["components"]["corpus"]
        actual_failures = {
            key
            for key, value in legacy_check["components"].items()
            if value["required"] and value["state"] in ("changed", "expired", "unverified")
        }
        legacy_receipts = {
            "exit_code": legacy_check["exit_code"],
            "prediction_changed": legacy_check["comparison"]["changed"],
            "tool_state": legacy_check["components"]["tool"]["state"],
            "corpus_state": checked_corpus["state"],
            "required_failures": sorted(actual_failures),
            "saved_coefficient_sha256": saved_corpus["sha256"],
            "consumed_coefficient_sha256": consumed_corpus["sha256"],
            "saved_input_sha256": saved_corpus["input"]["sha256"],
            "consumed_input_sha256": consumed_corpus["input"]["sha256"],
        }
        print(json.dumps({"legacy_corpus_check": legacy_receipts}), file=sys.stderr, flush=True)
        assert saved_corpus["sha256"] == consumed_corpus["sha256"], (
            "Legacy coefficient corpus differs"
        )
        assert saved_corpus["input"]["kind"] == consumed_corpus["input"]["kind"] == "bundled"
        corpus_state = "unchanged" if saved_corpus == consumed_corpus else "changed"
        assert legacy_check["comparison"]["changed"] is False, "Legacy predictions changed"
        assert len(legacy_check["comparison"]["matched"]) == 19
        assert legacy_check["exit_code"] == 1
        assert legacy_check["components"]["tool"]["state"] == "changed"
        assert checked_corpus["before"] == saved_corpus
        assert checked_corpus["after"] == consumed_corpus
        assert checked_corpus["required"] is True and checked_corpus["state"] == corpus_state
        expected_failures = {"tool"} | ({"corpus"} if corpus_state == "changed" else set())
        assert actual_failures == expected_failures
        assert all(row["state"] != "changed" for row in legacy_check["resolution_view"].values())
        assert all(
            row["state"] != "changed"
            for view in legacy_check["checkpoint_view"].values()
            for row in view.values()
        )
    finally:
        inventory_process.COMMAND = original_command
    assert all(path.read_bytes() == original for path, original in saved_paths.items())
    return {
        "scope": (
            "Declared archived geometry, genuine native producer/save/load; owned protocol only."
        ),
        "literal_addition_mib": 784,
        "controls": outcomes,
        "hosted_cpu_native_absence": native_absence,
        "all_saved_bytes_held": True,
        "legacy_exact_sha256": legacy_sha,
        "legacy_default_parity_and_selected_refusal": True,
        "legacy_prediction_equivalence_with_tool_change_retained": True,
        "legacy_receipts": legacy_receipts,
        "archived_config_raw_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "archived_config_lf_normalized_sha256": hashlib.sha256(
            archive.read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "deployment_ready": None,
    }


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
        "selected_batch": accept_selected_batch(
            cwd, env, hosted_native_absence=hosted_native_absence
        ),
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
            "source API and in-process Typer CLI on owned Python subprocess fixtures; "
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
        "selected_batch": actual["selected_batch"],
        "deployment_ready": None,
        "unassessed": actual["controls"]["complete"]["api"]["unassessed"],
        "hardware_queries": 0,
        "source_sha256": {
            str(path.relative_to(root)).replace("\\", "/"): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted(
                set((root / "src/chimeraforge").glob("inventory*.py"))
                | {
                    root / name
                    for name in (
                        "src/chimeraforge/api.py",
                        "src/chimeraforge/__init__.py",
                        "src/chimeraforge/commands/inventory_check.py",
                        "src/chimeraforge/planner/engine.py",
                        "src/chimeraforge/planner/models.py",
                        "src/chimeraforge/planner/resolver.py",
                        "src/chimeraforge/plan_check.py",
                        "scripts/ci_inventory_check.py",
                        "tests/test_inventory_selected_batch.py",
                        "tests/test_ci_inventory_selected_batch.py",
                        "tests/test_plan_check.py",
                        "tests/test_provenance_classes.py",
                        "tests/fixtures/inventory/legacy086-qwen-b8.json",
                        "tests/fixtures/hybrid_configs/Qwen_Qwen2.5-1.5B-Instruct.json",
                        "tests/fixtures/hybrid_configs/MANIFEST.json",
                        ".github/workflows/ci.yml",
                        "pyproject.toml",
                        "uv.lock",
                        "server.json",
                    )
                }
            )
        },
    }
    args.record.parent.mkdir(parents=True, exist_ok=True)
    args.record.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record["controls"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
