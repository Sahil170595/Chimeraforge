"""Full saved selector populations compared with one reported NVIDIA inventory view."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
import logging
import math
from pathlib import Path
from typing import TYPE_CHECKING

from chimeraforge import __version__
from chimeraforge import inventory_process
from chimeraforge.inventory_numbers import (
    SERIALIZATION_HALF_INTERVAL,
    number,
    decimal_text,
    comparison,
)
from chimeraforge.inventory_types import (
    InventoryBaseline,
    InventoryCheck,
    InventoryCheckError,
    InventoryObservation,
    InventorySlot,
)

if TYPE_CHECKING:
    from chimeraforge.api import PlanArtifact
    from chimeraforge.planner.engine import Candidate

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_TIMEOUT_SECONDS = 60.0
# Wider than current GPU memory while keeping every rendered bound small.
MAX_SAVED_BASELINE_GIB = 10**9


def _baseline(candidate: Candidate) -> InventoryBaseline:
    try:
        r = candidate.vram_gb
        if type(r) not in (int, float) or not math.isfinite(r):
            raise ValueError("unknown saved baseline")
        value = number(str(r))
        if value > MAX_SAVED_BASELINE_GIB:
            raise ValueError("saved baseline exceeds supported range")
        return InventoryBaseline(
            decimal_text(value),
            decimal_text(max(Fraction(0), value - SERIALIZATION_HALF_INTERVAL)),
            decimal_text(value + SERIALIZATION_HALF_INTERVAL),
            "saved_modeled_batch1_per_gpu",
            candidate.effective_batch,
        )
    except (ValueError, OverflowError) as exc:
        logger.info("saved inventory baseline unsupported (%s)", type(exc).__name__)
        return InventoryBaseline(
            None, None, None, "unsupported", candidate.effective_batch, "saved_baseline_unsupported"
        )


def _admit(
    saved: PlanArtifact | str | Path,
    index: int,
    devices: list[str] | None,
    groups: list[list[str]] | None,
    timeout: float,
) -> tuple[PlanArtifact, Candidate, list[list[str]]]:
    from chimeraforge.deploy import (
        DeploymentError,
        MAX_EXPORT_GPUS_PER_REPLICA,
        _device_selection,
        _replica_device_selection,
    )
    from chimeraforge.deployment_verify import _source
    from chimeraforge.planner.constants import MAX_REPLICAS

    try:
        if (
            type(timeout) not in (int, float)
            or not 0 < timeout <= MAX_TIMEOUT_SECONDS
            or not math.isfinite(timeout)
        ):
            raise ValueError("invalid timeout")
        artifact, _, _ = _source(saved)
        candidate = artifact.candidate(index)
        n, tp, pp = candidate.n_agents, candidate.tensor_parallel, candidate.pipeline_parallel
        if (
            any(type(v) is not int or v < 1 for v in (n, tp, pp))
            or n > MAX_REPLICAS
            or tp * pp > MAX_EXPORT_GPUS_PER_REPLICA
            or candidate.gpus_total != n * tp * pp
        ):
            raise ValueError("invalid original candidate population")
        if n == 1:
            if groups is not None or devices is None:
                raise ValueError("one replica needs explicit singular selectors")
            selected = _device_selection(devices, tp * pp)
            assert selected is not None
            layout = [selected]
        else:
            if devices is not None:
                raise ValueError("singular selectors cannot replace original replicas")
            layout = _replica_device_selection(candidate, groups)
        return artifact, candidate, layout
    except (ValueError, OSError, TypeError, KeyError, RecursionError, DeploymentError) as exc:
        logger.info("inventory input admission refused (%s)", type(exc).__name__)
        raise InventoryCheckError(
            "Invalid saved inventory source or selector declarations."
        ) from None


async def check_inventory(
    saved: PlanArtifact | str | Path,
    *,
    candidate_index: int = 0,
    gpu_devices: list[str] | None = None,
    replica_gpu_devices: list[list[str]] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> InventoryCheck:
    """Check declared selectors and saved B1 arithmetic, never deployment eligibility."""
    from chimeraforge.deploy import DeploymentError, _validate_fidelity

    artifact, candidate, layout = _admit(
        saved, candidate_index, gpu_devices, replica_gpu_devices, timeout
    )
    data = artifact.to_dict()
    baseline = _baseline(candidate)
    reason = baseline.reason
    try:
        inputs = data["inputs"]
        inputs["kv_quant"] = inputs["kv_quant"].lower()
        _validate_fidelity(
            candidate, artifact.spec(candidate.model), inputs, data["result"]["platform"], "compose"
        )
    except DeploymentError as exc:
        logger.info("saved inventory fidelity unsupported (%s)", type(exc).__name__)
        reason = "saved_fidelity_unsupported"
        baseline = replace(baseline, basis="unsupported", reason=reason)
    observation = InventoryObservation("not_started", inventory_process.COMMAND, reason=reason)
    if reason is None:
        observation = await inventory_process.observe(timeout)
    by_id = {key: row for row in observation.devices for key in (row.ordinal, row.uuid)}
    slots = []
    for replica, group in enumerate(layout):
        for position, selector in enumerate(group):
            if observation.state != "complete":
                slot = InventorySlot(
                    replica,
                    position,
                    selector,
                    "unknown",
                    reasons=(observation.reason or "observation_unavailable",),
                )
            elif selector not in by_id:
                slot = InventorySlot(
                    replica,
                    position,
                    selector,
                    "absent",
                    reasons=("selector_absent_from_queried_view",),
                )
            else:
                device = by_id[selector]
                free = comparison(device.memory_free_mib, baseline.lower_gib, baseline.upper_gib)
                total = comparison(device.memory_total_mib, baseline.lower_gib, baseline.upper_gib)
                slot = InventorySlot(
                    replica,
                    position,
                    selector,
                    "present",
                    device,
                    free,
                    total,
                    ("reported_memory_unavailable_or_overlap",)
                    if "unknown" in (free, total)
                    else (),
                )
            slots.append(slot)
    return InventoryCheck(
        __version__, data["fingerprint"], candidate_index, baseline, observation, tuple(slots)
    )
