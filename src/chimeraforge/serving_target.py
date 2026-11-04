"""Configuration-only fields shared by native renderers, without predictions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ServingTarget:
    model: str
    backend: str
    quant: str
    n_agents: int
    tensor_parallel: int
    pipeline_parallel: int
    effective_batch: int
    gpus_total: int
    platform: str = "linux-cuda"
    mode: str = "online"
    offload_fraction: float = 0.0
    lora_adapters: int = 0
