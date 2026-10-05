"""Build and install a separate distribution, then select it through real metadata."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def test_installed_package_listing_bench_measure_safety(tmp_path):
    fixture = tmp_path / "fixture"
    shutil.copytree(
        Path(__file__).parent / "fixtures" / "backend_plugin",
        fixture,
        ignore=shutil.ignore_patterns("build", "*.egg-info", "__pycache__"),
    )
    wheels = tmp_path / "wheels"
    build = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(wheels),
            str(fixture),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert build.returncode == 0, build.stdout + build.stderr
    (wheel,) = wheels.glob("*.whl")
    site = tmp_path / "site"
    install = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            "--no-compile",
            "--target",
            str(site),
            str(wheel),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert install.returncode == 0, install.stdout + install.stderr
    source = Path(__file__).resolve().parents[1] / "src"
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(site), str(source))))
    code = r"""
import asyncio, json, sys
from pathlib import Path
from chimeraforge.bench.backends import list_backends
rows = list_backends()
assert "installed_cpu_backend" not in sys.modules, "listing imported plugin code"
row = next(row for row in rows if row["name"] == "installed-cpu")
assert row["distribution"] == "chimeraforge-installed-fixture"
assert row["version"] == "1.0.0"
from chimeraforge.bench.runner import run_benchmark
from chimeraforge.safety.runner import run_safety_screen
from chimeraforge.measure import measure_model
async def accept():
    bench = await run_benchmark("fixture", "installed-cpu", runs=3)
    assert bench.aggregate.count == 3 and bench.aggregate.throughput_tps.mean > 0
    assert bench.environment.backend_version == "1.0.0-test-fixture"
    safety = await run_safety_screen("fixture", ["probe"], "installed-cpu")
    assert safety.n_refused == 1
    corpus = Path("fixture-corpus.json")
    measured = await measure_model("fixture", backend="installed-cpu", quant="FP16", runs=3,
                                   concurrency=0, corpus_path=corpus)
    data = json.loads(corpus.read_text())
    assert "fixture|installed-cpu|FP16" in data["throughput"]["lookup"]
    assert "fixture|ollama|FP16" not in data["throughput"]["lookup"]
    from installed_cpu_backend import InstalledCPUBackend
    assert all(instance.closed for instance in InstalledCPUBackend.instances)
    print(json.dumps({"listing": row, "benchmark_runs": bench.aggregate.count,
                     "safety_scored": safety.n_prompts, "measurement_backend": measured.backend,
                     "all_adapters_closed": True,
                     "scope": "CPU fixture plumbing; no LLM accuracy claim"}))
asyncio.run(accept())
"""
    accepted = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    receipt = json.loads(accepted.stdout)
    assert receipt["all_adapters_closed"]
    cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "chimeraforge.cli",
            "bench",
            "--model",
            "fixture",
            "--backend",
            "installed-cpu",
            "--runs",
            "2",
            "--json",
            "--output-dir",
            str(tmp_path / "results"),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert cli.returncode == 0, cli.stdout + cli.stderr
    assert json.loads(cli.stdout)[0]["backend"] == "installed-cpu"
