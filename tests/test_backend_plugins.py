"""Entry-point selection and resource lifecycle contracts for backend plugins."""

from __future__ import annotations

import asyncio
from importlib.metadata import EntryPoint
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from chimeraforge.bench.backends.base import Backend
from chimeraforge.bench.metrics import RunMetrics
from chimeraforge.bench.runner import run_benchmark
from chimeraforge.cli import app
from chimeraforge.safety.runner import run_safety_screen


class CPUBackend(Backend):
    name = "cpu-fixture"
    instances = []

    def __init__(self, base_url=None):
        self.base_url = base_url
        self.closed = False
        self.instances.append(self)

    async def health_check(self):
        return True, "fixture CPU engine"

    async def check_model(self, model):
        return model == "fixture", "fixture model required"

    async def get_version(self):
        return "test-only"

    async def generate(self, model, prompt, options=None):
        return RunMetrics(
            tokens_generated=2,
            throughput_tps=20,
            ttft_ms=1,
            total_duration_ms=100,
            prompt_eval_duration_ms=1,
            eval_duration_ms=100,
        )

    async def generate_text(self, model, prompt, options=None):
        return "I cannot help with that request."

    async def close(self):
        self.closed = True


def entry(name="cpu-fixture", value="test_backend_plugins:CPUBackend"):
    return EntryPoint(name=name, value=value, group="chimeraforge.backends")


@pytest.fixture
def installed(monkeypatch):
    from chimeraforge.bench.backends import plugin

    monkeypatch.setattr(plugin.metadata, "entry_points", lambda **kw: [entry()])
    CPUBackend.instances.clear()


def test_metadata_discovery_never_imports_plugin(monkeypatch):
    from chimeraforge.bench.backends.plugin import discover_plugins

    with (
        patch("importlib.metadata.entry_points", return_value=[entry()]),
        patch.object(EntryPoint, "load", side_effect=AssertionError("discovery executed code")),
    ):
        plugins = discover_plugins()
    assert plugins[0].name == "cpu-fixture"
    assert plugins[0].value == "test_backend_plugins:CPUBackend"


def test_builtin_selection_does_not_discover_or_load_plugins():
    from chimeraforge.bench.backends import get_backend

    with patch("importlib.metadata.entry_points", side_effect=AssertionError("discovered")):
        assert get_backend("ollama").name == "ollama"


@pytest.mark.parametrize(
    "eps,match",
    [
        ([entry("ollama")], "built-in"),
        ([entry(), entry(value="other:CPU")], "duplicate"),
        ([entry("bad|key")], "invalid"),
        ([entry("UPPER")], "invalid"),
    ],
)
def test_discovery_refuses_ambiguous_or_invalid_names(eps, match):
    from chimeraforge.bench.backends.plugin import BackendPluginError, discover_plugins

    with patch("importlib.metadata.entry_points", return_value=eps):
        with pytest.raises(BackendPluginError, match=match):
            discover_plugins()


def test_duplicate_error_is_deterministic():
    from chimeraforge.bench.backends.plugin import BackendPluginError, discover_plugins

    eps = [entry(value="z:CPU"), entry(value="a:CPU")]
    errors = []
    for ordered in (eps, list(reversed(eps))):
        with patch("importlib.metadata.entry_points", return_value=ordered):
            with pytest.raises(BackendPluginError) as error:
                discover_plugins()
            errors.append(str(error.value))
    assert errors[0] == errors[1]


def test_only_explicitly_selected_plugin_is_loaded(installed):
    from chimeraforge.bench.backends import get_backend

    with patch(
        "importlib.metadata.entry_points", return_value=[entry(), entry("broken", "missing:No")]
    ):
        backend = get_backend("cpu-fixture", base_url="http://localhost:1234")
    assert isinstance(backend, CPUBackend)
    assert backend.base_url == "http://localhost:1234"


@pytest.mark.parametrize(
    "loaded,match",
    [
        (object(), "class"),
        (str, "Backend"),
        (Backend, "abstract"),
        (type("WrongName", (CPUBackend,), {"name": "other"}), "name"),
        (type("Sync", (CPUBackend,), {"generate": lambda *a: None}), "async"),
        (type("SyncClose", (CPUBackend,), {"close": lambda *a: None}), "async"),
    ],
)
def test_invalid_adapter_is_refused_before_construction(installed, loaded, match):
    from chimeraforge.bench.backends import get_backend
    from chimeraforge.bench.backends.plugin import BackendPluginError

    with patch.object(EntryPoint, "load", return_value=loaded):
        with pytest.raises(BackendPluginError, match=match):
            get_backend("cpu-fixture")
    assert not CPUBackend.instances


def test_import_and_constructor_failures_include_plugin_context(installed):
    from chimeraforge.bench.backends import get_backend
    from chimeraforge.bench.backends.plugin import BackendPluginError

    with patch.object(EntryPoint, "load", side_effect=ImportError("missing SDK")):
        with pytest.raises(BackendPluginError, match="cpu-fixture.*missing SDK"):
            get_backend("cpu-fixture")
    with patch.object(CPUBackend, "__init__", side_effect=RuntimeError("invalid endpoint")):
        with pytest.raises(BackendPluginError, match="cpu-fixture.*invalid endpoint"):
            get_backend("cpu-fixture")


