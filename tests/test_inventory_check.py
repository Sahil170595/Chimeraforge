"""Inventory arithmetic is not physical capacity or deployment qualification."""

import asyncio
from decimal import Inexact, Rounded, ROUND_DOWN, ROUND_UP, localcontext
import json
import sys

import pytest
from typer.testing import CliRunner

from chimeraforge import api
from chimeraforge.cli import app
from test_deploy import artifact
from test_deploy_fleets import GROUPS, native_fleet as native_fleet


def uuid(index):
    return f"GPU-{index:08x}-1111-2222-3333-444444444444"


def csv_row(index=0, free="2048", total="4096", mig="N/A"):
    return f"{index}, {uuid(index)}, NVIDIA fixture, {total}, {free}, 595.00, {mig}\n"


def process_fixture(monkeypatch, raw):
    from chimeraforge import inventory_process

    monkeypatch.setattr(
        inventory_process,
        "COMMAND",
        (sys.executable, "-B", "-c", f"import sys;sys.stdout.buffer.write({raw!r})"),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("rounding", [ROUND_DOWN, ROUND_UP])
@pytest.mark.parametrize(
    "free,expected", [("1024", 4), ("1029.12", 0), ("1018.88", 4), ("1018.879", 5)]
)
async def test_public_hand_calculated_boundaries_ignore_hostile_decimal_context(
    monkeypatch, free, expected, rounding
):
    process_fixture(monkeypatch, csv_row(free=free).encode())
    saved = artifact(candidate_changes={"vram_gb": 1.0})
    before = saved.to_dict()
    with localcontext() as context:
        context.prec = 2
        context.rounding = rounding
        context.Emax, context.Emin = 2, -2
        context.traps[Inexact] = context.traps[Rounded] = True
        original = context.copy()
        result = await api.check_inventory(saved, gpu_devices=["0"])
        assert context.prec == original.prec and context.traps == original.traps
        assert context.rounding == original.rounding
    assert result.exit_code == expected
    data = result.to_dict()
    assert data["baseline"]["lower_gib"] == "0.995"
    assert data["baseline"]["upper_gib"] == "1.005"
    assert data["deployment_ready"] is None
    assert data["baseline"]["saved_effective_batch"] == 4
    assert saved.to_dict() == before


@pytest.mark.asyncio
async def test_full_native_population_in_original_order(native_fleet, monkeypatch):
    saved, indices = native_fleet
    raw = "".join(csv_row(i, free="100000", total="100000") for i in (2, 3, 4, 7, 8, 9))
    process_fixture(monkeypatch, raw.encode())
    before = saved.to_dict()
    result = await api.check_inventory(
        saved, candidate_index=indices["vllm"], replica_gpu_devices=GROUPS
    )
    assert result.exit_code == 0
    assert [(slot.replica_index, slot.device_index, slot.selector) for slot in result.slots] == [
        (r, d, value) for r, group in enumerate(GROUPS) for d, value in enumerate(group)
    ]
    assert [slot.device.uuid for slot in result.slots] == [
        uuid(int(value)) for group in GROUPS for value in group
    ]
    assert result.to_dict()["declared_coverage"] == {
        "expected": 6,
        "present": 6,
        "absent": 0,
        "unknown": 0,
    }
    assert saved.to_dict() == before


@pytest.mark.asyncio
@pytest.mark.parametrize("mig", ["Enabled", "Disabled", "N/A", "[N/A]"])
async def test_mig_does_not_change_arithmetic_or_certify_physical_pools(monkeypatch, mig):
    process_fixture(monkeypatch, csv_row(mig=mig).encode())
    result = await api.check_inventory(
        artifact(candidate_changes={"vram_gb": 1.0}), gpu_devices=[uuid(0).upper()]
    )
    assert result.exit_code == 0 and result.slots[0].device.mig_mode_raw == mig
    assert result.deployment_ready is None
    assert "independent_memory_pools" in result.unassessed
    assert "total_free" not in json.dumps(result.to_dict())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"broken\n",
        b"\xff",
        (csv_row() * 2).encode(),
        csv_row(free="NaN").encode(),
        csv_row(free="1e999999").encode(),
        csv_row(free="4097").encode(),
    ],
)
async def test_malformed_inventory_never_infers_selector_absence(monkeypatch, raw):
    process_fixture(monkeypatch, raw)
    result = await api.check_inventory(artifact(), gpu_devices=["99"])
    assert result.exit_code == 4 and result.observation.state == "unknown"
    assert result.slots[0].selector_state == "unknown" and result.slots[0].device is None
    assert not result.observation.devices


