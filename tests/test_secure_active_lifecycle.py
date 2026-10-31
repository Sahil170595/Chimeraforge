"""Native secure stream cancellation must retain every owned child and SDK scope."""

from __future__ import annotations

import asyncio
import logging
import threading

import pytest

from chimeraforge import api
from chimeraforge.bench.backends.vllm import VLLMBackend
from chimeraforge.bench.trace_workload import TraceRequest
from chimeraforge.monitor_connection import MonitorConnection
from test_ci_acceptance import load_script
from test_secure_monitor import certs as certs


@pytest.mark.asyncio
async def test_repeated_trace_cancel_joins_native_generation_cleanup(certs, monkeypatch):
    wire = load_script("ci_secure_active")
    server_release = threading.Event()
    first, closing, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    native = VLLMBackend.generate_observed
    children = []
    cancelled = []
    previous_factory = logging.getLogRecordFactory()

    async def observed(self, model, prompt, options, callback):
        children.append(asyncio.current_task())

        def first_output():
            first.set()
            callback()

        try:
            return await native(self, model, prompt, options, first_output)
        finally:
            closing.set()
            waiter = asyncio.create_task(release.wait())
            children.append(waiter)
            while True:
                try:
                    await asyncio.shield(waiter)
                    break
                except asyncio.CancelledError:
                    cancelled.append(True)
            logging.getLogger("httpcore.future.close").warning("FictionalCleanupSecret82")

    monkeypatch.setattr(VLLMBackend, "generate_observed", observed)
    owner = None
    with wire.server(certs, backend="vllm", release=server_release) as (url, _):
        connection = MonitorConnection(url, ca_bundle=certs["ca"])
        owner = asyncio.create_task(
            api.replay_trace(
                [TraceRequest("one", "fixture", 4, 0)],
                model=wire.MODEL,
                backend="vllm",
                base_url=url,
                connection=connection,
            )
        )
        try:
            await asyncio.wait_for(first.wait(), 5)
            assert owner.cancel()
            await asyncio.wait_for(closing.wait(), 5)
            assert owner.cancel()
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            assert not owner.done(), "trace owner cannot abandon its native generation cleanup"
            release.set()
            server_release.set()
            with pytest.raises(asyncio.CancelledError):
                await owner
            assert all(task.done() for task in children)
            assert logging.getLogRecordFactory() is previous_factory
        finally:
            release.set()
            server_release.set()
            if owner is not None:
                if not owner.done():
                    owner.cancel()
                await asyncio.gather(owner, return_exceptions=True)
            await asyncio.gather(*children, return_exceptions=True)


@pytest.mark.asyncio
async def test_anonymous_plugin_private_attribute_preserves_close_task():
    from chimeraforge.bench.backends.base import backend_lifecycle

    owner = asyncio.current_task()
    closed = []

    class OrdinaryPlugin:
        _connection = object()

        async def close(self):
            assert asyncio.current_task() is owner, (
                "legacy plugin close must keep caller-task ownership"
            )
            closed.append(True)

    async with backend_lifecycle(OrdinaryPlugin()):
        pass
    assert closed == [True]


@pytest.mark.asyncio
async def test_accepted_cancel_has_priority_over_joined_native_close_error(
    certs, monkeypatch, caplog
):
    import httpx
    from chimeraforge.bench.backends.base import backend_lifecycle

    wire = load_script("ci_secure_active")
    closing, release = asyncio.Event(), asyncio.Event()
    native_close = httpx.AsyncClient.aclose
    backend = None

    async def failing_close(client):
        closing.set()
        await release.wait()
        await native_close(client)
        raise OSError("FictionalPrivateClose82")

    async def consume():
        async with backend_lifecycle(backend, _secure=True):
            assert await backend.get_version() == "0.30.0"

    with wire.server(certs, backend="vllm") as (url, _):
        backend = VLLMBackend(url, connection=MonitorConnection(url, ca_bundle=certs["ca"]))
        monkeypatch.setattr(httpx.AsyncClient, "aclose", failing_close)
        owner = asyncio.create_task(consume())
        try:
            await asyncio.wait_for(closing.wait(), 5)
            assert owner.cancel()
            await asyncio.sleep(0)
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await owner
            assert backend._client.is_closed
            assert "FictionalPrivateClose82" not in caplog.text
        finally:
            release.set()
            if not owner.done():
                owner.cancel()
            await asyncio.gather(owner, return_exceptions=True)
            if backend._client is not None:
                await native_close(backend._client)


