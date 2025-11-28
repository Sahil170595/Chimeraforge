"""Thin wrapper around torch.profiler for optional usage."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

try:
    from torch.profiler import ProfilerActivity, profile, record_function  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    profile = None
    record_function = None
    ProfilerActivity = None


@contextmanager
def profile_inference(trace_path: Optional[Path] = None) -> Iterator[object]:
    if not profile or not ProfilerActivity:
        # Fallback no-op
        yield None
        return

    activities = [ProfilerActivity.CPU]
    try:
        activities.append(ProfilerActivity.CUDA)
    except Exception:
        pass

    with profile(activities=activities, record_shapes=True) as prof:
        yield prof
        if trace_path:
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            prof.export_chrome_trace(trace_path)


__all__ = ["profile_inference", "record_function"]
