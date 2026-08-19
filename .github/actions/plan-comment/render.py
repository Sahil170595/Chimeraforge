"""Run `chimeraforge plan --json` and render it as a PR comment.

Kept as a real script rather than inline YAML so it can be unit-tested: the
rendering is the part with edge cases (nothing fits, `--compare-api` wrapping the
payload, warnings that must survive into review) and inline shell in a composite
action is untestable by construction.

Reads its inputs from ``CF_*`` environment variables and writes GitHub Actions
outputs to ``$GITHUB_OUTPUT``.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys

MARKER_TITLE = "ChimeraForge deployment plan"
# Warnings carry the honesty contract (estimated numbers, unscreened safety,
# conservative KV). Truncating them in review would defeat the point, but a wall
# of them buries the plan -- so show a bounded number and say how many were cut.
MAX_WARNINGS = 6
MAX_ALTERNATIVES = 3


def build_argv() -> list[str]:
    """Assemble the plan invocation from the action's inputs."""
    argv = [
        "chimeraforge",
        "plan",
        "--json",
        "--hardware",
        os.environ["CF_HARDWARE"],
        "--request-rate",
        os.environ.get("CF_RATE", "1.0"),
        "--latency-slo",
        os.environ.get("CF_SLO", "5000"),
        "--budget",
        os.environ.get("CF_BUDGET", "1000"),
    ]
    model = (os.environ.get("CF_MODEL") or "").strip()
    if model:
        argv += ["--model", model]
    else:
        argv += ["--model-size", os.environ.get("CF_MODEL_SIZE", "8b")]
    extra = (os.environ.get("CF_EXTRA") or "").strip()
    if extra:
        argv += shlex.split(extra)
    return argv


def parse_plan(stdout: str) -> tuple[list[dict], dict | None]:
    """Return (candidates, api_comparison) from either --json shape.

    `--json` alone emits a bare array; `--launch`/`--compare-api` wrap it in an
    object. Both are supported so `extra-args` can turn those on freely.
    """
    payload = json.loads(stdout)
    if isinstance(payload, list):
        return payload, None
    if isinstance(payload, dict):
        if "error" in payload:
            raise RuntimeError(payload["error"])
        return payload.get("candidates", []), payload.get("api_comparison")
    raise RuntimeError(f"unexpected plan payload: {type(payload).__name__}")


def _money(value: float) -> str:
    return f"${value:,.2f}"


