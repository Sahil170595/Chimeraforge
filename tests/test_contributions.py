"""Tests for contributed measurements (`chimeraforge contribute`, `plan --contributions`).

First step of the federated corpus (roadmap Phase 9). A contribution is a `bench`
result with its full environment fingerprint and a content hash. It lands in a
local quarantine that is never blended into the bundled or measured corpus, and a
plan uses it only when asked, labelled `contributed` with the contribution ids it
came from. Outliers are flagged, not dropped. The hash proves the file is unaltered
since export; it does not prove who ran it, and the file says so.
"""

from __future__ import annotations

import json
from dataclasses import asdict

import pytest
from typer.testing import CliRunner

from chimeraforge import contrib
from chimeraforge.cli import app
from chimeraforge.planner.provenance import (
    PROV_CONTRIBUTED,
    PROVENANCE_ORDER,
    prov_class,
)
from chimeraforge.planner.service import run_plan


def bench_result(
    tps=(150.0, 152.0, 148.0, 151.0, 149.0),
    gpu="NVIDIA GeForce RTX 4090",
    model="llama3.2-3b",
    backend="vllm",
    quant=None,
):
    runs = [
        {
            "tokens_generated": 128,
            "throughput_tps": t,
            "ttft_ms": 40.0,
            "total_duration_ms": 900.0,
            "prompt_eval_duration_ms": 40.0,
            "eval_duration_ms": 850.0,
        }
        for t in tps
    ]
    mean = sum(tps) / len(tps)
    return {
        "model": model,
        "backend": backend,
        "quant": quant,
        "workload": "single",
        "runs": len(tps),
        "context_length": 2048,
        "individual_runs": runs,
        "aggregate": {"count": len(tps), "throughput_tps": {"mean": mean}},
        "environment": {
            "os": "Linux",
            "platform": "Linux-6.8-x86_64",
            "python_version": "3.12.4",
            "chimeraforge_version": "0.46.0",
            "gpu_name": gpu,
            "gpu_driver": "570.86",
            "cuda_version": "12.8",
            "backend_name": backend,
            "backend_version": "0.30.0",
        },
        "timestamp": "2026-10-01T12:00:00+00:00",
        "warnings": [],
    }


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path / "cache"))


class TestExport:
    def test_fingerprint_measurements_and_hash(self):
        c = contrib.build_contribution(bench_result())
        assert c["kind"] == contrib.CONTRIBUTION_KIND
        assert c["fingerprint"]["gpu_name"] == "NVIDIA GeForce RTX 4090"
        assert c["fingerprint"]["backend_version"] == "0.30.0"
        assert c["measurements"]["decode_tps"] == [150.0, 152.0, 148.0, 151.0, 149.0]
        assert len(c["id"]) == 64
        assert c["attestation"]["signed"] is False
        assert "does not prove who ran it" in c["attestation"]["note"]

    def test_hash_is_content_addressed(self):
        a = contrib.build_contribution(bench_result())
        b = contrib.build_contribution(bench_result())
        c = contrib.build_contribution(bench_result(tps=(150.0, 152.0, 148.0, 151.0, 150.0)))
        assert a["id"] == b["id"] != c["id"]

    def test_no_gpu_name_is_refused(self):
        with pytest.raises(contrib.ContribError, match="GPU"):
            contrib.build_contribution(bench_result(gpu=None))

    def test_too_few_runs_is_refused(self):
        with pytest.raises(contrib.ContribError, match="runs"):
            contrib.build_contribution(bench_result(tps=(150.0, 151.0)))

    def test_unstable_runs_are_flagged_not_dropped(self):
        c = contrib.build_contribution(bench_result(tps=(100.0, 150.0, 200.0)))
        assert c["measurements"]["decode_tps"] == [100.0, 150.0, 200.0]
        assert any("unstable" in f for f in c["flags"])


class TestVerify:
    def test_valid(self):
        contrib.verify_contribution(contrib.build_contribution(bench_result()))

    def test_tampered_numbers_fail(self):
        c = contrib.build_contribution(bench_result())
        c["measurements"]["decode_tps"][0] = 999.0
        with pytest.raises(contrib.ContribError, match="hash"):
            contrib.verify_contribution(c)

    def test_wrong_kind_fails(self):
        with pytest.raises(contrib.ContribError, match="kind"):
            contrib.verify_contribution({"kind": "something-else"})


class TestQuarantine:
    def test_import_dedupes_by_id(self, tmp_path):
        p = tmp_path / "c.json"
        p.write_text(json.dumps(contrib.build_contribution(bench_result())), encoding="utf-8")
        cid, new = contrib.import_contribution(p)
        assert new and contrib.import_contribution(p) == (cid, False)
        assert [c["id"] for c in contrib.load_quarantine()] == [cid]

    def test_import_verifies_first(self, tmp_path):
        c = contrib.build_contribution(bench_result())
        c["measurements"]["decode_tps"][0] = 1.0
        p = tmp_path / "bad.json"
        p.write_text(json.dumps(c), encoding="utf-8")
        with pytest.raises(contrib.ContribError):
            contrib.import_contribution(p)
        assert contrib.load_quarantine() == []

    def test_quarantine_never_touches_the_measured_corpus(self, tmp_path):
        from chimeraforge.planner.resolver import measured_corpus_path

        p = tmp_path / "c.json"
        p.write_text(json.dumps(contrib.build_contribution(bench_result())), encoding="utf-8")
        contrib.import_contribution(p)
        assert not measured_corpus_path().exists()


