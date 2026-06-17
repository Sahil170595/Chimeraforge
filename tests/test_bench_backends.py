"""Tests for bench backend registry, Ollama, vLLM, TGI adapters, and edge cases."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chimeraforge.bench.backends import BACKEND_REGISTRY, get_backend
from chimeraforge.bench.backends.ollama import OllamaBackend
from chimeraforge.bench.backends.tgi import TGIBackend
from chimeraforge.bench.backends.vllm import VLLMBackend


# -- Backend registry --------------------------------------------------------


class TestBackendRegistry:
    def test_registry_has_all_backends(self):
        assert "ollama" in BACKEND_REGISTRY
        assert "vllm" in BACKEND_REGISTRY
        assert "tgi" in BACKEND_REGISTRY

    def test_get_backend_ollama(self):
        b = get_backend("ollama")
        assert isinstance(b, OllamaBackend)
        assert b.name == "ollama"

    def test_get_backend_with_url(self):
        b = get_backend("ollama", base_url="http://localhost:9999")
        assert b.base_url == "http://localhost:9999"

    def test_get_backend_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown backend"):
            get_backend("nonexistent")


# -- Ollama backend (mocked HTTP) -------------------------------------------


class TestOllamaBackend:
    @pytest.fixture
    def backend(self) -> OllamaBackend:
        return OllamaBackend(base_url="http://localhost:11434")

    def test_name(self, backend):
        assert backend.name == "ollama"

    @pytest.mark.asyncio
    async def test_health_check_success(self, backend):
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("chimeraforge.bench.backends.ollama.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ok, msg = await backend.health_check()
            assert ok is True

    @pytest.mark.asyncio
    async def test_health_check_connection_refused(self, backend):
        import httpx

        with patch("chimeraforge.bench.backends.ollama.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ok, msg = await backend.health_check()
            assert ok is False
            assert "not running" in msg

    @pytest.mark.asyncio
    async def test_check_model_success(self, backend):
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("chimeraforge.bench.backends.ollama.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ok, msg = await backend.check_model("llama3.2-3b")
            assert ok is True

    @pytest.mark.asyncio
    async def test_check_model_not_found(self, backend):
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("chimeraforge.bench.backends.ollama.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ok, msg = await backend.check_model("nonexistent")
            assert ok is False
            assert "ollama pull" in msg

    @pytest.mark.asyncio
    async def test_generate_extracts_metrics(self, backend):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Neural networks are...",
            "eval_count": 50,
            "eval_duration": 2_000_000_000,  # 2s in ns
            "prompt_eval_duration": 100_000_000,  # 100ms in ns
            "total_duration": 2_500_000_000,  # 2.5s in ns
        }
        mock_response.raise_for_status = MagicMock()

        with patch("chimeraforge.bench.backends.ollama.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            metrics = await backend.generate("test-model", "Hello")

        assert metrics.tokens_generated == 50
        assert metrics.throughput_tps == pytest.approx(25.0, rel=0.01)
        assert metrics.ttft_ms == pytest.approx(100.0, rel=0.01)
        assert metrics.total_duration_ms == pytest.approx(2500.0, rel=0.01)
        assert metrics.eval_duration_ms == pytest.approx(2000.0, rel=0.01)

    @pytest.mark.asyncio
    async def test_get_version_success(self, backend):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"version": "0.6.2"}

        with patch("chimeraforge.bench.backends.ollama.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            version = await backend.get_version()
            assert version == "0.6.2"

    @pytest.mark.asyncio
    async def test_get_version_failure(self, backend):
        import httpx

        with patch("chimeraforge.bench.backends.ollama.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            version = await backend.get_version()
            assert version is None


# -- VLLMBackend basic -------------------------------------------------------


class TestVLLMBackend:
    def test_name(self):
        b = VLLMBackend()
        assert b.name == "vllm"

    def test_default_url(self):
        b = VLLMBackend()
        assert b.base_url == "http://localhost:8000"

    def test_custom_url(self):
        b = VLLMBackend(base_url="http://gpu-server:9000/")
        assert b.base_url == "http://gpu-server:9000"


# -- TGIBackend basic --------------------------------------------------------


class TestTGIBackend:
    def test_name(self):
        b = TGIBackend()
        assert b.name == "tgi"

    def test_default_url(self):
        b = TGIBackend()
        assert b.base_url == "http://localhost:8080"

    @pytest.mark.asyncio
    async def test_check_model_exact_match(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"model_id": "meta-llama/Llama-3.2-3B"}

        b = TGIBackend()
        with patch("chimeraforge.bench.backends.tgi.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client
            # Bypass client caching for this test
            b._client = mock_client

            ok, _ = await b.check_model("meta-llama/Llama-3.2-3B")
            assert ok is True

    @pytest.mark.asyncio
    async def test_check_model_rejects_substring(self):
        """Single char should not match via loose substring."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"model_id": "meta-llama/Llama-3.2-3B"}

        b = TGIBackend()
        with patch("chimeraforge.bench.backends.tgi.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client
            b._client = mock_client

            ok, _ = await b.check_model("a")
            assert ok is False


# -- Ollama eval_duration=0 edge case ----------------------------------------


class TestOllamaEdgeCases:
    @pytest.mark.asyncio
    async def test_missing_eval_duration_returns_zero_throughput(self):
        """eval_duration=0 should produce 0 throughput, not billions."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "test",
            "eval_count": 50,
            # eval_duration missing -> defaults to 0
            "prompt_eval_duration": 100_000_000,
            "total_duration": 2_000_000_000,
        }
        mock_response.raise_for_status = MagicMock()

        b = OllamaBackend()
        with patch("chimeraforge.bench.backends.ollama.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client
            b._client = mock_client

            metrics = await b.generate("test", "hello")

        assert metrics.throughput_tps == 0.0
        assert metrics.tokens_generated == 50
