"""Read-only local platform check: what is here, and what the planner can do with it.

Per vendor, because detection is vendor-specific: NVIDIA (pynvml / nvidia-smi),
AMD (amd-smi, then the legacy rocm-smi), Apple Silicon (system_profiler), Intel
(xpu-smi), and on Windows the CIM + display-class registry route that works for
any vendor. Each probe reports only what its tool said, names the tool, and
records why it found nothing -- a missing tool is a finding, not an error.

Nothing here changes state. The report says, per device, whether the planner can
model it today (matched in the GPU database, plannable only with supplied
figures, or not representable yet), so the fix that follows has a check to
be measured against.

Parsers are pure functions over captured tool output and are golden-tested
against real captures in tests/fixtures/doctor/.
"""

from __future__ import annotations

import json
import logging
import os
import platform as _platform
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass, field

logger = logging.getLogger(__name__)

# A probe that hangs is reported as timed out; the report must come back fast.
PROBE_TIMEOUT_S = 10

VENDOR_NVIDIA = "nvidia"
VENDOR_AMD = "amd"
VENDOR_APPLE = "apple"
VENDOR_INTEL = "intel"
VENDOR_OTHER = "other"

BYTES_PER_GB = 1024**3
MIB_PER_GB = 1024

# PCI vendor names as they appear in Windows adapter names.
_VENDOR_BY_NAME = (
    (re.compile(r"\bnvidia\b", re.I), VENDOR_NVIDIA),
    (re.compile(r"\b(amd|radeon|advanced micro devices)\b", re.I), VENDOR_AMD),
    (re.compile(r"\bintel\b", re.I), VENDOR_INTEL),
)

# Newer drivers print "CUDA UMD Version: 13.4"; older ones "CUDA Version: 12.2".
_CUDA_HEADER = re.compile(r"CUDA (?:UMD )?Version:\s*([0-9]+(?:\.[0-9]+)*)")

# The Windows display-adapter device class. Win32_VideoController.AdapterRAM is a
# uint32, so it tops out just under 4 GiB; the driver's QWORD in this class key
# holds the real figure.
WINDOWS_DISPLAY_CLASS = (
    r"HKLM:\SYSTEM\ControlSet001\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0*"
)
WINDOWS_ADAPTER_RAM_CAP = 2**32
WINDOWS_PROBE = (
    "$ErrorActionPreference='SilentlyContinue'; "
    "$a = @(Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion); "
    f"$r = @(Get-ItemProperty '{WINDOWS_DISPLAY_CLASS}' | "
    "Select-Object DriverDesc,'HardwareInformation.qwMemorySize'); "
    "@{adapters=$a; registry=$r} | ConvertTo-Json -Depth 3 -Compress"
)

Runner = Callable[[list[str]], "tuple[int, str, str]"]


@dataclass
class DetectedGPU:
    """One device, as its tool reported it."""

    vendor: str
    name: str
    vram_gb: float | None
    driver: str | None
    source: str
    unified_memory: bool = False
    notes: list[str] = field(default_factory=list)
    # Memory bandwidth as the vendor tool itself reported it (amd-smi does), so
    # an unlisted card's --gpu-bandwidth-gbps can come from the device, not a guess.
    bandwidth_gbps: float | None = None


@dataclass
class ProbeResult:
    """What one detection route found, or why it found nothing."""

    tool: str
    found: bool
    detail: str
    gpus: list[DetectedGPU] = field(default_factory=list)
    runtime: dict[str, str] = field(default_factory=dict)


@dataclass
class PlannerStatus:
    """What the planner can do with one detected device today."""

    gpu: str
    status: str  # "matched" | "supply-figures" | "not-representable"
    database_entry: str | None
    detail: str


@dataclass
class EngineProbe:
    backend: str
    url: str
    running: bool  # answered AND identified itself as this engine
    version: str | None
    detail: str
    answered: bool = False  # something on the port returned a healthy status


@dataclass
class DoctorReport:
    os: str
    os_version: str
    arch: str
    wsl: bool
    probes: list[ProbeResult]
    gpus: list[DetectedGPU]
    planner: list[PlannerStatus]
    engines: list[EngineProbe]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# -- command execution -------------------------------------------------------


