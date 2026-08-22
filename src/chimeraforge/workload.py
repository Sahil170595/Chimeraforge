"""Derive plan inputs from real traffic instead of asking someone to guess them.

`plan` takes a request rate, prompt and output lengths, a traffic-variance preset
and a prefix-cache hit rate. Today all five are typed in by hand, and the variance
one is a preset chosen from a menu -- which means the queueing tail, the part of
the answer people most want, rests on a guess.

Every one of those is already being measured by whatever is serving the traffic.
This reads them: a request log (exact), or a live `/metrics` endpoint (whatever
the engine's histograms can support).

Two rules shape the design.

**Never map a metric name you do not recognise.** vLLM renamed
`gpu_cache_usage_perc` to `kv_cache_usage_perc` and `time_per_output_token_seconds`
to `inter_token_latency_seconds` between documented versions. A scraper that
quietly falls back to a stale name reports a fabricated measurement, which is worse
than reporting nothing. So names are per-engine and explicit, an unrecognised
engine is an error, and a metric that is absent leaves its field absent.

**An absent field stays absent.** It does not get a default. `plan` keeps
requiring it explicitly, so a partial profile can never silently supply a made-up
number wearing a `measured` label.
"""

from __future__ import annotations

import datetime as _dt
import json
import math
import re
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path

SCHEMA_VERSION = 1

# Per-engine metric names, verified against each project's own metrics reference
# rather than recalled. Anything not listed is not read -- see the module docstring
# on why a "close enough" fallback is the failure mode this guards.
#
# vLLM: docs.vllm.ai/en/stable/design/metrics.html
# SGLang: docs.sglang.io/references/production_metrics.html
ENGINE_METRICS: dict[str, dict[str, str]] = {
    "vllm": {
        "prefix": "vllm:",
        "requests_total": "vllm:request_success_total",
        "e2e_latency": "vllm:e2e_request_latency_seconds",
        "prompt_tokens": "vllm:request_prompt_tokens",
        "decode_tokens": "vllm:request_generation_tokens",
        "running": "vllm:num_requests_running",
        "waiting": "vllm:num_requests_waiting",
        "prefix_cache_hits": "vllm:prefix_cache_hits",
        "prefix_cache_queries": "vllm:prefix_cache_queries",
    },
    "sglang": {
        "prefix": "sglang:",
        # SGLang has no request-success counter; rate is derived from the e2e
        # histogram's _count instead, which is the same quantity by another route.
        "e2e_latency": "sglang:e2e_request_latency_seconds",
        "running": "sglang:num_running_reqs",
        "waiting": "sglang:num_queue_reqs",
        # A rate gauge, not the hits/queries counters vLLM exposes.
        "cache_hit_rate": "sglang:cache_hit_rate",
    },
}

# Log field names. Anything else is reported as unreadable rather than guessed at.
LOG_FIELDS = {
    "timestamp": ("timestamp", "ts", "time", "start_time"),
    "prompt_tokens": ("prompt_tokens", "input_tokens", "num_prompt_tokens"),
    "decode_tokens": ("completion_tokens", "output_tokens", "generation_tokens"),
    "cached_tokens": ("cached_tokens", "cached_prompt_tokens", "prefix_cache_tokens"),
}
# Below this many requests, a CV^2 is noise wearing a decimal point.
MIN_SAMPLES_FOR_VARIANCE = 30
# A Prometheus histogram gives sum and count exactly, but the spread only through
# bucket boundaries -- so a CV^2 from one is approximated at bucket midpoints and
# is labeled estimated, never measured.
PROV_MEASURED = "measured"
PROV_ESTIMATED = "estimated"


class WorkloadError(RuntimeError):
    """The profile cannot be derived honestly from what was supplied."""


@dataclass
class Field:
    """One derived input, with how it was obtained."""

    value: float
    provenance: str
    note: str = ""


