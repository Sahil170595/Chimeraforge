"""Tests for the GitHub Action's plan renderer.

The rendering is where the edge cases live -- nothing fits, `--compare-api`
wrapping the payload, warnings that must survive into review -- so it is a real
script rather than inline YAML, and this is what makes it testable.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
RENDER_PY = ROOT / ".github" / "actions" / "plan-comment" / "render.py"
ACTION_YML = ROOT / ".github" / "actions" / "plan-comment" / "action.yml"


@pytest.fixture(scope="module")
def render_mod():
    spec = importlib.util.spec_from_file_location("cf_render", RENDER_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _candidate(**over) -> dict:
    base = {
        "model": "llama3.1-8b",
        "quant": "Q4_K_M",
        "backend": "ollama",
        "n_agents": 2,
        "gpus_total": 2,
        "vram_gb": 6.1,
        "total_throughput_tps": 240.0,
        "p95_latency_ms": 812.3,
        "monthly_cost": 1800.0,
        "cost_per_1m_tok": 0.9152,
        "cost_per_1m_tok_effective": 2.7127,
        "duty_cycle": 1.0,
        "quality": 0.71,
        "provenance": {"quality": "measured"},
        "warnings": [],
    }
    base.update(over)
    return base


class TestArgvConstruction:
    def test_model_takes_precedence_over_size(self, render_mod, monkeypatch):
        monkeypatch.setenv("CF_HARDWARE", "H100 80GB")
        monkeypatch.setenv("CF_MODEL", "Qwen/Qwen3-8B")
        monkeypatch.setenv("CF_MODEL_SIZE", "8b")
        argv = render_mod.build_argv()
        assert "--model" in argv and "Qwen/Qwen3-8B" in argv
        assert "--model-size" not in argv

    def test_falls_back_to_size_class(self, render_mod, monkeypatch):
        monkeypatch.setenv("CF_HARDWARE", "H100 80GB")
        monkeypatch.setenv("CF_MODEL", "")
        monkeypatch.setenv("CF_MODEL_SIZE", "3b")
        argv = render_mod.build_argv()
        assert "--model-size" in argv and "3b" in argv

    def test_extra_args_are_split_not_concatenated(self, render_mod, monkeypatch):
        monkeypatch.setenv("CF_HARDWARE", "H100 80GB")
        monkeypatch.setenv("CF_MODEL", "")
        monkeypatch.setenv("CF_EXTRA", "--duty-cycle 0.3 --compare-api")
        argv = render_mod.build_argv()
        assert "--duty-cycle" in argv and "0.3" in argv and "--compare-api" in argv

    def test_quoted_extra_arg_survives(self, render_mod, monkeypatch):
        monkeypatch.setenv("CF_HARDWARE", "H100 80GB")
        monkeypatch.setenv("CF_MODEL", "")
        monkeypatch.setenv("CF_EXTRA", '--hardware "RTX 4090 24GB"')
        assert "RTX 4090 24GB" in render_mod.build_argv()

    def test_json_is_always_requested(self, render_mod, monkeypatch):
        monkeypatch.setenv("CF_HARDWARE", "H100 80GB")
        monkeypatch.setenv("CF_MODEL", "")
        monkeypatch.delenv("CF_EXTRA", raising=False)
        assert "--json" in render_mod.build_argv()


class TestPayloadShapes:
    def test_bare_array(self, render_mod):
        cands, api = render_mod.parse_plan(json.dumps([_candidate()]))
        assert len(cands) == 1 and api is None

    def test_wrapped_by_compare_api(self, render_mod):
        payload = {"candidates": [_candidate()], "api_comparison": {"options": []}}
        cands, api = render_mod.parse_plan(json.dumps(payload))
        assert len(cands) == 1 and api == {"options": []}

    def test_wrapped_by_launch(self, render_mod):
        payload = {"candidates": [_candidate()], "launch": {"backend": "ollama"}}
        cands, api = render_mod.parse_plan(json.dumps(payload))
        assert len(cands) == 1 and api is None

    def test_error_payload_raises(self, render_mod):
        with pytest.raises(RuntimeError, match="unknown GPU"):
            render_mod.parse_plan(json.dumps({"error": "unknown GPU 'nope'"}))

    def test_empty_result(self, render_mod):
        cands, _ = render_mod.parse_plan("[]")
        assert cands == []


class TestRendering:
    def test_headline_numbers_present(self, render_mod):
        md = render_mod.render([_candidate()], None, ["chimeraforge", "plan", "--json"])
        assert "llama3.1-8b" in md and "$1,800.00" in md and "812.3" in md

    def test_effective_cost_shown_when_it_differs(self, render_mod):
        md = render_mod.render([_candidate(duty_cycle=0.3)], None, [])
        assert "effective" in md and "$2.71" in md

    def test_effective_cost_hidden_when_equal(self, render_mod):
        c = _candidate(cost_per_1m_tok_effective=0.9152)
        assert "effective" not in render_mod.render([c], None, [])

    def test_quality_provenance_is_surfaced(self, render_mod):
        md = render_mod.render([_candidate(provenance={"quality": "estimated"})], None, [])
        assert "estimated" in md

    def test_warnings_survive_into_review(self, render_mod):
        c = _candidate(warnings=["safety not screened (no TR134/TR142 data)"])
        assert "safety not screened" in render_mod.render([c], None, [])

    def test_warning_list_is_bounded_and_says_so(self, render_mod):
        c = _candidate(warnings=[f"w{i}" for i in range(20)])
        md = render_mod.render([c], None, [])
        assert "and 14 more" in md

    def test_empty_plan_explains_itself(self, render_mod):
        md = render_mod.render([], None, ["chimeraforge", "plan", "--json"])
        assert "No configuration satisfies" in md
        assert "which gate binds" in md

    def test_command_is_echoed_without_the_json_flag(self, render_mod):
        md = render_mod.render([_candidate()], None, ["chimeraforge", "plan", "--json", "-r", "2"])
        assert "chimeraforge plan" in md and "--json" not in md.split("command")[-1]

    def test_alternatives_table(self, render_mod):
        md = render_mod.render([_candidate(), _candidate(model="qwen2.5-3b")], None, [])
        assert "Alternatives" in md and "qwen2.5-3b" in md

    def test_api_comparison_flags_stale_prices(self, render_mod):
        api = {
            "prices_captured_at": "2020-01-01",
            "prices_stale": True,
            "options": [
                {
                    "name": "Tiny",
                    "provider": "acme",
                    "class": "open",
                    "monthly_cost_usd": 12.0,
                    "self_host_cheaper": False,
                }
            ],
        }
        md = render_mod.render([_candidate()], api, [])
        assert "prices stale" in md and "API wins" in md

    def test_provenance_footer_always_present(self, render_mod):
        assert "measured / estimated / unknown" in render_mod.render([_candidate()], None, [])


class TestOutputEmission:
    def test_multiline_uses_heredoc(self, render_mod, tmp_path, monkeypatch):
        out = tmp_path / "out.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(out))
        render_mod.emit("summary", "line1\nline2")
        text = out.read_text(encoding="utf-8")
        assert "summary<<__CF_EOF__" in text and "line1\nline2" in text

    def test_single_line_is_plain(self, render_mod, tmp_path, monkeypatch):
        out = tmp_path / "out.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(out))
        render_mod.emit("fits", "true")
        assert out.read_text(encoding="utf-8").strip() == "fits=true"


class TestActionMetadata:
    @pytest.fixture(scope="class")
    def action(self):
        yaml = pytest.importorskip("yaml")
        return yaml.safe_load(ACTION_YML.read_text(encoding="utf-8"))

    def test_is_a_composite_action(self, action):
        assert action["runs"]["using"] == "composite"

    def test_hardware_is_the_only_required_input(self, action):
        required = [k for k, v in action["inputs"].items() if v.get("required")]
        assert required == ["hardware"]

    def test_declares_the_documented_outputs(self, action):
        assert {"plan-json", "fits", "monthly-cost", "summary"} == set(action["outputs"])

    def test_fail_on_no_fit_defaults_off(self, action):
        # A plan that does not fit is information, not necessarily a broken build.
        assert action["inputs"]["fail-on-no-fit"]["default"] == "false"

    def test_every_composite_step_names_a_shell_or_uses(self, action):
        for step in action["runs"]["steps"]:
            assert "uses" in step or "shell" in step, step.get("name")
