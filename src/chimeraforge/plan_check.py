"""Offline saved-plan comparison using the planner's shared search."""

from __future__ import annotations

import copy
from dataclasses import dataclass, fields
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import get_type_hints

from chimeraforge.planner.hardware import GPUSpec
from chimeraforge.planner.replay import REPLAY_VERSION, digest, json_value
from chimeraforge.planner.resolver import ModelSpec

CONTEXT_FIELDS = {
    "version",
    "platform",
    "model_specs",
    "hardware",
    "corpus",
    "quality",
    "grid",
    "engine_support",
    "policy_sha256",
    "cloud",
    "contributions",
}
IDENTITY_FIELDS = (
    "model",
    "quant",
    "backend",
    "tensor_parallel",
    "pipeline_parallel",
    "n_agents",
    "mode",
    "platform",
)
UNITS = {
    "vram_gb": "GiB",
    "monthly_cost": "USD/month",
    "cost_per_1m_tok": "USD/million tokens",
    "throughput_tps": "tokens/second",
    "total_throughput_tps": "tokens/second",
    "p95_latency_ms": "ms",
    "ttft_ms": "ms",
    "tpot_ms": "ms",
    "params_b": "billion parameters",
    "active_params_b": "billion parameters",
    "quality": "score on recorded quality metric",
    "quality_mde": "score on recorded quality metric",
    "cost_per_1m_tok_effective": "USD/million tokens",
    "energy_cost_month": "USD/month",
    "energy_cost_per_1m_tok": "USD/million tokens",
    "tokens_served_month": "tokens/month",
    "reasoning_tokens": "tokens/request",
    "decode_tokens_per_req": "tokens/request",
    "prefill_tokens_effective": "tokens/request",
    "think_time_s": "seconds",
    "session_turns": "turns/session",
    "session_idle_conversations": "conversations",
    "session_capacity_conversations": "conversations",
    "quality_n": "evaluation samples",
    "max_concurrent_seqs": "sequences/GPU",
    "effective_batch": "requests/GPU",
    "tdp_watts": "watts",
    "perf_per_watt": "tokens/second/watt",
    "gpus_total": "GPUs",
    "host_bandwidth_gbps": "GB/second",
    "lora_adapters": "adapters",
    "lora_rank": "rank",
    "lora_gb": "GiB",
    "ttft_slo_ms": "ms",
    "tpot_slo_ms": "ms",
    "co2e_g_per_1m_tok": "gCO2e/million tokens",
    "co2e_kg_month": "kgCO2e/month",
}


def _exact(row, names, label):
    if not isinstance(row, dict) or set(row) != set(names):
        raise ValueError(f"invalid replay {label} fields")


def _sha(value):
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError("invalid replay digest")


def _input_receipt(row):
    if row is None:
        return
    if not isinstance(row, dict):
        raise ValueError("invalid replay input receipt")
    if row.get("kind") == "bundled":
        _exact(row, ("kind", "sha256"), "bundled input")
    else:
        names = ("kind", "path", "sha256")
        if "path_flavor" in row:
            names += ("path_flavor",)
        _exact(row, names, "file input")
        if row["kind"] != "file" or not isinstance(row["path"], str):
            raise ValueError("replay file source must be absolute")
        _path_flavor(row)
    _sha(row["sha256"])


def _path_flavor(receipt: dict) -> str:
    """Validate producer syntax without interpreting it on the checking host."""
    flavor = receipt.get("path_flavor")
    if flavor is None:
        flavor = "windows" if PureWindowsPath(receipt["path"]).is_absolute() else "posix"
    pure = {"windows": PureWindowsPath, "posix": PurePosixPath}.get(flavor)
    if pure is None or not pure(receipt["path"]).is_absolute():
        raise ValueError("replay file source must have a valid absolute path flavor")
    return flavor


def _local_file(receipt: dict) -> Path | None:
    native = "windows" if isinstance(Path(), PureWindowsPath) else "posix"
    return Path(receipt["path"]) if _path_flavor(receipt) == native else None


def _receipt_facts(value):
    if isinstance(value, dict):
        result = {key: _receipt_facts(item) for key, item in value.items()}
        if result.get("kind") == "file" and "path" in result:
            result["path_flavor"] = _path_flavor(result)
        return result
    if isinstance(value, list):
        return [_receipt_facts(item) for item in value]
    return value