def render(candidates: list[dict], api: dict | None, argv: list[str]) -> str:
    """Render the plan as markdown for a PR comment."""
    cmd = " ".join(shlex.quote(a) for a in argv if a != "--json")
    if not candidates:
        return (
            f"## {MARKER_TITLE}\n\n"
            "**No configuration satisfies these constraints.**\n\n"
            "Every candidate was rejected by a gate (VRAM, quality, latency, budget or "
            "safety). Run the command locally to see which gate binds -- the CLI prints "
            "a per-model breakdown on an empty result.\n\n"
            f"<details><summary>command</summary>\n\n```\n{cmd}\n```\n</details>\n"
        )

    best = candidates[0]
    gpus = best.get("gpus_total") or best.get("n_agents", 1)
    rows = [
        ("Model", f"`{best['model']}` @ `{best['quant']}` on `{best['backend']}`"),
        ("Fleet", f"{best.get('n_agents', 1)} replica(s), {gpus} GPU(s)"),
        ("VRAM / GPU", f"{best['vram_gb']} GB"),
        ("Throughput", f"{best['total_throughput_tps']:,.1f} tok/s total"),
        ("p95 latency", f"{best['p95_latency_ms']:,.1f} ms"),
        ("Monthly cost", _money(best["monthly_cost"])),
        ("$/1M tok", f"{_money(best['cost_per_1m_tok'])} at capacity"),
    ]
    effective = best.get("cost_per_1m_tok_effective")
    if effective and effective > best["cost_per_1m_tok"]:
        duty = best.get("duty_cycle", 1.0)
        rows.append(("$/1M tok (effective)", f"{_money(effective)} at {duty:.0%} duty"))
    quality = best.get("provenance", {}).get("quality", "measured")
    rows.append(("Quality", f"{best['quality']} ({quality})"))

    out = [f"## {MARKER_TITLE}", ""]
    out.append("| | |")
    out.append("|---|---|")
    out += [f"| **{k}** | {v} |" for k, v in rows]

    warnings = best.get("warnings") or []
    if warnings:
        out += ["", "**Warnings**", ""]
        out += [f"- {w}" for w in warnings[:MAX_WARNINGS]]
        if len(warnings) > MAX_WARNINGS:
            out.append(f"- _...and {len(warnings) - MAX_WARNINGS} more_")

    alts = candidates[1 : 1 + MAX_ALTERNATIVES]
    if alts:
        out += ["", "<details><summary>Alternatives</summary>", ""]
        out += ["| Model | Quant | Backend | GPUs | $/mo | p95 ms |", "|---|---|---|---|---|---|"]
        for a in alts:
            out.append(
                f"| {a['model']} | {a['quant']} | {a['backend']} | "
                f"{a.get('gpus_total') or a.get('n_agents', 1)} | "
                f"{_money(a['monthly_cost'])} | {a['p95_latency_ms']:,.1f} |"
            )
        out += ["", "</details>"]

    if api and api.get("options"):
        stale = " **(prices stale)**" if api.get("prices_stale") else ""
        out += ["", "<details><summary>Self-host vs hosted API</summary>", ""]
        out.append(f"Prices captured {api.get('prices_captured_at', 'unknown')}{stale}.")
        out += ["", "| Option | Class | $/mo | Verdict |", "|---|---|---|---|"]
        out.append(f"| **self-host (this plan)** | - | {_money(best['monthly_cost'])} | - |")
        for o in api["options"][:MAX_ALTERNATIVES]:
            verdict = "self-host wins" if o["self_host_cheaper"] else "API wins"
            out.append(
                f"| {o['name']} ({o['provider']}) | {o['class']} | "
                f"{_money(o['monthly_cost_usd'])} | {verdict} |"
            )
        out += ["", "</details>"]

    out += [
        "",
        f"<details><summary>command</summary>\n\n```\n{cmd}\n```\n</details>",
        "",
        "<sub>Numbers are labeled measured / estimated / unknown by "
        "[ChimeraForge](https://github.com/Sahil170595/Chimeraforge); an estimate is "
        "never presented as a measurement.</sub>",
    ]
    return "\n".join(out)


def emit(name: str, value: str) -> None:
    """Write a GitHub Actions output, using the heredoc form for multi-line values."""
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        print(f"{name}={value}")
        return
    with open(path, "a", encoding="utf-8") as fh:
        if "\n" in value:
            fh.write(f"{name}<<__CF_EOF__\n{value}\n__CF_EOF__\n")
        else:
            fh.write(f"{name}={value}\n")


def main() -> int:
    argv = build_argv()
    print("running:", " ".join(shlex.quote(a) for a in argv), file=sys.stderr)
    proc = subprocess.run(argv, capture_output=True, text=True)
    if proc.returncode != 0:
        # The CLI fails loud with a clean message; surface it rather than a traceback.
        sys.stderr.write(proc.stderr)
        print(f"::error::chimeraforge plan failed: {proc.stderr.strip()[:400]}")
        return 1
    try:
        candidates, api = parse_plan(proc.stdout)
    except (json.JSONDecodeError, RuntimeError) as exc:
        print(f"::error::could not read plan output: {exc}")
        return 1

    summary = render(candidates, api, argv)
    emit("plan-json", proc.stdout.strip())
    emit("fits", "true" if candidates else "false")
    emit("monthly-cost", str(candidates[0]["monthly_cost"]) if candidates else "")
    emit("summary", summary)

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as fh:
            fh.write(summary + "\n")

    if not candidates and os.environ.get("CF_FAIL_ON_NO_FIT", "false").lower() == "true":
        print("::error::no configuration satisfied the gates (fail-on-no-fit)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
