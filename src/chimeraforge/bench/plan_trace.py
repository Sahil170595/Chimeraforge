"""Replay a frozen saved candidate through the unchanged native scheduled trace."""

from __future__ import annotations

import asyncio
import copy
from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

from chimeraforge.bench.serving_binding import (
    BACKEND_WRAPPERS,
    bind,
    serving_binding,
    serving_stability,
)
from chimeraforge.bench.serving import sanitize_message
from chimeraforge.bench.trace import TraceReplay
from chimeraforge.bench.trace_workload import (
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_TRACE_TIMEOUT_SECONDS,
    MAX_OUTPUT_TOKENS,
    TraceRequest,
    TraceSLO,
    descriptor,
    load_workload,
    validate_options,
)
from chimeraforge.plan_bundle import PlanBundle, ROLE_PATHS, _artifact, _read, verify
from chimeraforge.plan_check import identity
from chimeraforge.planner.replay import digest

if TYPE_CHECKING:
    from chimeraforge.api import PlanArtifact

SLO_INPUTS = {
    "latency_ms": "latency_slo",
    "first_output_ms": "ttft_slo",
    "tpot_ms": "tpot_slo",
}
# Match the existing strict native trace receiver before launching any traffic.
MAX_NATIVE_IDENTITY_CHARS = 512
MAX_NATIVE_ENDPOINT_CHARS = 4096


@dataclass(frozen=True)
class PlanTraceReplay:
    """Defensive wrapper; its native child remains a separate trace receipt."""

    _data: dict
    _protected_paths: tuple[Path, ...] = field(default=(), repr=False)

    def to_dict(self) -> dict:
        return copy.deepcopy(self._data)

    @property
    def native_trace(self) -> TraceReplay:
        return TraceReplay(copy.deepcopy(self._data["native_trace"]), self._protected_paths)

    def save(self, path: str | Path) -> None:
        from chimeraforge.api import PlanArtifact
        from chimeraforge.plan_study import protect_output

        protect_output(path, self._protected_paths)
        PlanArtifact(self.to_dict()).save(path)


@dataclass(frozen=True)
class _PreparedPlanTrace:
    data: dict = field(repr=False)
    candidate: dict = field(repr=False)
    candidate_index: int
    plan_raw_sha256: str | None
    requests: tuple[TraceRequest, ...] = field(repr=False)
    workload: dict
    ordered_descriptors: tuple[dict, ...]
    served_model: str
    model_override: str | None
    backend: str
    base_url: str | None = field(repr=False)
    concurrency: int
    request_timeout: float
    trace_timeout: float
    slos: TraceSLO
    stop_event: asyncio.Event | None = field(repr=False)
    protected_paths: tuple[Path, ...] = field(repr=False)


def _source(
    saved: PlanArtifact | PlanBundle | str | Path,
) -> tuple[dict, str | None, tuple[Path, ...]]:
    from chimeraforge import api

    try:
        if isinstance(saved, api.PlanArtifact):
            return api.artifact_from_dict(saved.to_dict()).to_dict(), None, ()
        bundle = saved if isinstance(saved, PlanBundle) else None
        if bundle is None:
            path = Path(saved).absolute()
            if path.is_dir():
                bundle = verify(path)
            else:
                raw = _read(path, api.MAX_PLAN_BYTES)
                return _artifact(raw).to_dict(), hashlib.sha256(raw).hexdigest(), (path,)
        artifact, _, _ = bundle._prepare()
        # Inventory members are explicit: directory-only protection misses outside hardlinks.
        manifest = json.loads(bundle._manifest_bytes)
        paths = (bundle._directory, bundle._directory / "manifest.json") + tuple(
            bundle._directory / ROLE_PATHS[row["role"]] for row in manifest["files"]
        )
        return artifact.to_dict(), hashlib.sha256(bundle._plan_bytes).hexdigest(), paths
    except (api.PlanError, OSError, ValueError, TypeError, RecursionError):
        raise api.PlanError("invalid saved plan or verified plan bundle") from None