def validate_context(context: dict, result: dict, request) -> None:
    """Reject malformed or internally inconsistent bindings even after re-signing."""
    from chimeraforge.api import _check_type
    from chimeraforge.planner.hardware import apply_unified_fraction
    from chimeraforge.planner.evalstats import QualityCell

    _exact(context, CONTEXT_FIELDS, "context")
    if type(context["version"]) is not int or context["version"] != REPLAY_VERSION:
        raise ValueError("unsupported replay context version")
    if context["platform"] != result["platform"]:
        raise ValueError("replay platform must match result")
    specs = context["model_specs"]
    if not isinstance(specs, dict) or set(specs) != set(result["target_models"]):
        raise ValueError("replay must bind every target specification")
    for key, row in specs.items():
        _exact(row, (f.name for f in fields(ModelSpec)), "model specification")
        for name, annotation in get_type_hints(ModelSpec).items():
            _check_type(row[name], annotation, name)
        ModelSpec(**row)
        if any(row[name] <= 0 for name in ("params_b", "n_layers", "n_kv_heads", "d_head")):
            raise ValueError("replay model geometry must be positive")
        canonical = key.split("ollama:", 1)[-1] if row["source"] == "ollama" else key
        if row["name"] not in (key, canonical):
            raise ValueError("replay model identity must match target")
        if key in result["specs"] and row != result["specs"][key]:
            raise ValueError("replay and resolved specification must agree")
    _exact(context["hardware"], ("raw", "effective"), "hardware")
    for row in context["hardware"].values():
        _exact(row, (f.name for f in fields(GPUSpec)), "GPU specification")
        for name, annotation in get_type_hints(GPUSpec).items():
            if name == "memory_options_gb":
                _check_type(row[name], list[float], name)
            else:
                _check_type(row[name], annotation, name)
        if row["vram_gb"] <= 0 or row["bandwidth_gbps"] <= 0:
            raise ValueError("replay GPU capacity must be positive")
    effective, _ = apply_unified_fraction(
        GPUSpec.from_dict(context["hardware"]["raw"]), request.unified_memory_fraction
    )
    if json_value(effective) != context["hardware"]["effective"]:
        raise ValueError("replay effective GPU must apply the stated fraction exactly once")
    _exact(context["corpus"], ("sha256", "input"), "corpus")
    if context["corpus"]["sha256"] != result["corpus_sha256"]:
        raise ValueError("replay corpus digest must agree with result")
    _input_receipt(context["corpus"]["input"])
    _sha(context["policy_sha256"])
    _exact(context["engine_support"], ("sha256", "captured_at"), "engine support")
    _sha(context["engine_support"]["sha256"])
    from datetime import date

    date.fromisoformat(context["engine_support"]["captured_at"])
    if context["quality"] is not None:
        quality = context["quality"]
        _exact(quality, ("input", "scores", "aggregate"), "quality")
        _input_receipt(quality["input"])
        _exact(quality["aggregate"], (f.name for f in fields(QualityCell)), "quality aggregate")
        for name, annotation in get_type_hints(QualityCell).items():
            _check_type(quality["aggregate"][name], annotation, name)
        QualityCell(**quality["aggregate"])
        from chimeraforge.planner.qualityfile import IngestedQuality, aggregate

        scores = quality["scores"]
        _exact(scores, (f.name for f in fields(IngestedQuality)), "quality scores")
        for name, annotation in get_type_hints(IngestedQuality).items():
            if name != "cells":
                _check_type(scores[name], annotation, name)
        if not isinstance(scores["cells"], dict) or not scores["cells"]:
            raise ValueError("replay quality scores must contain consumed cells")
        cells = {}
        for key, cell in scores["cells"].items():
            _check_type(key, str, "quality task")
            _exact(cell, (f.name for f in fields(QualityCell)), "quality cell")
            for name, annotation in get_type_hints(QualityCell).items():
                _check_type(cell[name], annotation, name)
            cells[key] = QualityCell(**cell)
            if not 0 <= cell["score"] <= 1 or cell["n"] <= 0:
                raise ValueError(
                    "replay quality requires a bounded score and positive sample count"
                )
        if set(scores["tasks"]) != set(cells):
            raise ValueError("replay quality tasks must match consumed cells")
        ingested = IngestedQuality(**{**scores, "cells": cells})
        if json_value(aggregate(ingested)) != quality["aggregate"]:
            raise ValueError("replay quality aggregate must match consumed cells")
        if quality["input"] is not None and any(
            cell.source != quality["input"]["path"] for cell in cells.values()
        ):
            raise ValueError("replay quality cells must name the consumed file")
    if (context["quality"] is not None) != bool(request.quality_from):
        raise ValueError("replay quality binding must agree with request")
    if (context["cloud"] is not None) != bool(request.cloud):
        raise ValueError("replay cloud binding must agree with request")
    if context["cloud"] is not None:
        from chimeraforge.planner.cloudprice import CloudOffer

        _exact(context["cloud"], ("cloud", "captured_at", "offers"), "cloud")
        if context["cloud"]["cloud"] != request.cloud:
            raise ValueError("replay cloud identity must agree with request")
        date.fromisoformat(context["cloud"]["captured_at"])
        _check_type(context["cloud"]["offers"], list[dict], "offers")
        for offer in context["cloud"]["offers"]:
            _exact(offer, (f.name for f in fields(CloudOffer)), "cloud offer")
            for name, annotation in get_type_hints(CloudOffer).items():
                _check_type(offer[name], annotation, name)
            if offer["gpus"] <= 0 or offer["price_per_hour"] <= 0:
                raise ValueError("replay cloud capacity and price must be positive")
            if (
                offer["cloud"] != request.cloud
                or offer["gpu"] != context["hardware"]["raw"]["name"]
            ):
                raise ValueError("cloud offer must match bound target")
    contribution = context["contributions"]
    _exact(contribution, ("enabled", "records", "used_ids", "trust"), "contributions")
    if (
        type(contribution["enabled"]) is not bool
        or contribution["enabled"] != request.use_contributions
    ):
        raise ValueError("replay contribution permission must agree with request")
    _check_type(contribution["records"], list[dict], "contribution records")
    _check_type(contribution["used_ids"], list[str], "contribution IDs")
    if contribution["trust"] != "quarantined unsigned third-party evidence":
        raise ValueError("replay cannot upgrade contribution trust")
    if not contribution["enabled"] and (contribution["records"] or contribution["used_ids"]):
        raise ValueError("disabled contributions cannot bind quarantine records")
    for record in contribution["records"]:
        _exact(record, ("id", "sha256"), "contribution record")
        _check_type(record["id"], str, "contribution ID")
        _sha(record["sha256"])
    if not set(contribution["used_ids"]) <= {row["id"] for row in contribution["records"]}:
        raise ValueError("used contributions must belong to consumed quarantine")
    if context["grid"] is not None:
        from chimeraforge.planner.carbon import GridIntensity

        _exact(context["grid"], (f.name for f in fields(GridIntensity)), "grid")
        for name, annotation in get_type_hints(GridIntensity).items():
            _check_type(context["grid"][name], annotation, name)
    if (context["grid"] is not None) != bool(
        request.grid_region is not None or request.carbon_intensity is not None
    ):
        raise ValueError("replay grid binding must agree with request")


