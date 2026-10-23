"""Installed offline CLI sensitivity over a saved plan and absent-producer bundle."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

ALTERNATIVE_HARDWARE = "RTX 4090 24GB"
QUALITY_FIELDS = (
    "quality",
    "quality_tier",
    "quality_n",
    "quality_mde",
    "quality_indistinguishable",
)


def _timing_class(row: dict) -> str:
    timing = row["provenance"]["throughput"]
    label = timing.get("class") if isinstance(timing, dict) else timing
    assert isinstance(label, str)
    return label


def validate(report: dict, original: dict) -> None:
    """Require actual search/deltas and preserve negative outcomes and evidence scope."""
    from chimeraforge.planner.replay import digest

    assert report["source_fingerprint"] == original["fingerprint"]
    assert report["exit_code"] == 0 and report["source_authentication"] == "unverified"
    assert report["performance"]["state"] == "unverified"
    context = dict(report["frozen_context"])
    expected = context.pop("sha256")
    assert digest(context) == expected
    assert context["base_inputs"]["allow_network"] is False
    assert context["model_specs"] == original["result"]["replay_context"]["model_specs"]
    assert context["hardware"] == original["result"]["replay_context"]["hardware"]
    assert report["base"]["candidates"] == original["result"]["candidates"]
    assert report["base"]["comparison_to_saved"]["changed"] is False
    same, duty, refused = report["scenarios"]
    assert same["name"] == "same" and same["comparison"]["changed"] is False
    tokens = duty["comparison"]["matched"][0]["deltas"]["tokens_served_month"]
    assert tokens["unit"] == "tokens/month" and tokens["delta"] < 0
    assert not refused["feasible"] and refused["recommended"] is None and refused["trace"]
    assert refused["comparison"]["feasibility"] == "lost"


def validate_hardware(report: dict, original: dict) -> dict:
    """Check native rebinding and preserve each source's actual timing/quality evidence."""
    from chimeraforge.planner.replay import digest

    assert report["source_fingerprint"] == original["fingerprint"]
    assert report["performance"]["state"] == "unverified"
    assert report["source_authentication"] == "unverified" and report["exit_code"] == 0
    context = dict(report["frozen_context"])
    expected = context.pop("sha256")
    assert digest(context) == expected
    assert context["model_specs"] == original["result"]["replay_context"]["model_specs"]
    assert context["hardware"] == original["result"]["replay_context"]["hardware"]
    assert report["base"]["candidates"] == original["result"]["candidates"]
    registry = context["hardware_registry"]
    assert registry["sha256"] == digest(registry["entries"])
    larger, refused = report["scenarios"]
    assert larger["name"] == "larger" and larger["feasible"]
    assert larger["hardware"]["raw"] == registry["entries"][ALTERNATIVE_HARDWARE]
    assert larger["hardware"]["effective"] == larger["hardware"]["raw"]
    assert larger["hardware_binding"] == {
        "basis": "held-registry",
        "registry_sha256": registry["sha256"],
    }
    assert larger["recommended_configuration"]["hardware"] == ALTERNATIVE_HARDWARE
    assert larger["configuration_switch"]
    timing_classes: Counter[str] = Counter()
    quality_classes: Counter[str] = Counter()
    measured_to_extrapolated = matched_estimated = matched_quality = measured_quality = 0
    quality_scores = set()
    baseline = {
        (row["model"], row["backend"], row["quant"]): row for row in report["base"]["candidates"]
    }
    measured_keys = {key for key, row in baseline.items() if _timing_class(row) == "measured"}
    matched_measured_keys = set()
    for row in larger["candidates"]:
        label = _timing_class(row)
        assert label in {"estimated", "extrapolated", "unknown"}
        timing_classes[label] += 1
        quality_classes[row["provenance"]["quality"]] += 1
        key = (row["model"], row["backend"], row["quant"])
        before = baseline.get(key)
        if before is not None:
            source_timing = _timing_class(before)
            if source_timing == "measured":
                assert label == "extrapolated"
                matched_measured_keys.add(key)
                measured_to_extrapolated += 1
            else:
                assert label == source_timing
                matched_estimated += label == "estimated"
            assert row["provenance"]["quality"] == before["provenance"]["quality"]
            assert all(row[field] == before[field] for field in QUALITY_FIELDS)
            matched_quality += 1
            measured_quality += row["provenance"]["quality"] == "measured"
            quality_scores.add(row["quality"])
    assert matched_quality > 0 and matched_measured_keys == measured_keys
    assert refused["name"] == "no-budget" and not refused["feasible"]
    assert refused["recommended"] is None and refused["trace"]
    return {
        "timing_classes": dict(timing_classes),
        "quality_classes": dict(quality_classes),
        "measured_to_extrapolated": measured_to_extrapolated,
        "matched_estimated_timing": matched_estimated,
        "matched_quality": matched_quality,
        "matched_measured_quality": measured_quality,
        "matched_quality_scores": sorted(quality_scores),
        "unmatched_candidates": len(larger["candidates"]) - matched_quality,
    }


