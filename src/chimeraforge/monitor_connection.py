"""Explicit runtime-only HTTPS trust and per-origin monitoring credentials."""

from __future__ import annotations

from collections.abc import Generator
import logging
import os
from pathlib import Path
import re
import ssl
from typing import Any

import certifi
import httpx

from chimeraforge.plan_bundle import _read

logger = logging.getLogger(__name__)
MAX_BEARER_BYTES = 8192
MAX_TLS_FILE_BYTES = 1024 * 1024
MAX_CONNECTION_URL_CHARS = 2048
_BEARER = re.compile(r"[A-Za-z0-9._~+/-]+=*\Z", re.ASCII)


class MonitorConnectionError(ValueError):
    """Invalid or unavailable secure settings, without private input values."""


def _origin(value: str | httpx.URL) -> tuple[str, str, int]:
    try:
        if isinstance(value, str) and (
            not 0 < len(value) <= MAX_CONNECTION_URL_CHARS
            or any(ord(char) <= 32 or ord(char) == 127 for char in value)
            or "#" in value
        ):
            raise ValueError
        url = httpx.URL(value)
        if (
            url.scheme != "https"
            or not url.host
            or url.userinfo
            or url.query
            or url.fragment
            or url.port == 0
        ):
            raise ValueError
        return url.scheme, url.host, url.port or 443
    except (ValueError, TypeError, httpx.InvalidURL):
        raise MonitorConnectionError("invalid secure monitor origin") from None


class _OriginAuth(httpx.Auth):
    def __init__(self, origin: tuple[str, str, int], token: str | None) -> None:
        self._origin, self._token = origin, token

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        # Metadata uses query parameters, unlike the admitted operator endpoint.
        url = request.url
        if (url.scheme, url.host, url.port or 443) != self._origin or url.userinfo:
            raise MonitorConnectionError("secure monitor request origin mismatch")
        if self._token is not None:
            request.headers["Authorization"] = "Bearer " + self._token
        yield request

    def __repr__(self) -> str:
        return "MonitorOriginAuth(<redacted>)"


def _refuse_password() -> str:
    raise MonitorConnectionError("encrypted monitor client keys are unsupported")


class MonitorConnection:
    """Prepared, private HTTPS settings; never store this in a request or report."""

    __slots__ = ("__origin", "__context", "__auth")
    __origin: tuple[str, str, int]
    __context: ssl.SSLContext
    __auth: _OriginAuth

    def __init__(
        self,
        endpoint_url: str,
        *,
        bearer_token: str | None = None,
        ca_bundle: str | Path | None = None,
        client_cert: str | Path | None = None,
        client_key: str | Path | None = None,
    ) -> None:
        origin = _origin(endpoint_url)
        if bearer_token is not None and (
            type(bearer_token) is not str
            or not 0 < len(bearer_token) <= MAX_BEARER_BYTES
            or not _BEARER.fullmatch(bearer_token)
        ):
            raise MonitorConnectionError("invalid monitor bearer configuration")
        if (client_cert is None) != (client_key is None):
            raise MonitorConnectionError("monitor client certificate and key are required together")
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.verify_mode = ssl.CERT_REQUIRED
            context.check_hostname = True
            if ca_bundle is None:
                context.load_verify_locations(cafile=certifi.where())
            else:
                raw = _read(Path(ca_bundle), MAX_TLS_FILE_BYTES)
                context.load_verify_locations(cadata=raw.decode("ascii"))
            if client_cert is not None and client_key is not None:
                # OpenSSL rereads these paths: size/type checks are preflight, not a snapshot.
                _read(Path(client_cert), MAX_TLS_FILE_BYTES)
                _read(Path(client_key), MAX_TLS_FILE_BYTES)
                context.load_cert_chain(client_cert, client_key, password=_refuse_password)
        except (OSError, ValueError, TypeError, RuntimeError) as exc:
            logger.info("secure monitor TLS admission failed (%s)", type(exc).__name__)
            raise MonitorConnectionError(
                "invalid or unavailable monitor TLS configuration"
            ) from None
        object.__setattr__(self, "_MonitorConnection__origin", origin)
        object.__setattr__(self, "_MonitorConnection__context", context)
        object.__setattr__(self, "_MonitorConnection__auth", _OriginAuth(origin, bearer_token))

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("monitor connection settings are immutable")

    def __repr__(self) -> str:
        return "MonitorConnection(<redacted>)"

    @classmethod
    def from_env(
        cls,
        endpoint_url: str,
        *,
        bearer_env: str | None = None,
        ca_bundle: str | Path | None = None,
        client_cert: str | Path | None = None,
        client_key: str | Path | None = None,
    ) -> MonitorConnection:
        token = None
        if bearer_env is not None:
            if (
                type(bearer_env) is not str
                or not bearer_env
                or len(bearer_env) > MAX_BEARER_BYTES
                or "\x00" in bearer_env
                or "=" in bearer_env
            ):
                raise MonitorConnectionError("invalid monitor bearer configuration")
            token = os.environ.get(bearer_env)
            if token is None:
                raise MonitorConnectionError("invalid monitor bearer configuration")
        return cls(
            endpoint_url,
            bearer_token=token,
            ca_bundle=ca_bundle,
            client_cert=client_cert,
            client_key=client_key,
        )

    def _admit_url(self, url: str) -> None:
        if _origin(url) != self.__origin:
            raise MonitorConnectionError("secure monitor request origin mismatch")

    def _client_kwargs(self) -> dict[str, Any]:
        return {
            "verify": self.__context,
            "auth": self.__auth,
            "trust_env": False,
            "follow_redirects": False,
        }

    def _transport_kwargs(self) -> dict[str, Any]:
        return {"verify": self.__context}


def admit_connection(connection: MonitorConnection | None, url: str) -> None:
    """Admit optional runtime settings before any monitor contact or budget starts."""
    if connection is not None:
        if type(connection) is not MonitorConnection:
            raise MonitorConnectionError("invalid monitor connection type")
        connection._admit_url(url)