@pytest.mark.asyncio
async def test_complete_missing_selector_and_no_total_for_unavailable_free(monkeypatch):
    process_fixture(monkeypatch, csv_row(free="N/A").encode())
    saved = artifact(candidate_changes={"vram_gb": 1.0})
    result = await api.check_inventory(saved, gpu_devices=["0"])
    assert result.exit_code == 4 and result.slots[0].selector_state == "present"
    assert result.slots[0].total_comparison == "at_least_saved_baseline"
    missing = await api.check_inventory(saved, gpu_devices=["99"])
    assert missing.exit_code == 5 and missing.slots[0].selector_state == "absent"


@pytest.mark.asyncio
async def test_known_free_can_pass_with_diagnostic_total_unavailable(monkeypatch):
    process_fixture(monkeypatch, csv_row(free="2048", total="N/A").encode())
    result = await api.check_inventory(
        artifact(candidate_changes={"vram_gb": 1.0}), gpu_devices=["0"]
    )
    assert result.exit_code == 0
    assert result.slots[0].total_comparison == "unknown"
    assert result.slots[0].device.memory_total_mib is None


@pytest.mark.asyncio
async def test_standard_comma_space_quoted_gpu_name(monkeypatch):
    raw = csv_row().replace("NVIDIA fixture", '"GPU, Example"')
    process_fixture(monkeypatch, raw.encode())
    result = await api.check_inventory(
        artifact(candidate_changes={"vram_gb": 1.0}), gpu_devices=["0"]
    )
    assert result.exit_code == 0 and result.slots[0].device.name == "GPU, Example"


@pytest.mark.asyncio
async def test_huge_integer_timeout_is_invalid_before_contact(monkeypatch):
    from chimeraforge import inventory_process

    async def forbidden(*args, **kwargs):
        pytest.fail("invalid timeout contacted native process")

    monkeypatch.setattr(inventory_process, "observe", forbidden)
    with pytest.raises(api.InventoryCheckError):
        await api.check_inventory(artifact(), gpu_devices=["0"], timeout=10**1000)


@pytest.mark.asyncio
@pytest.mark.parametrize("devices", [None, [], ["00"], ["0", "0"], ["0", uuid(0)]])
async def test_invalid_selection_refused_before_native_contact(monkeypatch, devices):
    from chimeraforge import inventory_process

    async def forbidden(*args, **kwargs):
        pytest.fail("invalid selection contacted native process")

    monkeypatch.setattr(inventory_process, "observe", forbidden)
    with pytest.raises(api.InventoryCheckError):
        await api.check_inventory(artifact(), gpu_devices=devices)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes", [{"offload_fraction": 0.5}, {"vram_gb": None}, {"vram_gb": 1e200}]
)
async def test_valid_unsupported_baseline_retains_slots_without_contact(monkeypatch, changes):
    from chimeraforge import inventory_process

    async def forbidden(*args, **kwargs):
        pytest.fail("unsupported baseline contacted native process")

    monkeypatch.setattr(inventory_process, "observe", forbidden)
    result = await api.check_inventory(artifact(candidate_changes=changes), gpu_devices=["0"])
    assert result.exit_code == 4 and len(result.slots) == 1
    assert result.slots[0].device is None and result.observation.state == "not_started"


def test_cli_rejects_bad_input_without_native_process(tmp_path):
    saved = tmp_path / "saved.json"
    artifact().save(saved)
    result = CliRunner().invoke(
        app, ["inventory-check", "--plan", str(saved), "--gpu-device", "00", "--json"]
    )
    assert result.exit_code == 1 and json.loads(result.stdout)["exit_code"] == 1


@pytest.mark.asyncio
async def test_cancel_during_pending_launch_and_again_during_cleanup_does_not_orphan(monkeypatch):
    from chimeraforge import inventory_process

    original = asyncio.create_subprocess_exec
    launched, release = asyncio.Event(), asyncio.Event()
    children = []

    async def delayed_launch(*args, **kwargs):
        child = await original(sys.executable, "-B", "-c", "import time;time.sleep(60)", **kwargs)
        children.append(child)
        launched.set()
        await release.wait()
        return child

    monkeypatch.setattr(asyncio, "create_subprocess_exec", delayed_launch)
    before = set(asyncio.all_tasks())
    task = asyncio.create_task(inventory_process.observe(2))
    await asyncio.wait_for(launched.wait(), 5)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 5)
    assert len(children) == 1 and children[0].returncode is not None
    assert not [
        value
        for value in asyncio.all_tasks() - before
        if value is not asyncio.current_task() and not value.done()
    ]
