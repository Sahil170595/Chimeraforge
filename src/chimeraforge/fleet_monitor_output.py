"""Replica-labelled native gauges and atomic textfile replacement."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

from chimeraforge.fleet_monitor_types import FleetMonitorError, FleetMonitorReport
from chimeraforge.monitor import MonitorReport, _escape_label, prometheus_text as native_text


def prometheus_text(report: FleetMonitorReport) -> str:
    headers: dict[str, str] = {}
    samples: list[str] = []
    for slot in report.slots:
        native = MonitorReport(
            report.backend,
            report.model,
            slot.slo,
            slot.windows,
            slot.state != "complete",
            plan_binding=slot.binding,
        )
        for line in native_text(native).splitlines():
            if line.startswith("#"):
                parts = line.split(" ", 3)
                parts[2] = parts[2].replace("chimeraforge_monitor_", "chimeraforge_fleet_slot_", 1)
                line = " ".join(parts)
                headers.setdefault(" ".join(line.split()[:3]), line)
            else:
                name, labels = line.split("{", 1)
                line = (
                    name.replace("chimeraforge_monitor_", "chimeraforge_fleet_slot_", 1)
                    + "{"
                    + labels
                )
                samples.append(line.replace("{", f'{{replica="{_escape_label(slot.id)}",', 1))
    name = "chimeraforge_fleet_qualification"
    headers[name + " help"] = f"# HELP {name} Qualification of all declared endpoints only."
    headers[name + " type"] = f"# TYPE {name} gauge"
    for outcome, code in (("pass", 0), ("breach", 3), ("unknown", 4), ("mismatch", 5)):
        samples.append(f'{name}{{outcome="{outcome}"}} {int(report.exit_code == code)}')
    return "\n".join([*headers.values(), *samples]) + "\n"


def write_prometheus(report: FleetMonitorReport, path: str | Path) -> None:
    target, temporary = Path(path), None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target.parent, delete=False, suffix=".tmp"
        ) as stream:
            temporary = Path(stream.name)
            stream.write(prometheus_text(report))
        temporary.replace(target)
    except OSError:
        raise FleetMonitorError("cannot atomically replace fleet Prometheus output") from None
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
