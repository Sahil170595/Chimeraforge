"""A queried inventory view and saved-baseline arithmetic, without allocation claims."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

MemoryComparison = Literal["at_least_saved_baseline", "below_saved_baseline", "unknown"]

UNASSESSED = (
    "physical_identity",
    "independent_memory_pools",
    "partition_topology",
    "cuda_process_visibility",
    "hardware_equivalence",
    "engine_compatibility",
    "runtime_peak",
    "allocation",
    "deployment_eligibility",
)


class InventoryCheckError(ValueError):
    """Malformed original source, options or selector declarations."""


@dataclass(frozen=True)
class InventoryDevice:
    ordinal: str
    uuid: str
    name: str
    memory_total_mib: str | None
    memory_free_mib: str | None
    driver_version: str
    mig_mode_raw: str


@dataclass(frozen=True)
class InventoryBaseline:
    saved_gib: str | None
    lower_gib: str | None
    upper_gib: str | None
    basis: Literal["saved_modeled_batch1_per_gpu", "unsupported"]
    saved_effective_batch: int
    reason: str | None = None


@dataclass(frozen=True)
class InventorySlot:
    replica_index: int
    device_index: int
    selector: str
    selector_state: Literal["present", "absent", "unknown"]
    device: InventoryDevice | None = None
    free_comparison: MemoryComparison = "unknown"
    total_comparison: MemoryComparison = "unknown"
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class InventoryObservation:
    state: Literal["complete", "unknown", "not_started"]
    command: tuple[str, ...]
    started_at: str | None = None
    finished_at: str | None = None
    returncode: int | None = None
    reason: str | None = None
    devices: tuple[InventoryDevice, ...] = ()
    stdout_sha256: str | None = None
    cleanup_state: Literal["completed", "not_started", "failed"] = "not_started"


@dataclass(frozen=True)
class InventoryCheck:
    tool_version: str
    plan_fingerprint: str
    candidate_index: int
    baseline: InventoryBaseline
    observation: InventoryObservation
    slots: tuple[InventorySlot, ...]
    schema_version: int = 1
    scope: Literal["queried_inventory_and_saved_b1_memory"] = (
        "queried_inventory_and_saved_b1_memory"
    )
    deployment_ready: None = None
    unassessed: tuple[str, ...] = UNASSESSED

    @property
    def exit_code(self) -> int:
        if self.observation.state != "complete" or self.observation.cleanup_state != "completed":
            return 4
        if any(
            slot.selector_state == "absent" or slot.free_comparison == "below_saved_baseline"
            for slot in self.slots
        ):
            return 5
        if not self.slots or any(
            slot.selector_state != "present" or slot.free_comparison != "at_least_saved_baseline"
            for slot in self.slots
        ):
            return 4
        return 0

    @property
    def outcome(self) -> Literal["pass", "unknown", "mismatch"]:
        return "pass" if self.exit_code == 0 else "mismatch" if self.exit_code == 5 else "unknown"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.update(exit_code=self.exit_code, outcome=self.outcome)
        data["declared_coverage"] = {
            "expected": len(self.slots),
            **{
                key: sum(slot.selector_state == key for slot in self.slots)
                for key in ("present", "absent", "unknown")
            },
        }
        return data
