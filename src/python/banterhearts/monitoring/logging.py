"""Structured logging configuration for monitoring components."""

from __future__ import annotations

import logging
import sys
from typing import Any, Dict

import structlog


def configure_logging(level: int = logging.INFO, json_output: bool = False) -> None:
    processors = [
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(
        level=level,
        stream=sys.stdout,
        format="%(message)s",
    )


def get_logger(name: str = "monitoring", **kwargs: Dict[str, Any]):
    if not structlog.is_configured():
        configure_logging()
    return structlog.get_logger(name).bind(**kwargs)