def default_runner(cmd: list[str]) -> tuple[int, str, str]:
    """Run a probe command. Timeouts and launch failures come back as rc != 0."""
    try:
        done = subprocess.run(
            cmd, capture_output=True, text=True, timeout=PROBE_TIMEOUT_S, check=False
        )
        return done.returncode, done.stdout, done.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {PROBE_TIMEOUT_S}s"
    except OSError as exc:
        return 127, "", str(exc)


# -- pure parsers (golden-tested) --------------------------------------------


def parse_nvidia_smi_query(text: str) -> list[DetectedGPU]:
    """``nvidia-smi --query-gpu=index,name,memory.total,driver_version
    --format=csv,noheader,nounits`` -> one device per line (memory in MiB)."""
    gpus = []
    for line in text.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        _index, name, mib, driver = parts[:4]
        try:
            vram = round(float(mib) / MIB_PER_GB, 1)
        except ValueError:
            vram = None
        gpus.append(DetectedGPU(VENDOR_NVIDIA, name, vram, driver or None, "nvidia-smi"))
    return gpus


def parse_cuda_version_header(text: str) -> str | None:
    """The CUDA version from plain ``nvidia-smi`` output, either header spelling."""
    m = _CUDA_HEADER.search(text)
    return m.group(1) if m else None


def cuda_version_from_nvml(value: int) -> str:
    """NVML encodes CUDA 13.4 as 13040 (major * 1000 + minor * 10)."""
    return f"{value // 1000}.{(value % 1000) // 10}"


def vendor_from_name(name: str) -> str:
    for pattern, vendor in _VENDOR_BY_NAME:
        if pattern.search(name):
            return vendor
    return VENDOR_OTHER


def parse_windows_adapters(text: str) -> list[DetectedGPU]:
    """The WINDOWS_PROBE JSON -> one device per display adapter.

    VRAM comes from the registry QWORD where the driver writes one; otherwise
    from AdapterRAM, flagged when it sits at the uint32 cap (the true figure is
    then unknown, not 4 GB).
    """
    data = json.loads(text)
    adapters = data.get("adapters") or []
    registry = data.get("registry") or []
    if isinstance(adapters, dict):
        adapters = [adapters]
    if isinstance(registry, dict):
        registry = [registry]
    qword = {
        r.get("DriverDesc"): r.get("HardwareInformation.qwMemorySize")
        for r in registry
        if isinstance(r, dict)
    }
    gpus = []
    for a in adapters:
        name = (a.get("Name") or "").strip()
        if not name:
            continue
        notes: list[str] = []
        exact = qword.get(name)
        if isinstance(exact, int) and exact > 0:
            vram = round(exact / BYTES_PER_GB, 1)
        else:
            raw = a.get("AdapterRAM")
            vram = round(raw / BYTES_PER_GB, 1) if isinstance(raw, int) and raw > 0 else None
            if isinstance(raw, int) and raw >= WINDOWS_ADAPTER_RAM_CAP - BYTES_PER_GB:
                vram = None
                notes.append(
                    "AdapterRAM is at its 4 GB uint32 cap and the driver wrote no "
                    "qwMemorySize, so the real VRAM is unknown"
                )
            elif vram is not None:
                # Integrated GPUs typically write no qwMemorySize; their AdapterRAM
                # is a slice of system memory, not dedicated VRAM.
                notes.append(
                    "VRAM from AdapterRAM (no driver qwMemorySize): for an "
                    "integrated GPU this is a shared-memory aperture, not dedicated VRAM"
                )
        gpus.append(
            DetectedGPU(
                vendor_from_name(name),
                name,
                vram,
                a.get("DriverVersion"),
                "windows-cim",
                notes=notes,
            )
        )
    return gpus


def _json_after_banner(text: str):
    """JSON that may follow a plain-text banner (amd-smi prints a permission
    warning first when the user is not in the render group)."""
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if not starts:
        raise json.JSONDecodeError("no JSON object in output", text, 0)
    return json.loads(text[min(starts) :])


