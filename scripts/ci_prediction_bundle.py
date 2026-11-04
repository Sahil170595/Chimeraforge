"""Private bundle transport acceptance; synthetic protocols are not measurement truth."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil

PRIVATE_INPUT = "PRIVATE_PREDICTION_BUNDLE_INPUT_070"
METADATA_FIELDS = {
    "schema_version",
    "kind",
    "status",
    "plan_fingerprint",
    "manifest_sha256",
    "policy_sha256",
    "files",
    "receipt_count",
    "transport_bytes",
    "private_handoff",
    "source_authentication",
    "limits",
}


def fixtures(source: Path) -> tuple[dict, dict, dict]:
    from ci_prediction_score import protocol_receipt, seal, synthetic_plan

    saved, index = synthetic_plan(source)
    policy = {
        "plan_fingerprint": saved["fingerprint"],
        "candidate_indices": [index],
        "expected_receipts_per_index": {str(index): 1},
        "relative_error_band": 0.25,
    }
    native = protocol_receipt(saved, index)
    native["measurement"]["warnings"].append(PRIVATE_INPUT)
    native["execution"]["request"]["options"]["private"] = PRIVATE_INPUT
    return saved, policy, seal(native)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_report(raw: str) -> dict:
    data = json.loads(raw)
    assert isinstance(data, dict)
    return data


def _inventory(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def validate_metadata(
    report: dict, directory: Path, fingerprint: str, policy: bytes, receipts: list[bytes]
) -> dict[str, bytes]:
    assert set(report) == METADATA_FIELDS
    assert type(report["schema_version"]) is int and report["schema_version"] == 1
    assert report["kind"] == "chimeraforge.prediction-bundle-verification"
    assert report["status"] == "verified_content" and report["plan_fingerprint"] == fingerprint
    assert report["private_handoff"] is True and report["source_authentication"] == "unverified"
    assert "PRIVATE HANDOFF" in report["limits"]
    assert PRIVATE_INPUT not in json.dumps(report) and str(directory) not in json.dumps(report)
    inventory = _inventory(directory)
    expected = ["plan/manifest.json", "plan/plan.json", "plan/corpus.json"]
    if "plan/quality.json" in inventory:
        expected.append("plan/quality.json")
    expected.extend(["policy.json", *[f"receipts/{i:04}.json" for i in range(len(receipts))]])
    assert set(inventory) == {"manifest.json", *expected}
    assert report["files"] == [
        {"path": name, "sha256": _sha(inventory[name]), "size_bytes": len(inventory[name])}
        for name in expected
    ]
    assert type(report["receipt_count"]) is int and report["receipt_count"] == len(receipts)
    assert type(report["transport_bytes"]) is int
    assert report["transport_bytes"] == sum(len(raw) for raw in inventory.values())
    manifest = json.loads(inventory["manifest.json"])
    assert report["manifest_sha256"] == _sha(inventory["manifest.json"])
    assert report["policy_sha256"] == manifest["policy_sha256"] == _sha(policy)
    assert inventory["policy.json"] == policy
    assert [inventory[f"receipts/{i:04}.json"] for i in range(len(receipts))] == receipts
    assert (directory / "receipts").is_dir()
    return inventory


def projection(report: dict, fingerprint: str, receipts: list[bytes]) -> dict:
    from chimeraforge.planner.replay import digest

    assert report["kind"] == "chimeraforge.prediction-scorecard"
    assert report["fingerprint"] == digest({k: v for k, v in report.items() if k != "fingerprint"})
    assert report["plan"]["fingerprint"] == fingerprint
    assert report["assurance"]["source_authentication"] == "unverified"
    assert report["assurance"]["physical_hardware"] == "unverified"
    assert PRIVATE_INPUT not in json.dumps(report)
    assert len(report["inputs"]["receipts"]) == len(receipts)
    for received, raw in zip(report["inputs"]["receipts"], receipts):
        assert received["sha256"] == _sha(raw) and received["size_bytes"] == len(raw)
    states = Counter(row["state"] for row in report["rows"])
    return {
        "exit_code": report["exit_code"],
        "outcome": report["outcome"],
        "counts": {
            "received": len(report["inputs"]["receipts"]),
            "comparable": sum(row["relative_error"] is not None for row in report["rows"]),
            "missing": states["missing"],
            "duplicate": states["duplicate"],
            "binding_mismatch": states["binding_mismatch"],
        },
    }


def _create(
    cwd: Path, env: dict, plan: Path, policy: Path, receipts: list[Path], directory: Path
) -> dict:
    from ci_installed_acceptance import run_cli

    args = [
        "bundle",
        "prediction-create",
        str(plan),
        "--policy",
        str(policy),
        "--out",
        str(directory),
        "--json",
    ]
    for path in receipts:
        args.extend(["--benchmark", str(path)])
    return _json_report(run_cli(args, cwd, env))


def _score(cwd: Path, env: dict, directory: Path, output: Path, expected: int) -> dict:
    from ci_installed_acceptance import run_cli

    report = _json_report(
        run_cli(
            ["bundle", "prediction-score", str(directory), "--out", str(output), "--json"],
            cwd,
            env,
            expected,
        )
    )
    assert json.loads(output.read_bytes()) == report
    assert PRIVATE_INPUT not in json.dumps(report)
    return report


def _roundtrip(
    cwd: Path,
    env: dict,
    plan: Path,
    policy: Path,
    receipts: list[Path],
    name: str,
    expected: int,
    *,
    hide_sources: bool = False,
) -> tuple[dict, dict, Path]:
    from ci_installed_acceptance import run_cli

    fingerprint = json.loads(policy.read_bytes())["plan_fingerprint"]
    raw_policy, raw_receipts = policy.read_bytes(), [path.read_bytes() for path in receipts]
    directory = cwd / name
    created = _create(cwd, env, plan, policy, receipts, directory)
    original = validate_metadata(created, directory, fingerprint, raw_policy, raw_receipts)
    relocated = cwd / (name + "-relocated")
    shutil.copytree(directory, relocated)
    held = []
    try:
        if hide_sources:
            for path in dict.fromkeys([plan, policy, *receipts]):
                target = path.with_name(path.name + ".producer-held")
                assert path.resolve().is_relative_to(cwd.resolve())
                assert target.resolve().is_relative_to(cwd.resolve()) and not target.exists()
                path.rename(target)
                held.append((path, target))
            assert all(not path.exists() for path, _ in held)
        verified = json.loads(
            run_cli(["bundle", "prediction-verify", str(relocated), "--json"], cwd, env)
        )
        assert created == verified
        assert (
            validate_metadata(verified, relocated, fingerprint, raw_policy, raw_receipts)
            == original
        )
        report = _score(cwd, env, relocated, cwd / (name + "-score.json"), expected)
        assert report["inputs"]["total_bytes"] == created["transport_bytes"] - len(
            original["manifest.json"]
        )
        assert _inventory(relocated) == original
    finally:
        for path, target in reversed(held):
            target.rename(path)
    return projection(report, fingerprint, raw_receipts), report, relocated


def _negative_inventory_and_aliases(cwd: Path, env: dict, directory: Path) -> None:
    from ci_installed_acceptance import run_cli

    original = _inventory(directory)
    receipt = directory / "receipts/0000.json"
    for invalid in ("tamper", "extra"):
        extra = directory / "PRIVATE-unlisted.json"
        if invalid == "tamper":
            receipt.write_bytes(original["receipts/0000.json"] + b"\n")
        else:
            extra.write_text(PRIVATE_INPUT)
        try:
            for command in ("prediction-verify", "prediction-score"):
                refused = json.loads(
                    run_cli(["bundle", command, str(directory), "--json"], cwd, env, 2)
                )
                assert refused["error"] and PRIVATE_INPUT not in json.dumps(refused)
        finally:
            receipt.write_bytes(original["receipts/0000.json"])
            if extra.exists():
                extra.unlink()
    for name in original:
        refused = json.loads(
            run_cli(
                [
                    "bundle",
                    "prediction-score",
                    str(directory),
                    "--out",
                    str(directory / name),
                    "--json",
                ],
                cwd,
                env,
                2,
            )
        )
        assert refused["error"]
        assert _inventory(directory) == original
    alias = cwd / "outside-bundle-receipt-alias.json"
    os.link(receipt, alias)
    try:
        assert json.loads(
            run_cli(
                ["bundle", "prediction-score", str(directory), "--out", str(alias), "--json"],
                cwd,
                env,
                2,
            )
        )["error"]
        assert alias.read_bytes() == original["receipts/0000.json"]
    finally:
        alias.unlink()
    assert _inventory(directory) == original


def accept(cwd: Path, env: dict, checkout: Path, source: Path) -> dict:
    import chimeraforge
    from ci_installed_acceptance import assert_installed_origin
    from ci_prediction_score import protocol_receipt, seal, validate

    assert_installed_origin(chimeraforge.__file__, checkout)
    source_original = source.read_bytes()
    saved, chosen, native = fixtures(source)
    index = chosen["candidate_indices"][0]
    plan, policy, receipt = [
        cwd / name
        for name in (
            "prediction-private-plan.json",
            "prediction-policy.json",
            "prediction-native.json",
        )
    ]
    plan.write_bytes((json.dumps(saved, indent=2) + "\n\n").encode())
    policy.write_bytes((json.dumps(chosen, indent=3) + "\n").encode())
    receipt.write_bytes((json.dumps(native, indent=3) + "\n\n").encode())
    originals = {path: path.read_bytes() for path in (plan, policy, receipt)}
    result, report, bundle = _roundtrip(
        cwd, env, plan, policy, [receipt], "prediction-roundtrip", 0, hide_sources=True
    )
    validate(report, 0, saved, native)
    assert (bundle / "plan/plan.json").read_bytes() == originals[plan]
    _negative_inventory_and_aliases(cwd, env, bundle)
    # The verified inner PlanBundle is also a supported source; no producer planning is rerun.
    zero, empty, _ = _roundtrip(cwd, env, bundle / "plan", policy, [], "prediction-zero", 3)
    validate(empty, 3, saved, None)
    duplicate, copied, _ = _roundtrip(
        cwd, env, plan, policy, [receipt, receipt], "prediction-duplicate", 3
    )
    assert len(copied["rows"]) == duplicate["counts"]["duplicate"] == 2
    negative = protocol_receipt(saved, index)
    for phase in ("serving_before", "serving_after"):
        negative["execution"][phase].update(device="cpu", hardware=None)
    receipt.write_bytes((json.dumps(seal(negative), indent=3) + "\n\n").encode())
    unavailable, unscored, _ = _roundtrip(
        cwd, env, plan, policy, [receipt], "prediction-negative", 3
    )
    validate(unscored, 3, saved, negative)
    breached = protocol_receipt(saved, index, 200.0)
    receipt.write_bytes((json.dumps(breached, indent=3) + "\n\n").encode())
    breach, breached_score, _ = _roundtrip(
        cwd, env, plan, policy, [receipt], "prediction-breach", 1
    )
    validate(breached_score, 1, saved, breached)
    receipt.write_bytes(originals[receipt])
    assert all(path.read_bytes() == raw for path, raw in originals.items())
    assert source.read_bytes() == source_original
    return {
        "roundtrip": result,
        "known_breach": breach,
        "zero_receipts": zero,
        "duplicate_receipts": duplicate,
        "negative_receipt": unavailable,
        "raw_receipt_preserved": True,
        "source_inputs_unchanged": True,
        "malformed_inventory_refused": True,
        "input_aliases_refused": True,
        "scope": (
            "synthetic installed private transport protocol; "
            "no serving, independent execution or GPU accuracy proof"
        ),
    }


def accept_cpu(cwd: Path, env: dict, plan: Path, index: int, receipt: Path) -> dict:
    from ci_prediction_score import validate

    saved, raw = json.loads(plan.read_bytes()), receipt.read_bytes()
    original_plan = plan.read_bytes()
    native = json.loads(raw)
    assert native["execution"]["serving_after"]["device"] == "cpu"
    policy = cwd / "cpu-prediction-bundle-policy.json"
    policy.write_text(
        json.dumps(
            {
                "plan_fingerprint": saved["fingerprint"],
                "candidate_indices": [index],
                "expected_receipts_per_index": {str(index): 1},
                "relative_error_band": 0.25,
            }
        )
    )
    result, score, bundle = _roundtrip(
        cwd, env, plan, policy, [receipt], "cpu-prediction-bundle", 3
    )
    validate(score, 3, saved, native)
    assert result["counts"]["binding_mismatch"] == 1 and "hardware" in score["rows"][0]["reasons"]
    assert (bundle / "receipts/0000.json").read_bytes() == raw
    assert receipt.read_bytes() == raw and plan.read_bytes() == original_plan
    return {
        **result,
        "raw_receipt_preserved": True,
        "extra_inference_requests": 0,
        "evidence_class": "existing actual hosted CPU receipt; GPU prediction remains ineligible",
    }