@dataclass(frozen=True)
class PlanCheck:
    _data: dict

    def to_dict(self) -> dict:
        return copy.deepcopy(self._data)


def component(before, after, *, required=True, state=None, detail=None):
    return {
        "state": state or ("unchanged" if before == after else "changed"),
        "required": required,
        "before": before,
        "after": after,
        "detail": detail,
    }


def identity(row):
    return {name: row[name] for name in IDENTITY_FIELDS}


def compare(before: list[dict], after: list[dict]) -> dict:
    old = {tuple(identity(row).values()): (i, row) for i, row in enumerate(before)}
    new = {tuple(identity(row).values()): (i, row) for i, row in enumerate(after)}
    matched = []
    for key, (i, row) in old.items():
        if key not in new:
            continue
        j, current = new[key]
        deltas = {}
        for name, value in row.items():
            now = current[name]
            if name in IDENTITY_FIELDS or isinstance(value, bool):
                continue
            if isinstance(value, (int, float)) or isinstance(now, (int, float)) or name in UNITS:
                unknown = value is None or now is None
                deltas[name] = {
                    "before": value,
                    "after": now,
                    "delta": None if unknown else now - value,
                    "unit": UNITS.get(name, "ratio"),
                    "state": "unknown" if unknown else "unchanged" if value == now else "changed",
                }
        matched.append(
            {
                "identity": identity(row),
                "before_rank": i,
                "after_rank": j,
                "deltas": deltas,
                "provenance": component(row["provenance"], current["provenance"]),
            }
        )
    same_order = list(old) == list(new)
    feasibility = (
        "lost" if before and not after else "gained" if after and not before else "unchanged"
    )
    changed = not same_order or any(
        any(delta["state"] == "changed" for delta in row["deltas"].values())
        or row["provenance"]["state"] == "changed"
        for row in matched
    )
    return {
        "added": [identity(row) for key, (_, row) in new.items() if key not in old],
        "removed": [identity(row) for key, (_, row) in old.items() if key not in new],
        "matched": matched,
        "feasibility": feasibility,
        "ordering_changed": not same_order,
        "recommendation_before": identity(before[0]) if before else None,
        "recommendation_after": identity(after[0]) if after else None,
        "changed": changed,
    }


