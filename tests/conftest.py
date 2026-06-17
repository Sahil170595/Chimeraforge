"""Shared pytest fixtures for ChimeraForge tests."""

from __future__ import annotations

import pytest

from chimeraforge.planner.models import PlannerModels, load_bundled_models
from helpers import make_result


@pytest.fixture()
def bench_result():
    """Return a single default bench result dict."""
    return make_result()


@pytest.fixture(scope="session")
def bundled_models() -> PlannerModels:
    """Load the bundled fitted models (real data from TR133)."""
    return load_bundled_models()
