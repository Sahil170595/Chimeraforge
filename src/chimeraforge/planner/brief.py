"""Decision-report artifact: a plan rendered as a document a team can argue with.

A terminal panel answers "what should I run". Defending a GPU purchase in a meeting
needs something else -- a dated record of what was assumed, where each number came
from, what the alternatives cost, and the exact command that reproduces it. Same
numbers, different job.

The prose is generated *from* the provenance labels rather than written alongside
them, because the risk here is entirely one-sided: a confident sentence
("throughput: 412 tok/s") silently outranks the `~` that qualifies it, and a brief
is read by people who will never see the JSON. So `PROVENANCE_PHRASE` keys the
wording to the label, and a rule test asserts every metric row carries one.

The report also refuses to render a stale price snapshot. Printing a nine-month-old
GPU price in a nicer font is worse than printing nothing: the document format is
itself a claim to durability, and a reader who sees a formatted brief does not
re-derive the arithmetic.
"""

from __future__ import annotations

import datetime as _dt
import shlex
from dataclasses import dataclass, field

from chimeraforge import __version__
from chimeraforge.planner.engine import Candidate

PROV_DERIVED = "derived"

# Prose keyed to the provenance label, so the sentence cannot outrun the evidence.
PROVENANCE_PHRASE = {
    "measured": "measured on the TR benchmark corpus",
    "estimated": "estimated (first-principles model, not measured)",
    "unknown": "unknown -- not screened, treat as unvalidated",
    # Not a prediction at all: exact arithmetic over the inputs and the GPU
    # database. Folding these into "measured" would claim the TR corpus as the
    # source of a number it never measured -- the precise confabulation this
    # module exists to make impossible.
    PROV_DERIVED: "derived (exact arithmetic over the inputs, not a prediction)",
}
# Marks a value in a table so the qualifier survives being skim-read.
PROVENANCE_MARK = {"measured": "", "estimated": "~", "unknown": "?", PROV_DERIVED: ""}

# A brief without a date is undatable evidence; a brief whose prices are older than
# this is misleading evidence. Both are refusals, not warnings.
STALE_REFUSAL = (
    "refusing to render: the API price snapshot is {age} days old (captured "
    "{captured}), past the {limit}-day limit. A dated document lends a stale price "
    "more authority than a terminal line does. Re-run scripts/build_api_pricing.py, "
    "or drop --compare-api to render the brief without the API section."
)


class BriefError(RuntimeError):
    """The brief cannot be rendered honestly with the inputs given."""


@dataclass
class BriefInputs:
    """The workload and constraints the plan was run against, verbatim."""

    hardware: str
    # `plan --model` is repeatable, so this mirrors it: str for the common single
    # case, list when several were planned together.
    model: str | list[str] | None = None
    model_size: str = "3b"
    request_rate: float = 1.0
    latency_slo_ms: float = 5000.0
    quality_target: float = 0.5
    budget_usd_month: float = 100000.0
    avg_output_tokens: int = 128
    reasoning_tokens: int = 0
    prompt_tokens: int = 512
    context_length: int = 2048
    kv_quant: str = "fp16"
    workload: str = "steady"
    duty_cycle: float = 1.0
    tensor_parallel: int = 1
    pipeline_parallel: int = 1
    prefix_cache_hit_rate: float = 0.0
    gpu_price_multiplier: float = 1.0
    safety_target: float | None = None
    lora_adapters: int = 0
    lora_rank: int = 16
    lora_target: str = "qv"
    ttft_slo_ms: float | None = None
    tpot_slo_ms: float | None = None

    @property
    def models(self) -> list[str]:
        """The explicit model ids, normalised to a list (empty = size-class search)."""
        if not self.model:
            return []
        return [self.model] if isinstance(self.model, str) else list(self.model)

    def repro_command(self) -> str:
        """The exact `chimeraforge plan` invocation that regenerates this brief.

        A brief nobody can re-run is an assertion, not evidence. Only non-default
        values are emitted, so the command stays readable and every flag in it is a
        decision someone actually made.
        """
        parts = ["chimeraforge", "plan", "--hardware", self.hardware]
        for m in self.models:
            parts += ["--model", m]
        if not self.models:
            parts += ["--model-size", self.model_size]
        defaults = BriefInputs(hardware=self.hardware)
        flags: list[tuple[str, object, object]] = [
            ("--request-rate", self.request_rate, defaults.request_rate),
            ("--latency-slo", self.latency_slo_ms, defaults.latency_slo_ms),
            ("--quality-target", self.quality_target, defaults.quality_target),
            ("--budget", self.budget_usd_month, defaults.budget_usd_month),
            ("--avg-tokens", self.avg_output_tokens, defaults.avg_output_tokens),
            ("--reasoning-tokens", self.reasoning_tokens, defaults.reasoning_tokens),
            ("--prompt-tokens", self.prompt_tokens, defaults.prompt_tokens),
            ("--context-length", self.context_length, defaults.context_length),
            ("--kv-quant", self.kv_quant, defaults.kv_quant),
            ("--workload", self.workload, defaults.workload),
            ("--duty-cycle", self.duty_cycle, defaults.duty_cycle),
            ("--tensor-parallel", self.tensor_parallel, defaults.tensor_parallel),
            ("--pipeline-parallel", self.pipeline_parallel, defaults.pipeline_parallel),
            ("--prefix-cache-hit-rate", self.prefix_cache_hit_rate, 0.0),
            ("--gpu-price-multiplier", self.gpu_price_multiplier, 1.0),
            ("--safety-target", self.safety_target, None),
            ("--lora-adapters", self.lora_adapters, 0),
            ("--lora-rank", self.lora_rank, defaults.lora_rank),
            ("--lora-target", self.lora_target, defaults.lora_target),
            ("--ttft-slo", self.ttft_slo_ms, None),
            ("--tpot-slo", self.tpot_slo_ms, None),
        ]
        for flag, value, default in flags:
            if value != default and value is not None:
                parts += [flag, _num(value)]
        return " ".join(shlex.quote(str(p)) for p in parts)