def _resolution(data, context):
    from chimeraforge.planner import resolver

    view = {}
    for key, saved in context["model_specs"].items():
        try:
            current = json_value(
                resolver.resolve_spec(
                    key,
                    allow_network=False,
                    overrides=data["inputs"]["overrides"],
                    ollama_url=data["inputs"]["ollama_url"],
                )
            )
            approximate = current["source"] == resolver.SOURCE_REGISTRY_APPROX
            view[key] = component(
                saved,
                current,
                required=False,
                state="unverified" if approximate else None,
                detail="Local metadata observation; served weights/revision are unverified.",
            )
        except (resolver.ResolverError, OSError, ValueError) as exc:
            view[key] = component(saved, None, required=False, state="unverified", detail=str(exc))
    return view


def _legacy_components(data: dict) -> dict:
    """Inspect still-comparable facts without manufacturing missing replay bindings."""
    from chimeraforge.planner import service
    from chimeraforge.planner import cloudprice

    inputs = data["inputs"]
    rows = {}
    if inputs["models_path"] is None:
        try:
            corpus = service.load_effective_models()
            rows["corpus"] = component(
                data["corpus_sha256"],
                digest(corpus),
                detail=(
                    "Coefficient identity only; original corpus source and geometry are unverified."
                ),
            )
            rows["corpus"]["current_source"] = getattr(corpus, "_input_receipt", None)
        except (ValueError, OSError, TypeError) as exc:
            rows["corpus"] = component(
                data["corpus_sha256"], None, state="unverified", detail=str(exc)
            )
    else:
        rows["corpus"] = component(
            data["corpus_sha256"],
            None,
            state="unverified",
            detail=(
                "Legacy external corpus lacks a consumed source receipt; "
                "its filename is not replayed."
            ),
        )
    rows["quality"] = component(
        None,
        None,
        state="unverified" if inputs["quality_from"] else "not_used",
        detail="Legacy external quality scores and consumed source were not bound.",
    )
    rows["price"] = component(
        None, None, state="unverified", detail="Original GPU price facts were not bound."
    )
    if inputs["cloud"]:
        try:
            snapshot = cloudprice.load_cloud_prices()
            age = cloudprice.snapshot_age_days(snapshot=snapshot)
            rows["cloud"] = component(
                None,
                {"cloud": inputs["cloud"], "captured_at": snapshot["captured_at"]},
                state="expired" if age > cloudprice.STALE_AFTER_DAYS else "unverified",
                detail=(
                    "Current cloud expiry only; original offers and price history were not bound."
                ),
            )
            rows["cloud"]["age_days"] = age
        except (ValueError, OSError, TypeError, KeyError) as exc:
            rows["cloud"] = component(None, None, state="unverified", detail=str(exc))
    else:
        rows["cloud"] = component(None, None, state="not_used")
    return rows


