"""Replay an explicit workload; client timing never substitutes for server prefill."""

from __future__ import annotations

import asyncio
import copy
from dataclasses import asdict, dataclass, field
import logging
from pathlib import Path
import time
from typing import Any, Awaitable, Callable, Coroutine, TypeVar

from chimeraforge.transport_logging import sdk_logging
from chimeraforge.bench.backends import get_backend
from chimeraforge.bench.backends.base import (
    Backend,
    GenerationObservation,
    backend_lifecycle,
    error_category,
)
from chimeraforge.bench.serving import observe_backend, sanitize_message
from chimeraforge.bench.serving_binding import serving_stability
from chimeraforge.bench.trace_workload import (
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_TRACE_TIMEOUT_SECONDS,
    TraceRequest,
    TraceSLO,
    descriptor,
    load_workload,
    number,
    validate_options,
)
from chimeraforge.planner.replay import digest

from chimeraforge.monitor_connection import MonitorConnection

logger = logging.getLogger(__name__)
_clock = time.perf_counter
T = TypeVar("T")
BUILTIN_TPOT_BASES = {
    "server-decode-duration/output-token-count",
    "client-first-to-last-content/(server-output-count-1)",
    "client-first-to-last-native-output/(server-output-count-1)",
}
NATIVE_FIELDS = {
    "tokens_generated",
    "prompt_tokens",
    "cached_prompt_tokens",
    "throughput_tps",
    "ttft_ms",
    "total_duration_ms",
    "prompt_eval_duration_ms",
    "eval_duration_ms",
}


@dataclass(frozen=True)
class TraceReplay:
    """Complete population receipt with private prompts replaced by hashes."""

    _data: dict
    _protected_paths: tuple[Path, ...] = field(default=(), repr=False)
    _secure_output: bool = field(default=False, repr=False, compare=False)

    def to_dict(self) -> dict:
        return copy.deepcopy(self._data)

    def save(self, path: str | Path) -> None:
        from chimeraforge.api import PlanArtifact, PlanError
        from chimeraforge.plan_study import protect_output

        try:
            protect_output(path, self._protected_paths)
            PlanArtifact(self.to_dict()).save(path)
        except (OSError, PlanError) as exc:
            if not self._secure_output:
                raise
            logger.info("Secure trace output refused (%s)", type(exc).__name__)
            raise PlanError("secure trace output unavailable") from None


def _error(exc: Exception, stage: str) -> dict:
    category = error_category(exc)
    logger.warning("Trace %s failed (%s)", stage, category)
    return {"stage": stage, "type": category}


def _native(observed: GenerationObservation, backend_name: str) -> tuple[dict, float | None, str]:
    if type(observed) is not GenerationObservation or type(observed.native) is not dict:
        raise ValueError("invalid generation observation")
    values = {
        name: value if number(value) else None
        for name in NATIVE_FIELDS
        for value in (observed.native.get(name),)
    }
    for name in ("tokens_generated", "prompt_tokens", "cached_prompt_tokens"):
        if type(values[name]) is not int:
            values[name] = None
    values["ttft_basis"] = (
        observed.native.get("ttft_basis")
        if observed.native.get("ttft_basis")
        in ("server-prefill-duration", "client-stream-first-content")
        else "unknown"
    )
    basis = observed.mean_tpot_basis
    tpot = observed.mean_tpot_ms
    if (
        backend_name not in ("ollama", "vllm", "tgi", "sglang")
        or type(basis) is not str
        or basis not in BUILTIN_TPOT_BASES
    ):
        basis, tpot = "unavailable", None
    elif not number(tpot, positive=True):
        tpot = None
    return values, tpot, basis


