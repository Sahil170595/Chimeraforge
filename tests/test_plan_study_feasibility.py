"""Opt-in requirements preserve every native frozen-context study row."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import date, datetime, timezone

import pytest
from typer.testing import CliRunner

from chimeraforge import api, plan_study
from chimeraforge.cli import app
from chimeraforge.planner import service


@pytest.fixture
def source():
    return api.plan(
        api.PlanRequest(
            models=["llama3.2-3b"],
            allow_network=False,
            request_rate=0.1,
            latency_slo=10000,
            quality_target=0,
            budget=1e8,
            grid_region="USA",
        )
    )


@pytest.fixture
def frozen_clock(monkeypatch):
    class HeldDate(date):
        @classmethod
        def today(cls):
            return date(2026, 11, 14)

    class HeldTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 14, 12, tzinfo=timezone.utc)

    monkeypatch.setattr(plan_study, "date", HeldDate)
    monkeypatch.setattr(plan_study, "datetime", HeldTime)
    monkeypatch.setattr(api, "__version__", "0.101.0")


def scenarios():
    return [
        api.PlanScenario("same", {}),
        api.PlanScenario("half-duty", {"duty_cycle": 0.5}),
        api.PlanScenario("no-budget", {"budget": 0}),
    ]


def test_requirement_passes_when_every_original_row_is_native_feasible(source):
    result = api.study_plan(
        source,
        scenarios()[:2],
        feasibility_policy=api.StudyFeasibilityPolicy(),
    ).to_dict()
    requirement = result["feasibility_requirement"]
    assert result["exit_code"] == requirement["qualification_exit_code"] == 0
    assert requirement["native_study_exit_code"] == 0
    assert requirement["met"] is True
    assert requirement["expected_rows"] == requirement["completed_rows"] == 3
    assert requirement["coverage_complete"] is True
    assert requirement["feasible_rows"] == 3
    assert requirement["rows"] == [
        {"role": "base", "scenario_index": None, "feasible": True},
        {"role": "scenario", "scenario_index": 0, "feasible": True},
        {"role": "scenario", "scenario_index": 1, "feasible": True},
    ]


def test_late_failure_preserves_all_sixteen_scenarios_and_only_one_replay_each(source, monkeypatch):
    original = service.replay_plan
    requests = []

    def replay(request, context, **kwargs):
        requests.append(dict(request))
        return original(request, context, **kwargs)

    monkeypatch.setattr(service, "replay_plan", replay)
    cases = [api.PlanScenario(f"row-{index}", {}) for index in range(15)]
    cases.append(api.PlanScenario("late-no-budget", {"budget": 0}))
    result = api.study_plan(
        source, cases, feasibility_policy=api.StudyFeasibilityPolicy()
    ).to_dict()
    assert len(requests) == 17 and all(row["allow_network"] is False for row in requests)
    assert len(result["scenarios"]) == 16
    assert [row["name"] for row in result["scenarios"]] == [case.name for case in cases]
    assert all(row["feasible"] for row in result["scenarios"][:15])
    assert not result["scenarios"][-1]["feasible"]
    requirement = result["feasibility_requirement"]
    assert result["exit_code"] == requirement["qualification_exit_code"] == 1
    assert requirement["met"] is False
    assert requirement["expected_rows"] == requirement["completed_rows"] == 17
    assert requirement["feasible_rows"] == 16
    assert requirement["rows"][-1] == {"role": "scenario", "scenario_index": 15, "feasible": False}


def test_omitted_none_and_validated_false_are_exact_old_shape_even_with_infeasible_rows(
    source, frozen_clock
):
    default = api.study_plan(source, scenarios()).to_dict()
    none = api.study_plan(source, scenarios(), feasibility_policy=None).to_dict()
    disabled = api.study_plan(
        source, scenarios(), feasibility_policy=api.StudyFeasibilityPolicy(False)
    ).to_dict()
    assert default == none == disabled
    assert "feasibility_requirement" not in default and default["exit_code"] == 0
    assert default["schema_version"] == 1 and not default["scenarios"][-1]["feasible"]


def test_cli_prints_and_saves_complete_unmet_receipt_before_exit_one(tmp_path, source):
    saved, cases, output = tmp_path / "plan.json", tmp_path / "cases.json", tmp_path / "study.json"
    source.save(saved)
    cases.write_text(
        json.dumps([{"name": row.name, "changes": row.changes} for row in scenarios()]),
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        app,
        [
            "study",
            str(saved),
            "--cases",
            str(cases),
            "--out",
            str(output),
            "--require-all-feasible",
            "--json",
        ],
    )
    assert result.exit_code == 1, result.output
    data = json.loads(result.stdout)
    assert data == json.loads(output.read_bytes())
    assert len(data["scenarios"]) == 3 and data["feasibility_requirement"]["met"] is False


def test_true_changes_only_requirement_and_exit_not_any_native_row_or_context(source, frozen_clock):
    default = api.study_plan(source, scenarios()).to_dict()
    required = api.study_plan(
        source, scenarios(), feasibility_policy=api.StudyFeasibilityPolicy()
    ).to_dict()
    qualification = required.pop("feasibility_requirement")
    assert required.pop("exit_code") == 1
    assert default.pop("exit_code") == 0
    assert required == default
    assert qualification["scope"] == "base_and_all_requested_scenarios"
    assert qualification["basis"] == "native_feasible_candidate_exists"
    assert qualification["policy"] == {"require_all_feasible": True}
    assert qualification["infeasible_rows"] == 1


@pytest.mark.parametrize("observed", [1, 3])
def test_projection_keeps_original_expected_coverage_when_observed_population_is_wrong(
    source, observed
):
    native = api.study_plan(source, scenarios()).to_dict()
    requirement = plan_study._feasibility_requirement(
        native["base"], native["scenarios"][:observed], expected_scenarios=2
    )
    assert requirement["expected_rows"] == 3
    assert requirement["completed_rows"] == 1 + observed
    assert requirement["coverage_complete"] is False
    assert requirement["met"] is False and requirement["qualification_exit_code"] == 1


def test_early_failure_never_short_circuits_later_native_scenarios(source, monkeypatch):
    original = service.replay_plan
    budgets = []

    def replay(request, context, **kwargs):
        budgets.append(request["budget"])
        return original(request, context, **kwargs)

    monkeypatch.setattr(service, "replay_plan", replay)
    result = api.study_plan(
        source,
        [api.PlanScenario("first-fails", {"budget": 0}), api.PlanScenario("later-works", {})],
        feasibility_policy=api.StudyFeasibilityPolicy(),
    ).to_dict()
    assert budgets == [1e8, 0, 1e8]
    assert [row["feasible"] for row in result["scenarios"]] == [False, True]
    assert result["exit_code"] == 1 and result["feasibility_requirement"]["completed_rows"] == 3


def test_original_base_is_required_even_when_every_requested_scenario_succeeds():
    saved = api.plan(
        api.PlanRequest(
            models=["llama3.2-3b"],
            allow_network=False,
            request_rate=0.1,
            latency_slo=10000,
            quality_target=0,
            budget=0,
        )
    )
    result = api.study_plan(
        saved,
        [api.PlanScenario("scenario-works", {"budget": 1e8})],
        feasibility_policy=api.StudyFeasibilityPolicy(),
    ).to_dict()
    assert not result["base"]["feasible"] and result["scenarios"][0]["feasible"]
    assert result["exit_code"] == 1
    assert result["feasibility_requirement"]["rows"][0] == {
        "role": "base",
        "scenario_index": None,
        "feasible": False,
    }


def test_unknown_price_remains_native_infeasible_and_preserves_its_reason(source):
    result = api.study_plan(
        source,
        [api.PlanScenario("unknown-price", {"gpu_cost_per_hour": 0})],
        feasibility_policy=api.StudyFeasibilityPolicy(),
    ).to_dict()
    row = result["scenarios"][0]
    assert not row["feasible"] and row["recommended"] is None
    assert any("price" in entry[3] for entry in row["trace"])
    assert row["price"]["cost_per_gpu_hour"] == 0
    assert row["price"]["basis"] == "operator-assumed-hourly-cost"
    assert result["exit_code"] == 1 and result["performance"]["state"] == "unverified"


def test_rejected_alternatives_do_not_fail_a_row_with_native_feasible_candidates(source):
    result = api.study_plan(
        source, [api.PlanScenario("same", {})], feasibility_policy=api.StudyFeasibilityPolicy()
    ).to_dict()
    for row in (result["base"], *result["scenarios"]):
        assert row["candidates"] and row["trace"] and row["feasible"]
        assert any(entry[2] == "format" for entry in row["trace"])
    assert result["exit_code"] == 0 and result["feasibility_requirement"]["met"]


@pytest.mark.parametrize("policy", [True, False, 0, 1, "yes", {}, []])
def test_invalid_policy_types_refuse_before_source_freeze_or_native_work(monkeypatch, policy):
    def forbidden(*args, **kwargs):
        pytest.fail("work started before policy admission")

    monkeypatch.setattr(plan_study, "_source", forbidden)
    monkeypatch.setattr(plan_study, "_freeze", forbidden)
    monkeypatch.setattr(service, "replay_plan", forbidden)
    with pytest.raises(api.PlanError, match="StudyFeasibilityPolicy"):
        api.study_plan(
            "PRIVATE-missing.json", [api.PlanScenario("same", {})], feasibility_policy=policy
        )


@pytest.mark.parametrize("value", [0, 1, 0.0, 1.0, None, "true", {}, []])
def test_policy_field_is_an_exact_boolean_before_any_work(monkeypatch, value):
    def forbidden(*args, **kwargs):
        pytest.fail("work started before policy field admission")

    monkeypatch.setattr(plan_study, "_source", forbidden)
    monkeypatch.setattr(plan_study, "_freeze", forbidden)
    monkeypatch.setattr(service, "replay_plan", forbidden)
    with pytest.raises(api.PlanError, match="boolean"):
        api.study_plan(
            "PRIVATE-missing.json",
            [api.PlanScenario("same", {})],
            feasibility_policy=api.StudyFeasibilityPolicy(value),
        )


def test_policy_is_frozen_exact_type_and_enabled_value_is_snapshotted_once(source, monkeypatch):
    class ForeignPolicy(api.StudyFeasibilityPolicy):
        pass

    with pytest.raises(api.PlanError, match="StudyFeasibilityPolicy"):
        api.study_plan(source, scenarios(), feasibility_policy=ForeignPolicy())
    policy = api.StudyFeasibilityPolicy()
    with pytest.raises(FrozenInstanceError):
        policy.require_all_feasible = False
    original = plan_study._source

    def receive(saved):
        object.__setattr__(policy, "require_all_feasible", False)
        return original(saved)

    monkeypatch.setattr(plan_study, "_source", receive)
    result = api.study_plan(source, scenarios(), feasibility_policy=policy).to_dict()
    assert result["exit_code"] == 1 and result["feasibility_requirement"]["policy"] == {
        "require_all_feasible": True
    }


def test_requirement_does_not_repeat_source_freeze_or_resolve_saved_geometry(source, monkeypatch):
    counts = {"source": 0, "freeze": 0, "replay": 0}
    original_source, original_freeze, original_replay = (
        plan_study._source,
        plan_study._freeze,
        service.replay_plan,
    )

    def receive(*args, **kwargs):
        counts["source"] += 1
        return original_source(*args, **kwargs)

    def freeze(*args, **kwargs):
        counts["freeze"] += 1
        return original_freeze(*args, **kwargs)

    def replay(*args, **kwargs):
        counts["replay"] += 1
        return original_replay(*args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("saved geometry or ordinary plan was resolved again")

    monkeypatch.setattr(plan_study, "_source", receive)
    monkeypatch.setattr(plan_study, "_freeze", freeze)
    monkeypatch.setattr(service, "replay_plan", replay)
    monkeypatch.setattr(api, "plan", forbidden)
    monkeypatch.setattr(service, "resolve_spec", forbidden)
    result = api.study_plan(source, scenarios(), feasibility_policy=api.StudyFeasibilityPolicy())
    assert result.to_dict()["exit_code"] == 1
    assert counts == {"source": 1, "freeze": 1, "replay": 4}


@pytest.mark.parametrize("hardlink", [False, True])
def test_required_sdk_receipt_keeps_source_output_alias_guards(tmp_path, source, hardlink):
    saved = tmp_path / "source.json"
    source.save(saved)
    report = api.study_plan(saved, scenarios(), feasibility_policy=api.StudyFeasibilityPolicy())
    original = saved.read_bytes()
    destination = tmp_path / "alias.json" if hardlink else saved
    if hardlink:
        destination.hardlink_to(saved)
    with pytest.raises(api.PlanError, match="cannot replace"):
        report.save(destination)
    assert saved.read_bytes() == original


@pytest.mark.parametrize("target", ["plan", "cases", "corpus", "quality", "bundle"])
def test_required_cli_does_not_replace_any_known_source_role(tmp_path, target):
    from test_plan_bundle import source_plan

    saved, corpus, quality = source_plan(tmp_path)
    bundle = api.create_plan_bundle(saved, tmp_path / "bundle")
    cases = tmp_path / "cases.json"
    cases.write_text('[{"name":"unmet","changes":{"budget":0}}]', encoding="utf-8")
    paths = {
        "plan": saved,
        "cases": cases,
        "corpus": corpus,
        "quality": quality,
        "bundle": bundle._directory / "corpus.json",
    }
    destination = paths[target]
    before = destination.read_bytes()
    result = CliRunner().invoke(
        app,
        [
            "study",
            str(bundle._directory if target == "bundle" else saved),
            "--cases",
            str(cases),
            "--out",
            str(destination),
            "--require-all-feasible",
            "--json",
        ],
    )
    assert result.exit_code == 2 and "error" in json.loads(result.stdout)
    assert destination.read_bytes() == before


def test_output_failure_stays_invalid_two_before_unmet_one(tmp_path, source, monkeypatch):
    saved, cases, output = tmp_path / "plan.json", tmp_path / "cases.json", tmp_path / "out.json"
    source.save(saved)
    cases.write_text('[{"name":"unmet","changes":{"budget":0}}]', encoding="utf-8")
    observed = []

    def fail(report, path):
        observed.append(report.to_dict()["exit_code"])
        raise api.PlanError("controlled output failure")

    monkeypatch.setattr(api.PlanStudy, "save", fail)
    result = CliRunner().invoke(
        app,
        [
            "study",
            str(saved),
            "--cases",
            str(cases),
            "--out",
            str(output),
            "--require-all-feasible",
            "--json",
        ],
    )
    assert observed == [1] and result.exit_code == 2
    assert json.loads(result.stdout) == {"error": "controlled output failure"}
    assert not output.exists()


@pytest.mark.parametrize("required", [False, True])
def test_completed_plaintext_and_all_feasible_success(tmp_path, source, required):
    saved, cases = tmp_path / "source.json", tmp_path / "cases.json"
    source.save(saved)
    cases.write_text('[{"name":"same","changes":{}}]', encoding="utf-8")
    result = CliRunner().invoke(
        app,
        [
            "study",
            str(saved),
            "--cases",
            str(cases),
            *(["--require-all-feasible"] if required else []),
        ],
    )
    assert result.exit_code == 0 and "same: feasible" in result.stdout
    assert ("All-feasible requirement met: 2/2 original rows." in result.stdout) == required
    assert result.stdout.endswith(
        "Modeled sensitivity; served weights and performance remain unverified.\n"
    )
