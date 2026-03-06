"""Shared pytest fixtures for ChimeraForge tests."""

from __future__ import annotations

import pytest

from helpers import make_result


@pytest.fixture()
def bench_result():
    """Return a single default bench result dict."""
    return make_result()