def accept(cwd: Path, env: dict, checkout: Path, saved: Path, bundle: Path) -> dict:
    from ci_installed_acceptance import assert_installed_origin, run_cli
    from chimeraforge import api

    assert_installed_origin(api.__file__, checkout)
    cases = cwd / "sensitivity-cases.json"
    cases.write_text(
        json.dumps(
            [
                {"name": "same", "changes": {}},
                {"name": "half-duty", "changes": {"duty_cycle": 0.5}},
                {"name": "no-budget", "changes": {"budget": 0}},
            ]
        ),
        encoding="utf-8",
    )
    hardware_cases = cwd / "hardware-cases.json"
    hardware_cases.write_text(
        json.dumps(
            [
                {"name": "larger", "changes": {"hardware": ALTERNATIVE_HARDWARE}},
                {
                    "name": "no-budget",
                    "changes": {"hardware": ALTERNATIVE_HARDWARE, "budget": 0},
                },
            ]
        ),
        encoding="utf-8",
    )
    receipts = []
    for index, source in enumerate((saved, bundle)):
        plan_path = source / "plan.json" if source.is_dir() else source
        original_bytes = plan_path.read_bytes()
        output = cwd / f"installed-study-{index}.json"
        report = json.loads(
            run_cli(
                [
                    "study",
                    str(source),
                    "--cases",
                    str(cases),
                    "--out",
                    str(output),
                    "--json",
                ],
                cwd,
                env,
            )
        )
        validate(report, json.loads(original_bytes))
        assert original_bytes == plan_path.read_bytes()
        assert report == json.loads(output.read_text(encoding="utf-8"))
        public = api.study_plan(source, [api.PlanScenario("same", {})]).to_dict()
        assert public["base"]["candidates"] == report["base"]["candidates"]
        hardware_output = cwd / f"installed-hardware-study-{index}.json"
        hardware_report = json.loads(
            run_cli(
                [
                    "study",
                    str(source),
                    "--cases",
                    str(hardware_cases),
                    "--out",
                    str(hardware_output),
                    "--json",
                ],
                cwd,
                env,
            )
        )
        hardware_evidence = validate_hardware(hardware_report, json.loads(original_bytes))
        assert hardware_report == json.loads(hardware_output.read_text(encoding="utf-8"))
        hardware_public = api.study_plan(
            source, [api.PlanScenario("larger", {"hardware": ALTERNATIVE_HARDWARE})]
        ).to_dict()
        assert (
            hardware_public["scenarios"][0]["candidates"]
            == hardware_report["scenarios"][0]["candidates"]
        )
        assert original_bytes == plan_path.read_bytes()
        invalid = json.loads(
            run_cli(
                [
                    "study",
                    str(source),
                    "--cases",
                    str(cases),
                    "--out",
                    str(plan_path),
                    "--json",
                ],
                cwd,
                env,
                2,
            )
        )
        assert invalid["error"] and plan_path.read_bytes() == original_bytes
        receipts.append(
            {
                "source_kind": "bundle" if source.is_dir() else "saved_plan",
                "source_plan_sha256": hashlib.sha256(original_bytes).hexdigest(),
                "fingerprint": report["source_fingerprint"],
                "context_sha256": report["frozen_context"]["sha256"],
                "scenarios": 3,
                "infeasible_retained": True,
                "native_duty_delta": "tokens/month",
                "original_bytes_unchanged": True,
                "installed_cli_and_python": "passed",
                "hardware_alternative": {
                    "canonical_name": ALTERNATIVE_HARDWARE,
                    "hardware": hardware_report["scenarios"][0]["hardware"],
                    "registry_sha256": hardware_report["frozen_context"]["hardware_registry"][
                        "sha256"
                    ],
                    "infeasible_retained": True,
                    "checked_evidence": hardware_evidence,
                },
                "performance": "unverified",
            }
        )
    control = cwd / "registered-hardware-control.json"
    run_cli(
        [
            "plan",
            "--model",
            "llama3.2-3b",
            "--hardware",
            "RTX 4080 12GB",
            "--request-rate",
            "0.1",
            "--latency-slo",
            "10000",
            "--quality-target",
            "0",
            "--budget",
            "100000000",
            "--no-network",
            "--save",
            str(control),
            "--json",
        ],
        cwd,
        env,
    )
    control_bytes = control.read_bytes()
    control_report = json.loads(
        run_cli(["study", str(control), "--cases", str(hardware_cases), "--json"], cwd, env)
    )
    control_evidence = validate_hardware(control_report, json.loads(control_bytes))
    assert control_evidence["measured_to_extrapolated"] > 0
    assert control_evidence["matched_measured_quality"] > 0
    assert control.read_bytes() == control_bytes
    return {
        "offline": True,
        "receipts": receipts,
        "registered_hardware_control": {
            "model": "llama3.2-3b",
            "source_plan_sha256": hashlib.sha256(control_bytes).hexdigest(),
            "checked_evidence": control_evidence,
            "performance": "unverified",
        },
    }
