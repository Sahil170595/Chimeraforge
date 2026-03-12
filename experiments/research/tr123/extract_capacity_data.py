#!/usr/bin/env python3
"""
TR123 — Business Impact & Capacity Planning Extraction Script
=============================================================
Reads summary_stats.csv from the latest benchmark run and computes:
  (a) Mean throughput per model/backend (decode & prefill tok/s)
  (b) Capacity planning: workers for 100 req/s, monthly cost at 1B tokens
  (c) Product scenario packs: cost per 1k requests for 4 canonical mixes
  (d) Break-even analysis: consumer GPU vs AWS on-demand
"""

from collections import defaultdict
import csv
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
RESULTS_DIR = Path(__file__).resolve().parent / "results" / "20260216_181539"
SUMMARY_CSV = RESULTS_DIR / "summary_stats.csv"

CONSUMER_HOURLY = 0.046  # RTX 4080 amortised $/hr
AWS_ON_DEMAND_HOURLY = 1.006  # g5.xlarge $/hr
CONSUMER_HW_COST = 1200.0  # RTX 4080 purchase price

PRODUCT_SCENARIOS = {
    "chat_default": {"prompt": 128, "gen": 64},
    "agent_tool_step": {"prompt": 64, "gen": 256},
    "codegen_medium": {"prompt": 256, "gen": 512},
    "long_context_summary": {"prompt": 1024, "gen": 128},
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_summary() -> list[dict]:
    with open(SUMMARY_CSV, newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# (a) Mean throughput per (model, backend)
# ---------------------------------------------------------------------------
def compute_throughput(rows: list[dict]) -> dict:
    """Return {(model, backend): {decode_tok_per_s, prefill_tok_per_s}}."""
    accum: dict[tuple, dict] = defaultdict(
        lambda: {"decode_sum": 0.0, "prefill_sum": 0.0, "n": 0}
    )
    for r in rows:
        key = (r["model"], r["backend"])
        decode_val = r.get("decode_tok_per_s_mean", "")
        prefill_val = r.get("prefill_tok_per_s_mean", "")
        if decode_val and prefill_val:
            accum[key]["decode_sum"] += float(decode_val)
            accum[key]["prefill_sum"] += float(prefill_val)
            accum[key]["n"] += 1

    result = {}
    for key, v in sorted(accum.items()):
        n = v["n"]
        result[key] = {
            "decode_tok_per_s": v["decode_sum"] / n,
            "prefill_tok_per_s": v["prefill_sum"] / n,
        }
    return result


# ---------------------------------------------------------------------------
# (b) Capacity planning
# ---------------------------------------------------------------------------
def capacity_planning(throughput: dict) -> list[dict]:
    """Workers for 100 req/s (256 prompt + 128 gen) & monthly cost at 1B tok."""
    rows = []
    for (model, backend), t in sorted(throughput.items()):
        decode = t["decode_tok_per_s"]
        prefill = t["prefill_tok_per_s"]

        # Each request: 256 prompt + 128 generate tokens
        # Time per request (seconds)
        time_per_req = 256.0 / prefill + 128.0 / decode
        reqs_per_worker_per_sec = 1.0 / time_per_req

        workers_100rps = 100.0 / reqs_per_worker_per_sec

        # Monthly cost at 1B tokens/month (consumer tier)
        # 1B tokens; avg tokens per request = 256+128 = 384
        total_requests = 1_000_000_000 / 384.0
        total_worker_seconds = total_requests * time_per_req
        total_worker_hours = total_worker_seconds / 3600.0
        monthly_cost = total_worker_hours * CONSUMER_HOURLY

        rows.append(
            {
                "model": model,
                "backend": backend,
                "decode_tok_s": f"{decode:.1f}",
                "prefill_tok_s": f"{prefill:.1f}",
                "time_per_req_s": f"{time_per_req:.4f}",
                "reqs_per_worker_s": f"{reqs_per_worker_per_sec:.2f}",
                "workers_100rps": f"{workers_100rps:.1f}",
                "monthly_cost_1B_tok": f"${monthly_cost:,.2f}",
            }
        )
    return rows


# ---------------------------------------------------------------------------
# (c) Product scenario packs — cost per 1k requests
# ---------------------------------------------------------------------------
def product_scenarios(throughput: dict) -> list[dict]:
    rows = []
    for (model, backend), t in sorted(throughput.items()):
        decode = t["decode_tok_per_s"]
        prefill = t["prefill_tok_per_s"]
        row = {"model": model, "backend": backend}
        for scenario_name, cfg in PRODUCT_SCENARIOS.items():
            time_per_req = cfg["prompt"] / prefill + cfg["gen"] / decode
            cost_per_req = (time_per_req / 3600.0) * CONSUMER_HOURLY
            cost_per_1k = cost_per_req * 1000.0
            row[scenario_name] = f"${cost_per_1k:.4f}"
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# (d) Break-even analysis
# ---------------------------------------------------------------------------
def breakeven_analysis(throughput: dict) -> list[dict]:
    """Consumer GPU ($1200) vs AWS on-demand ($1.006/hr).
    For each model/backend, compute break-even months at 1M, 10M, 100M req/mo.
    """
    rows = []
    for (model, backend), t in sorted(throughput.items()):
        decode = t["decode_tok_per_s"]
        prefill = t["prefill_tok_per_s"]

        # Use the chat_default mix (128 prompt + 64 gen) as the reference
        time_per_req = 128.0 / prefill + 64.0 / decode
        cost_aws_per_req = (time_per_req / 3600.0) * AWS_ON_DEMAND_HOURLY
        cost_consumer_per_req = (time_per_req / 3600.0) * CONSUMER_HOURLY
        cost_diff_per_req = cost_aws_per_req - cost_consumer_per_req

        row = {
            "model": model,
            "backend": backend,
            "aws_cost_per_1k": f"${cost_aws_per_req * 1000:.4f}",
            "consumer_cost_per_1k": f"${cost_consumer_per_req * 1000:.4f}",
            "savings_per_1k": f"${cost_diff_per_req * 1000:.4f}",
        }

        for volume_label, volume in [
            ("1M", 1_000_000),
            ("10M", 10_000_000),
            ("100M", 100_000_000),
        ]:
            if cost_diff_per_req > 0:
                monthly_savings = cost_diff_per_req * volume
                breakeven_months = CONSUMER_HW_COST / monthly_savings
                row[f"breakeven_{volume_label}"] = f"{breakeven_months:.2f}"
            else:
                row[f"breakeven_{volume_label}"] = "N/A"

        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Markdown table printer
# ---------------------------------------------------------------------------
def print_md_table(title: str, rows: list[dict], col_order: list[str] | None = None):
    if not rows:
        print(f"\n## {title}\n\n(no data)\n")
        return
    cols = col_order or list(rows[0].keys())
    print(f"\n## {title}\n")
    # Header
    print("| " + " | ".join(cols) + " |")
    print("| " + " | ".join(["---"] * len(cols)) + " |")
    for r in rows:
        print("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 80)
    print("TR123 — BUSINESS IMPACT & CAPACITY PLANNING REPORT")
    print("=" * 80)
    print(f"Data source: {SUMMARY_CSV}")
    print()

    rows = load_summary()
    print(f"Loaded {len(rows)} measurement rows from summary_stats.csv")

    # (a) Throughput
    throughput = compute_throughput(rows)
    tp_rows = []
    for (m, b), t in sorted(throughput.items()):
        tp_rows.append(
            {
                "model": m,
                "backend": b,
                "mean_decode_tok/s": f"{t['decode_tok_per_s']:.1f}",
                "mean_prefill_tok/s": f"{t['prefill_tok_per_s']:.1f}",
            }
        )
    print_md_table(
        "(a) Mean Throughput per Model/Backend (averaged across scenarios)",
        tp_rows,
    )

    # (b) Capacity planning
    cap_rows = capacity_planning(throughput)
    print_md_table(
        "(b) Capacity Planning — 100 req/s target (256 prompt + 128 gen tokens per request)",
        cap_rows,
        col_order=[
            "model",
            "backend",
            "decode_tok_s",
            "prefill_tok_s",
            "time_per_req_s",
            "reqs_per_worker_s",
            "workers_100rps",
            "monthly_cost_1B_tok",
        ],
    )

    # (c) Product scenario packs
    scenario_rows = product_scenarios(throughput)
    scenario_cols = ["model", "backend", *list(PRODUCT_SCENARIOS.keys())]
    print_md_table(
        "(c) Product Scenario Packs — Cost per 1k Requests (consumer tier $0.046/hr)",
        scenario_rows,
        col_order=scenario_cols,
    )

    # (d) Break-even analysis
    be_rows = breakeven_analysis(throughput)
    print_md_table(
        "(d) Break-even: Consumer GPU ($1,200) vs AWS On-Demand ($1.006/hr) — chat_default mix (128p+64g)",
        be_rows,
        col_order=[
            "model",
            "backend",
            "aws_cost_per_1k",
            "consumer_cost_per_1k",
            "savings_per_1k",
            "breakeven_1M",
            "breakeven_10M",
            "breakeven_100M",
        ],
    )

    # Highlight best model for break-even
    print("\n## Break-even Spotlight: Best Model (lowest break-even at 10M req/mo)\n")
    best = None
    best_val = float("inf")
    for r in be_rows:
        try:
            val = float(r["breakeven_10M"])
            if val < best_val:
                best_val = val
                best = r
        except (ValueError, KeyError):
            continue
    if best:
        print(f"**{best['model']} / {best['backend']}**")
        print(f"- AWS cost per 1k requests:      {best['aws_cost_per_1k']}")
        print(f"- Consumer cost per 1k requests:  {best['consumer_cost_per_1k']}")
        print(f"- Savings per 1k requests:        {best['savings_per_1k']}")
        print(f"- Break-even at   1M req/mo:      {best['breakeven_1M']} months")
        print(f"- Break-even at  10M req/mo:      {best['breakeven_10M']} months")
        print(f"- Break-even at 100M req/mo:      {best['breakeven_100M']} months")
    else:
        print("(could not determine best model)")

    print()
    print("=" * 80)
    print("END OF REPORT")
    print("=" * 80)


if __name__ == "__main__":
    main()
