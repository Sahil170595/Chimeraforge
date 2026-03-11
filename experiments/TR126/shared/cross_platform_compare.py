"""Cross-platform comparison utilities for TR126.

Loads Windows baseline results from TR120/TR117 and computes per-group
deltas against Linux results. This is TR126's core novel contribution:
the first Windows-vs-Linux A/B comparison on the same consumer GPU.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import scipy.stats as stats


def compute_platform_deltas(
    linux_df: pd.DataFrame,
    windows_df: pd.DataFrame,
    group_cols: list[str],
    value_col: str = "latency_ms",
) -> pd.DataFrame:
    """Compute per-group deltas between Linux and Windows results.

    Returns DataFrame with columns:
        group_cols + [n_linux, n_windows, mean_linux, mean_windows,
                      mean_delta_ms, mean_delta_pct, median_linux, median_windows,
                      median_delta_ms, p95_linux, p95_windows, p95_delta_ms,
                      mann_whitney_U, mann_whitney_p, cohens_d]
    """
    rows: list[dict[str, Any]] = []

    linux_groups = linux_df.groupby(group_cols)
    windows_groups = windows_df.groupby(group_cols)

    for key, linux_grp in linux_groups:
        if key not in windows_groups.groups:
            continue
        windows_grp = windows_groups.get_group(key)

        lv = linux_grp[value_col].dropna().values
        wv = windows_grp[value_col].dropna().values

        if len(lv) < 2 or len(wv) < 2:
            continue

        row: dict[str, Any] = {}
        if isinstance(key, tuple):
            for col, val in zip(group_cols, key, strict=False):
                row[col] = val
        else:
            row[group_cols[0]] = key

        row["n_linux"] = len(lv)
        row["n_windows"] = len(wv)
        row["mean_linux"] = float(np.mean(lv))
        row["mean_windows"] = float(np.mean(wv))
        row["mean_delta_ms"] = row["mean_linux"] - row["mean_windows"]
        row["mean_delta_pct"] = (
            100.0 * row["mean_delta_ms"] / row["mean_windows"]
            if row["mean_windows"] != 0
            else 0.0
        )
        row["median_linux"] = float(np.median(lv))
        row["median_windows"] = float(np.median(wv))
        row["median_delta_ms"] = row["median_linux"] - row["median_windows"]
        row["p95_linux"] = float(np.percentile(lv, 95))
        row["p95_windows"] = float(np.percentile(wv, 95))
        row["p95_delta_ms"] = row["p95_linux"] - row["p95_windows"]

        # Mann-Whitney U test (non-parametric)
        try:
            u_stat, u_p = stats.mannwhitneyu(lv, wv, alternative="two-sided")
            row["mann_whitney_U"] = float(u_stat)
            row["mann_whitney_p"] = float(u_p)
        except ValueError:
            row["mann_whitney_U"] = float("nan")
            row["mann_whitney_p"] = float("nan")

        # Cohen's d (effect size)
        pooled_std = np.sqrt(
            ((len(lv) - 1) * np.var(lv, ddof=1) + (len(wv) - 1) * np.var(wv, ddof=1))
            / (len(lv) + len(wv) - 2)
        )
        row["cohens_d"] = (
            float((np.mean(lv) - np.mean(wv)) / pooled_std) if pooled_std > 0 else 0.0
        )

        rows.append(row)

    return pd.DataFrame(rows)


def plot_platform_comparison(
    linux_df: pd.DataFrame,
    windows_df: pd.DataFrame,
    value_col: str,
    label: str,
    out_path: str | Path,
) -> None:
    """Side-by-side CDF overlay for Linux vs Windows latency distributions."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 5))

    for df, platform, color in [
        (linux_df, "Linux (Docker)", "tab:blue"),
        (windows_df, "Windows", "tab:orange"),
    ]:
        vals = np.sort(df[value_col].dropna().values)
        cdf = np.arange(1, len(vals) + 1) / len(vals)
        ax.plot(
            vals, cdf, label=f"{platform} (n={len(vals)})", color=color, linewidth=1.5
        )

    ax.set_xlabel(f"{label} (ms)")
    ax.set_ylabel("CDF")
    ax.set_title(f"Cross-Platform CDF: {label}")
    ax.legend()
    ax.grid(True, alpha=0.3)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out_path), dpi=150, bbox_inches="tight")
    plt.close(fig)
