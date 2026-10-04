"""NVML metadata conversion and cleanup are testable on CPU runners."""

import sys
from types import SimpleNamespace

import pytest

from chimeraforge.bench.metrics import collect_environment


@pytest.mark.parametrize("encoded", [False, True])
def test_nvml_metadata_records_driver_version_and_closes_handle(monkeypatch, encoded):
    closed = []
    name, driver = "Test GPU", "580.82.09"
    module = SimpleNamespace(
        nvmlInit=lambda: None,
        nvmlDeviceGetHandleByIndex=lambda index: index,
        nvmlDeviceGetName=lambda handle: name.encode() if encoded else name,
        nvmlDeviceGetMemoryInfo=lambda handle: SimpleNamespace(total=24 * 1024**3),
        nvmlSystemGetDriverVersion=lambda: driver.encode() if encoded else driver,
        nvmlSystemGetCudaDriverVersion_v2=lambda: 12090,
        nvmlShutdown=lambda: closed.append(True),
    )
    monkeypatch.setitem(sys.modules, "pynvml", module)
    env = collect_environment("ollama", "test-version")
    assert (env.gpu_name, env.gpu_driver, env.cuda_version) == (name, driver, "12.9")
    assert env.gpu_memory_gb == 24.0
    assert closed == [True]


def test_nvml_failure_still_closes_initialized_handle(monkeypatch):
    closed = []

    def missing_device(index):
        raise RuntimeError("no device")

    monkeypatch.setitem(
        sys.modules,
        "pynvml",
        SimpleNamespace(
            nvmlInit=lambda: None,
            nvmlDeviceGetHandleByIndex=missing_device,
            nvmlShutdown=lambda: closed.append(True),
        ),
    )
    env = collect_environment("ollama")
    assert (env.gpu_name, env.gpu_driver, env.cuda_version) == (None, None, None)
    assert closed == [True]
