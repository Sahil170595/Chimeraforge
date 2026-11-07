"""Privacy-scoped static diagnostics for strict traces and whole native campaigns."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import InitVar, dataclass
import logging
from pathlib import Path
import unicodedata
from typing import cast

from chimeraforge.report.trace_formats import chunks
from chimeraforge.report.trace_inputs import hold
from chimeraforge.report.trace_view import projection

MAX_OUTPUT_BYTES = 8 * 1024 * 1024
MAX_TITLE_CHARS = 200
MAX_TITLE_BYTES = 1024
KINDS = {"trace", "fleet-trace", "trace-campaign", "fleet-trace-campaign"}
FORMATS = {"html", "markdown", "svg"}
LOG = logging.getLogger(__name__)


def admitted(content: str, profile: str = "trace report") -> bytes:
    from chimeraforge.api import PlanError

    try:
        if type(content) is not str:
            raise TypeError
        raw = content.encode("utf-8")
        if len(raw) > MAX_OUTPUT_BYTES or "\r" in content:
            raise ValueError
        return raw
    except (ValueError, TypeError, UnicodeError) as exc:
        LOG.info("Trace report bytes refused (%s)", type(exc).__name__)
        raise PlanError(f"complete {profile} exceeds its output profile") from None


@dataclass(frozen=True)
class TraceReport:
    """Admitted public artifact; runtime file guards are not persisted data fields."""

    content: str
    kind: str
    format: str
    _protected_paths: InitVar[tuple[Path, ...]] = ()

    def __post_init__(self, _protected_paths: tuple[Path, ...]) -> None:
        object.__setattr__(self, "_protected_paths", _protected_paths)

    @property
    def _input_paths(self) -> tuple[Path, ...]:
        return cast(tuple[Path, ...], object.__getattribute__(self, "_protected_paths"))

    def save(self, path: str | Path) -> None:
        from chimeraforge.api import PlanError
        from chimeraforge.bench.fleet_gate_output import _write
        from chimeraforge.plan_study import protect_output

        profile = "fleet monitor report" if self.kind == "fleet-monitor" else "trace report"
        try:
            raw = admitted(self.content, profile)
            protect_output(path, self._input_paths)
            _write(Path(path), raw)
        except (PlanError, OSError) as exc:
            LOG.info("Trace report publication refused (%s)", type(exc).__name__)
            raise PlanError(f"{profile} output unavailable") from None


def admit_title(title: str, profile: str = "trace report") -> None:
    from chimeraforge.api import PlanError

    try:
        if (
            type(title) is not str
            or not 0 < len(title) <= MAX_TITLE_CHARS
            or len(title.encode("utf-8")) > MAX_TITLE_BYTES
            or any(
                (unicodedata.category(c).startswith("C") or unicodedata.category(c) in {"Zl", "Zp"})
                for c in title
            )
        ):
            raise ValueError
    except (ValueError, UnicodeError):
        raise PlanError(f"{profile} title is outside its public profile") from None


def materialize(stream: Iterable[str], profile: str = "trace report") -> str:
    from chimeraforge.api import PlanError

    output = bytearray()
    for chunk in stream:
        raw = chunk.encode("utf-8")
        if len(raw) > MAX_OUTPUT_BYTES - len(output):
            raise PlanError(f"complete {profile} exceeds its output profile")
        output.extend(raw)
    return output.decode("utf-8")


def render_trace_report(
    source: object, *, kind: str = "trace", format: str = "html", title: str = "Trace diagnostics"
) -> TraceReport:
    """Validate one complete native input, then render a closed public presentation."""
    from chimeraforge.api import PlanError

    if (
        type(kind) is not str
        or kind not in KINDS
        or type(format) is not str
        or format not in FORMATS
    ):
        raise PlanError("unsupported trace report kind or format")
    admit_title(title)
    campaign = kind in {"trace-campaign", "fleet-trace-campaign"}
    if campaign:
        from chimeraforge.report.campaign_inputs import hold as hold_campaign
        from chimeraforge.report.campaign_view import projection as campaign_projection
        from chimeraforge.report.campaign_formats import chunks as campaign_chunks

        held = hold_campaign(source, kind)
        view = campaign_projection(held, kind)
        stream = campaign_chunks(view, title, format)
    else:
        held = hold(source, kind)
        view = projection(held, kind)
        stream = chunks(view, title, format)
    return TraceReport(materialize(stream), kind, format, held["protected_paths"])
