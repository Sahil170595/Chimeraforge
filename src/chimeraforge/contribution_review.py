"""Review and replay unsigned v1 contributions without changing quarantine or trust."""

from __future__ import annotations

import copy
import hashlib
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
import statistics

from chimeraforge import __version__
from chimeraforge.bench.metrics import now_iso, result_to_dict
from chimeraforge.bench.plan import MAX_BENCHMARK_REQUESTS
from chimeraforge.bench.serving import safe_observation, sanitize_message
from chimeraforge.bench.serving_binding import (
    BACKEND_WRAPPERS,
    bind,
    observed_model,
    serving_stability,
)
from chimeraforge.contrib import (
    CONTRIBUTION_KIND,
    FINGERPRINT_FIELDS,
    ContribError,
    quarantine_dir,
    read_json_file,
    verify_contribution,
)
from chimeraforge.planner.hardware import match_driver_name
from chimeraforge.planner.replay import digest, json_value

MISSING_V1_BINDINGS = (
    "original_prompt",
    "generation_options",
    "prompt_and_output_token_counts",
    "concurrency",
    "arrival_rate",
    "serving_configuration",
    "remote_hardware",
    "immutable_model_artifact",
    "original_ttft_basis",
    "authenticated_producer",
)
DISPOSITIONS = {"pending", "retain", "reject"}
log = logging.getLogger(__name__)


