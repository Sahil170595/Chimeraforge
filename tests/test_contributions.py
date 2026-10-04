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
import copy
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


MALFORMED_JSON_INPUTS = [
    pytest.param(b"\xff", id="invalid-utf8"),
    pytest.param(b"[" * 5000 + b"0" + b"]" * 5000, id="excessive-nesting"),
    pytest.param(b'{"number":' + b"9" * 10000 + b"}", id="oversized-integer"),
]


def bench_result(
    tps=(150.0, 152.0, 148.0, 151.0, 149.0),
    gpu="NVIDIA GeForce RTX 4090",
    model="llama3.2-3b",
    backend="vllm",
    quant="FP16",
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
    def test_backend_default_quant_is_unknown(self):
        with pytest.raises(contrib.ContribError, match="quant"):
            contrib.build_contribution(bench_result(quant=None))

    def test_unapplied_sweep_labels_are_not_evidence(self):
        result = bench_result(quant="Q4_K_M")
        result["warnings"] = ["quant=Q4_K_M recorded but NOT applied: no backend accepts it"]
        with pytest.raises(contrib.ContribError, match="NOT applied"):
            contrib.build_contribution(result)

    @pytest.mark.parametrize("rate", [0, -1, float("nan"), float("inf"), "fast", True])
    def test_invalid_decode_sample_is_refused(self, rate):
        result = bench_result()
        result["individual_runs"][0]["throughput_tps"] = rate
        with pytest.raises(contrib.ContribError, match="decode"):
            contrib.build_contribution(result)

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
    def test_excessively_nested_content_fails_cleanly(self):
        c = contrib.build_contribution(bench_result())
        nested = None
        for _ in range(5000):
            nested = [nested]
        c["fingerprint"]["extra"] = nested
        with pytest.raises(contrib.ContribError, match="content"):
            contrib.verify_contribution(c)

    @pytest.mark.parametrize(
        "field, value",
        [
            ("decode_tps_mean", None),
            ("decode_tps_mean", "fast"),
            ("decode_tps_mean", float("nan")),
            ("decode_tps_mean", 1e9),
            ("decode_tps_cv", -1),
            ("decode_tps_cv", 1.0),
            ("decode_tps", [150, 150, -1]),
            ("decode_tps", "150"),
            ("ttft_ms", [40, float("inf"), 40, 40, 40]),
            ("measured_at", "yesterday"),
        ],
    )
    def test_hash_valid_malformed_measurements_fail(self, field, value):
        c = contrib.build_contribution(bench_result())
        c["measurements"][field] = value
        c["id"] = contrib._content_id(c["fingerprint"], c["measurements"])
        with pytest.raises(contrib.ContribError):
            contrib.verify_contribution(c)

    def test_required_mean_cannot_be_omitted(self):
        c = contrib.build_contribution(bench_result())
        del c["measurements"]["decode_tps_mean"]
        c["id"] = contrib._content_id(c["fingerprint"], c["measurements"])
        with pytest.raises(contrib.ContribError, match="mean"):
            contrib.verify_contribution(c)

    @pytest.mark.parametrize(
        "field, value",
        [
            ("model", ""),
            ("backend", "unsupported"),
            ("backend_name", "other"),
            ("quant", None),
            ("gpu_name", ""),
            ("gpu_memory_gb", -1),
            ("gpu_driver", []),
            ("os", None),
            ("context_length", 0),
        ],
    )
    def test_hash_valid_malformed_fingerprint_fails(self, field, value):
        c = contrib.build_contribution(bench_result())
        c["fingerprint"][field] = value
        c["id"] = contrib._content_id(c["fingerprint"], c["measurements"])
        with pytest.raises(contrib.ContribError):
            contrib.verify_contribution(c)

    def test_instability_flag_cannot_be_removed(self):
        c = contrib.build_contribution(bench_result(tps=(100, 150, 200)))
        c["flags"] = []
        with pytest.raises(contrib.ContribError, match="flags"):
            contrib.verify_contribution(c)

    @pytest.mark.parametrize("signed", [True, 0, None])
    def test_unsupported_signature_claim_is_refused(self, signed):
        c = contrib.build_contribution(bench_result())
        c["attestation"]["signed"] = signed
        with pytest.raises(contrib.ContribError, match="unsigned"):
            contrib.verify_contribution(c)

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
    @pytest.mark.parametrize("payload", MALFORMED_JSON_INPUTS)
    def test_malformed_encoding_and_parser_limits_are_skipped(self, tmp_path, caplog, payload):
        good = contrib.build_contribution(bench_result())
        folder = contrib.quarantine_dir()
        folder.mkdir(parents=True)
        (folder / f"{good['id']}.json").write_text(json.dumps(good), encoding="utf-8")
        (folder / "malformed.json").write_bytes(payload)
        assert [c["id"] for c in contrib.load_quarantine()] == [good["id"]]
        assert "skipping quarantined contribution malformed.json" in caplog.text
        r = CliRunner().invoke(app, ["contribute", "list", "--json"])
        assert r.exit_code == 0, r.output
        assert [c["id"] for c in json.loads(r.output)] == [good["id"]]
        assert _cell(run_plan(**PLAN, use_contributions=True).candidates).throughput_tps == 150.0

    @pytest.mark.parametrize("payload", MALFORMED_JSON_INPUTS)
    def test_malformed_import_raises_contribution_error(self, tmp_path, payload):
        path = tmp_path / "malformed.json"
        path.write_bytes(payload)
        with pytest.raises(contrib.ContribError, match="could not read"):
            contrib.import_contribution(path)
        assert contrib.load_quarantine() == []

    def test_hash_valid_bad_file_is_skipped_by_list_and_plan(self, tmp_path, caplog):
        good = contrib.build_contribution(bench_result())
        bad = copy.deepcopy(good)
        del bad["measurements"]["decode_tps_mean"]
        bad["id"] = contrib._content_id(bad["fingerprint"], bad["measurements"])
        folder = contrib.quarantine_dir()
        folder.mkdir(parents=True)
        for c in (good, bad):
            (folder / f"{c['id']}.json").write_text(json.dumps(c), encoding="utf-8")
        assert [c["id"] for c in contrib.load_quarantine()] == [good["id"]]
        assert "skipping quarantined contribution" in caplog.text
        r = CliRunner().invoke(app, ["contribute", "list", "--json"])
        assert r.exit_code == 0
        assert [c["id"] for c in json.loads(r.output)] == [good["id"]]
        assert _cell(run_plan(**PLAN, use_contributions=True).candidates).throughput_tps == 150.0

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
    model_size="3b",
    hardware="RTX 4090 24GB",
    request_rate=0.5,
    budget=1e9,
    quality_target=0.0,
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
    @pytest.mark.parametrize("command", ["export", "verify", "import"])
    @pytest.mark.parametrize("payload", MALFORMED_JSON_INPUTS)
    def test_malformed_inputs_fail_with_cli_error(self, tmp_path, command, payload):
        path = tmp_path / "malformed.json"
        path.write_bytes(payload)
        args = ["contribute", command, str(path)]
        if command == "export":
            args.extend(["--out", str(tmp_path / "out")])
        r = runner.invoke(app, args)
        assert r.exit_code == 1
        assert "Error:" in r.output
        assert "Traceback" not in r.output

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