def _known(value) -> str | None:
    """A tool field, or None where the tool said it could not read it."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() == "N/A" or text.startswith("AMDSMI_STATUS"):
        return None
    return text


def _amd_size_gb(size) -> float | None:
    """amd-smi ``{"value": 196592, "unit": "MB"}`` -> GB. Its "MB" is binary:
    196592 reads as the 192 GB AMD publishes for MI300X only as MiB (inferred
    from that match; AMD does not define the unit in the output)."""
    if not isinstance(size, dict):
        return None
    try:
        value = float(size.get("value"))
    except (TypeError, ValueError):
        return None
    unit = str(size.get("unit", "")).upper()
    if unit == "MB":
        return round(value / MIB_PER_GB, 1)
    if unit == "GB":
        return round(value, 1)
    return None


def parse_amd_smi_static(text: str) -> list[DetectedGPU]:
    """``amd-smi static --json``: a top-level list up to ROCm 6.4, and
    ``{"gpu_data": [...]}`` from ROCm 7.0."""
    data = _json_after_banner(text)
    items = data.get("gpu_data", []) if isinstance(data, dict) else data
    gpus = []
    for g in items or []:
        if not isinstance(g, dict):
            continue
        asic, vram = g.get("asic") or {}, g.get("vram") or {}
        name = _known(asic.get("market_name"))
        if not name:
            continue
        bandwidth = None
        bw = vram.get("max_bandwidth")
        if isinstance(bw, dict) and str(bw.get("unit", "")).upper() == "GB/S":
            try:
                bandwidth = float(bw.get("value"))
            except (TypeError, ValueError):
                bandwidth = None
        gpus.append(
            DetectedGPU(
                VENDOR_AMD,
                name,
                _amd_size_gb(vram.get("size")),
                _known((g.get("driver") or {}).get("version")),
                "amd-smi",
                bandwidth_gbps=bandwidth,
            )
        )
    return gpus


def parse_amd_smi_version(text: str) -> dict[str, str]:
    """``amd-smi version --json``: a one-item list, even on ROCm 7.2."""
    data = _json_after_banner(text)
    if isinstance(data, list):
        row = data[0] if data else {}
    else:
        row = data if isinstance(data, dict) else {}
    out = {}
    for key, label in (("rocm_version", "rocm"), ("amdgpu_version", "amdgpu-driver")):
        value = _known(row.get(key))
        if value:
            out[label] = value
    return out


def _bytes_to_gb(raw) -> float | None:
    if not _known(raw):
        return None
    try:
        return round(int(raw) / BYTES_PER_GB, 1)
    except (TypeError, ValueError):
        return None


def parse_rocm_smi(text: str) -> list[DetectedGPU]:
    """Legacy ``rocm-smi --showproductname --showmeminfo vram --json``: one
    ``cardN`` object each. "Card Series" can be a board string rather than a
    clean marketing name, so it is reported as given and matched only if it does."""
    data = _json_after_banner(text)
    gpus = []
    for key in sorted(k for k in data if k.startswith("card")):
        card = data[key] or {}
        name = _known(card.get("Card Series")) or key
        vram = _bytes_to_gb(card.get("VRAM Total Memory (B)"))
        gpus.append(DetectedGPU(VENDOR_AMD, name, vram, None, "rocm-smi"))
    return gpus


_GB_FIGURE = re.compile(r"\s*([0-9]+(?:\.[0-9]+)?)\s*GB")


def parse_system_profiler_hardware(text: str) -> list[DetectedGPU]:
    """``system_profiler SPHardwareDataType -json``: Apple Silicon names its chip
    in ``chip_type``, and the GPU shares ``physical_memory`` with the CPU."""
    data = json.loads(text)
    gpus = []
    for row in data.get("SPHardwareDataType") or []:
        chip = _known(row.get("chip_type"))
        if not chip:
            continue  # an Intel Mac reports cpu_type instead
        m = _GB_FIGURE.match(str(row.get("physical_memory", "")))
        gpus.append(
            DetectedGPU(
                VENDOR_APPLE,
                chip,
                float(m.group(1)) if m else None,
                None,
                "system_profiler",
                unified_memory=True,
                notes=["unified memory: the figure is the whole CPU+GPU pool"],
            )
        )
    return gpus


def parse_xpu_smi(text: str) -> list[DetectedGPU]:
    """``xpu-smi discovery -j`` (``device_list``) or ``discovery -d N -j`` (one
    device object). The name is PCI-ID style ("Intel(R) Graphics [0xe211]")."""
    data = json.loads(text)
    if isinstance(data, dict) and "device_list" in data:
        items = data["device_list"] or []
    else:
        items = [data]
    gpus = []
    for d in items:
        name = _known(d.get("device_name"))
        if not name:
            continue
        gpus.append(
            DetectedGPU(
                VENDOR_INTEL,
                name,
                _bytes_to_gb(d.get("memory_physical_size_byte")),
                _known(d.get("driver_version")),
                "xpu-smi",
            )
        )
    return gpus


# -- probes ------------------------------------------------------------------


def nvml_cuda_version() -> str | None:  # pragma: no cover - depends on a local driver
    """The driver's CUDA version via NVML, or None when NVML is absent."""
    try:
        import pynvml

        pynvml.nvmlInit()
        try:
            return cuda_version_from_nvml(pynvml.nvmlSystemGetCudaDriverVersion())
        finally:
            pynvml.nvmlShutdown()
    except Exception as exc:  # noqa: BLE001 - absent NVML is a finding, not an error
        logger.debug("pynvml unavailable: %s", exc)
        return None


