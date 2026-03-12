"""TR126 shared utilities: paths, data loading, results discovery."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
_REPO = Path(__file__).resolve().parents[3]

TR120_WINDOWS_RESULTS = _REPO / "research" / "tr120" / "results"
TR117_WINDOWS_RESULTS = _REPO / "results" / "tr117_tier3"
TR126_RESULTS = _REPO / "research" / "tr126" / "results"

# ---------------------------------------------------------------------------
# Results discovery
# ---------------------------------------------------------------------------


def find_latest_run(results_dir: str | Path) -> Path | None:
    """Find the latest timestamped run directory (YYYYMMDD_HHMMSS pattern)."""
    d = Path(results_dir)
    if not d.is_dir():
        return None
    candidates = sorted(
        [
            p
            for p in d.iterdir()
            if p.is_dir() and len(p.name) == 15 and p.name[8] == "_"
        ],
        key=lambda p: p.name,
        reverse=True,
    )
    return candidates[0] if candidates else None


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_metrics_csv(path: str | Path) -> pd.DataFrame:
    """Load a metrics.csv, filtering to status=='ok' rows if column exists."""
    df = pd.read_csv(path)
    if "status" in df.columns:
        df = df[df["status"] == "ok"].copy()
    return df


def load_run_json(path: str | Path) -> dict[str, Any]:
    """Load a single run_*.json artifact."""
    import json

    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Windows baseline resolution
# ---------------------------------------------------------------------------


def get_tr120_windows_run(run_name: str = "tr120_root_cause") -> Path | None:
    """Resolve to the latest TR120 Windows root-cause results directory."""
    base = TR120_WINDOWS_RESULTS / run_name
    return find_latest_run(base)


def get_tr117_windows_metrics() -> Path | None:
    """Resolve to TR117 Tier-3 metrics.csv (Windows baseline)."""
    csv = TR117_WINDOWS_RESULTS / "metrics.csv"
    return csv if csv.is_file() else None
