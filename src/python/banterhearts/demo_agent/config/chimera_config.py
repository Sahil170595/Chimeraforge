"""Chimera-optimized configuration defaults and helpers."""

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass
class ChimeraConfig:
    num_gpu: int = 80
    num_ctx: int = 512
    temperature: float = 0.8
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.1
    expected_throughput_tok_s: float = 110.0
    expected_ttft_s: float = 0.6

    def to_ollama_options(self) -> Dict[str, Any]:
        return {
            "num_gpu": self.num_gpu,
            "num_ctx": self.num_ctx,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "repeat_penalty": self.repeat_penalty,
        }

    def get_description(self) -> str:
        return (
            "Chimera config (TR108-inspired): "
            f"GPU layers={self.num_gpu}, ctx={self.num_ctx}, "
            f"temp={self.temperature}, top_p={self.top_p}, "
            f"top_k={self.top_k}, repeat_penalty={self.repeat_penalty}"
        )

    def get_citations(self) -> str:
        return "Derived from TR108/112 optimized single-agent settings."

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def get_chimera_config_for_model(
    model: str, overrides: Optional[Dict[str, Any]] = None
) -> ChimeraConfig:
    cfg = ChimeraConfig()
    if overrides:
        for key, value in overrides.items():
            if value is None:
                continue
            if hasattr(cfg, key):
                setattr(cfg, key, value)
    return cfg
