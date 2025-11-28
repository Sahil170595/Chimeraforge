"""Adapters for persisting monitoring metrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, Optional

from ..analysis import MetricPoint


class StorageAdapter:
    def __init__(self, path: Path, *, rotate_bytes: Optional[int] = None) -> None:
        self.path = Path(path)
        self.rotate_bytes = rotate_bytes
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _maybe_rotate(self) -> None:
        if not self.rotate_bytes:
            return
        if self.path.exists() and self.path.stat().st_size >= self.rotate_bytes:
            rotated = self.path.with_name(self.path.stem + ".1" + self.path.suffix)
            self.path.replace(rotated)

    def write_points(self, points: Iterable[MetricPoint]) -> None:
        self._maybe_rotate()
        with self.path.open("a", encoding="utf-8") as fh:
            for p in points:
                fh.write(
                    json.dumps(
                        {
                            "name": p.name,
                            "value": p.value,
                            "unit": p.unit,
                            "timestamp": p.timestamp.isoformat(),
                            "tags": p.tags,
                        }
                    )
                )
                fh.write("\n")

    def write_summary(self, summary: Dict[str, Dict[str, float]]) -> None:
        summary_path = self.path.with_suffix(".summary.json")
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
