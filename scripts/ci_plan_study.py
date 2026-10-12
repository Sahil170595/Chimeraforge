"""Installed offline CLI sensitivity over a saved plan and absent-producer bundle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


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
                "performance": "unverified",
            }
        )
    return {"offline": True, "receipts": receipts}
