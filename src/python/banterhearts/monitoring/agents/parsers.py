"""Parsers for turning log output into MetricPoints."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Dict, Iterable, List

from ..analysis import MetricPoint


LAT_RE = re.compile(r"latency_ms[=:]\s*(?P<lat>[\d\.]+)", re.IGNORECASE)
TP_RE = re.compile(r"throughput[=\s:](?P<tp>[\d\.]+)", re.IGNORECASE)


def parse_log_lines(lines: Iterable[str], default_tags: Dict[str, str] | None = None) -> List[MetricPoint]:
    tags = default_tags or {}
    points: List[MetricPoint] = []

    for line in lines:
        if "{" in line and "}" in line:
            try:
                payload = json.loads(line)
                if isinstance(payload, dict):
                    for key in ("latency_ms", "ttft_ms", "throughput_tok_s"):
                        if key in payload:
                            points.append(
                                MetricPoint(
                                    key,
                                    float(payload[key]),
                                    "ms" if key.endswith("ms") else "tok/s",
                                    tags={**tags, "source": "json_log"},
                                )
                            )
                    continue
            except Exception:
                pass

        lat_match = LAT_RE.search(line)
        if lat_match:
            points.append(
                MetricPoint(
                    "latency_ms",
                    float(lat_match.group("lat")),
                    "ms",
                    tags={**tags, "source": "text_log"},
                )
            )

        tp_match = TP_RE.search(line)
        if tp_match:
            points.append(
                MetricPoint(
                    "throughput_tok_s",
                    float(tp_match.group("tp")),
                    "tok/s",
                    tags={**tags, "source": "text_log"},
                )
            )

    return points
