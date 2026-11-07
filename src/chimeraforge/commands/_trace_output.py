"""Read-only receipt destination admission before native trace replay."""

from __future__ import annotations

import os
from pathlib import Path
import stat

from chimeraforge.api import PlanError


class TraceOutputError(PlanError):
    """A receipt destination is unusable before replay starts."""


def _mode(path: Path, *, follow_symlinks: bool = False) -> int | None:
    if os.name == "nt":
        reserved = getattr(os.path, "isreserved", None)
        is_reserved = reserved(path) if reserved is not None else path.is_reserved()
        if is_reserved:
            raise TraceOutputError("trace receipt output uses a reserved path")
    try:
        return path.stat(follow_symlinks=follow_symlinks).st_mode
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        raise TraceOutputError("trace receipt output path is unavailable") from None


def preflight_trace_output(path: Path, *, create_parents: bool = False) -> None:
    """Match the writer's parent policy without creating or opening anything."""
    mode = _mode(path)
    # Atomic replacement operates on the destination entry, including a symlink.
    if mode is not None and not (stat.S_ISREG(mode) or stat.S_ISLNK(mode)):
        raise TraceOutputError("trace receipt output must be a file destination")
    for parent in path.parents:
        mode = _mode(parent, follow_symlinks=True)
        if mode is not None:
            if stat.S_ISDIR(mode):
                return
            break
        if not create_parents or _mode(parent) is not None:
            break
    raise TraceOutputError("trace receipt output requires a directory parent")