def _timing(row: dict) -> dict:
    times = row["times"]

    def difference(end: str, start: str) -> float | None:
        if times[end] is None or times[start] is None or times[end] < times[start]:
            return None
        return (times[end] - times[start]) * 1000

    first = times["first_output_s"]
    first_is_observed = (
        first is not None
        and times["start_s"] is not None
        and times["terminal_s"] is not None
        and times["start_s"] <= first <= times["terminal_s"]
    )
    return {
        "scheduler_lag_ms": difference("arrival_s", "scheduled_s"),
        "client_queue_ms": difference("start_s", "arrival_s"),
        "latency_ms": difference("terminal_s", "scheduled_s"),
        "first_output_ms": difference("first_output_s", "scheduled_s")
        if first_is_observed
        else None,
        "tpot_ms": row["mean_tpot_ms"],
    }


def _qualify(row: dict, targets: dict) -> dict:
    states = {}
    for key, target in targets.items():
        value = row["timing"][key]
        states[key] = (
            "not_requested"
            if target is None
            else "unknown"
            if value is None
            else "pass"
            if value <= target
            else "breach"
        )
    active = [state for state in states.values() if state != "not_requested"]
    states["joint"] = (
        "not_requested"
        if not active
        else "not_completed"
        if row["state"] != "completed"
        else "breach"
        if "breach" in active
        else "unknown"
        if "unknown" in active
        else "pass"
    )
    return states


async def _sleep_until(deadline: float) -> None:
    # Event-loop timers may wake early; observed arrivals must not precede their schedule.
    while (remaining := deadline - _clock()) > 0:
        await asyncio.sleep(remaining)


class _TraceStopped(Exception):
    """Graceful control stop, distinct from an operational probe failure."""


async def _until_stopped(
    call: Callable[[], Awaitable[T]], timeout: float, stopped: asyncio.Event
) -> T:
    if stopped.is_set():
        raise _TraceStopped
    running = asyncio.create_task(call())
    control = asyncio.create_task(stopped.wait())
    try:
        completed, _ = await asyncio.wait(
            (running, control), timeout=timeout, return_when=asyncio.FIRST_COMPLETED
        )
        if control in completed:
            raise _TraceStopped
        if running in completed:
            return await running
        raise asyncio.TimeoutError
    finally:
        for task in (running, control):
            if not task.done():
                task.cancel()
        await asyncio.gather(running, control, return_exceptions=True)


