"""Finite workload/hardware/cost studies against held facts and the shared planner."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, cast

from chimeraforge.plan_check import _local_file, compare, identity
from chimeraforge.plan_bundle import (
    PlanBundle,
    ROLE_PATHS,
    _capture_inputs,
    _quality_equivalent,
    _required,
)
from chimeraforge.planner import engine, hardware, service
from chimeraforge.planner.models import PlannerModels, _models_from_bytes
from chimeraforge.planner.qualityfile import IngestedQuality, _quality_from_bytes, aggregate
from chimeraforge.planner.replay import digest, json_value, policy_digest

if TYPE_CHECKING:
    from chimeraforge.api import PlanArtifact

MAX_SCENARIOS = 16
MAX_STUDY_MODELS = 16
MAX_CASES_BYTES = 64 * 1024
MAX_SCENARIO_NAME = 80
PHYSICAL_HARDWARE_FIELDS = (
    "name",
    "vram_gb",
    "bandwidth_gbps",
    "fp16_tflops",
    "tdp_watts",
    "interconnect_gbps",
    "fp8_supported",
    "vendor",
    "product_line",
    "unified_memory",
    "memory_options_gb",
)
SCENARIO_FIELDS = frozenset(
    {
        "hardware",
        "request_rate",
        "avg_tokens",
        "reasoning_tokens",
        "prompt_tokens",
        "context_length",
        "prefix_cache_hit_rate",
        "workload_cv2",
        "latency_slo",
        "ttft_slo",
        "tpot_slo",
        "quality_target",
        "safety_target",
        "budget",
        "duty_cycle",
        "gpu_price_multiplier",
        "electricity_rate",
        "gpu_cost_per_hour",
    }
)


@dataclass(frozen=True)
class PlanScenario:
    """A named change to supported workload, hardware, targets or cost assumptions."""

    name: str
    changes: dict


@dataclass(frozen=True)
class PlanStudy:
    """Modeled study receipt, never an attestation of serving performance."""

    _data: dict
    _protected_paths: tuple[Path, ...] = field(default=(), repr=False)

    def to_dict(self) -> dict:
        return copy.deepcopy(self._data)

    def save(self, path: str | Path) -> None:
        from chimeraforge.api import PlanArtifact

        protect_output(path, self._protected_paths)
        PlanArtifact(self.to_dict()).save(path)


def protect_output(path: str | Path, inputs: Iterable[str | Path]) -> None:
    from chimeraforge.api import PlanError

    try:
        target = Path(path).resolve()
        for source in inputs:
            original = Path(source).resolve()
            same_file = target.exists() and original.exists() and target.samefile(original)
            if (
                target == original
                or same_file
                or (original.is_dir() and original in target.parents)
            ):
                raise PlanError(
                    "study output cannot replace a source plan, bundle member or case/input file"
                )
    except OSError as exc:
        raise PlanError(f"invalid study output: {exc}") from exc


def _policy_identity(registry: dict[str, hardware.GPUSpec] | None = None) -> str:
    from chimeraforge.planner import advisories, carbon, cloudprice, platform_support

    modules = (advisories, carbon, cloudprice, platform_support)
    extra = {}
    for module in modules:
        rows = {}
        for name, value in vars(module).items():
            if name.isupper():
                try:
                    digest(value)
                except (TypeError, ValueError):
                    continue  # callable policy remains bound to the current tool release
                rows[name] = json_value(value)
        extra[module.__name__] = rows
    return digest(
        {
            "planner": policy_digest(),
            "extra": extra,
            "hardware_registry": hardware.GPU_DB if registry is None else registry,
        }
    )


def _validate_cases(cases: list[PlanScenario], inputs: dict) -> list[PlanScenario]:
    from chimeraforge.api import PlanError, PlanRequest, _finite_input

    if type(cases) is not list or not 1 <= len(cases) <= MAX_SCENARIOS:
        raise PlanError(f"supply between 1 and {MAX_SCENARIOS} scenarios")
    result, names = [], set()
    for case in cases:
        if type(case) is not PlanScenario or type(case.name) is not str or not case.name.strip():
            raise PlanError("each scenario needs a nonempty name and typed changes")
        if len(case.name) > MAX_SCENARIO_NAME or case.name in names:
            raise PlanError("scenario names must be unique and at most 80 characters")
        names.add(case.name)
        if type(case.changes) is not dict or set(case.changes) - SCENARIO_FIELDS:
            raise PlanError("unsupported scenario field; model and platform stay fixed")
        changes = copy.deepcopy(case.changes)
        _finite_input(changes)
        if "hardware" in changes and (inputs["cloud"] is not None or inputs["gpu_overrides"]):
            raise PlanError(
                "hardware scenarios cannot rebind source cloud pricing or gpu_overrides"
            )
        request = {**inputs, **{k: v for k, v in changes.items() if k != "gpu_cost_per_hour"}}
        PlanRequest(**request).validate()
        if "gpu_cost_per_hour" in changes:
            value = changes["gpu_cost_per_hour"]
            if type(value) not in (int, float) or value < 0:
                raise PlanError(
                    "gpu_cost_per_hour must be finite and non-negative; zero means unknown"
                )
            if inputs["cloud"] is not None:
                raise PlanError("gpu_cost_per_hour cannot override cloud instance pricing")
        result.append(PlanScenario(case.name, changes))
    return result


def _source(
    saved: PlanArtifact | PlanBundle | str | Path,
) -> tuple[PlanArtifact, service.ConsumedPlanInputs, dict]:
    from chimeraforge import api

    if isinstance(saved, PlanBundle):
        return cast("tuple[PlanArtifact, service.ConsumedPlanInputs, dict]", saved._prepare())
    if isinstance(saved, api.PlanArtifact):
        artifact = api.artifact_from_dict(saved.to_dict())
    else:
        path = Path(saved)
        if path.is_dir():
            return _source(api.verify_plan_bundle(path))
        artifact = api.load_plan(path)
    data = artifact.to_dict()
    context = data["result"].get("replay_context")
    if context is None:
        raise api.PlanError("study requires a bound replay context; save a new plan")
    corpus: PlannerModels | None = None
    quality: IngestedQuality | None = None
    receipts = {}
    bindings = _required(artifact, allow_contributions=True)
    for role, (raw, source) in _capture_inputs(artifact, allow_contributions=True).items():
        binding = bindings[role]
        if hashlib.sha256(raw).hexdigest() != binding["sha256"]:
            raise api.PlanError(
                f"original {role} bytes changed; use a verified bundle or save a new plan"
            )
        if role == "corpus":
            corpus = _models_from_bytes(source, raw, captured_source=True)
            local = getattr(corpus, "_input_receipt")
            if digest(corpus) != context[role]["sha256"]:
                raise api.PlanError("consumed corpus differs from producing coefficients")
        else:
            quality = _quality_from_bytes(source, raw, captured_source=True)
            local = getattr(quality, "_input_receipt")
            quality_facts = {
                "input": local,
                "scores": json_value(quality),
                "aggregate": json_value(aggregate(quality)),
            }
            if not _quality_equivalent(context[role], quality_facts):
                raise api.PlanError("consumed quality differs from producing scores")
        receipts[role] = {"state": "verified_content", "producer": binding, "local": local}
    if corpus is None:
        raise api.PlanError("study requires the bound coefficient corpus")
    return artifact, service.ConsumedPlanInputs(corpus, quality), receipts


def _freeze(inputs: dict) -> tuple[service.FrozenPlanFacts, dict, dict[str, hardware.GPUSpec]]:
    from chimeraforge.planner.cloudprice import snapshot_age_days
    from chimeraforge.planner.platform_support import staleness_warning

    registry = copy.deepcopy(hardware.GPU_DB)
    today = date.today()
    support = copy.deepcopy(engine.load_engine_support())
    contributions = copy.deepcopy(engine.load_quarantine()) if inputs["use_contributions"] else None
    cloud = copy.deepcopy(engine.load_cloud_prices()) if inputs["cloud"] else None
    stale = engine.cloud_is_stale(today=today, snapshot=cloud) if cloud is not None else None
    grid = service.grid_intensity(inputs["grid_region"], inputs["carbon_intensity"], today=today)
    frozen = service.FrozenPlanFacts(
        engine.FrozenEngineInputs(support, contributions, cloud, stale), grid
    )
    receipt = {
        "as_of_date": today.isoformat(),
        "policy_sha256": _policy_identity(registry),
        "planner_policy_sha256": policy_digest(),
        "policy_scope": (
            "Shared planner tables plus engine/grid/cloud/advisory constants "
            "and one held full hardware registry; live policy must agree before/after each replay."
        ),
        "hardware_registry": {"sha256": digest(registry), "entries": json_value(registry)},
        "engine_support": {
            "sha256": digest(support),
            "captured_at": support["captured_at"],
            "staleness_warning": staleness_warning(today, data=support),
        },
        "cloud": {
            "sha256": digest(cloud),
            "captured_at": cloud["captured_at"],
            "age_days": snapshot_age_days(today, snapshot=cloud),
            "stale": stale,
        }
        if cloud is not None
        else None,
        "grid": json_value(grid),
        "contributions": {
            "enabled": inputs["use_contributions"],
            "records": [{"id": row["id"], "sha256": digest(row)} for row in contributions or []],
            "trust": "quarantined unsigned third-party evidence",
        },
        "dynamic_sources": (
            "Current sources consumed once for this study, not historical producer snapshots."
        ),
    }
    return frozen, receipt, registry


def _hardware_cases(
    cases: list[PlanScenario], registry: dict[str, hardware.GPUSpec]
) -> dict[str, hardware.GPUSpec]:
    from chimeraforge.api import PlanError

    selected: dict[str, hardware.GPUSpec] = {}
    for case in cases:
        if "hardware" not in case.changes:
            continue
        name = case.changes["hardware"].strip().casefold()
        matches = [gpu for key, gpu in registry.items() if key.casefold() == name]
        if not name or name == hardware.AUTO_HARDWARE or len(matches) != 1:
            reason = "ambiguous" if len(matches) > 1 else "unknown or noncanonical"
            raise PlanError(f"{reason} hardware; name one exact GPU registry entry, never auto")
        selected[case.name] = matches[0]
    return selected


def _result(result: service.PlanResult, request: dict) -> dict:
    if result.replay_context is None:
        raise ValueError("study replay did not retain consumed hardware facts")
    candidates = json_value(result.candidates)
    selected = candidates[0] if candidates else None
    return {
        "feasible": bool(candidates),
        "recommended": selected,
        "recommended_configuration": {
            **identity(selected),
            "hardware": result.replay_context["hardware"]["effective"]["name"],
            "hardware_spec_sha256": digest(
                {
                    name: result.replay_context["hardware"]["effective"][name]
                    for name in PHYSICAL_HARDWARE_FIELDS
                }
            ),
            "effective_batch": selected["effective_batch"],
            **{
                name: request[name]
                for name in ("context_length", "kv_quant", "max_num_batched_tokens")
            },
        }
        if selected
        else None,
        "candidates": candidates,
        "trace": json_value(result.trace),
        "hardware": result.replay_context["hardware"],
        "used_contribution_ids": result.replay_context["contributions"]["used_ids"],
    }


def study(
    saved: PlanArtifact | PlanBundle | str | Path, scenarios: list[PlanScenario]
) -> PlanStudy:
    from chimeraforge import api

    try:
        # Case shape/type checks precede source reads; values depend on recorded mode.
        if type(scenarios) is not list or not 1 <= len(scenarios) <= MAX_SCENARIOS:
            raise api.PlanError(f"supply between 1 and {MAX_SCENARIOS} scenarios")
        artifact, consumed, input_receipts = _source(saved)
        data = artifact.to_dict()
        inputs = copy.deepcopy(data["inputs"])
        inputs["allow_network"] = False
        cases = _validate_cases(scenarios, inputs)
        if len(data["result"]["target_models"]) > MAX_STUDY_MODELS:
            raise api.PlanError(f"study supports at most {MAX_STUDY_MODELS} bound model targets")
        context = copy.deepcopy(data["result"]["replay_context"])
        frozen, receipt, registry = _freeze(inputs)
        alternatives = _hardware_cases(cases, registry)
        receipt.update(
            inputs=input_receipts,
            corpus_sha256=digest(consumed.models),
            quality_sha256=digest(consumed.quality) if consumed.quality is not None else None,
            model_specs=context["model_specs"],
            hardware=context["hardware"],
            platform=context["platform"],
            base_inputs=inputs,
            producer_fact_receipts={
                name: context[name]
                for name in ("engine_support", "policy_sha256", "cloud", "contributions", "grid")
            },
            geometry=(
                "Full saved model geometry and platform; base GPU facts remain saved, "
                "explicit alternatives use the held registry's full GPUSpec. "
                "no current host probe or served-weight proof."
            ),
        )

        def run(changes: dict, alternative: hardware.GPUSpec | None = None) -> dict:
            if _policy_identity() != receipt["policy_sha256"]:
                raise api.PlanError("study policy identity changed during execution")
            request = {**inputs, **{k: v for k, v in changes.items() if k != "gpu_cost_per_hour"}}
            bound = copy.deepcopy(context)
            if alternative is not None:
                request["hardware"] = alternative.name
                # Native replay recomputes effective unified memory from these raw facts.
                raw = json_value(alternative)
                bound["hardware"] = {"raw": raw, "effective": copy.deepcopy(raw)}
            if "gpu_cost_per_hour" in changes:
                bound["hardware"]["raw"]["cost_per_hour"] = changes["gpu_cost_per_hour"]
                bound["hardware"]["raw"]["price_basis"] = "operator-assumed-hourly-cost"
            result = service.replay_plan(
                request,
                bound,
                consumed_inputs=copy.deepcopy(consumed),
                frozen_facts=copy.deepcopy(frozen),
            )
            if _policy_identity() != receipt["policy_sha256"]:
                raise api.PlanError("study policy identity changed during execution")
            row = _result(result, request)
            row["hardware_binding"] = {
                "basis": "held-registry" if alternative is not None else "saved-source",
                "registry_sha256": receipt["hardware_registry"]["sha256"]
                if alternative is not None
                else None,
            }
            return row

        base = run({})
        base["comparison_to_saved"] = compare(data["result"]["candidates"], base["candidates"])
        rows = []
        for case in cases:
            row = run(case.changes, alternatives.get(case.name))
            row.update(
                name=case.name,
                changes=case.changes,
                comparison=compare(base["candidates"], row["candidates"]),
            )
            row["configuration_switch"] = (
                base["recommended_configuration"] != row["recommended_configuration"]
            )
            row["price"] = {
                "cost_per_gpu_hour": row["hardware"]["raw"]["cost_per_hour"],
                "basis": row["hardware"]["raw"]["price_basis"],
                "operator_override": "gpu_cost_per_hour" in case.changes,
                "cloud": inputs["cloud"],
                "gpu_price_multiplier": case.changes.get(
                    "gpu_price_multiplier", inputs["gpu_price_multiplier"]
                ),
            }
            rows.append(row)
        receipt["sha256"] = digest(receipt)
        protected = [Path(row["local"]["path"]) for row in input_receipts.values()]
        for row in input_receipts.values():
            if row["producer"]["kind"] == "file":
                producer = _local_file(row["producer"])
                if producer is not None:
                    protected.append(producer)
        if isinstance(saved, PlanBundle):
            directory = saved._directory
            protected.extend(
                [directory, *(directory / name for name in ("manifest.json", *ROLE_PATHS.values()))]
            )
        elif not isinstance(saved, api.PlanArtifact):
            path = Path(saved)
            protected.append(path)
            if path.is_dir():
                protected.extend(path / name for name in ("manifest.json", *ROLE_PATHS.values()))
        return PlanStudy(
            {
                "schema_version": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "source_fingerprint": data["fingerprint"],
                "producer_tool": data["tool"],
                "producer_inputs": data["inputs"],
                "tool": {"name": "chimeraforge", "version": api.__version__},
                "frozen_context": receipt,
                "base": base,
                "scenarios": rows,
                "exit_code": 0,
                "source_authentication": "unverified",
                "performance": {
                    "state": "unverified",
                    "detail": (
                        "Native-unit modeled comparisons, not measured performance "
                        "or sensitivity confidence bounds."
                    ),
                },
            },
            tuple(protected),
        )
    except api.PlanError:
        raise
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        raise api.PlanError(f"invalid planning study: {exc}") from exc


def load_cases(path: str | Path) -> list[PlanScenario]:
    from chimeraforge.api import PlanError, _unique_object
    from chimeraforge.plan_bundle import _read

    try:
        rows = json.loads(
            _read(Path(path).absolute(), MAX_CASES_BYTES), object_pairs_hook=_unique_object
        )
        if type(rows) is not list or any(
            type(row) is not dict or set(row) != {"name", "changes"} for row in rows
        ):
            raise PlanError("cases must be a list of name/changes objects")
        return [PlanScenario(**row) for row in rows]
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        raise PlanError(f"invalid study cases: {exc}") from exc