def probe_nvidia(
    run: Runner,
    which: Callable[[str], str | None],
    nvml: Callable[[], str | None] = nvml_cuda_version,
) -> ProbeResult:
    runtime: dict[str, str] = {}
    cuda = nvml()
    if cuda:
        runtime["cuda"] = cuda

    exe = which("nvidia-smi")
    if not exe:
        return ProbeResult("nvidia-smi", False, "nvidia-smi not on PATH", runtime=runtime)
    rc, out, err = run(
        [
            exe,
            "--query-gpu=index,name,memory.total,driver_version",
            "--format=csv,noheader,nounits",
        ]
    )
    if rc != 0:
        return ProbeResult("nvidia-smi", False, f"exit {rc}: {err.strip()[:200]}", runtime=runtime)
    gpus = parse_nvidia_smi_query(out)
    if "cuda" not in runtime:
        rc2, header, _ = run([exe])
        cuda = parse_cuda_version_header(header) if rc2 == 0 else None
        if cuda:
            runtime["cuda"] = cuda
    if gpus and gpus[0].driver:
        runtime["nvidia-driver"] = gpus[0].driver
    return ProbeResult(
        "nvidia-smi", bool(gpus), f"{len(gpus)} device(s)", gpus=gpus, runtime=runtime
    )


_UNPARSEABLE = (json.JSONDecodeError, AttributeError, TypeError)


def probe_amd(run: Runner, which: Callable[[str], str | None]) -> ProbeResult:
    """amd-smi (ROCm 6+), else the deprecated rocm-smi. Exit codes are not
    trusted: rocm-smi exits 0 with nothing to report, amd-smi exits 255 when the
    driver is not loaded."""
    exe = which("amd-smi")
    if exe:
        rc, out, err = run([exe, "static", "--json"])
        try:
            gpus = parse_amd_smi_static(out)
        except _UNPARSEABLE as exc:
            reason = (err or str(exc)).strip()[:200]
            return ProbeResult("amd-smi", False, f"exit {rc}: {reason}")
        _rc, vout, _err = run([exe, "version", "--json"])
        try:
            runtime = parse_amd_smi_version(vout)
        except _UNPARSEABLE:
            runtime = {}
        detail = f"{len(gpus)} device(s)"
        if not gpus and "N/A" in out:
            detail = "devices present but unreadable (is the user in the render group?)"
        return ProbeResult("amd-smi", bool(gpus), detail, gpus=gpus, runtime=runtime)

    exe = which("rocm-smi")
    if not exe:
        return ProbeResult("amd-smi", False, "neither amd-smi nor rocm-smi on PATH")
    rc, out, err = run([exe, "--showproductname", "--showmeminfo", "vram", "--json"])
    try:
        gpus = parse_rocm_smi(out)
    except _UNPARSEABLE:
        return ProbeResult("rocm-smi", False, (out or err).strip()[:200] or f"exit {rc}")
    detail = f"{len(gpus)} device(s) (rocm-smi is deprecated in favour of amd-smi)"
    return ProbeResult("rocm-smi", bool(gpus), detail, gpus=gpus)


