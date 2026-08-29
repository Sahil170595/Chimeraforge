"""Tests for the shared planning service (`run_plan`) and the MCP tool layer.

The MCP tool *logic* is tested by calling the plain functions directly -- no MCP
transport/client needed. `build_server` is guarded by importorskip so the suite
still runs without the optional `mcp` extra.
"""

from __future__ import annotations

import pytest

from chimeraforge.mcp_server import (
    list_hardware,
    plan_deployment,
    resolve_model,
)
from chimeraforge.planner.hardware import GPU_DB
from chimeraforge.planner.service import PlanResult, run_plan


class TestRunPlanService:
    def test_size_class_search(self):
        r = run_plan(model_size="8b", hardware="RTX 4090 24GB", request_rate=2.0, budget=5000)
        assert isinstance(r, PlanResult)
        assert r.candidates
        assert all(c.tensor_parallel == 1 and c.pipeline_parallel == 1 for c in r.candidates)

    def test_explicit_registry_model_offline(self):
        r = run_plan(
            models=["llama3.1-8b"],
            hardware="H100 80GB",
            quality_target=0.0,
            budget=1e9,
            allow_network=False,
        )
        assert r.candidates
        assert "llama3.1-8b" in r.specs

    def test_pareto_frontier_returned_only_when_requested(self):
        assert run_plan(model_size="3b", hardware="RTX 4090 24GB", budget=5000).frontier is None
        assert (
            run_plan(model_size="3b", hardware="RTX 4090 24GB", budget=5000, pareto=True).frontier
            is not None
        )

    def test_trace_populated_on_empty(self):
        # Impossible budget -> no candidates, but the trace explains why.
        r = run_plan(model_size="3b", hardware="RTX 4090 24GB", budget=0.0001)
        assert not r.candidates
        assert r.trace


class TestMcpTools:
    def test_list_hardware(self):
        h = list_hardware()
        assert h["ok"] and h["count"] == len(GPU_DB)
        assert all("vram_gb" in g and "interconnect_gbps" in g for g in h["gpus"])

    def test_plan_success_surfaces_provenance(self):
        r = plan_deployment(
            hardware="RTX 4090 24GB", model_size="8b", request_rate=2.0, budget_usd_month=5000
        )
        assert r["ok"]
        assert "provenance" in r["recommended"]
        assert set(r["recommended"]["provenance"]) >= {"vram", "throughput", "quality"}

    def test_plan_unknown_gpu_is_actionable(self):
        r = plan_deployment(hardware="RTX 9999 imaginary")
        assert r["ok"] is False
        assert "unknown GPU" in r["error"]
        assert "hint" in r  # tells the model to call list_hardware

    def test_plan_unresolvable_model_is_actionable(self):
        r = plan_deployment(
            hardware="H100 80GB", model="totally/nonexistent-xyz-9000", allow_network=False
        )
        assert r["ok"] is False
        assert "hint" in r

    def test_plan_empty_reports_why(self):
        """The no-fit branch returns the SAME envelope as the success branch.

        It used to return {candidates, why_nothing_fit} against the success
        path's {recommended, alternatives}, so no client could write one parser
        and an LLM would confabulate whichever branch it had not been shown.
        """
        r = plan_deployment(hardware="RTX 4090 24GB", model_size="8b", budget_usd_month=0.0001)
        assert r["ok"]
        assert r["recommended"] is None
        assert r["alternatives"] == []
        assert r["total_evaluated"] == 0
        assert r["why_nothing_fit"]
        assert isinstance(r["why_nothing_fit"], list), (
            "always a list -- it used to be the bare string 'no candidates'"
        )

    def test_both_outcomes_share_one_envelope(self):
        feasible = plan_deployment(
            hardware="RTX 4090 24GB", model_size="8b", request_rate=2.0, budget_usd_month=5000
        )
        infeasible = plan_deployment(
            hardware="RTX 4090 24GB", model_size="8b", budget_usd_month=0.0001
        )
        assert sorted(feasible) == sorted(infeasible)

    def test_resolve_model_offline(self):
        r = resolve_model("llama3.1-8b", allow_network=False)
        assert r["ok"]
        assert r["params_b"] == 8.03
        assert r["n_layers"] == 32

    def test_resolve_model_unresolvable(self):
        r = resolve_model("totally/nonexistent-xyz-9000", allow_network=False)
        assert r["ok"] is False


def test_build_server_registers_tools():
    # Skip only when the optional extra is genuinely absent. If `mcp` IS installed
    # but the submodule build_server needs is gone, that is a real break and must
    # fail: guarding the whole thing with importorskip made an incompatible major
    # (mcp 2.0 moved `mcp.server.fastmcp`) SKIP this test, so CI went green while
    # the [mcp] extra was broken. A dependency bump found that hole; this closes it.
    pytest.importorskip("mcp", reason="optional [mcp] extra not installed")
    import importlib.util

    assert importlib.util.find_spec("mcp.server.fastmcp") is not None, (
        "mcp is installed but `mcp.server.fastmcp` is missing -- the installed mcp "
        "major is incompatible with build_server(). Port to the new API before "
        "widening the pin in pyproject.toml."
    )
    from chimeraforge.mcp_server import build_server

    server = build_server()
    assert server is not None
    assert type(server).__name__ == "FastMCP"


def test_server_reports_our_version_not_the_sdks():
    """A tool that labels every number's provenance must not misreport its own version.

    FastMCP has no `version` parameter, so leaving it unset makes clients display the
    MCP SDK's version as ChimeraForge's -- observed as "chimeraforge 1.29.0" when
    probing the container. Setting it reaches into a private handle, so this asserts
    the outcome rather than the mechanism: if a future SDK removes it, the version is
    absent (acceptable) but never wrong (not acceptable).
    """
    pytest.importorskip("mcp", reason="optional [mcp] extra not installed")
    import chimeraforge
    from chimeraforge.mcp_server import build_server

    low_level = getattr(build_server(), "_mcp_server", None)
    reported = getattr(low_level, "version", None)
    assert reported in (chimeraforge.__version__, None), (
        f"MCP server reports version {reported!r}, which is neither ours "
        f"({chimeraforge.__version__}) nor absent -- clients would show a wrong version."
    )