def check(artifact) -> PlanCheck:
    from chimeraforge import api
    from chimeraforge.planner import hardware, service
    from chimeraforge.planner.cloudprice import snapshot_age_days, STALE_AFTER_DAYS

    data = artifact.to_dict()
    context = data["result"].get("replay_context")
    components = {
        "tool": component(data["tool"]["version"], api.__version__),
        "replay_context": component(
            context is not None,
            context is not None,
            state="unchanged" if context is not None else "unverified",
            detail="Bound target geometry; immutable model weights/revisions were not captured.",
        ),
    }
    report = {
        "fingerprint": data["fingerprint"],
        "components": components,
        "comparison": None,
        "resolution_view": {},
        "performance": {
            "state": "unverified",
            "required": False,
            "detail": "A modeled recommendation is not a measured performance guarantee.",
        },
    }
    if context is None:
        components.update(_legacy_components(data))
        known_change = any(row["state"] in ("changed", "expired") for row in components.values())
        report.update(status="changed" if known_change else "unverified", exit_code=1)
        return PlanCheck(report)
    inputs = copy.deepcopy(data["inputs"])
    inputs["allow_network"] = False
    replay = copy.deepcopy(context)
    unavailable = False
    for name, binding, option in (
        ("corpus", context["corpus"]["input"], "models_path"),
        ("quality", (context["quality"] or {}).get("input"), "quality_from"),
    ):
        if binding is not None and binding["kind"] == "file":
            source = _local_file(binding)
            if source is None or not source.is_file():
                components[name] = component(
                    binding,
                    None,
                    state="unverified",
                    detail=(
                        "Original input is unavailable on this host; "
                        "foreign paths are never coerced."
                    ),
                )
                unavailable = True
            else:
                inputs[option] = str(source)
        elif name == "quality" and context["quality"] is not None:
            components[name] = component(
                binding, None, state="unverified", detail="Original quality input was not bound."
            )
            unavailable = True
    raw = replay["hardware"]["raw"]
    current_gpu = hardware.GPU_DB.get(raw["name"])
    if current_gpu is not None and inputs["gpu_overrides"]:
        current_gpu, _ = hardware.resolve_hardware(raw["name"], inputs["gpu_overrides"])
    explicit_price = (inputs["gpu_overrides"] or {}).get("cost_per_hour") is not None
    if current_gpu is not None:
        current = json_value(current_gpu)
        physical_before = {
            key: value for key, value in raw.items() if key not in ("cost_per_hour", "price_basis")
        }
        physical_after = {
            key: value
            for key, value in current.items()
            if key not in ("cost_per_hour", "price_basis")
        }
        # Explicit scenario overrides take precedence over registry metadata.
        for key in inputs["gpu_overrides"] or {}:
            if key in physical_after:
                physical_after[key] = physical_before[key]
        components["hardware"] = component(physical_before, physical_after)
        if not explicit_price and not inputs["cloud"]:
            raw["cost_per_hour"] = current_gpu.cost_per_hour
            raw["price_basis"] = current_gpu.price_basis
    else:
        components["hardware"] = component(
            context["hardware"]["raw"],
            None,
            required=False,
            state="unverified",
            detail="Bound device is absent from current local registry.",
        )
    components["price"] = component(
        {key: context["hardware"]["raw"][key] for key in ("cost_per_hour", "price_basis")},
        {key: raw[key] for key in ("cost_per_hour", "price_basis")},
        required=not bool(inputs["cloud"]),
        state="not_used" if inputs["cloud"] else None,
    )
    report["resolution_view"] = _resolution(data, context)
    if not unavailable:
        try:
            result = service.replay_plan(inputs, replay)
        except (OSError, ValueError, TypeError) as exc:
            components["inputs"] = component(
                None, None, state="unverified", detail=f"Current inputs cannot be consumed: {exc}"
            )
        else:
            now = json_value(result.replay_context)
            for name in (
                "corpus",
                "quality",
                "engine_support",
                "policy_sha256",
                "contributions",
                "grid",
            ):
                components[name] = component(
                    context[name],
                    now[name],
                    state=(
                        "not_used"
                        if context[name] is None and now[name] is None
                        else "unchanged"
                        if _receipt_facts(context[name]) == _receipt_facts(now[name])
                        else "changed"
                    ),
                )
            components["cloud"] = component(
                context["cloud"],
                now["cloud"],
                state="not_used" if context["cloud"] is None else None,
            )
            if now["cloud"] is not None:
                age = snapshot_age_days(snapshot=now["cloud"])
                components["cloud"]["age_days"] = age
                if age > STALE_AFTER_DAYS:
                    components["cloud"]["state"] = "expired"
            report["comparison"] = compare(
                data["result"]["candidates"], json_value(result.candidates)
            )
            report["comparison"]["trace_before"] = data["result"]["trace"]
            report["comparison"]["trace_after"] = json_value(result.trace)
    failed = any(
        row["required"] and row["state"] in ("changed", "expired", "unverified")
        for row in components.values()
    )
    changed = any(row["state"] == "changed" for row in report["resolution_view"].values())
    changed = changed or bool(report["comparison"] and report["comparison"]["changed"])
    report.update(
        exit_code=int(failed or changed),
        status="changed"
        if changed or any(row["state"] in ("changed", "expired") for row in components.values())
        else "unverified"
        if failed
        else "unchanged",
    )
    return PlanCheck(report)
