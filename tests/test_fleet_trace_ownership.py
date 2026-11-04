"""Managed native trace workers keep real generation leases until children join."""

import asyncio

import pytest

from chimeraforge.bench import trace
from chimeraforge.bench.backends.base import Backend, GenerationObservation
from chimeraforge.bench.trace_workload import TraceRequest, descriptor


class HeldBackend(Backend):
    name = "ollama"

    def __init__(self, *, hold=False):
        self.hold = hold
        self.calls = 0
        self.active = 0
        self.entered = asyncio.Event()
        self.closing = asyncio.Event()
        self.release = asyncio.Event()

    async def health_check(self):
        return True, ""

    async def check_model(self, model):
        return True, ""

    async def get_version(self):
        return "controlled"

    async def generate(self, model, prompt, options=None):
        raise AssertionError("observed path required")

    async def generate_observed(self, model, prompt, options, on_first_output):
        self.calls += 1
        self.active += 1
        self.entered.set()
        try:
            if self.hold:
                await asyncio.Event().wait()
            return GenerationObservation(
                {"tokens_generated": 4, "eval_duration_ms": 4},
                1,
                "server-decode-duration/output-token-count",
            )
        finally:
            if self.hold:
                self.closing.set()
                await self.release.wait()
            self.active -= 1


def initial(requests):
    return [
        {
            "descriptor": descriptor(request),
            "state": "not_started",
            "times": {
                "scheduled_s": 0,
                "arrival_s": None,
                "start_s": None,
                "first_output_s": None,
                "terminal_s": None,
            },
            "native": dict.fromkeys(trace.NATIVE_FIELDS),
            "error": None,
            "mean_tpot_ms": None,
            "mean_tpot_basis": "unavailable",
        }
        for request in requests
    ]


@pytest.mark.asyncio
async def test_request_timeout_keeps_global_lease_while_child_is_still_closing():
    ownership = trace._TraceOwnership()
    first, second = HeldBackend(hold=True), HeldBackend()
    requests = [TraceRequest(f"r{i}", "controlled", 4, 0) for i in range(2)]
    rows = initial(requests)
    task = ownership.task(
        trace._execute(
            first,
            "ollama",
            "served",
            requests,
            rows,
            trace._clock(),
            1,
            0.01,
            5,
            asyncio.Event(),
            backends={"r0": first, "r1": second},
            ownership=ownership,
        )
    )
    try:
        await asyncio.wait_for(first.closing.wait(), 5)
        assert first.active == 1 and second.calls == 0
        first.release.set()
        assert await task is None
        assert second.calls == 1 and rows[0]["state"] == "failed"
    finally:
        first.release.set()
        ownership.cancel_pending()
        await asyncio.gather(*ownership.tasks, *ownership.joins, return_exceptions=True)
    assert first.active == second.active == 0


@pytest.mark.asyncio
async def test_managed_deadline_returns_before_private_drain_then_owned_join_finishes():
    ownership = trace._TraceOwnership()
    backend = HeldBackend(hold=True)
    requests = [TraceRequest("r0", "controlled", 4, 0)]
    rows = initial(requests)
    task = ownership.task(
        trace._execute(
            backend,
            "ollama",
            "served",
            requests,
            rows,
            trace._clock(),
            1,
            5,
            0.01,
            asyncio.Event(),
            ownership=ownership,
        )
    )
    try:
        await asyncio.wait_for(backend.entered.wait(), 5)
        assert await asyncio.wait_for(asyncio.shield(task), 5) == "trace_deadline"
        assert backend.active == 1 and not backend.closing.is_set()
        ownership.cancel_pending()
        await asyncio.wait_for(backend.closing.wait(), 5)
        # A repeated final sweep cannot re-cancel and abandon held child cleanup.
        ownership.cancel_pending()
        await asyncio.sleep(0)
        assert backend.active == 1
    finally:
        backend.release.set()
        ownership.cancel_pending()
        await asyncio.gather(*ownership.tasks, *ownership.joins, return_exceptions=True)
    assert backend.active == 0 and rows[0]["state"] == "cancelled"