def probe_apple(run: Runner, which: Callable[[str], str | None]) -> ProbeResult:
    exe = which("system_profiler")
    if not exe:
        return ProbeResult("system_profiler", False, "system_profiler not on PATH")
    rc, out, err = run([exe, "SPHardwareDataType", "-json"])
    try:
        gpus = parse_system_profiler_hardware(out)
    except _UNPARSEABLE:
        return ProbeResult("system_profiler", False, f"exit {rc}: {err.strip()[:200]}")
    detail = f"{len(gpus)} device(s)" if gpus else "no Apple Silicon chip reported"
    return ProbeResult("system_profiler", bool(gpus), detail, gpus=gpus)


def probe_intel(run: Runner, which: Callable[[str], str | None]) -> ProbeResult:
    exe = which("xpu-smi")
    if not exe:
        return ProbeResult("xpu-smi", False, "xpu-smi not on PATH")
    rc, out, err = run([exe, "discovery", "-j"])
    try:
        listed = parse_xpu_smi(out)
        ids = [d.get("device_id") for d in json.loads(out).get("device_list", [])]
    except _UNPARSEABLE:
        return ProbeResult("xpu-smi", False, f"exit {rc}: {err.strip()[:200]}")
    gpus: list[DetectedGPU] = []
    for dev_id, summary in zip(ids, listed):
        if summary.vram_gb is not None or dev_id is None:
            gpus.append(summary)
            continue
        # The summary list carries no memory size; the per-device query does.
        _rc, detail_out, _err = run([exe, "discovery", "-d", str(dev_id), "-j"])
        try:
            gpus.extend(parse_xpu_smi(detail_out) or [summary])
        except _UNPARSEABLE:
            gpus.append(summary)
    return ProbeResult("xpu-smi", bool(gpus), f"{len(gpus)} device(s)", gpus=gpus)


def probe_windows(run: Runner, which: Callable[[str], str | None]) -> ProbeResult:
    exe = which("powershell") or which("pwsh")
    if not exe:
        return ProbeResult("windows-cim", False, "PowerShell not found")
    rc, out, err = run([exe, "-NoProfile", "-NonInteractive", "-Command", WINDOWS_PROBE])
    if rc != 0 or not out.strip():
        return ProbeResult("windows-cim", False, f"exit {rc}: {err.strip()[:200]}")
    try:
        gpus = parse_windows_adapters(out)
    except (json.JSONDecodeError, AttributeError, TypeError) as exc:
        return ProbeResult("windows-cim", False, f"unparseable output: {exc}")
    return ProbeResult("windows-cim", bool(gpus), f"{len(gpus)} adapter(s)", gpus=gpus)


def detect_wsl(env: dict[str, str], read_text: Callable[[str], str | None]) -> bool:
    """Inside Linux: WSL init sets WSL_DISTRO_NAME, and a WSL kernel release names
    WSL (e.g. ``4.19.112-microsoft-WSL2-standard``). Microsoft staff advise
    matching "WSL" there, since "microsoft" alone can appear in non-WSL kernel
    images (microsoft/WSL#423)."""
    if env.get("WSL_DISTRO_NAME"):
        return True
    release = read_text("/proc/sys/kernel/osrelease") or ""
    return "wsl" in release.lower()