@dataclass
class WorkloadProfile:
    """Measured traffic, in the shape `plan` consumes.

    Fields absent from the source stay ``None``: `plan` then keeps requiring them
    explicitly rather than filling in a default that would inherit this profile's
    `measured` badge.
    """

    captured_at: str
    source: str
    engine: str = "unknown"
    engine_version: str = "unknown"
    sample_count: int = 0
    window_seconds: float = 0.0
    request_rate: Field | None = None
    prompt_tokens: Field | None = None
    output_tokens: Field | None = None
    workload_cv2: Field | None = None
    prefix_cache_hit_rate: Field | None = None
    peak_concurrency: Field | None = None
    queue_depth: Field | None = None
    absent: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        out: dict = {
            "schema_version": SCHEMA_VERSION,
            "captured_at": self.captured_at,
            "source": self.source,
            "engine": self.engine,
            "engine_version": self.engine_version,
            "sample_count": self.sample_count,
            "window_seconds": round(self.window_seconds, 3),
            "fields": {},
            "absent": list(self.absent),
            "notes": list(self.notes),
        }
        for name in (
            "request_rate",
            "prompt_tokens",
            "output_tokens",
            "workload_cv2",
            "prefix_cache_hit_rate",
            "peak_concurrency",
            "queue_depth",
        ):
            f = getattr(self, name)
            if f is not None:
                out["fields"][name] = asdict(f)
        return out

    def plan_kwargs(self) -> dict:
        """The subset of `run_plan` arguments this profile can actually supply."""
        kw: dict = {}
        if self.request_rate is not None:
            kw["request_rate"] = self.request_rate.value
        if self.prompt_tokens is not None:
            kw["prompt_tokens"] = int(round(self.prompt_tokens.value))
        if self.output_tokens is not None:
            kw["avg_tokens"] = int(round(self.output_tokens.value))
        if self.workload_cv2 is not None:
            kw["workload_cv2"] = self.workload_cv2.value
        if self.prefix_cache_hit_rate is not None:
            kw["prefix_cache_hit_rate"] = self.prefix_cache_hit_rate.value
        return kw

    @classmethod
    def from_dict(cls, data: dict) -> WorkloadProfile:
        version = data.get("schema_version")
        if version != SCHEMA_VERSION:
            raise WorkloadError(
                f"workload profile schema_version {version!r} is not {SCHEMA_VERSION}; "
                "regenerate it with `chimeraforge workload`"
            )
        p = cls(
            captured_at=data.get("captured_at", ""),
            source=data.get("source", "unknown"),
            engine=data.get("engine", "unknown"),
            engine_version=data.get("engine_version", "unknown"),
            sample_count=int(data.get("sample_count", 0)),
            window_seconds=float(data.get("window_seconds", 0.0)),
            absent=list(data.get("absent", [])),
            notes=list(data.get("notes", [])),
        )
        for name, raw in (data.get("fields") or {}).items():
            if not hasattr(p, name):
                continue
            try:
                value = float(raw["value"])
            except (KeyError, TypeError, ValueError) as exc:
                # A raw KeyError escaped the CLI's WorkloadError handler and came
                # out as a traceback, which is exactly what test_cli_fail_loud
                # exists to prevent.
                raise WorkloadError(f"workload profile field {name!r} is malformed: {exc}") from exc
            setattr(
                p,
                name,
                Field(
                    value=value,
                    # Absent provenance means we do not know how it was derived.
                    # Defaulting to "estimated" claimed more than the file said.
                    provenance=str(raw.get("provenance", "unknown")),
                    note=str(raw.get("note", "")),
                ),
            )
        return p

    @classmethod
    def load(cls, path: str | Path) -> WorkloadProfile:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise WorkloadError(f"workload profile not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise WorkloadError(f"workload profile is not valid JSON: {exc}") from exc
        return cls.from_dict(data)


def _today() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _pick(row: dict, names: tuple[str, ...]):
    for n in names:
        if n in row and row[n] is not None:
            return row[n]
    return None


def _cv2(values: list[float]) -> float | None:
    """Squared coefficient of variation: variance over mean squared."""
    if len(values) < 2:
        return None
    mean = statistics.fmean(values)
    if mean <= 0:
        return None
    return statistics.pvariance(values) / (mean * mean)


def _parse_timestamp(raw) -> float | None:
    """Epoch seconds from a float, an int, or an ISO-8601 string."""
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return _dt.datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def from_log(path: str | Path, *, engine: str = "unknown") -> WorkloadProfile:
    """Derive a profile from a JSONL request log -- one JSON object per request.

    This is the exact path: per-request token counts give a real distribution, so
    the mean AND the variance are measured rather than reconstructed from buckets.
    """
    p = Path(path)
    try:
        raw_lines = p.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise WorkloadError(f"request log not found: {path}") from exc

    rows: list[dict] = []
    bad = 0
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            bad += 1
            continue
        if isinstance(obj, dict):
            rows.append(obj)
        else:
            bad += 1
    if not rows:
        raise WorkloadError(
            f"no JSON objects found in {path}: expected JSONL, one request per line"
        )

    profile = WorkloadProfile(captured_at=_today(), source=str(p), engine=engine)
    profile.sample_count = len(rows)
    if bad:
        profile.notes.append(f"{bad} line(s) were not JSON objects and were skipped")

    stamps = [t for t in (_parse_timestamp(_pick(r, LOG_FIELDS["timestamp"])) for r in rows) if t]
    if len(stamps) >= 2:
        window = max(stamps) - min(stamps)
        if window > 0:
            profile.window_seconds = window
            profile.request_rate = Field(
                round(len(rows) / window, 4),
                PROV_MEASURED,
                f"{len(rows)} requests over {window:.0f}s",
            )
            # Inter-arrival variability drives the queueing tail, so it is derived
            # from the arrivals themselves rather than borrowed from a preset.
            gaps = [b - a for a, b in zip(sorted(stamps), sorted(stamps)[1:]) if b > a]
            cv2 = _cv2(gaps) if len(gaps) >= MIN_SAMPLES_FOR_VARIANCE else None
            if cv2 is not None:
                profile.workload_cv2 = Field(
                    round(cv2, 4), PROV_MEASURED, f"from {len(gaps)} inter-arrival gaps"
                )
            elif gaps:
                profile.notes.append(
                    f"only {len(gaps)} inter-arrival gaps (< {MIN_SAMPLES_FOR_VARIANCE}); "
                    "a CV^2 from that few is noise, so it is left absent"
                )
    if profile.request_rate is None:
        profile.absent.append("request_rate")
        profile.notes.append(
            "no usable timestamps: expected one of "
            f"{', '.join(LOG_FIELDS['timestamp'])} as epoch seconds or ISO-8601"
        )
    if profile.workload_cv2 is None and "workload_cv2" not in profile.absent:
        profile.absent.append("workload_cv2")

    for name, key in (("prompt_tokens", "prompt_tokens"), ("output_tokens", "decode_tokens")):
        vals = [
            float(v)
            for v in (_pick(r, LOG_FIELDS[key]) for r in rows)
            if isinstance(v, (int, float))
        ]
        if vals:
            setattr(
                profile,
                name,
                Field(round(statistics.fmean(vals), 2), PROV_MEASURED, f"mean of {len(vals)}"),
            )
        else:
            profile.absent.append(name)
            profile.notes.append(f"{name}: none of {', '.join(LOG_FIELDS[key])} present in the log")

    cached = [
        float(v)
        for v in (_pick(r, LOG_FIELDS["cached_tokens"]) for r in rows)
        if isinstance(v, (int, float))
    ]
    prompts = [
        float(v)
        for v in (_pick(r, LOG_FIELDS["prompt_tokens"]) for r in rows)
        if isinstance(v, (int, float))
    ]
    if cached and prompts and sum(prompts) > 0:
        profile.prefix_cache_hit_rate = Field(
            round(min(sum(cached) / sum(prompts), 1.0), 4),
            PROV_MEASURED,
            "cached prompt tokens / total prompt tokens",
        )
    else:
        profile.absent.append("prefix_cache_hit_rate")
    return profile


_SAMPLE = re.compile(r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)(?P<labels>\{[^}]*\})?\s+(?P<value>\S+)$")