@pytest.mark.asyncio
async def test_native_trace_never_returns_before_held_generation_finalizer(certs, monkeypatch):
    """Isolate generation ownership; real client close is retained by fixture finally."""
    wire = load_script("ci_secure_active")
    server_release = threading.Event()
    first, closing, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    native_generate, native_close = VLLMBackend.generate_observed, VLLMBackend.close
    generation_tasks, waiters, backends, early_returns, close_entries = [], [], [], [], []
    prior = logging.getLogRecordFactory()
    seen = []
    canary = "FictionalHeldGeneration82"
    owner = None
    observation_seconds = 1

    def factory(*args, **kwargs):
        if args[0] == "httpcore.owned.finalizer":
            seen.append((args[4:], kwargs))
        return prior(*args, **kwargs)

    async def observed(self, model, prompt, options, callback):
        generation_tasks.append(asyncio.current_task())
        backends.append(self)

        def first_output():
            first.set()
            callback()

        try:
            return await native_generate(self, model, prompt, options, first_output)
        finally:
            closing.set()
            waiter = asyncio.create_task(release.wait())
            waiters.append(waiter)
            while not waiter.done():
                try:
                    await asyncio.shield(waiter)
                except asyncio.CancelledError:
                    continue
            logging.getLogger("httpcore.owned.finalizer").warning(canary)

    async def immediate_close(self):
        # Diagnostic barrier only: an actual asynchronous client close cannot mask detachment.
        close_entries.append(True)
        if self not in backends:
            backends.append(self)

    monkeypatch.setattr(VLLMBackend, "generate_observed", observed)
    monkeypatch.setattr(VLLMBackend, "close", immediate_close)
    with wire.server(certs, backend="vllm", release=server_release) as (url, _):
        logging.setLogRecordFactory(factory)
        try:
            owner = asyncio.create_task(
                api.replay_trace(
                    [TraceRequest("one", "fixture", 4, 0)],
                    model=wire.MODEL,
                    backend="vllm",
                    base_url=url,
                    connection=MonitorConnection(url, ca_bundle=certs["ca"]),
                )
            )
            owner.add_done_callback(lambda task: early_returns.append(not release.is_set()))
            await asyncio.wait_for(first.wait(), 5)
            assert owner.cancel()
            await asyncio.wait_for(closing.wait(), 5)
            assert owner.cancel()
            done, _ = await asyncio.wait({owner}, timeout=observation_seconds)
            assert not done and not early_returns, {
                "owner_done": owner.done(),
                "generation_done": [task.done() for task in generation_tasks],
                "close_entries": len(close_entries),
                "early_returns": early_returns,
            }
            assert any(not task.done() for task in generation_tasks)
            release.set()
            server_release.set()
            with pytest.raises(asyncio.CancelledError):
                await owner
            assert all(task.done() for task in generation_tasks + waiters)
            assert seen and canary not in repr(seen)
        finally:
            release.set()
            server_release.set()
            if owner is not None:
                if not owner.done():
                    owner.cancel()
                await asyncio.gather(owner, return_exceptions=True)
            await asyncio.gather(*generation_tasks, *waiters, return_exceptions=True)
            try:
                for backend in backends:
                    await native_close(backend)
                    if backend._client is not None:
                        assert backend._client.is_closed
                        assert backend._client._transport._pool.connections == []
            finally:
                logging.setLogRecordFactory(prior)
