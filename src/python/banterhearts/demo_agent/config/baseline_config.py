"""Baseline Ollama configuration for demo agents."""

from dataclasses import dataclass, asdict
from typing import Any, Dict


@dataclass
class BaselineConfig:
    num_gpu: int = 80
    num_ctx: int = 1024
    temperature: float = 0.8
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.1

    def to_ollama_options(self) -> Dict[str, Any]:
        """Return options dict compatible with Ollama generate."""
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
            f"Baseline config: GPU layers={self.num_gpu}, ctx={self.num_ctx}, "
            f"temp={self.temperature}, top_p={self.top_p}, top_k={self.top_k}, "
            f"repeat_penalty={self.repeat_penalty}"
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
