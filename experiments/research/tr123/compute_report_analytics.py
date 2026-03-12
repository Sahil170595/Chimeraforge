"""Compute all missing analytics for TR123 report rewrite."""

from collections import defaultdict
import json
import statistics


def main():
    rows = []
    with open("research/tr123/results/20260216_181539/raw_measurements.jsonl") as f:
        for line in f:
            r = json.loads(line)
            if r.get("status") == "ok":
                rows.append(r)

    print(f"Total OK rows: {len(rows)}")

    HOURLY_RATES = {
        "consumer_rtx4080": 0.046,
        "aws_spot": 0.302,
        "azure_spot": 0.270,
        "gcp_spot": 0.360,
        "aws_reserved_3yr": 0.503,
        "azure_reserved_3yr": 0.420,
        "gcp_reserved_3yr": 0.560,
        "aws_reserved_1yr": 0.704,
        "azure_on_demand": 0.900,
        "aws_on_demand": 1.006,
        "gcp_on_demand": 1.200,
    }
    USD_PER_KWH = 0.20
    CARBON_GCO2E_PER_KWH = 500.0

    # Group by model/backend
    groups = defaultdict(list)
    for r in rows:
        key = (r["model"], r["backend"])
        pp = r.get("phase_power", {})
        prefill_p = pp.get("prefill", {})
        decode_p = pp.get("decode", {})
        prefill_power = prefill_p.get("power_mean_w", 0) or 0
        decode_power = decode_p.get("power_mean_w", 0) or 0
        prefill_ms = r.get("prefill_ms", 0)
        decode_ms = r.get("decode_ms", 0)
        prompt_tok = r.get("prompt_tokens", 0)
        gen_tok = r.get("gen_tokens", 0)

        prefill_tps = prompt_tok / (prefill_ms / 1000.0) if prefill_ms > 0 else 0
        decode_tps = gen_tok / (decode_ms / 1000.0) if decode_ms > 0 else 0

        prefill_energy_j = prefill_power * (prefill_ms / 1000.0)
        decode_energy_j = decode_power * (decode_ms / 1000.0)

        groups[key].append(
            {
                "prefill_power_w": prefill_power,
                "decode_power_w": decode_power,
                "prefill_tps": prefill_tps,
                "decode_tps": decode_tps,
                "prefill_energy_j": prefill_energy_j,
                "decode_energy_j": decode_energy_j,
                "prefill_ms": prefill_ms,
                "decode_ms": decode_ms,
                "prompt_tokens": prompt_tok,
                "gen_tokens": gen_tok,
                "scenario": r["scenario"],
            }
        )

    # === 1. COST BREAKDOWN (INFRA VS ENERGY) ===
    print("\n=== COST BREAKDOWN (Infra vs Energy, Consumer, Chat Blend) ===")
    print(
        "model|backend|infra_usd_per_1m|energy_usd_per_1m|total_usd_per_1m|infra_pct|energy_pct"
    )
    cost_data = {}
    for (model, backend), vals in sorted(groups.items()):
        ptps = statistics.mean([v["prefill_tps"] for v in vals])
        dtps = statistics.mean([v["decode_tps"] for v in vals])
        ppow = statistics.mean([v["prefill_power_w"] for v in vals])
        dpow = statistics.mean([v["decode_power_w"] for v in vals])

        rate = HOURLY_RATES["consumer_rtx4080"]

        prefill_gpu_hrs = 1_000_000 / ptps / 3600 if ptps > 0 else 0
        decode_gpu_hrs = 1_000_000 / dtps / 3600 if dtps > 0 else 0
        prefill_infra = prefill_gpu_hrs * rate
        decode_infra = decode_gpu_hrs * rate

        prefill_seconds_per_1m = 1_000_000 / ptps if ptps > 0 else 0
        decode_seconds_per_1m = 1_000_000 / dtps if dtps > 0 else 0
        prefill_energy_kwh = (ppow * prefill_seconds_per_1m) / 3_600_000
        decode_energy_kwh = (dpow * decode_seconds_per_1m) / 3_600_000
        prefill_energy_cost = prefill_energy_kwh * USD_PER_KWH
        decode_energy_cost = decode_energy_kwh * USD_PER_KWH

        infra_blend = 0.67 * prefill_infra + 0.33 * decode_infra
        energy_blend = 0.67 * prefill_energy_cost + 0.33 * decode_energy_cost
        total_blend = infra_blend + energy_blend

        infra_pct = (infra_blend / total_blend * 100) if total_blend > 0 else 0
        energy_pct = (energy_blend / total_blend * 100) if total_blend > 0 else 0

        cost_data[(model, backend)] = {
            "infra": infra_blend,
            "energy": energy_blend,
            "total": total_blend,
            "ptps": ptps,
            "dtps": dtps,
            "ppow": ppow,
            "dpow": dpow,
            "prefill_energy_kwh": prefill_energy_kwh,
            "decode_energy_kwh": decode_energy_kwh,
        }

        print(
            f"{model}|{backend}|{infra_blend:.4f}|{energy_blend:.6f}|{total_blend:.4f}|{infra_pct:.2f}|{energy_pct:.2f}"
        )

    # === 2. ENERGY EFFICIENCY RANKING ===
    print("\n=== ENERGY EFFICIENCY (decode phase, ranked) ===")
    print("model|backend|decode_tok_per_kwh|decode_j_per_tok|decode_kwh_per_1m")
    efficiencies = []
    for (model, backend), vals in sorted(groups.items()):
        dtps = statistics.mean([v["decode_tps"] for v in vals])
        dpow = statistics.mean([v["decode_power_w"] for v in vals])
        if dpow > 0 and dtps > 0:
            decode_j_per_tok = dpow / dtps
            decode_kwh_per_1m = (dpow * (1_000_000 / dtps)) / 3_600_000
            tok_per_kwh = 3_600_000 / decode_j_per_tok
            efficiencies.append(
                (model, backend, tok_per_kwh, decode_j_per_tok, decode_kwh_per_1m)
            )

    efficiencies.sort(key=lambda x: -x[2])  # highest tok/kwh first
    for model, backend, tpk, jpt, kpm in efficiencies:
        print(f"{model}|{backend}|{tpk:.0f}|{jpt:.4f}|{kpm:.6f}")

    # === 3. CARBON FOOTPRINT ===
    print("\n=== CARBON FOOTPRINT (chat blend) ===")
    print("model|backend|energy_kwh_per_1m|carbon_gco2e_per_1m")
    for (model, backend), cd in sorted(cost_data.items()):
        energy_kwh_blend = (
            0.67 * cd["prefill_energy_kwh"] + 0.33 * cd["decode_energy_kwh"]
        )
        carbon = energy_kwh_blend * CARBON_GCO2E_PER_KWH
        print(f"{model}|{backend}|{energy_kwh_blend:.6f}|{carbon:.2f}")

    # === 4. ALL TIERS FOR ALL MODELS (chat blend) ===
    print("\n=== MULTI-TIER PRICING (all models, chat blend) ===")
    print(
        "model|backend|consumer|aws_spot|azure_spot|gcp_spot|aws_3yr|azure_3yr|gcp_3yr|aws_1yr|azure_od|aws_od|gcp_od"
    )
    for (model, backend), vals in sorted(groups.items()):
        ptps = statistics.mean([v["prefill_tps"] for v in vals])
        dtps = statistics.mean([v["decode_tps"] for v in vals])
        tier_costs = {}
        for tier, rate in HOURLY_RATES.items():
            prefill_gpu_hrs = 1_000_000 / ptps / 3600 if ptps > 0 else 0
            decode_gpu_hrs = 1_000_000 / dtps / 3600 if dtps > 0 else 0
            infra_blend = 0.67 * (prefill_gpu_hrs * rate) + 0.33 * (
                decode_gpu_hrs * rate
            )
            tier_costs[tier] = infra_blend

        # Add energy cost (same across tiers)
        cd = cost_data[(model, backend)]
        e = cd["energy"]
        vals_str = "|".join(
            f"{tier_costs[t] + e:.4f}"
            for t in [
                "consumer_rtx4080",
                "aws_spot",
                "azure_spot",
                "gcp_spot",
                "aws_reserved_3yr",
                "azure_reserved_3yr",
                "gcp_reserved_3yr",
                "aws_reserved_1yr",
                "azure_on_demand",
                "aws_on_demand",
                "gcp_on_demand",
            ]
        )
        print(f"{model}|{backend}|{vals_str}")

    # === 5. ROI / SAVINGS ===
    print("\n=== ROI SAVINGS (vs on-demand) ===")
    print(
        "model|backend|spot_savings_pct|reserved_3yr_savings_pct|consumer_savings_pct"
    )
    for (model, backend), vals in sorted(groups.items()):
        ptps = statistics.mean([v["prefill_tps"] for v in vals])
        dtps = statistics.mean([v["decode_tps"] for v in vals])

        def blend_cost(rate):
            prefill_gpu_hrs = 1_000_000 / ptps / 3600 if ptps > 0 else 0
            decode_gpu_hrs = 1_000_000 / dtps / 3600 if dtps > 0 else 0
            return 0.67 * (prefill_gpu_hrs * rate) + 0.33 * (decode_gpu_hrs * rate)

        od = blend_cost(HOURLY_RATES["aws_on_demand"])
        spot = blend_cost(HOURLY_RATES["aws_spot"])
        r3yr = blend_cost(HOURLY_RATES["aws_reserved_3yr"])
        consumer = blend_cost(HOURLY_RATES["consumer_rtx4080"])

        spot_sav = (1 - spot / od) * 100 if od > 0 else 0
        r3yr_sav = (1 - r3yr / od) * 100 if od > 0 else 0
        consumer_sav = (1 - consumer / od) * 100 if od > 0 else 0

        print(f"{model}|{backend}|{spot_sav:.1f}|{r3yr_sav:.1f}|{consumer_sav:.1f}")

    # === 6. REQUEST-LEVEL COST ===
    print("\n=== REQUEST-LEVEL COST (256 prompt + 128 generate) ===")
    print(
        "model|backend|time_prefill_s|time_decode_s|energy_kwh_per_req|cost_usd_per_req_consumer|cost_usd_per_req_od"
    )
    for (model, backend), vals in sorted(groups.items()):
        ptps = statistics.mean([v["prefill_tps"] for v in vals])
        dtps = statistics.mean([v["decode_tps"] for v in vals])
        ppow = statistics.mean([v["prefill_power_w"] for v in vals])
        dpow = statistics.mean([v["decode_power_w"] for v in vals])

        t_prefill = 256 / ptps if ptps > 0 else 0
        t_decode = 128 / dtps if dtps > 0 else 0
        energy_kwh = (ppow * t_prefill + dpow * t_decode) / 3_600_000

        for label, rate in [("consumer", 0.046), ("on_demand", 1.006)]:
            infra_cost = (t_prefill + t_decode) / 3600 * rate
            energy_cost = energy_kwh * USD_PER_KWH
            total_cost = infra_cost + energy_cost
            if label == "consumer":
                c_consumer = total_cost
            else:
                c_od = total_cost

        print(
            f"{model}|{backend}|{t_prefill:.4f}|{t_decode:.4f}|{energy_kwh:.2e}|{c_consumer:.7f}|{c_od:.6f}"
        )

    # === 7. TCO ===
    print("\n=== TCO (1B tokens/month, 12 months) ===")
    print("model|backend|consumer_annual|consumer_monthly|od_annual|od_monthly")
    for (model, backend), vals in sorted(groups.items()):
        ptps = statistics.mean([v["prefill_tps"] for v in vals])
        dtps = statistics.mean([v["decode_tps"] for v in vals])

        for rate_label, rate in [("consumer", 0.046), ("aws_od", 1.006)]:
            prefill_gpu_hrs = 1_000_000 / ptps / 3600 if ptps > 0 else 0
            decode_gpu_hrs = 1_000_000 / dtps / 3600 if dtps > 0 else 0
            infra_blend = 0.67 * (prefill_gpu_hrs * rate) + 0.33 * (
                decode_gpu_hrs * rate
            )
            cd = cost_data[(model, backend)]
            total_per_1m = infra_blend + cd["energy"]
            monthly = total_per_1m * 1000  # 1B tokens
            annual = monthly * 12
            if rate_label == "consumer":
                c_monthly, c_annual = monthly, annual
            else:
                od_monthly, od_annual = monthly, annual

        print(
            f"{model}|{backend}|{c_annual:.0f}|{c_monthly:.0f}|{od_annual:.0f}|{od_monthly:.0f}"
        )

    # === 8. STATISTICAL ANALYSIS ===
    print("\n=== STATISTICAL ANALYSIS (decode cost, per model) ===")
    # For each model, compare backends
    from itertools import combinations

    model_backend_costs = defaultdict(lambda: defaultdict(list))
    for r in rows:
        model = r["model"]
        backend = r["backend"]
        pp = r.get("phase_power", {})
        decode_p = pp.get("decode", {})
        decode_power = decode_p.get("power_mean_w", 0) or 0
        decode_ms = r.get("decode_ms", 0)
        gen_tok = r.get("gen_tokens", 0)

        decode_tps = gen_tok / (decode_ms / 1000.0) if decode_ms > 0 else 0
        decode_gpu_hrs = 1_000_000 / decode_tps / 3600 if decode_tps > 0 else 0
        decode_cost = decode_gpu_hrs * 0.046  # consumer

        model_backend_costs[model][backend].append(decode_cost)

    for model in sorted(model_backend_costs.keys()):
        backends = model_backend_costs[model]
        if len(backends) < 2:
            continue

        print(f"\n--- {model} ---")
        # Compute means and compare
        backend_names = sorted(backends.keys())
        for b in backend_names:
            vals = backends[b]
            m = statistics.mean(vals)
            s = statistics.stdev(vals) if len(vals) > 1 else 0
            print(f"  {b}: mean={m:.4f}, std={s:.4f}, n={len(vals)}")

        # Pairwise t-tests (manual Welch's t-test)
        for b1, b2 in combinations(backend_names, 2):
            v1 = backends[b1]
            v2 = backends[b2]
            m1, m2 = statistics.mean(v1), statistics.mean(v2)
            s1 = statistics.stdev(v1) if len(v1) > 1 else 0.001
            s2 = statistics.stdev(v2) if len(v2) > 1 else 0.001
            n1, n2 = len(v1), len(v2)

            se = (s1**2 / n1 + s2**2 / n2) ** 0.5
            t_stat = (m1 - m2) / se if se > 0 else 0

            diff = m1 - m2
            pct = (diff / m2 * 100) if m2 != 0 else 0

            # Cohen's d
            sp = ((s1**2 + s2**2) / 2) ** 0.5
            cohens_d = diff / sp if sp > 0 else 0

            print(
                f"  {b1} vs {b2}: diff=${diff:.4f} ({pct:+.1f}%), t={t_stat:.2f}, d={cohens_d:.2f}"
            )

    # === 9. CONFIDENCE INTERVALS (for latency table) ===
    print("\n=== LATENCY WITH CIs (per model/backend, mean across scenarios) ===")
    print(
        "model|backend|prefill_ms_mean|prefill_ci_lo|prefill_ci_hi|decode_ms_mean|decode_ci_lo|decode_ci_hi"
    )
    for (model, backend), vals in sorted(groups.items()):
        pms = [v["prefill_ms"] for v in vals]
        dms = [v["decode_ms"] for v in vals]
        pm_mean = statistics.mean(pms)
        dm_mean = statistics.mean(dms)
        pm_std = statistics.stdev(pms) if len(pms) > 1 else 0
        dm_std = statistics.stdev(dms) if len(dms) > 1 else 0
        n = len(pms)
        z = 1.96
        pm_ci = z * pm_std / n**0.5
        dm_ci = z * dm_std / n**0.5
        print(
            f"{model}|{backend}|{pm_mean:.1f}|{pm_mean-pm_ci:.1f}|{pm_mean+pm_ci:.1f}|{dm_mean:.1f}|{dm_mean-dm_ci:.1f}|{dm_mean+dm_ci:.1f}"
        )


if __name__ == "__main__":
    main()
