"""Context-local categorical SDK records, composed before the caller's factory."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
import logging
import threading
from typing import Any, Callable

_secure: ContextVar[bool] = ContextVar("chimeraforge_secure_transport", default=False)
_lock = threading.RLock()
_users = 0
_installed: Callable[..., logging.LogRecord] | None = None
_restore: Callable[..., logging.LogRecord] | None = None


@contextmanager
def sdk_logging(secure: bool) -> Iterator[None]:
    """Own only this factory slot and standard HTTPX/httpcore record inputs."""
    global _users, _installed, _restore
    token = _secure.set(secure)
    if secure:
        with _lock:
            if _users == 0:
                previous = logging.getLogRecordFactory()
                _restore = previous

                def categorical(*args: Any, **kwargs: Any) -> logging.LogRecord:
                    name = args[0] if args else kwargs.get("name", "")
                    family = name in ("httpx", "httpcore") or name.startswith(
                        ("httpx.", "httpcore.")
                    )
                    if _secure.get() and family:
                        values = list(args)
                        for index, key, value in (
                            (4, "msg", "secure transport event"),
                            (5, "args", ()),
                            (6, "exc_info", None),
                            (8, "sinfo", None),
                        ):
                            if index < len(values):
                                values[index] = value
                            elif key in kwargs:
                                kwargs[key] = value
                        args = tuple(values)
                    return previous(*args, **kwargs)

                _installed = categorical
                logging.setLogRecordFactory(categorical)
            _users += 1
    try:
        yield
    finally:
        _secure.reset(token)
        if secure:
            with _lock:
                _users -= 1
                if _users == 0:
                    if logging.getLogRecordFactory() is _installed:
                        assert _restore is not None
                        logging.setLogRecordFactory(_restore)
                    _installed = None
                    _restore = None