@dataclass
class _TraceOwnership:
    """Managed fleet work and join-only aggregates; cancellation intent is shared."""

    tasks: list[asyncio.Task[Any]] = field(default_factory=list)
    joins: list[asyncio.Future[Any]] = field(default_factory=list)
    cancelled: set[asyncio.Task[Any]] = field(default_factory=set)

    def task(self, operation: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
        task = asyncio.create_task(operation)
        self.tasks.append(task)
        return task

    def cancel(self, task: asyncio.Task[Any]) -> None:
        if not task.done() and task not in self.cancelled:
            self.cancelled.add(task)
            task.cancel()

    def cancel_pending(self) -> None:
        for task in self.tasks:
            self.cancel(task)


async def _owned_generation(
    operation: Callable[[], Coroutine[Any, Any, GenerationObservation]],
    timeout: float,
    ownership: _TraceOwnership,
) -> GenerationObservation:
    task = ownership.task(operation())
    cancelled = False
    error: Exception | None = None
    result: GenerationObservation | None = None
    try:
        done, _ = await asyncio.wait({task}, timeout=timeout)
        if not done:
            raise asyncio.TimeoutError
        result = task.result()
    except asyncio.CancelledError:
        cancelled = True
    except Exception as exc:
        error = exc
    finally:
        ownership.cancel(task)
        joined = asyncio.gather(task, return_exceptions=True)
        ownership.joins.append(joined)
        while True:
            try:
                await asyncio.shield(joined)
                break
            except asyncio.CancelledError:
                cancelled = True
    if cancelled:
        raise asyncio.CancelledError
    if error is not None:
        raise error
    assert result is not None
    return result


async def _execute(
    backend: Backend,
    backend_name: str,
    model: str,
    requests: list[TraceRequest],
    rows: list[dict],
    origin: float,
    concurrency: int,
    request_timeout: float,
    trace_timeout: float,
    stop_event: asyncio.Event,
    *,
    backends: dict[str, Backend] | None = None,
    ownership: _TraceOwnership | None = None,
) -> str | None:
    semaphore = asyncio.Semaphore(concurrency)

    async def one(request: TraceRequest, row: dict) -> None:
        times = row["times"]
        active_generation = False
        try:
            await _sleep_until(origin + request.arrival_offset_s)
            times["arrival_s"] = _clock() - origin
            row["state"] = "queued"
            async with semaphore:
                times["start_s"] = _clock() - origin
                row["state"] = "running"

                def first_output() -> None:
                    observed = _clock() - origin
                    if (
                        active_generation
                        and times["first_output_s"] is None
                        and observed >= times["start_s"]
                        and (times["terminal_s"] is None or observed <= times["terminal_s"])
                    ):
                        times["first_output_s"] = observed

                cap = request.max_output_tokens
                options = {"num_predict": cap} if backend_name == "ollama" else {"max_tokens": cap}
                selected_backend = backends[request.request_id] if backends is not None else backend
                capability = getattr(selected_backend, "generate_observed", None)

                async def generation() -> GenerationObservation:
                    nonlocal active_generation
                    active_generation = True
                    try:
                        if capability is None:
                            metrics = await selected_backend.generate(
                                model, request.prompt, options
                            )
                            return GenerationObservation(asdict(metrics))
                        return await capability(model, request.prompt, options, first_output)
                    finally:
                        active_generation = False

                observed = (
                    await asyncio.wait_for(generation(), request_timeout)
                    if ownership is None
                    else await _owned_generation(generation, request_timeout, ownership)
                )
                native, tpot, basis = _native(observed, backend_name)
                row.update(
                    native=native, mean_tpot_ms=tpot, mean_tpot_basis=basis, state="completed"
                )
        except asyncio.CancelledError:
            if row["state"] != "not_started":
                row["state"] = "cancelled"
            raise
        except Exception as exc:
            row["state"] = "partial" if times["first_output_s"] is not None else "failed"
            row["error"] = _error(exc, "generation")
        finally:
            if row["state"] != "not_started":
                times["terminal_s"] = _clock() - origin

    create = ownership.task if ownership is not None else asyncio.create_task
    tasks = [create(one(request, row)) for request, row in zip(requests, rows)]
    stopped = create(stop_event.wait())
    deadline = create(_sleep_until(origin + trace_timeout))
    finished = asyncio.gather(*tasks)
    if ownership is not None:
        ownership.joins.append(finished)
    try:
        completed, _ = await asyncio.wait(
            (finished, stopped, deadline), return_when=asyncio.FIRST_COMPLETED
        )
        if finished in completed:
            await finished
            return None
        return "cancelled" if stopped in completed else "trace_deadline"
    finally:
        if ownership is None:
            stopped.cancel()
            deadline.cancel()
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(stopped, deadline, *tasks, return_exceptions=True)
            # Retrieve the aggregate exception too; it must not escape as an unowned task.
            await asyncio.gather(finished, return_exceptions=True)


def _initial_rows(requests: list[TraceRequest]) -> list[dict]:
    return [
        {
            "descriptor": descriptor(request),
            "state": "not_started",
            "times": {
                "scheduled_s": request.arrival_offset_s,
                **dict.fromkeys(("arrival_s", "start_s", "first_output_s", "terminal_s")),
            },
            "native": dict.fromkeys(NATIVE_FIELDS),
            "error": None,
            "mean_tpot_ms": None,
            "mean_tpot_basis": "unavailable",
        }
        for request in requests
    ]


def _report(
    requests: list[TraceRequest],
    rows: list[dict],
    *,
    workload: dict,
    targets: TraceSLO,
    model: str,
    backend_name: str,
    base_url: str | None,
    concurrency: int,
    request_timeout: float,
    trace_timeout: float,
    cleanup: dict,
    observation: dict,
    stop_reason: str | None,
    error: dict | None,
    elapsed: float,
    origin: float | None,
) -> dict:
    from chimeraforge import __version__
    from chimeraforge.bench.metrics import now_iso

    for row in rows:
        row["timing"] = _timing(row)
        row["slo"] = _qualify(row, asdict(targets))
        tokens = row["native"]["tokens_generated"]
        row["output_cap_state"] = (
            "unknown"
            if tokens is None
            else "within_cap"
            if tokens <= row["descriptor"]["max_output_tokens"]
            else "exceeded"
        )
    counts = {
        state: sum(row["state"] == state for row in rows)
        for state in ("completed", "failed", "partial", "cancelled", "not_started")
    }
    planned_horizon = max(request.arrival_offset_s for request in requests)
    horizon = max(elapsed, planned_horizon) if origin is not None else None
    qualified = sum(row["slo"]["joint"] == "pass" for row in rows)
    requested_slos = any(value is not None for value in asdict(targets).values())
    report = {
        "schema_version": 1,
        "created_at": now_iso(),
        "tool": {"name": "chimeraforge", "version": __version__},
        "model": model,
        "backend": backend_name,
        "endpoint": sanitize_message(base_url) if base_url else None,
        "workload": workload,
        "requests": rows,
        "targets": asdict(targets),
        "execution": {
            "planned": len(rows),
            "attempted": sum(row["times"]["start_s"] is not None for row in rows),
            **counts,
            "concurrency": concurrency,
            "request_timeout_seconds": request_timeout,
            "trace_timeout_seconds": trace_timeout,
            "elapsed_seconds": elapsed if origin is not None else None,
        },
        "clock": {
            "basis": "client time.perf_counter monotonic offsets in seconds",
            "origin": origin,
            "resolution_seconds": time.get_clock_info("perf_counter").resolution,
        },
        "timing_bases": {
            "latency_ms": "scheduled-arrival-to-client-terminal",
            "first_output_ms": "scheduled-arrival-to-client-first-output",
            "tpot_ms": "per-request explicitly named mean decode basis; not every-token latency",
        },
        "deadline_scope": (
            "scheduled replay only; preflight/metadata separately bounded, cleanup cooperative"
        ),
        "goodput": {
            "qualification": "not_requested"
            if not requested_slos
            else "observed_targets"
            if origin is not None
            else "unavailable",
            "qualified_requests": qualified,
            "horizon_seconds": horizon,
            "planned_horizon_seconds": planned_horizon,
            "horizon_basis": "origin to max(last planned arrival, observed terminal/stop)",
            "joint_outcomes": {
                state: sum(row["slo"]["joint"] == state for row in rows)
                for state in ("pass", "breach", "unknown", "not_completed", "not_requested")
            },
            "requests_per_second": qualified / horizon
            if requested_slos and horizon is not None and horizon > 0
            else None,
        },
        "serving_before": observation.get("before"),
        "serving_after": observation.get("after"),
        "serving_stability": serving_stability(
            observation.get("before") or {}, observation.get("after") or {}
        ),
        "resource_cleanup": cleanup,
        "stop_reason": stop_reason,
        "error": error,
        "exit_code": 0
        if counts["completed"] == len(rows) and error is None and stop_reason is None
        else 1,
        "performance": {
            "state": "observed_client_workload" if origin is not None else "unavailable",
            "gpu_qualification": "unverified",
            "served_file_authentication": "unverified",
        },
        "limits": (
            "Observed client workload, not GPU qualification or served-file authentication; "
            "output caps are requested, means do not prove every-token targets."
        ),
    }
    report["fingerprint"] = digest(report)
    return report


async def replay(
    source: list[TraceRequest] | str | Path,
    *,
    model: str,
    backend_name: str = "ollama",
    base_url: str | None = None,
    concurrency: int = 1,
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    trace_timeout: float = DEFAULT_TRACE_TIMEOUT_SECONDS,
    slos: TraceSLO | None = None,
    stop_event: asyncio.Event | None = None,
    connection: MonitorConnection | None = None,
) -> TraceReplay:
    with sdk_logging(connection is not None):
        from chimeraforge.api import PlanError

        requests, workload, protected = load_workload(source)
        targets = slos if slos is not None else TraceSLO()
        validate_options(
            requests,
            model,
            backend_name,
            concurrency,
            request_timeout,
            trace_timeout,
            targets,
            base_url,
        )
        if stop_event is not None and not isinstance(stop_event, asyncio.Event):
            raise PlanError("stop_event needs an asyncio.Event")
        rows = _initial_rows(requests)
        cleanup, observation = {}, {}
        stopped = stop_event if stop_event is not None else asyncio.Event()
        stop_reason, error, elapsed, origin = None, None, 0.0, None
        stage = "preflight"
        try:
            kwargs = {"base_url": base_url} if base_url else {}
            if connection is not None:
                kwargs["connection"] = connection
            backend = get_backend(backend_name, **kwargs)
        except (ValueError, TypeError) as exc:
            if connection is not None:
                raise PlanError("secure backend configuration is unavailable") from None
            raise PlanError("backend configuration is unavailable") from exc
        try:
            async with backend_lifecycle(
                backend, _cleanup=cleanup, **({"_secure": True} if connection is not None else {})
            ):
                if stopped.is_set():
                    stop_reason = "cancelled"
                else:
                    for probe in (backend.health_check, lambda: backend.check_model(model)):
                        ok, _ = await _until_stopped(probe, request_timeout, stopped)
                        if not ok:
                            raise RuntimeError("preflight refused")
                    stage = "metadata_before"
                    observation["before"] = await _until_stopped(
                        lambda: observe_backend(backend, model), request_timeout, stopped
                    )
                    origin = _clock()
                    stage = "scheduled_replay"
                    ownership = _TraceOwnership() if connection is not None else None
                    try:
                        stop_reason = await _execute(
                            backend,
                            backend_name,
                            model,
                            requests,
                            rows,
                            origin,
                            concurrency,
                            request_timeout,
                            trace_timeout,
                            stopped,
                            **({"ownership": ownership} if ownership is not None else {}),
                        )
                    finally:
                        if ownership is not None:
                            ownership.cancel_pending()
                            joined = asyncio.gather(
                                *ownership.tasks, *ownership.joins, return_exceptions=True
                            )
                            cancelled = False
                            while True:
                                try:
                                    await asyncio.shield(joined)
                                    break
                                except asyncio.CancelledError:
                                    cancelled = True
                            if cancelled:
                                raise asyncio.CancelledError from None
                    elapsed = _clock() - origin
                    if stop_reason is None:
                        stage = "metadata_after"
                        observation["after"] = await _until_stopped(
                            lambda: observe_backend(backend, model), request_timeout, stopped
                        )
        except _TraceStopped:
            stop_reason = "cancelled"
            if cleanup.get("state") == "incomplete":
                error = _error(RuntimeError(), "cleanup")
        except Exception as exc:
            error = _error(exc, "cleanup" if cleanup.get("state") == "incomplete" else stage)
        report = _report(
            requests,
            rows,
            workload=workload,
            targets=targets,
            model=model,
            backend_name=backend_name,
            base_url=base_url,
            cleanup=cleanup,
            concurrency=concurrency,
            request_timeout=request_timeout,
            trace_timeout=trace_timeout,
            observation=observation,
            stop_reason=stop_reason,
            error=error,
            elapsed=elapsed,
            origin=origin,
        )
        if connection is not None:
            protected += connection._input_paths()
        return TraceReplay(report, protected, connection is not None)