def _read_text(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


# -- merge + planner assessment ------------------------------------------------


def merge_gpus(probes: list[ProbeResult]) -> list[DetectedGPU]:
    """One entry per device. A vendor tool's reading wins over the generic
    Windows route for the same card, since it reports VRAM without the cap."""
    vendor_named = {g.name.lower() for p in probes if p.tool != "windows-cim" for g in p.gpus}
    merged: list[DetectedGPU] = []
    for p in probes:
        for g in p.gpus:
            if p.tool == "windows-cim" and g.name.lower() in vendor_named:
                continue
            merged.append(g)
    return merged


def assess(gpu: DetectedGPU) -> PlannerStatus:
    """What the planner can do with this device today -- no inference from names."""
    from chimeraforge.planner.hardware import match_driver_name

    if gpu.unified_memory:
        return PlannerStatus(
            gpu.name,
            "not-representable",
            None,
            "unified-memory device: the planner cannot model a shared CPU/GPU pool yet",
        )
    spec = match_driver_name(gpu.name, gpu.vram_gb)
    if spec is not None:
        missing = []
        if spec.cost_per_hour <= 0:
            missing.append("no vendor price (pass --gpu-price-per-hour)")
        if spec.fp16_tflops <= 0:
            missing.append("no vendor FP16 figure (TTFT is a floor)")
        how = (
            "--hardware auto"
            if gpu.vendor == VENDOR_NVIDIA
            else f'--hardware "{spec.name}" (auto reads NVIDIA only)'
        )
        detail = f"plan with {how}" + (f"; {'; '.join(missing)}" if missing else "")
        return PlannerStatus(gpu.name, "matched", spec.name, detail)
    # Only a dedicated-VRAM reading is offered as a flag value; an aperture or
    # an unknown stays a placeholder rather than a number to copy.
    dedicated = gpu.vram_gb and not gpu.notes
    vram = f"--gpu-vram-gb {gpu.vram_gb:g} " if dedicated else "--gpu-vram-gb <GB> "
    bw = (
        f"--gpu-bandwidth-gbps {gpu.bandwidth_gbps:g} (as {gpu.source} reports it)"
        if gpu.bandwidth_gbps
        else "--gpu-bandwidth-gbps <vendor GB/s>"
    )
    detail = f"not in the GPU database; plan it with {vram}{bw}"
    if gpu.notes:
        detail += f" ({gpu.notes[0]})"
    return PlannerStatus(gpu.name, "supply-figures", None, detail)


# -- engines -----------------------------------------------------------------


def probe_engines(backends: tuple[str, ...] | None = None) -> list[EngineProbe]:
    """Which serving engines answer on their default local URLs, via the bench
    adapters (so the endpoints are the ones `bench` and `measure` use)."""
    import asyncio

    from chimeraforge.bench.backends import BACKEND_REGISTRY, get_backend

    names = backends or tuple(BACKEND_REGISTRY)

    async def one(name: str) -> EngineProbe:
        backend = get_backend(name)
        url = getattr(backend, "base_url", "")
        try:
            ok, msg = await backend.health_check()
            version = await backend.get_version() if ok else None
        except Exception as exc:  # noqa: BLE001 - one engine must not fail the report
            ok, msg, version = False, f"{type(exc).__name__}: {exc}", None
        finally:
            close = getattr(backend, "close", None)
            if close:
                await close()
        if ok and not version:
            # A healthy status proves only that SOMETHING listens there: a
            # generic web app answering /health on :8000 read as "vLLM is running".
            # Running means the engine named itself via its version endpoint.
            return EngineProbe(
                name,
                url,
                False,
                None,
                f"a service answers at {url} but did not identify as {name} "
                "(no version from its version endpoint)",
                answered=True,
            )
        return EngineProbe(name, url, ok, version, msg, answered=ok)

    async def run_all() -> list[EngineProbe]:
        return list(await asyncio.gather(*(one(n) for n in names)))

    return asyncio.run(run_all())


# -- orchestration -----------------------------------------------------------


def run_doctor(
    run: Runner = default_runner,
    which: Callable[[str], str | None] = shutil.which,
    system: str | None = None,
    env: dict[str, str] | None = None,
    read_text: Callable[[str], str | None] = _read_text,
    check_engines: bool = True,
    nvml: Callable[[], str | None] = nvml_cuda_version,
) -> DoctorReport:
    """Probe the platform. Every input is injectable so each path is testable."""
    system = system or _platform.system()
    env = dict(os.environ) if env is None else env

    probes = [probe_nvidia(run, which, nvml)]
    if system == "Linux":
        probes += [probe_amd(run, which), probe_intel(run, which)]
    elif system == "Darwin":
        probes.append(probe_apple(run, which))
    elif system == "Windows":
        # CIM + the display-class registry covers every vendor's adapters.
        probes.append(probe_windows(run, which))

    gpus = merge_gpus(probes)
    notes: list[str] = []
    if not gpus:
        notes.append(
            "no GPU detected by any probe; plan an unlisted card with "
            "--gpu-vram-gb and --gpu-bandwidth-gbps"
        )
    return DoctorReport(
        os=system,
        os_version=_platform.release(),
        arch=_platform.machine(),
        wsl=system == "Linux" and detect_wsl(env, read_text),
        probes=probes,
        gpus=gpus,
        planner=[assess(g) for g in gpus],
        engines=probe_engines() if check_engines else [],
        notes=notes,
    )