@dataclass
class MetricRow:
    """One reported number, inseparable from where it came from."""

    label: str
    value: str
    provenance: str
    note: str = ""

    @property
    def marked(self) -> str:
        return f"{PROVENANCE_MARK.get(self.provenance, '?')}{self.value}"

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "value": self.value,
            "provenance": self.provenance,
            "note": self.note,
        }


@dataclass
class Brief:
    """A rendered decision record: recommendation, evidence, and how to redo it."""

    generated_at: str
    tool_version: str
    inputs: BriefInputs
    winner: Candidate
    alternatives: list[Candidate] = field(default_factory=list)
    metrics: list[MetricRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    api_comparison: dict | None = None
    launch: dict | None = None

    def to_dict(self) -> dict:
        return {
            "schema_version": 1,
            "generated_at": self.generated_at,
            "tool_version": self.tool_version,
            "hardware": self.inputs.hardware,
            "repro_command": self.inputs.repro_command(),
            "models_requested": self.inputs.models,
            "recommendation": {
                "model": self.winner.model,
                "quant": self.winner.quant,
                "backend": self.winner.backend,
                "gpus_total": self.winner.gpus_total or self.winner.n_agents,
            },
            "metrics": [m.to_dict() for m in self.metrics],
            "warnings": list(self.warnings),
            "api_comparison": self.api_comparison,
            "launch": self.launch,
        }


def _num(v: object) -> str:
    """Render a number without a trailing `.0` that implies false precision."""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _today() -> str:
    return _dt.date.today().isoformat()


def build_brief(
    *,
    inputs: BriefInputs,
    candidates: list[Candidate],
    api_comparison: dict | None = None,
    launch: dict | None = None,
    generated_at: str | None = None,
    max_alternatives: int = 4,
) -> Brief:
    """Assemble the brief, refusing rather than rendering something misleading."""
    if not candidates:
        raise BriefError(
            "refusing to render: no feasible configuration was found, so there is "
            "nothing to recommend. Run `chimeraforge plan` without --report to see "
            "which gate rejected every candidate."
        )
    if api_comparison and api_comparison.get("prices_stale"):
        from chimeraforge.planner.apicost import STALE_AFTER_DAYS

        raise BriefError(
            STALE_REFUSAL.format(
                age=api_comparison.get("prices_age_days", "?"),
                captured=api_comparison.get("prices_captured_at") or "an unrecorded date",
                limit=STALE_AFTER_DAYS,
            )
        )

    w = candidates[0]
    prov = w.provenance or {}
    vram_p = prov.get("vram", "estimated")
    tput_p = prov.get("throughput", "estimated")
    qual_p = prov.get("quality", "unknown")

    gpus = w.gpus_total or w.n_agents
    metrics = [
        MetricRow(
            "VRAM per GPU",
            f"{w.vram_gb:.1f} GB",
            vram_p,
            "weights + KV cache + activations",
        ),
        MetricRow(
            "GPUs",
            str(gpus),
            PROV_DERIVED,
            f"{w.n_agents} replica{'s' if w.n_agents != 1 else ''}, chosen by the search",
        ),
        MetricRow(
            "Throughput (fleet)",
            f"{w.total_throughput_tps:.1f} tok/s",
            tput_p,
            f"{w.throughput_tps:.1f} tok/s per replica",
        ),
        MetricRow("p95 latency", f"{w.p95_latency_ms:.0f} ms", tput_p, "service + queueing"),
        MetricRow("Quality score", f"{w.quality:.3f}", qual_p, w.quality_tier),
        MetricRow(
            "Cost",
            f"${w.monthly_cost:,.2f}/mo",
            PROV_DERIVED,
            f"${w.cost_per_1m_tok:.3f} per 1M tokens; GPU list price only, "
            "excludes engineering time",
        ),
    ]
    # Only report a dimension the plan actually exercised -- a row of zeros reads as
    # a measurement of nothing.
    if w.ttft_ms:
        metrics.append(MetricRow("TTFT", f"{w.ttft_ms:.0f} ms", tput_p, "prefill"))
    if w.tpot_ms:
        metrics.append(MetricRow("TPOT", f"{w.tpot_ms:.1f} ms", tput_p, "per output token"))
    if w.energy_cost_month:
        metrics.append(
            MetricRow(
                "Energy",
                f"${w.energy_cost_month:,.2f}/mo",
                "estimated",  # board TDP is a rating, not a measured draw
                f"{w.perf_per_watt:.2f} tok/s per watt, from board TDP",
            )
        )
    if w.lora_adapters:
        # Two different epistemic classes in one feature, so they get two rows
        # rather than one averaged claim.
        metrics.append(
            MetricRow(
                "LoRA adapters",
                f"{w.lora_adapters} x rank-{w.lora_rank}",
                PROV_DERIVED,
                f"{w.lora_gb * 1000:.0f} MB resident; exact geometry, shared base weights",
            )
        )
    if w.safety_refusal is not None:
        metrics.append(
            MetricRow(
                "Refusal rate",
                f"{w.safety_refusal:.1%}",
                prov.get("safety", "unknown"),
                f"RTSI risk: {w.rtsi_risk}",
            )
        )

    return Brief(
        generated_at=generated_at or _today(),
        tool_version=__version__,
        inputs=inputs,
        winner=w,
        alternatives=candidates[1 : 1 + max_alternatives],
        metrics=metrics,
        warnings=list(w.warnings),
        api_comparison=api_comparison,
        launch=launch,
    )


def render_markdown(brief: Brief) -> str:
    """Render the brief as markdown a reviewer can read without the tool."""
    i = brief.inputs
    w = brief.winner
    gpus = w.gpus_total or w.n_agents
    parallel = ""
    if w.tensor_parallel > 1:
        parallel = f", tensor-parallel {w.tensor_parallel}"
    elif w.pipeline_parallel > 1:
        parallel = f", pipeline-parallel {w.pipeline_parallel}"

    out = [
        f"# Deployment brief: {w.model} on {i.hardware}",
        "",
        f"**Generated {brief.generated_at}** by ChimeraForge {brief.tool_version}. "
        "Every number below carries a provenance label; nothing here is a vendor claim.",
        "",
        "## Recommendation",
        "",
        f"Serve **{w.model}** at **{w.quant}** on **{w.backend}**, "
        f"across **{gpus} x {i.hardware}**{parallel}"
        + (f", batching {w.effective_batch} sequences per GPU." if w.effective_batch > 1 else "."),
        "",
        "| Metric | Value | Provenance |",
        "|---|---|---|",
    ]
    for m in brief.metrics:
        phrase = PROVENANCE_PHRASE.get(m.provenance, PROVENANCE_PHRASE["unknown"])
        detail = f"{phrase}" + (f" -- {m.note}" if m.note else "")
        out.append(f"| {m.label} | {m.marked} | {detail} |")

    out += [
        "",
        "`~` marks an estimate and `?` an unscreened value. An estimate is a "
        "first-principles prediction, not a measurement: run `chimeraforge measure` "
        "on the target rig to replace it with a measured figure.",
        "",
        "## Assumptions",
        "",
        "The recommendation holds only for this workload. Each line is an input, not a finding.",
        "",
        "| Assumption | Value |",
        "|---|---|",
        f"| Request rate | {_num(i.request_rate)} req/s |",
        f"| Output tokens per request | {i.avg_output_tokens}"
        + (f" (+{i.reasoning_tokens} hidden reasoning)" if i.reasoning_tokens else "")
        + " |",
        f"| Prompt tokens | {i.prompt_tokens} |",
        f"| Context length | {i.context_length} |",
        f"| Latency SLO (p95) | {_num(i.latency_slo_ms)} ms |",
        f"| Quality floor | {i.quality_target} |",
        f"| Budget | ${i.budget_usd_month:,.2f}/mo |",
        f"| Traffic variance | {i.workload} |",
        f"| Duty cycle | {i.duty_cycle:.0%} of the month |",
        f"| KV cache dtype | {i.kv_quant} |",
    ]
    if i.prefix_cache_hit_rate:
        out.append(f"| Prefix cache hit rate | {i.prefix_cache_hit_rate:.0%} |")
    if i.gpu_price_multiplier != 1.0:
        out.append(f"| GPU price multiplier | {i.gpu_price_multiplier}x |")
    if i.safety_target is not None:
        out.append(f"| Safety floor (refusal) | {i.safety_target} |")
    if i.lora_adapters:
        out.append(
            f"| LoRA adapters | {i.lora_adapters} x rank-{i.lora_rank}, targeting {i.lora_target} |"
        )

    if brief.alternatives:
        out += [
            "",
            "## Alternatives considered",
            "",
            "| Config | GPUs | Throughput | p95 | Quality | Cost/mo |",
            "|---|---|---|---|---|---|",
        ]
        for c in brief.alternatives:
            cp = c.provenance or {}
            tp = PROVENANCE_MARK.get(cp.get("throughput", "estimated"), "?")
            qp = PROVENANCE_MARK.get(cp.get("quality", "unknown"), "?")
            out.append(
                f"| {c.model} {c.quant} / {c.backend} | {c.gpus_total or c.n_agents} "
                f"| {tp}{c.total_throughput_tps:.0f} tok/s | {tp}{c.p95_latency_ms:.0f} ms "
                f"| {qp}{c.quality:.3f} | ${c.monthly_cost:,.2f} |"
            )

    if brief.api_comparison:
        api = brief.api_comparison
        out += [
            "",
            "## Self-host vs hosted API",
            "",
            f"Prices captured **{api.get('prices_captured_at') or 'undated'}** "
            f"({api.get('prices_age_days', '?')} days old). Self-hosting this fleet costs "
            f"**${api.get('self_host_monthly_usd', 0):,.2f}/mo** at "
            f"{_num(round(api.get('requests_per_month', 0)))} requests/month.",
            "",
            "| Hosted model | $/mo | Break-even output tok/mo | Cheaper |",
            "|---|---|---|---|",
        ]
        for o in api.get("options", []):
            be = o.get("breakeven_output_tokens_month")
            out.append(
                f"| {o['provider']} {o['name']} | ${o['monthly_cost_usd']:,.2f} "
                f"| {f'{be:,}' if be else 'n/a'} "
                f"| {'self-host' if o['self_host_cheaper'] else 'API'} |"
            )
        out += [
            "",
            "The self-host figure is GPU cost only. It excludes engineering time, "
            "on-call, and the idle capacity a duty cycle below 100% implies.",
        ]

    if brief.warnings:
        out += ["", "## Risks and caveats", "", "Reproduced verbatim from the planner:", ""]
        out += [f"- {wn}" for wn in brief.warnings]

    if brief.launch and brief.launch.get("command"):
        out += ["", "## How to run it", "", "```", brief.launch["command"], "```"]
        if brief.launch.get("env"):
            out += ["", "Environment:", "", "```", "\n".join(brief.launch["env"]), "```"]
        if brief.launch.get("notes"):
            out += [""] + [f"- {n}" for n in brief.launch["notes"]]

    out += [
        "",
        "## Reproduce",
        "",
        "```",
        brief.inputs.repro_command(),
        "```",
        "",
        f"Generated by ChimeraForge {brief.tool_version} on {brief.generated_at}. "
        "Re-run the command above to check whether the recommendation still holds; "
        "prices, hardware availability and the measured corpus all move.",
        "",
    ]
    return "\n".join(out)
