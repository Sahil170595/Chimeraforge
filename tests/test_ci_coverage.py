"""The merge gate rejects missing evidence and independent coverage regressions."""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_coverage.py"


def invoke(tmp_path, *, lines=95, branches=95, files=True):
    summary = {
        "num_statements": 100,
        "covered_lines": lines,
        "num_branches": 100,
        "covered_branches": branches,
    }
    data = {"totals": summary, "files": {}}
    if files:
        for name in ("src/chimeraforge/bench/metrics.py", "src/chimeraforge/planner/constants.py"):
            data["files"][name] = {"summary": summary}
    report = tmp_path / "coverage.json"
    report.write_text(json.dumps(data), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(report)], capture_output=True, text=True, check=False
    )


def test_accepts_complete_evidence(tmp_path):
    assert invoke(tmp_path).returncode == 0


def test_rejects_line_regression_even_with_high_branch_coverage(tmp_path):
    result = invoke(tmp_path, lines=70)
    assert result.returncode == 1
    assert "line" in result.stdout


def test_rejects_branch_regression_even_with_high_line_coverage(tmp_path):
    result = invoke(tmp_path, branches=50)
    assert result.returncode == 1
    assert "branch" in result.stdout


def test_missing_critical_module_cannot_pass(tmp_path):
    assert invoke(tmp_path, files=False).returncode == 1
