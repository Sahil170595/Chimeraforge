"""Kill focused numerical mutations in disposable copies; never mutate the checkout."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TIMEOUT_SECONDS = 120
MUTATIONS = (
    (
        "kv-gib-unit",
        "planner/models.py",
        "return total_bytes / (1024**3)",
        "return total_bytes / (1000**3)",
    ),
    (
        "kv-batch-omitted",
        "planner/models.py",
        "caching_layers * batch_size * effective_ctx",
        "caching_layers * effective_ctx",
    ),
    (
        "kv-k-and-v",
        "planner/models.py",
        'per_token = arch.get("kv_elems_per_token_per_layer") or (\n'
        '            2 * arch["n_kv_heads"] * arch["d_head"]\n        )',
        'per_token = arch.get("kv_elems_per_token_per_layer") or (\n'
        '            arch["n_kv_heads"] * arch["d_head"]\n        )',
    ),
    ("cost-hour-unit", "planner/models.py", "rate / (tok_per_s * 3600)", "rate / (tok_per_s * 60)"),
    ("monthly-days", "planner/models.py", "return rate * 24 * 30", "return rate * 24 * 31"),
    (
        "prefill-ceiling",
        "planner/models.py",
        "return math.ceil(prompt_tokens / max_num_batched_tokens)",
        "return math.floor(prompt_tokens / max_num_batched_tokens)",
    ),
    ("percentile-p95", "bench/metrics.py", "p95=_percentile(s, 0.95)", "p95=_percentile(s, 0.05)"),
    ("dispersion-zero", "bench/metrics.py", "stddev=sd,", "stddev=0.0,"),
)


def replace_once(source: str, anchor: str, replacement: str) -> str:
    """An obsolete mutation must fail instead of producing a vacuous score."""
    if source.count(anchor) != 1:
        raise ValueError(f"mutation anchor must occur exactly once: {anchor!r}")
    return source.replace(anchor, replacement, 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    checkout = args.checkout.resolve()
    receipts = []
    with tempfile.TemporaryDirectory(prefix="chimeraforge-mutations-") as temporary:
        work = Path(temporary)
        shutil.copytree(
            checkout / "src/chimeraforge",
            work / "src/chimeraforge",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        shutil.copy(checkout / "tests/test_planner_properties.py", work / "test_properties.py")
        (work / "pytest.ini").write_text("[pytest]\npythonpath = src\n", encoding="utf-8")
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        command = [sys.executable, "-m", "pytest", "-q", "test_properties.py", "--tb=short"]
        baseline = subprocess.run(
            command, cwd=work, env=env, text=True, capture_output=True, timeout=TIMEOUT_SECONDS
        )
        assert baseline.returncode == 0, (
            f"unmutated baseline failed:\n{baseline.stdout}\n{baseline.stderr}"
        )
        for name, relative, anchor, replacement in MUTATIONS:
            target = work / "src/chimeraforge" / relative
            original = target.read_text(encoding="utf-8")
            target.write_text(replace_once(original, anchor, replacement), encoding="utf-8")
            for cache in (work / "src").rglob("__pycache__"):
                shutil.rmtree(cache)
            try:
                result = subprocess.run(
                    command,
                    cwd=work,
                    env=env,
                    text=True,
                    capture_output=True,
                    timeout=TIMEOUT_SECONDS,
                )
                assert (
                    result.returncode == 1
                    and " failed" in result.stdout
                    and "ERROR" not in result.stdout + result.stderr
                ), (
                    f"mutation {name} survived or did not reach assertions:\n"
                    f"{result.stdout}\n{result.stderr}"
                )
                receipts.append({"mutation": name, "status": "killed"})
                print(f"killed: {name}", flush=True)
            finally:
                target.write_text(original, encoding="utf-8")
    print(json.dumps({"baseline": "passed", "mutations": receipts}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
