from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def _gather_runs(root: Path) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for path in root.rglob("run_*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        runs.append({"path": str(path), **data})
    return runs


def _rowify(run: dict[str, Any]) -> list[dict[str, Any]]:
    spec = run.get("spec", {})
    latencies = run.get("latencies_ms", []) or []
    tokens = run.get("tokens", []) or []
    ttft = run.get("ttft_ms", []) or []
    accuracy = run.get("accuracy")
    degraded_count = run.get("degraded_count", 0)
    degraded_reasons = run.get("degraded_reasons", [])
    rows: list[dict[str, Any]] = []
    for idx, latency in enumerate(latencies):
        tok = tokens[idx] if idx < len(tokens) else 0
        ttft_val = ttft[idx] if idx < len(ttft) else latency
        rows.append(
            {
                "scenario": spec.get("scenario"),
                "prompt_set": spec.get("prompt_set"),
                "backend": spec.get("backend"),
                "model": spec.get("model"),
                "quantization": spec.get("quantization"),
                "sample_idx": idx,
                "is_first_sample": idx == 0,
                "latency_ms": latency,
                "ttft_ms": ttft_val,
                "tokens": tok,
                "tokens_per_s": tok / (latency / 1000.0) if latency else 0.0,
                "status": run.get("status"),
                "error": run.get("error"),
                "accuracy": accuracy,
                "degraded_count": degraded_count,
                "degraded_reasons": (
                    "; ".join(degraded_reasons) if degraded_reasons else ""
                ),
                "path": run.get("path"),
            }
        )
    return rows


def _write_csv(rows: list[dict[str, Any]], out_file: Path) -> None:
    if not rows:
        out_file.write_text("", encoding="utf-8")
        return
    out_file.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with out_file.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze TR117 benchmark results.")
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=Path("results/tr117/runs"),
        help="Path containing run_*.json files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/tr117/metrics.csv"),
        help="Where to write the aggregated CSV.",
    )
    args = parser.parse_args()

    runs = _gather_runs(args.runs_root)
    rows: list[dict[str, Any]] = []
    for run in runs:
        rows.extend(_rowify(run))
    _write_csv(rows, args.output)
    print(f"Wrote {len(rows)} rows to {args.output}")

    # Optional plotting if matplotlib is present.
    try:  # pragma: no cover - optional dependency
        import matplotlib.pyplot as plt  # type: ignore

        by_backend: dict[str, list[float]] = {}
        for row in rows:
            if row["status"] != "ok":
                continue
            by_backend.setdefault(str(row["backend"]), []).append(
                float(row["latency_ms"])
            )
        if by_backend:
            names = list(by_backend.keys())
            means = [
                sum(vals) / len(vals) if vals else 0.0 for vals in by_backend.values()
            ]
            plt.figure(figsize=(8, 4))
            plt.bar(names, means)
            plt.ylabel("Mean latency (ms)")
            plt.title("TR117 Mean Latency by Backend")
            plt.xticks(rotation=30, ha="right")
            plot_path = args.output.parent / "latency_by_backend.png"
            plt.tight_layout()
            plt.savefig(plot_path)
            print(f"Wrote plot {plot_path}")
    except Exception as exc:
        print(f"Plotting skipped: {exc}")


if __name__ == "__main__":
    main()