def _prepare(
    saved: PlanArtifact | PlanBundle | str | Path,
    requests: list[TraceRequest] | str | Path,
    *,
    candidate_index: int = 0,
    model: str | None = None,
    base_url: str | None = None,
    concurrency: int = 1,
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    trace_timeout: float = DEFAULT_TRACE_TIMEOUT_SECONDS,
    stop_event: asyncio.Event | None = None,
) -> _PreparedPlanTrace:
    """Hold/validate every input once, before an output guard or endpoint contact."""
    from chimeraforge.api import PlanArtifact, PlanError

    data, raw_sha, paths = _source(saved)
    artifact = PlanArtifact(data)
    artifact.candidate(candidate_index)
    selected = copy.deepcopy(data["result"]["candidates"][candidate_index])
    rows, workload, workload_paths = load_workload(requests)
    cap = selected["decode_tokens_per_req"]
    if type(cap) is not int or not 1 <= cap <= MAX_OUTPUT_TOKENS:
        raise PlanError("selected candidate output length is not a supported trace cap")
    if any(row.max_output_tokens != cap for row in rows):
        raise PlanError("every trace output cap must equal saved candidate decode_tokens_per_req")
    if model is not None and (type(model) is not str or not model.strip()):
        raise PlanError("served model override must be a nonempty name")
    served = (selected["model"] if model is None else model).removeprefix("ollama:")
    backend = BACKEND_WRAPPERS.get(selected["backend"], selected["backend"])
    slos = TraceSLO(**{target: data["inputs"][source] for target, source in SLO_INPUTS.items()})
    validate_options(
        rows, served, backend, concurrency, request_timeout, trace_timeout, slos, base_url
    )
    if len(served) > MAX_NATIVE_IDENTITY_CHARS or len(backend) > MAX_NATIVE_IDENTITY_CHARS:
        raise PlanError("served model and backend exceed the native receipt identity limit")
    if base_url is not None and len(sanitize_message(base_url)) > MAX_NATIVE_ENDPOINT_CHARS:
        raise PlanError("endpoint exceeds the native receipt identity limit")
    if stop_event is not None and not isinstance(stop_event, asyncio.Event):
        raise PlanError("stop_event needs an asyncio.Event")
    return _PreparedPlanTrace(
        data,
        selected,
        candidate_index,
        raw_sha,
        tuple(rows),
        workload,
        tuple(descriptor(row) for row in rows),
        served,
        model,
        backend,
        base_url,
        concurrency,
        request_timeout,
        trace_timeout,
        slos,
        stop_event,
        tuple(dict.fromkeys((*paths, *workload_paths))),
    )


def _bindings(prepared: _PreparedPlanTrace, native: dict) -> dict:
    before, after = native["serving_before"] or {}, native["serving_after"] or {}
    phases = {
        "before": serving_binding(prepared.data, prepared.candidate, before, before),
        "after": serving_binding(prepared.data, prepared.candidate, after, after),
    }
    summary = {}
    for name, prior in phases["before"].items():
        current = phases["after"][name]
        chosen = (
            prior
            if prior["state"] == "mismatch"
            else current
            if current["state"] == "mismatch"
            else prior
            if prior["state"] == "unavailable"
            else current
        )
        summary[name] = copy.deepcopy(chosen)
    summary["serving_stability"] = serving_stability(before, after)
    lengths = {}
    for name, field_name, expected in (
        ("prompt_tokens", "prompt_tokens", prepared.data["inputs"]["prompt_tokens"]),
        ("output_tokens", "tokens_generated", prepared.candidate["decode_tokens_per_req"]),
    ):
        values = [row["native"][field_name] for row in native["requests"]]
        known_mismatch = any(value is not None and value != expected for value in values)
        complete = all(
            row["state"] == "completed" and value is not None
            for row, value in zip(native["requests"], values)
        )
        lengths[name] = bind(
            expected,
            values,
            state="mismatch" if known_mismatch else "matched" if complete else "unavailable",
            source="server-reported actual token counts across the full native population",
            detail="A requested output cap does not guarantee generated length or tokenization.",
        )
    return {**phases, "summary": summary, "token_lengths": lengths}


def _slo(prepared: _PreparedPlanTrace, native: dict, complete: bool) -> dict:
    targets = asdict(prepared.slos)
    outcomes = native["goodput"]["joint_outcomes"]
    state = (
        "not_requested"
        if not any(value is not None for value in targets.values())
        else "breach"
        if outcomes["breach"]
        else "incomplete"
        if not complete
        else "unavailable"
        if outcomes["unknown"] or outcomes["not_completed"]
        else "observed_pass"
    )
    return {
        "state": state,
        "targets": targets,
        "sources": {
            target: {
                "input": source,
                "unit": "ms/token" if target == "tpot_ms" else "ms",
                "source": "saved_request",
            }
            if targets[target] is not None
            else None
            for target, source in SLO_INPUTS.items()
        },
        "interpretation": (
            "Saved explicit targets are native per-request ceilings. Planner p95 latency, "
            "modeled TTFT and native queue-inclusive first output have different bases; "
            "native TPOT is an explicitly named per-request mean, not every-token latency. "
            "Observed target outcomes do not qualify the saved deployment."
        ),
    }