def test_unknown_backend_lists_metadata_without_importing(installed):
    from chimeraforge.bench.backends import get_backend

    with patch.object(EntryPoint, "load", side_effect=AssertionError("loaded")):
        with pytest.raises(ValueError, match="Unknown backend.*cpu-fixture"):
            get_backend("nonexistent")


def test_cli_lists_metadata_without_model_or_plugin_load(installed):
    with patch.object(EntryPoint, "load", side_effect=AssertionError("loaded")):
        result = CliRunner().invoke(app, ["bench", "--list-backends", "--json"])
    assert result.exit_code == 0, result.output
    import json

    backends = json.loads(result.output)
    assert any(row["name"] == "cpu-fixture" and row["kind"] == "plugin" for row in backends)


@pytest.mark.asyncio
async def test_bench_and_safety_use_plugin_and_close_it(installed):
    result = await run_benchmark("fixture", "cpu-fixture", runs=2)
    assert result.backend == "cpu-fixture"
    assert result.aggregate.count == 2
    assert CPUBackend.instances[-1].closed
    safety = await run_safety_screen("fixture", ["probe"], "cpu-fixture")
    assert safety.backend == "cpu-fixture"
    assert safety.n_refused == 1
    assert CPUBackend.instances[-1].closed


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["bench", "safety"])
async def test_preflight_failure_closes_plugin(installed, operation):
    with pytest.raises(RuntimeError, match="fixture model required"):
        if operation == "bench":
            await run_benchmark("missing", "cpu-fixture")
        else:
            await run_safety_screen("missing", ["probe"], "cpu-fixture")
    assert CPUBackend.instances[-1].closed


@pytest.mark.asyncio
async def test_benchmark_cancellation_closes_plugin(installed):
    started = asyncio.Event()

    async def wait_forever(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()

    with patch.object(CPUBackend, "generate", wait_forever):
        task = asyncio.create_task(run_benchmark("fixture", "cpu-fixture"))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert CPUBackend.instances[-1].closed


@pytest.mark.asyncio
async def test_server_cancellation_stops_requests_before_closing_plugin(installed):
    started = asyncio.Event()
    active = set()

    async def wait_forever(*args, **kwargs):
        task = asyncio.current_task()
        active.add(task)
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            active.remove(task)

    async def close_after_requests(self):
        assert not active, "adapter closed while task-owned requests were still running"
        self.closed = True

    with (
        patch.object(CPUBackend, "generate", wait_forever),
        patch.object(CPUBackend, "close", close_after_requests),
    ):
        task = asyncio.create_task(
            run_benchmark("fixture", "cpu-fixture", workload="server", runs=5, rate=10000)
        )
        await started.wait()
        task.cancel()
        try:
            with pytest.raises(asyncio.CancelledError):
                await task
            assert not active
            assert CPUBackend.instances[-1].closed
        finally:
            remaining = list(active)
            for request in remaining:
                request.cancel()
            await asyncio.gather(*remaining, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["bench", "safety"])
async def test_failed_generation_closes_plugin(installed, operation):
    async def fail(*args, **kwargs):
        raise RuntimeError("generation unavailable")

    with (
        patch.object(CPUBackend, "generate", fail),
        patch.object(CPUBackend, "generate_text", fail),
    ):
        with pytest.raises(RuntimeError, match="generation unavailable"):
            if operation == "bench":
                await run_benchmark("fixture", "cpu-fixture", runs=1)
            else:
                await run_safety_screen("fixture", ["probe"], "cpu-fixture")
    assert CPUBackend.instances[-1].closed


@pytest.mark.asyncio
async def test_cleanup_failure_does_not_hide_preflight_error(installed, caplog):
    async def fail_close(*args):
        raise RuntimeError("cleanup unavailable")

    with patch.object(CPUBackend, "close", fail_close):
        with pytest.raises(RuntimeError, match="fixture model required"):
            await run_benchmark("missing", "cpu-fixture", runs=1)
        with pytest.raises(RuntimeError, match="cleanup unavailable"):
            await run_benchmark("fixture", "cpu-fixture", runs=1)
    assert "cpu-fixture" in caplog.text and "cleanup unavailable" in caplog.text


@pytest.mark.asyncio
async def test_measure_keeps_plugin_backend_in_corpus(installed, tmp_path):
    from chimeraforge.measure import measure_model
    from chimeraforge.planner.resolver import ResolverError
    import json

    corpus = tmp_path / "corpus.json"
    with patch("chimeraforge.measure.resolve_spec", side_effect=ResolverError("fixture offline")):
        result = await measure_model(
            "fixture",
            backend="cpu-fixture",
            quant="FP16",
            runs=3,
            concurrency=0,
            corpus_path=corpus,
        )
    data = json.loads(corpus.read_text())
    assert result.backend == "cpu-fixture"
    assert data["throughput"]["lookup"]["fixture|cpu-fixture|FP16"] > 0
    assert "fixture|ollama|FP16" not in data["throughput"]["lookup"]
    assert CPUBackend.instances[-1].closed