def _quarantine(*results):
    for r in results:
        c = contrib.build_contribution(r)
        contrib.quarantine_dir().mkdir(parents=True, exist_ok=True)
        (contrib.quarantine_dir() / f"{c['id']}.json").write_text(json.dumps(c), encoding="utf-8")


PLAN = dict(
    model_size="3b", hardware="RTX 4090 24GB", request_rate=0.5, budget=1e9, quality_target=0.0
)


def _cell(cands, backend="vllm", quant="FP16"):
    return next(
        c for c in cands if c.backend == backend and c.quant == quant and c.model == "llama3.2-3b"
    )


class TestPlan:
    def test_contributed_class_ranks_below_extrapolated(self):
        order = list(PROVENANCE_ORDER)
        assert (
            order.index("extrapolated") < order.index(PROV_CONTRIBUTED) < order.index("estimated")
        )

    def test_ignored_without_the_flag(self):
        before = [asdict(c) for c in run_plan(**PLAN).candidates]
        _quarantine(bench_result())
        assert [asdict(c) for c in run_plan(**PLAN).candidates] == before

    def test_used_with_the_flag_and_labelled(self):
        _quarantine(bench_result(), bench_result(tps=(160.0, 162.0, 158.0)))
        c = _cell(run_plan(**PLAN, use_contributions=True).candidates)
        assert c.throughput_tps == pytest.approx(155.0)  # median of 150.0 and 160.0
        prov = c.provenance["throughput"]
        assert prov_class(prov) == PROV_CONTRIBUTED
        assert prov["contributions"] == 2 and len(prov["ids"]) == 2
        assert any("contributed" in w and "unverified" in w for w in c.warnings)

    def test_exact_gpu_only(self):
        _quarantine(bench_result(gpu="NVIDIA GeForce RTX 4080"))
        c = _cell(run_plan(**PLAN, use_contributions=True).candidates)
        assert prov_class(c.provenance["throughput"]) != PROV_CONTRIBUTED

    def test_exact_quant_and_backend_only(self):
        _quarantine(bench_result(quant="Q4_K_M", backend="ollama"))
        c = _cell(run_plan(**PLAN, use_contributions=True).candidates)
        assert prov_class(c.provenance["throughput"]) != PROV_CONTRIBUTED

    def test_own_measurement_on_the_reference_gpu_wins(self):
        _quarantine(bench_result(gpu="NVIDIA GeForce RTX 4080 Laptop GPU"))
        res = run_plan(**{**PLAN, "hardware": "RTX 4080 12GB"}, use_contributions=True)
        c = _cell(res.candidates)
        assert prov_class(c.provenance["throughput"]) == "measured"


runner = CliRunner()


class TestCli:
    def test_export_verify_import_list(self, tmp_path):
        bench = tmp_path / "bench.json"
        bench.write_text(json.dumps([bench_result()]), encoding="utf-8")
        out = tmp_path / "out"
        r = runner.invoke(app, ["contribute", "export", str(bench), "--out", str(out)])
        assert r.exit_code == 0, r.output
        files = list(out.glob("*.json"))
        assert len(files) == 1
        assert runner.invoke(app, ["contribute", "verify", str(files[0])]).exit_code == 0
        assert runner.invoke(app, ["contribute", "import", str(files[0])]).exit_code == 0
        r = runner.invoke(app, ["contribute", "list", "--json"])
        assert r.exit_code == 0, r.output
        assert [c["fingerprint"]["model"] for c in json.loads(r.output)] == ["llama3.2-3b"]
        assert runner.invoke(app, ["contribute", "list"]).exit_code == 0

    def test_verify_tampered_fails_clean(self, tmp_path):
        c = contrib.build_contribution(bench_result())
        c["fingerprint"]["gpu_name"] = "H100"
        p = tmp_path / "t.json"
        p.write_text(json.dumps(c), encoding="utf-8")
        r = runner.invoke(app, ["contribute", "verify", str(p)])
        assert r.exit_code == 1 and "Traceback" not in r.output

    def test_plan_flag(self):
        _quarantine(bench_result())
        r = runner.invoke(
            app,
            ["plan", "--model-size", "3b", "--hardware", "RTX 4090 24GB", "--budget", "1000000",
             "--request-rate", "0.5", "--quality-target", "0", "--contributions", "--json"],
        )  # fmt: skip
        assert r.exit_code == 0, r.output
        assert "contributed" in r.output

    def test_mcp(self):
        _quarantine(bench_result())
        from chimeraforge.mcp_server import plan_deployment

        out = plan_deployment(
            model_size="3b", hardware="RTX 4090 24GB", request_rate=0.5, quality_target=0.0,
            use_contributions=True,
        )  # fmt: skip
        assert out["ok"], out