async def _replay_prepared(prepared: _PreparedPlanTrace) -> PlanTraceReplay:
    """Execute only held typed rows; never reread or rewrite the native receipt."""
    from chimeraforge import __version__
    from chimeraforge.api import PlanError
    from chimeraforge.bench import trace
    from chimeraforge.bench.metrics import now_iso
    from chimeraforge.bench.trace_gate_inputs import load_trace

    result = await trace.replay(
        list(prepared.requests),
        model=prepared.served_model,
        backend_name=prepared.backend,
        base_url=prepared.base_url,
        concurrency=prepared.concurrency,
        request_timeout=prepared.request_timeout,
        trace_timeout=prepared.trace_timeout,
        slos=prepared.slos,
        stop_event=prepared.stop_event,
    )
    if type(result) is not TraceReplay:
        raise PlanError("native plan trace receipt is unavailable")
    native = load_trace(result)["data"]
    if (
        native["workload"]
        != {"canonical_sha256": prepared.workload["canonical_sha256"], "raw_sha256": None}
        or [row["descriptor"] for row in native["requests"]] != list(prepared.ordered_descriptors)
        or native["model"] != prepared.served_model
        or native["backend"] != prepared.backend
        or native["targets"] != asdict(prepared.slos)
        or native["execution"]["concurrency"] != prepared.concurrency
        or native["execution"]["request_timeout_seconds"] != prepared.request_timeout
        or native["execution"]["trace_timeout_seconds"] != prepared.trace_timeout
    ):
        raise PlanError("native trace disagrees with held plan workload or applied controls")
    complete = native["exit_code"] == 0 and native["resource_cleanup"].get("state") == "completed"
    bound = _bindings(prepared, native)
    mismatch = any(
        row["state"] == "mismatch"
        for rows in (bound["summary"], bound["token_lengths"])
        for row in rows.values()
    )
    inputs, selected = prepared.data["inputs"], prepared.candidate
    report = {
        "schema_version": 1,
        "kind": "chimeraforge.plan-trace",
        "created_at": now_iso(),
        "tool": {"name": "chimeraforge", "version": __version__},
        "plan": {
            "fingerprint": prepared.data["fingerprint"],
            "raw_sha256": prepared.plan_raw_sha256,
            "candidate_index": prepared.candidate_index,
            "identity": identity(selected),
            "candidate_sha256": digest(selected),
            "candidate": copy.deepcopy(selected),
            "served_model": prepared.served_model,
            "model_override": prepared.model_override,
        },
        "workload": copy.deepcopy(prepared.workload),
        "ordered_descriptors": copy.deepcopy(list(prepared.ordered_descriptors)),
        "controls": {
            "applied": {
                "backend": prepared.backend,
                "model": prepared.served_model,
                "output_cap_tokens": selected["decode_tokens_per_req"],
                "concurrency": prepared.concurrency,
                "request_timeout_seconds": prepared.request_timeout,
                "trace_timeout_seconds": prepared.trace_timeout,
                "targets": asdict(prepared.slos),
                "schedule": "explicit workload arrival_offset_s; no generated arrival process",
            },
            "modeled_unapplied": {
                "context_length": inputs["context_length"],
                "prompt_tokens": inputs["prompt_tokens"],
                "request_rate": inputs["request_rate"],
                "tensor_parallel": selected["tensor_parallel"],
                "pipeline_parallel": selected["pipeline_parallel"],
                "replicas": selected["n_agents"],
                "effective_batch": selected["effective_batch"],
                "prefix_cache_hit_rate": inputs["prefix_cache_hit_rate"],
                "lora_adapters": selected["lora_adapters"],
                "offload_fraction": selected["offload_fraction"],
            },
        },
        "binding": bound,
        "native_trace": native,
        "status": "completed" if complete else "incomplete",
        "configuration_status": "mismatch" if mismatch else "unverified",
        "slo": _slo(prepared, native, complete),
        "exit_code": int(not complete or mismatch),
        "limits": (
            "Only output caps, explicit schedule and client controls are applied. "
            "Serving metadata and actual lengths are observations, not immutable weights, "
            "GPU, fleet, calibration or deployment qualification. Exit 0 means complete "
            "execution without a known binding mismatch, even when observations are unavailable "
            "or a requested SLO is breached. Native timing/deadline/cleanup scope is unchanged."
        ),
    }
    report["fingerprint"] = digest(report)
    return PlanTraceReplay(report, prepared.protected_paths)


async def replay_plan_trace(
    saved: PlanArtifact | PlanBundle | str | Path,
    requests: list[TraceRequest] | str | Path,
    *,
    candidate_index: int = 0,
    model: str | None = None,
    base_url: str | None = None,
    concurrency: int = 1,
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    trace_timeout: float = DEFAULT_TRACE_TIMEOUT_SECONDS,
    stop_event: asyncio.Event | None = None,
) -> PlanTraceReplay:
    """Replay one saved candidate with explicit client controls and honest bindings."""
    prepared = _prepare(
        saved,
        requests,
        candidate_index=candidate_index,
        model=model,
        base_url=base_url,
        concurrency=concurrency,
        request_timeout=request_timeout,
        trace_timeout=trace_timeout,
        stop_event=stop_event,
    )
    return await _replay_prepared(prepared)