def _safe(value):
    if isinstance(value, str):
        return sanitize_message(value)
    if isinstance(value, dict):
        return {key: _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    return value


@dataclass(frozen=True)
class ContributionReceipt:
    """A defensive, fingerprinted review/run receipt; never a contribution import."""

    _data: dict
    _source: Path | None = field(default=None, repr=False)

    @property
    def exit_code(self) -> int:
        return self._data["exit_code"]

    def to_dict(self) -> dict:
        return copy.deepcopy(self._data)

    def check_output(self, path: str | Path) -> None:
        try:
            target, quarantine = Path(path).resolve(), quarantine_dir().resolve()
            if target == self._source or target.is_relative_to(quarantine):
                raise ContribError("receipt cannot overwrite an input or write into quarantine")
            if target.exists():
                try:
                    existing = read_json_file(target)
                except ContribError as exc:
                    log.debug("existing receipt destination is not JSON: %s", type(exc).__name__)
                    existing = None
                if isinstance(existing, dict) and existing.get("kind") == CONTRIBUTION_KIND:
                    raise ContribError("receipt cannot overwrite a contribution")
        except (OSError, RuntimeError) as exc:
            raise ContribError("receipt output path cannot be resolved") from exc

    def save(self, path: str | Path) -> None:
        from chimeraforge.api import PlanArtifact

        self.check_output(path)
        PlanArtifact(self.to_dict()).save(path)


def _load(source: dict | str | Path) -> tuple[dict, Path | None]:
    path = None
    if isinstance(source, dict):
        data = copy.deepcopy(source)
    else:
        if (
            isinstance(source, str)
            and len(source) == 64
            and all(c in "0123456789abcdef" for c in source)
        ):
            path = quarantine_dir() / f"{source}.json"
        else:
            path = Path(source)
        data = read_json_file(path)
        path = path.resolve()
    verify_contribution(data)
    return data, path


def _base(data: dict, *, kind: str) -> dict:
    location = quarantine_dir() / f"{data['id']}.json"
    quarantine_state = "not_present"
    if location.exists():
        try:
            present = read_json_file(location)
            verify_contribution(present)
            quarantine_state = "present" if present["id"] == data["id"] else "unavailable"
        except ContribError as exc:
            log.debug("quarantine membership could not be verified: %s", type(exc).__name__)
            quarantine_state = "unavailable"
    names = {*FINGERPRINT_FIELDS, "model", "backend", "quant", "context_length", "workload"}
    return {
        "kind": kind,
        "schema_version": 1,
        "created_at": now_iso(),
        "tool": {"name": "chimeraforge", "version": __version__},
        "contribution": {
            "id": data["id"],
            "envelope_sha256": digest(data),
            "fingerprint": {
                key: value for key, value in data["fingerprint"].items() if key in names
            },
            "measurements": data["measurements"],
            "flags": data["flags"],
            "attestation": data["attestation"],
            "quarantine_state": quarantine_state,
            "hardware_scope": (
                "original benchmark client host claim; not verified remote serving hardware"
            ),
        },
        "replay_equivalence": {"state": "unverified", "missing": list(MISSING_V1_BINDINGS)},
        "trust": {
            "state": "unsigned_unverified",
            "changes_quarantine": False,
            "changes_corpus": False,
            "authenticates_producer": False,
        },
    }


def _receipt(data: dict, source: Path | None) -> ContributionReceipt:
    data = _safe(json_value(data))
    data["fingerprint"] = digest(data)
    return ContributionReceipt(data, source)


def review(
    source: dict | str | Path, *, decision: str = "pending", reason: str | None = None
) -> ContributionReceipt:
    if decision not in DISPOSITIONS:
        raise ContribError(
            "decision must be pending, retain or reject; no trust promotion is supported"
        )
    if reason is not None and (not isinstance(reason, str) or not reason.strip()):
        raise ContribError("reason must be a nonempty string")
    if decision != "pending" and reason is None:
        raise ContribError("retain/reject dispositions require a reason")
    data, path = _load(source)
    report = _base(data, kind="chimeraforge.contribution-review")
    report.update(
        decision={
            "disposition": decision,
            "reason": reason,
            "changes_quarantine": False,
            "scope": (
                "unsigned reviewer disposition only; "
                "not producer attestation or measurement verification"
            ),
        },
        status="completed",
        exit_code=0,
    )
    return _receipt(report, path)


def _field(expected, before, after, *, source: str, wrapper: bool = False) -> dict:
    known = [item for item in (before, after) if item is not None]
    state = (
        "mismatch"
        if any(item != expected for item in known)
        else "unavailable"
        if len(known) != 2
        else "matched"
    )
    if wrapper and known and all(item == "ollama" for item in known):
        state = "unavailable"
    if expected is None:
        state = "unavailable"
    return bind(
        expected,
        {"before": before, "after": after},
        state=state,
        source=source,
        detail=(
            "Agreement concerns the original declared label; original execution remains unverified."
        ),
    )


def _binding(fp: dict, execution: dict) -> dict:
    before, after = execution.get("serving_before", {}), execution.get("serving_after", {})
    source = "actual before/after serving API observations versus unsigned original declaration"
    result = {
        name: _field(fp[original], before.get(observed), after.get(observed), source=source)
        for name, original, observed in (
            ("quant", "quant", "quant"),
            ("backend_version", "backend_version", "version"),
            ("context_length", "context_length", "context_length"),
        )
    }
    result["backend"] = _field(
        fp["backend"],
        before.get("backend"),
        after.get("backend"),
        source=source,
        wrapper=fp["backend"] == "llama.cpp",
    )
    result["model"] = _field(
        fp["model"].removeprefix("ollama:"),
        observed_model(before.get("model"), fp["model"]),
        observed_model(after.get("model"), fp["model"]),
        source=source,
    )
    result["serving_stability"] = serving_stability(before, after)
    result["workload"] = bind(
        fp["workload"],
        execution.get("request", {}).get("workload"),
        source="declared original profile versus actually applied replay profile",
    )
    return result


def _gpu(fp: dict, execution: dict) -> dict:
    declared = match_driver_name(fp["gpu_name"], fp["gpu_memory_gb"])
    observations = [execution.get(key, {}) for key in ("serving_before", "serving_after")]
    cpu = any(
        item.get("device") == "cpu" or item.get("loaded_gpu_bytes") == 0 for item in observations
    )
    hardware = [item["hardware"] for item in observations if isinstance(item.get("hardware"), dict)]
    names = [item.get("name") for item in hardware]
    cards = [match_driver_name(item.get("name") or "", item.get("vram_gb")) for item in hardware]
    different = declared is not None and any(
        card is not None and card.name != declared.name for card in cards
    )
    wrong_memory = declared is not None and any(
        type(item.get("vram_gb")) in (int, float)
        and item["vram_gb"] > 0
        and item["vram_gb"] != declared.vram_gb
        for item in hardware
    )
    different = different or wrong_memory
    return {
        "state": "ineligible" if cpu or different else "unverified",
        "declared_canonical_gpu": declared.name if declared else None,
        "observed_devices": [item.get("device") for item in observations],
        "observed_hardware_names": names,
        "reason": "Observed CPU/different hardware cannot qualify the declared GPU measurement."
        if cpu or different
        else "Client NVML and GPU placement do not bind original remote hardware or execution.",
    }


def _comparison(original: list, current: list, unit: str) -> dict:
    def mean(samples):
        if not samples or any(
            type(value) not in (int, float) or not math.isfinite(value) or value < 0
            for value in samples
        ):
            return None
        try:
            return statistics.fmean(samples)
        except OverflowError:
            log.debug("contribution replay metric mean overflowed; preserving unknown")
            return None

    old, new = mean(original), mean(current)
    return {
        "original": old,
        "replayed": new,
        "original_count": len(original),
        "replayed_count": len(current),
        "original_samples": original,
        "replayed_samples": current,
        "unit": unit,
        "raw_delta": new - old if new is not None and old is not None else None,
        "delta": None,
        "state": "unverified",
        "interpretation": (
            "Arithmetic difference only; legacy workload/configuration/timing binding is missing."
        ),
    }


async def replay(
    source: dict | str | Path,
    *,
    prompt: str,
    output_tokens: int,
    runs: int = 5,
    model: str | None = None,
    backend: str | None = None,
    base_url: str | None = None,
    workload: str | None = None,
    rate: float | None = None,
    concurrency: int | None = None,
) -> ContributionReceipt:
    from chimeraforge.bench.backends import list_backends
    from chimeraforge.bench.runner import run_benchmark

    data, path = _load(source)
    fp = data["fingerprint"]
    if not isinstance(prompt, str) or not prompt.strip():
        raise ContribError("replay requires an explicit nonempty prompt")
    if type(output_tokens) is not int or output_tokens <= 0:
        raise ContribError(
            "output_tokens must be a positive integer (an applied cap, not observed length)"
        )
    if type(runs) is not int or not 1 <= runs <= MAX_BENCHMARK_REQUESTS:
        raise ContribError(f"runs must be between 1 and {MAX_BENCHMARK_REQUESTS}")
    workload = fp["workload"] if workload is None else workload
    if not isinstance(workload, str) or workload not in {"single", "batch", "server"}:
        raise ContribError("workload must be single, batch or server")
    if concurrency is not None and (type(concurrency) is not int or concurrency <= 0):
        raise ContribError("concurrency must be a positive integer")
    if workload == "single" and concurrency not in (None, 1):
        raise ContribError("single workload applies concurrency 1")
    rate_valid = type(rate) in (int, float) and math.isfinite(rate) and rate > 0
    if workload == "server" and not rate_valid:
        raise ContribError("server replay requires an explicit positive finite arrival rate")
    if rate is not None and (workload != "server" or not rate_valid):
        raise ContribError("rate applies only to server workload and must be positive and finite")
    model = fp["model"] if model is None else model
    backend = BACKEND_WRAPPERS.get(fp["backend"], fp["backend"]) if backend is None else backend
    if not isinstance(model, str) or not model.strip():
        raise ContribError("model must be nonempty")
    if not isinstance(backend, str) or backend not in {row["name"] for row in list_backends()}:
        raise ContribError("backend must name a supported installed adapter")
    report = _base(data, kind="chimeraforge.contribution-replay")
    model = model.removeprefix("ollama:")
    report["requested_execution"] = {
        "model": model,
        "adapter": backend,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "output_token_cap": output_tokens,
        "context_length": fp["context_length"],
        "workload": workload,
        "runs": runs,
        "concurrency": concurrency,
        "arrival_rate": rate,
        "scope": (
            "requested intent; applied workload and observed tokens "
            "are recorded separately in execution/measurement"
        ),
    }
    execution: dict = {}
    measurement = None
    error = None
    try:
        result = await run_benchmark(
            model=model,
            backend_name=backend,
            quant=None,
            workload=workload,
            runs=runs,
            rate=rate,
            concurrency=concurrency,
            context_length=fp["context_length"],
            prompt=prompt,
            base_url=base_url,
            options={"num_predict" if backend == "ollama" else "max_tokens": output_tokens},
            _evidence=execution,
        )
        measurement = result_to_dict(result)
    except RuntimeError as exc:
        log.info("contribution replay execution failed: %s", type(exc).__name__)
        error = {
            "type": type(exc).__name__,
            "reason": "serving preflight or benchmark execution failed",
        }
    for key in ("serving_before", "serving_after"):
        execution[key] = safe_observation(execution.get(key, {}))
    rows = measurement["individual_runs"] if measurement else []
    execution.setdefault("requested_count", runs)
    execution.setdefault("successful_count", 0)
    execution.setdefault("failed_count", 0)
    execution["attempted_count"] = execution["successful_count"] + execution["failed_count"]
    execution["not_started_count"] = runs - execution["attempted_count"]
    execution["endpoint"] = sanitize_message(base_url) if base_url else None
    bound = _binding(fp, execution)
    gpu = _gpu(fp, execution)
    mismatch = (
        any(item["state"] == "mismatch" for item in bound.values()) or gpu["state"] == "ineligible"
    )
    report.update(
        execution=execution,
        measurement=measurement,
        error=error,
        binding=bound,
        gpu_eligibility=gpu,
        comparison={
            "decode_tps": _comparison(
                data["measurements"]["decode_tps"],
                [row["throughput_tps"] for row in rows],
                "tokens/second",
            ),
            "ttft_ms": _comparison(
                data["measurements"]["ttft_ms"], [row["ttft_ms"] for row in rows], "ms"
            ),
        },
        status="failed" if error else "partial" if execution["failed_count"] else "completed",
        exit_code=int(mismatch or error is not None or bool(execution["failed_count"])),
        limits=(
            "Exit 0 means operation completed without known mismatch; "
            "it never means a passed reproduction or trusted measurement."
        ),
    )
    return _receipt(report, path)
