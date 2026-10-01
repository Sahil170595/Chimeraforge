"""Bench adapters refuse a server that answers but does not identify as the engine.

The dev-box case: a generic uvicorn app on :8000 returned 200 on /health, so
`bench --backend vllm` would have benchmarked it and filed the numbers as vLLM.
Each adapter's health_check now requires the engine's own identity response
(read from engine source: vLLM /version, TGI /info, SGLang /server_info, and
Ollama's root banner).
"""

from __future__ import annotations

import httpx
import pytest

from chimeraforge.bench import runner
from chimeraforge.bench.backends import get_backend


def _wired(name: str, handler) -> object:
    backend = get_backend(name, base_url="http://engine.test:9")
    backend._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return backend


def _impostor(req: httpx.Request) -> httpx.Response:
    # Answers health and root probes like any web app; knows nothing of engines.
    if req.url.path in ("/", "/health"):
        return httpx.Response(200, text="OK")
    return httpx.Response(404, text="Not Found")


def _json_impostor(req: httpx.Request) -> httpx.Response:
    # A JSON API that answers every path with 200 but never names an engine.
    return httpx.Response(200, json={"detail": "Forbidden"})


def _refuse(req: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("refused", request=req)


GENUINE = {
    "ollama": lambda req: (
        httpx.Response(200, text="Ollama is running")
        if req.url.path == "/"
        else httpx.Response(200, json={"version": "0.34.4"})
    ),
    "vllm": lambda req: (
        httpx.Response(200, json={"version": "0.30.0"})
        if req.url.path == "/version"
        else httpx.Response(200, text="")
    ),
    "tgi": lambda req: (
        httpx.Response(200, json={"model_id": "org/model", "version": "3.3.7"})
        if req.url.path == "/info"
        else httpx.Response(200, text="")
    ),
    "sglang": lambda req: (
        httpx.Response(200, json={"version": "0.5.20"})
        if req.url.path in ("/server_info", "/get_server_info")
        else httpx.Response(200, text="")
    ),
}
ENGINES = sorted(GENUINE)


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ENGINES)
async def test_genuine_engine_is_accepted(name):
    ok, msg = await _wired(name, GENUINE[name]).health_check()
    assert ok, msg


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ENGINES)
async def test_text_impostor_is_refused(name):
    ok, msg = await _wired(name, _impostor).health_check()
    assert not ok
    assert "did not identify" in msg


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ENGINES)
async def test_json_impostor_is_refused(name):
    ok, msg = await _wired(name, _json_impostor).health_check()
    assert not ok
    assert "did not identify" in msg


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ENGINES)
async def test_nothing_listening_is_not_running(name):
    ok, msg = await _wired(name, _refuse).health_check()
    assert not ok
    assert "not running" in msg


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ENGINES)
async def test_json_impostor_has_no_version(name):
    assert await _wired(name, _json_impostor).get_version() is None


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ENGINES)
async def test_runner_preflight_refuses_impostor(name, monkeypatch):
    backend = _wired(name, _impostor)
    monkeypatch.setattr(runner, "get_backend", lambda *a, **k: backend)
    with pytest.raises(RuntimeError, match="did not identify"):
        await runner.run_benchmark(model="m", backend_name=name, runs=1)
