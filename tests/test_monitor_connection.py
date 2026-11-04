"""Runtime-only TLS admission and native origin authorization."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import os

import httpx
import pytest

from chimeraforge.monitor import MonitorRequest


def test_connection_is_runtime_only_and_origin_bound(monkeypatch, tmp_path):
    from chimeraforge.monitor_connection import MonitorConnection, MonitorConnectionError

    canary = "PrivateBearerCanary_78"
    monkeypatch.setenv("CF_PRIVATE_TOKEN_78", canary)
    monkeypatch.setenv("SSLKEYLOGFILE", str(tmp_path / "keylog"))
    connection = MonitorConnection.from_env(
        "https://EXAMPLE.test:443/metrics", bearer_env="CF_PRIVATE_TOKEN_78"
    )
    assert not is_dataclass(connection)
    assert repr(connection) == "MonitorConnection(<redacted>)"
    assert canary not in repr(connection)
    with pytest.raises(TypeError):
        asdict(connection)
    assert "connection" not in asdict(MonitorRequest("vllm", "https://example.test", "model"))
    assert not (tmp_path / "keylog").exists()
    calls = []

    def reply(request):
        calls.append(request)
        assert request.headers["authorization"] == "Bearer " + canary
        return httpx.Response(200)

    with httpx.Client(
        transport=httpx.MockTransport(reply), **connection._client_kwargs()
    ) as client:
        assert client.get("https://example.test/version").status_code == 200
        with pytest.raises(MonitorConnectionError, match="origin"):
            client.get("https://other.test/version")
    assert len(calls) == 1


@pytest.mark.parametrize(
    "token", ["", " ", "bad\nHeader", "nonascii\u00e9", "x" * 8193, "token:password"]
)
def test_invalid_bearer_refuses_categorically(token):
    from chimeraforge.monitor_connection import MonitorConnection, MonitorConnectionError

    with pytest.raises(MonitorConnectionError) as caught:
        MonitorConnection("https://example.test", bearer_token=token)
    assert str(caught.value) == "invalid monitor bearer configuration"


@pytest.mark.parametrize(
    "url",
    [
        "http://example.test",
        "https://u:p@example.test",
        "https://example.test?q=secret",
        "https://example.test/#secret",
    ],
)
def test_secure_url_refuses_unsafe_settings(url):
    from chimeraforge.monitor_connection import MonitorConnection, MonitorConnectionError

    with pytest.raises(MonitorConnectionError):
        MonitorConnection(url)


def test_explicit_env_lookup_is_once_and_missing_value_is_private(monkeypatch):
    from chimeraforge.monitor_connection import MonitorConnection, MonitorConnectionError

    reads = []
    original = os.environ.get

    def get(key, default=None):
        if key == "PrivateEnvCanary_78":
            reads.append(key)
            return "token_78"
        return original(key, default)

    monkeypatch.setattr(os.environ, "get", get)
    MonitorConnection.from_env("https://example.test", bearer_env="PrivateEnvCanary_78")
    assert reads == ["PrivateEnvCanary_78"]
    with pytest.raises(MonitorConnectionError) as caught:
        MonitorConnection.from_env("https://example.test", bearer_env="MissingEnvCanary_78")
    assert "MissingEnvCanary_78" not in str(caught.value)


def test_anonymous_origin_guard_also_prevents_cross_origin_contact():
    from chimeraforge.monitor_connection import MonitorConnection, MonitorConnectionError

    calls = []
    connection = MonitorConnection("https://example.test")

    def reply(request):
        calls.append(request)
        return httpx.Response(200)

    with httpx.Client(
        transport=httpx.MockTransport(reply),
        **connection._client_kwargs(),
    ) as client:
        with pytest.raises(MonitorConnectionError):
            client.get("https://other.test")
    assert calls == []
