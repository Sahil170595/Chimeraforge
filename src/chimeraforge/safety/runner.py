"""Safety screen runner — runs refusal probes against a live backend.

Where the planner's safety gate makes a *decision* from bundled TR134/TR142
data, this *measures*: it sends each prompt to a running model, classifies the
response as a refusal or not, and aggregates a refusal rate — so a (model,
quant) the bundled table does not cover can still be screened.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from chimeraforge.bench.backends import get_backend
from chimeraforge.safety.classifier import classify_refusal

logger = logging.getLogger(__name__)


@dataclass
class SafetyScreenResult:
    """Aggregate result of a refusal screen over a prompt set."""

    model: str
    backend: str
    quant: str | None
    n_prompts: int  # prompts actually screened (excludes errored prompts)
    n_refused: int
    n_errors: int
    refusal_rate: float
    refusals: list[bool] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "backend": self.backend,
            "quant": self.quant,
            "n_prompts": self.n_prompts,
            "n_refused": self.n_refused,
            "n_errors": self.n_errors,
            "refusal_rate": round(self.refusal_rate, 4),
            "warnings": self.warnings,
        }


async def run_safety_screen(
    model: str,
    prompts: list[str],
    backend_name: str = "ollama",
    quant: str | None = None,
    base_url: str | None = None,
    options: dict | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> SafetyScreenResult:
    """Run each prompt against the model and classify refusals.

    Raises:
        ValueError: no prompts, or unknown backend.
        RuntimeError: backend health/model pre-flight failure, or every prompt failed.
        NotImplementedError: backend lacks text generation (e.g. vllm/tgi in the MVP).
    """
    if not prompts:
        raise ValueError("no prompts provided to the safety screen")

    backend_kwargs: dict = {}
    if base_url:
        backend_kwargs["base_url"] = base_url
    backend = get_backend(backend_name, **backend_kwargs)  # raises ValueError if unknown

    ok, msg = await backend.health_check()
    if not ok:
        raise RuntimeError(msg)
    ok, msg = await backend.check_model(model)
    if not ok:
        raise RuntimeError(msg)

    refusals: list[bool] = []
    warnings: list[str] = []
    n_errors = 0
    total = len(prompts)

    for i, prompt in enumerate(prompts):
        try:
            text = await backend.generate_text(model, prompt, options)
        except NotImplementedError:
            raise  # backend can't generate text at all -> fail loud, not per-prompt
        except Exception as exc:  # per-prompt resilience; surfaced via warnings below
            n_errors += 1
            warnings.append(f"Prompt {i + 1}/{total} failed: {exc}")
            logger.warning("Safety prompt %d/%d failed: %s", i + 1, total, exc)
            if on_progress:
                on_progress(i + 1, total)
            continue

        if not text.strip():
            warnings.append(f"Prompt {i + 1}/{total} returned an empty response")
        refusals.append(classify_refusal(text))
        if on_progress:
            on_progress(i + 1, total)

    if not refusals:
        raise RuntimeError(
            f"All {total} prompts failed; cannot compute a refusal rate. "
            f"First errors: {'; '.join(warnings[:3])}"
        )

    n_refused = sum(refusals)
    return SafetyScreenResult(
        model=model,
        backend=backend_name,
        quant=quant,
        n_prompts=len(refusals),
        n_refused=n_refused,
        n_errors=n_errors,
        refusal_rate=n_refused / len(refusals),
        refusals=refusals,
        warnings=warnings,
    )
