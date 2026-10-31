"""Privacy-scoped static diagnostics for strict ordinary and whole-fleet traces."""

from __future__ import annotations

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
KINDS = {"trace", "fleet-trace"}
FORMATS = {"html", "markdown", "svg"}
LOG = logging.getLogger(__name__)


def admitted(content: str) -> bytes:
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
        raise PlanError("complete trace report exceeds its output profile") from None


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

        try:
            raw = admitted(self.content)
            protect_output(path, self._input_paths)
            _write(Path(path), raw)
        except (PlanError, OSError) as exc:
            LOG.info("Trace report publication refused (%s)", type(exc).__name__)
            raise PlanError("trace report output unavailable") from None


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
        raise PlanError("trace report title is outside its public profile") from None
    held = hold(source, kind)
    view = projection(held, kind)
    output = bytearray()
    for chunk in chunks(view, title, format):
        raw = chunk.encode("utf-8")
        if len(raw) > MAX_OUTPUT_BYTES - len(output):
            raise PlanError("complete trace report exceeds its output profile")
        output.extend(raw)
    return TraceReport(output.decode("utf-8"), kind, format, held["protected_paths"])