def parse_prometheus(text: str) -> dict[str, list[tuple[dict, float]]]:
    """Parse a Prometheus text exposition into {name: [(labels, value), ...]}."""
    out: dict[str, list[tuple[dict, float]]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _SAMPLE.match(line)
        if not m:
            continue
        try:
            value = float(m.group("value"))
        except ValueError:
            continue
        labels: dict[str, str] = {}
        if m.group("labels"):
            for part in m.group("labels")[1:-1].split(","):
                if "=" in part:
                    k, _, v = part.partition("=")
                    labels[k.strip()] = v.strip().strip('"')
        out.setdefault(m.group("name"), []).append((labels, value))
    return out


def _total(samples: dict, name: str) -> float | None:
    rows = samples.get(name)
    return sum(v for _, v in rows) if rows else None


def _hist_stats(samples: dict, base: str) -> tuple[float, float | None, int] | None:
    """Mean, bucket-approximated CV^2, and count for a Prometheus histogram.

    The sum and count are exact, so the mean is exact. The spread is only visible
    through bucket boundaries, so the CV^2 is computed at bucket midpoints and is
    an approximation -- callers label it accordingly and never as measured.
    """
    total = _total(samples, f"{base}_sum")
    count = _total(samples, f"{base}_count")
    if total is None or not count:
        return None
    mean = total / count
    buckets = samples.get(f"{base}_bucket") or []
    edges: list[tuple[float, float]] = []
    for labels, cumulative in buckets:
        le = labels.get("le")
        if le is None:
            continue
        edges.append((math.inf if le in ("+Inf", "Inf") else float(le), cumulative))
    cv2 = None
    if len(edges) >= 2 and mean > 0:
        edges.sort(key=lambda e: e[0])
        prev_edge, prev_cum, sq = 0.0, 0.0, 0.0
        for edge, cum in edges:
            n = cum - prev_cum
            if n > 0:
                # The open-ended +Inf bucket has no midpoint; the bucket floor is
                # the only defensible representative and it understates the tail.
                mid = prev_edge if math.isinf(edge) else (prev_edge + edge) / 2.0
                sq += n * mid * mid
            prev_edge, prev_cum = (prev_edge if math.isinf(edge) else edge), cum
        var = sq / count - mean * mean
        if var > 0:
            cv2 = var / (mean * mean)
    return mean, cv2, int(count)


def from_metrics(
    text: str, *, engine: str, source: str, engine_version: str = "unknown"
) -> WorkloadProfile:
    """Derive a profile from a Prometheus `/metrics` scrape.

    Rate needs two scrapes to be a rate, so a single scrape reports totals and
    distributions and leaves `request_rate` absent rather than dividing a counter
    by a process uptime nobody measured.
    """
    if engine not in ENGINE_METRICS:
        raise WorkloadError(
            f"unknown engine {engine!r}: metric names differ per engine and per "
            "version, and guessing one fabricates a measurement. Known engines: "
            f"{', '.join(sorted(ENGINE_METRICS))}"
        )
    names = ENGINE_METRICS[engine]
    samples = parse_prometheus(text)
    if not samples:
        raise WorkloadError(f"no Prometheus samples parsed from {source}")

    seen_prefix = any(k.startswith(names["prefix"]) for k in samples)
    if not seen_prefix:
        found = sorted({k.split(":")[0] + ":" for k in samples if ":" in k})
        raise WorkloadError(
            f"no {names['prefix']} metrics in {source} -- this does not look like a "
            f"{engine} endpoint. Prefixes present: {', '.join(found) or 'none'}"
        )

    profile = WorkloadProfile(
        captured_at=_today(), source=source, engine=engine, engine_version=engine_version
    )
    profile.notes.append(
        "a single scrape shows totals and distributions, not a rate: request_rate "
        "must still be supplied explicitly, or derived from a request log"
    )
    profile.absent.append("request_rate")

    for field_name, key in (("prompt_tokens", "prompt_tokens"), ("output_tokens", "decode_tokens")):
        metric = names.get(key)
        stats = _hist_stats(samples, metric) if metric else None
        if stats:
            mean, _, count = stats
            profile.sample_count = max(profile.sample_count, count)
            setattr(
                profile,
                field_name,
                Field(round(mean, 2), PROV_MEASURED, f"{metric} sum/count over {count} requests"),
            )
        else:
            profile.absent.append(field_name)
            profile.notes.append(
                f"{field_name}: {metric or 'no metric'} not exposed by this {engine} build"
            )

    e2e = _hist_stats(samples, names["e2e_latency"]) if names.get("e2e_latency") else None
    if e2e:
        _, cv2, count = e2e
        profile.sample_count = max(profile.sample_count, count)
        if cv2 is not None:
            profile.workload_cv2 = Field(
                round(cv2, 4),
                # Buckets, not samples: this is an approximation by construction.
                PROV_ESTIMATED,
                f"approximated from {names['e2e_latency']} bucket midpoints",
            )
    if profile.workload_cv2 is None:
        profile.absent.append("workload_cv2")

    if engine == "vllm":
        hits = _total(samples, names["prefix_cache_hits"])
        queries = _total(samples, names["prefix_cache_queries"])
        if hits is not None and queries:
            profile.prefix_cache_hit_rate = Field(
                round(min(hits / queries, 1.0), 4),
                PROV_MEASURED,
                f"{names['prefix_cache_hits']} / {names['prefix_cache_queries']}",
            )
    elif engine == "sglang":
        rate = _total(samples, names["cache_hit_rate"])
        if rate is not None:
            # SGLang publishes a percentage gauge, not the two counters.
            profile.prefix_cache_hit_rate = Field(
                round(min(rate / 100.0 if rate > 1 else rate, 1.0), 4),
                PROV_MEASURED,
                names["cache_hit_rate"],
            )
    if profile.prefix_cache_hit_rate is None:
        profile.absent.append("prefix_cache_hit_rate")

    running = _total(samples, names["running"]) if names.get("running") else None
    if running is not None:
        profile.peak_concurrency = Field(
            running, PROV_MEASURED, f"{names['running']} at scrape time (instantaneous)"
        )
    waiting = _total(samples, names["waiting"]) if names.get("waiting") else None
    if waiting is not None:
        profile.queue_depth = Field(
            waiting, PROV_MEASURED, f"{names['waiting']} at scrape time (instantaneous)"
        )
    return profile


def fetch_metrics(url: str, timeout: float = 10.0) -> str:
    """GET a `/metrics` endpoint. Needs httpx (the ``resolve`` extra)."""
    try:
        import httpx
    except ImportError as exc:
        raise WorkloadError(
            'scraping /metrics needs httpx: pip install "chimeraforge[resolve]"'
        ) from exc
    try:
        r = httpx.get(url, timeout=timeout)
        r.raise_for_status()
    except Exception as exc:  # httpx raises several distinct types here
        raise WorkloadError(f"could not scrape {url}: {exc}") from exc
    return r.text


def format_markdown(profile: WorkloadProfile) -> str:
    """Render the profile as a short human-readable summary."""
    out = [
        f"# Workload profile ({profile.engine})",
        "",
        f"- **Captured:** {profile.captured_at}",
        f"- **Source:** {profile.source}",
        f"- **Engine:** {profile.engine} {profile.engine_version}",
        f"- **Requests observed:** {profile.sample_count}",
        "",
        "| Field | Value | Provenance |",
        "|---|---|---|",
    ]
    for name in (
        "request_rate",
        "prompt_tokens",
        "output_tokens",
        "workload_cv2",
        "prefix_cache_hit_rate",
        "peak_concurrency",
        "queue_depth",
    ):
        f = getattr(profile, name)
        if f is not None:
            out.append(f"| {name} | {f.value} | {f.provenance} -- {f.note} |")
    if profile.absent:
        out += [
            "",
            "## Not measured",
            "",
            "These stay required inputs to `plan`; they are not defaulted.",
            "",
        ]
        out += [f"- {a}" for a in profile.absent]
    if profile.notes:
        out += ["", "## Notes", ""] + [f"- {n}" for n in profile.notes]
    return "\n".join(out) + "\n"
