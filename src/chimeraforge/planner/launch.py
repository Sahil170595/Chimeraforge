"""Launch-command export: turn a winning Candidate into a copy-paste serve command.

Bridges "which config" -> "how do I actually run it". Emits a vLLM / Ollama / TGI
launch command with the flags *derived from the plan* -- context length, tensor/
pipeline-parallel degree, concurrent batch, KV-cache dtype -- which are exactly the
error-prone parts to hand-compute.

Honesty rules (same principle as the planner's provenance): anything that is a
recommendation rather than a derived fact is surfaced as a note, never silently
emitted as if certain. Specifically:
  - the model identifier when the plan's source doesn't match the backend's expected
    format (an Ollama tag can't be handed to `vllm serve`, which wants an HF repo) ->
    a `<placeholder>` plus a note, never a wrong-looking real id;
  - a GGUF quant level (Q4_K_M, ...) has no vLLM/TGI-native flag name -> a note to pick
    the native-equivalent checkpoint, never a fabricated `--quantization Q4_K_M`;
  - `--gpu-memory-utilization` is a starting point, flagged as such.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from chimeraforge.planner.resolver import SOURCE_HF, SOURCE_OLLAMA

# vLLM reserves this fraction of VRAM for weights + KV + activations. 0.90 is the
# common starting point (vLLM's own default); a recommendation, not a derived value.
RECOMMENDED_GPU_MEM_UTIL = 0.90
TGI_IMAGE = "ghcr.io/huggingface/text-generation-inference:latest"
# vLLM's only quantized KV-cache dtype is fp8 (no int8/int4); TGI likewise. The
# planner's q8/q4 KV both map here, with a note when the modeled cache is smaller
# than fp8 (so real VRAM will be higher than the plan assumed on these backends).
VLLM_KV_CACHE_DTYPE = "fp8"
TGI_KV_CACHE_DTYPE = "fp8_e5m2"
# Ollama exposes KV-cache quantization through an env var (needs flash attention on).
OLLAMA_KV_CACHE_TYPE = {"q8": "q8_0", "q4": "q4_0"}

_HF_PLACEHOLDER = "<hf-repo>"
_OLLAMA_PLACEHOLDER = "<ollama-tag>"


@dataclass
class LaunchCommand:
    """A ready-to-run serve command for one backend, plus env and honesty notes."""

    backend: str
    command: str
    env: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "backend": self.backend,
            "command": self.command,
            "env": list(self.env),
            "notes": list(self.notes),
        }


def _source_of(spec) -> str:
    return spec.source if spec is not None else "registry size-class"


def _hf_repo(candidate, spec) -> tuple[str, bool]:
    """(identifier, is_placeholder) for a backend that needs a Hugging Face repo."""
    name = candidate.model
    if spec is not None and spec.source == SOURCE_HF:
        return name, False
    if "/" in name:  # already looks like org/name even without a resolved spec
        return name, False
    return _HF_PLACEHOLDER, True


def _ollama_tag(candidate, spec) -> tuple[str, bool]:
    """(identifier, is_placeholder) for the Ollama backend, which wants a model tag."""
    name = candidate.model
    if spec is not None and spec.source == SOURCE_OLLAMA:
        return name.split("ollama:", 1)[-1], False
    if name.startswith("ollama:"):
        return name.split("ollama:", 1)[-1], False
    return _OLLAMA_PLACEHOLDER, True


def _quant_note(candidate) -> list[str]:
    """vLLM/TGI take a *format* (fp8/awq/gptq), not the planner's GGUF quant level."""
    if candidate.quant in ("FP16", "BF16", "FP8"):
        return []  # FP8 is a real vLLM/TGI format -- emitted as a flag, not a note
    return [
        f"Planner modeled quant {candidate.quant} (a GGUF scale). vLLM/TGI serve "
        "fp16/fp8/AWQ/GPTQ checkpoints, not GGUF quant names -- serve the "
        "native-equivalent quantized checkpoint and add its "
        "--quantization/--quantize flag (fp8, awq, gptq)."
    ]


def _join(parts: list[str]) -> str:
    """Render a multi-flag command as a copy-pasteable line-continued block."""
    return " \\\n  ".join(parts)


def _build_vllm(candidate, spec, *, context_length: int, kv_quant: str) -> LaunchCommand:
    model_id, placeholder = _hf_repo(candidate, spec)
    parts = [
        f"vllm serve {model_id}",
        f"--max-model-len {context_length}",
        f"--gpu-memory-utilization {RECOMMENDED_GPU_MEM_UTIL}",
    ]
    if candidate.quant == "FP8":
        parts.append("--quantization fp8")
    if candidate.tensor_parallel > 1:
        parts.append(f"--tensor-parallel-size {candidate.tensor_parallel}")
    if candidate.pipeline_parallel > 1:
        parts.append(f"--pipeline-parallel-size {candidate.pipeline_parallel}")
    if candidate.effective_batch > 1:
        parts.append(f"--max-num-seqs {candidate.effective_batch}")

    notes: list[str] = []
    if kv_quant != "fp16":
        parts.append(f"--kv-cache-dtype {VLLM_KV_CACHE_DTYPE}")
        if kv_quant == "q4":
            notes.append(
                "vLLM's smallest KV-cache dtype is fp8; the plan modeled q4 KV, so "
                "real KV VRAM on vLLM will be higher than the plan assumed."
            )
    notes.extend(_quant_note(candidate))
    notes.append(
        f"--gpu-memory-utilization {RECOMMENDED_GPU_MEM_UTIL} is a starting point: "
        "raise toward 0.95 if you have headroom, lower it on OOM."
    )
    if placeholder:
        notes.append(
            f"Replace {_HF_PLACEHOLDER} with the model's Hugging Face repo "
            f"(the plan's model came from {_source_of(spec)}, not an HF repo)."
        )
    return LaunchCommand(backend="vllm", command=_join(parts), notes=notes)


def _build_ollama(candidate, spec, *, context_length: int, kv_quant: str) -> LaunchCommand:
    tag, placeholder = _ollama_tag(candidate, spec)
    env: list[str] = []
    notes: list[str] = []
    if candidate.effective_batch > 1:
        env.append(f"OLLAMA_NUM_PARALLEL={candidate.effective_batch}")
    if kv_quant != "fp16":
        env.append("OLLAMA_FLASH_ATTENTION=1")
        env.append(f"OLLAMA_KV_CACHE_TYPE={OLLAMA_KV_CACHE_TYPE[kv_quant]}")

    notes.append(
        f"Set the context window to {context_length} tokens "
        f"(`/set parameter num_ctx {context_length}` in the session, or "
        "options.num_ctx via the /api/generate call)."
    )
    if candidate.gpus_total > 1:
        notes.append(
            "Ollama auto-distributes a large model across visible GPUs and has no "
            f"explicit TP/PP flag (the plan used {candidate.gpus_total} GPUs); "
            "control placement with CUDA_VISIBLE_DEVICES."
        )
    if placeholder:
        notes.append(
            f"Replace {_OLLAMA_PLACEHOLDER} with the Ollama model tag "
            f"(the plan's model came from {_source_of(spec)})."
        )
    return LaunchCommand(backend="ollama", command=f"ollama run {tag}", env=env, notes=notes)


def _build_tgi(
    candidate, spec, *, context_length: int, prompt_tokens: int, kv_quant: str
) -> LaunchCommand:
    model_id, placeholder = _hf_repo(candidate, spec)
    max_input = min(prompt_tokens, context_length - 1)
    parts = [
        "docker run --gpus all --shm-size 1g -p 8080:80",
        "-v $HOME/.cache/huggingface:/data",
        TGI_IMAGE,
        f"--model-id {model_id}",
        f"--max-input-tokens {max_input}",
        f"--max-total-tokens {context_length}",
    ]
    if candidate.quant == "FP8":
        parts.append("--quantize fp8")
    if candidate.effective_batch > 1:
        parts.append(f"--max-concurrent-requests {candidate.effective_batch}")
    if candidate.tensor_parallel > 1:
        parts.append(f"--num-shard {candidate.tensor_parallel}")

    notes: list[str] = []
    if kv_quant != "fp16":
        parts.append(f"--kv-cache-dtype {TGI_KV_CACHE_DTYPE}")
        if kv_quant == "q4":
            notes.append(
                "TGI's smallest KV-cache dtype is fp8; the plan modeled q4 KV, so "
                "real KV VRAM on TGI will be higher than the plan assumed."
            )
    if candidate.pipeline_parallel > 1:
        notes.append(
            "TGI parallelises with tensor sharding (--num-shard); it has no "
            f"pipeline-parallel flag (the plan used PP={candidate.pipeline_parallel})."
        )
    notes.extend(_quant_note(candidate))
    if placeholder:
        notes.append(
            f"Replace {_HF_PLACEHOLDER} with the model's Hugging Face repo "
            f"(the plan's model came from {_source_of(spec)}, not an HF repo)."
        )
    return LaunchCommand(backend="tgi", command=_join(parts), notes=notes)


def build_launch_command(
    candidate,
    spec=None,
    *,
    context_length: int,
    prompt_tokens: int = 512,
    kv_quant: str = "fp16",
) -> LaunchCommand:
    """Build the serve command for ``candidate.backend`` from the plan's parameters.

    Args:
        candidate: the chosen :class:`~chimeraforge.planner.engine.Candidate`.
        spec: the resolved :class:`~chimeraforge.planner.resolver.ModelSpec` for the
            model, when an explicit ``--model`` was given (lets the emitter use the
            real identifier and know its source); ``None`` for a registry size-class
            search, which yields a placeholder identifier plus a note.
        context_length: max sequence length the plan sized for (-> max-model-len etc.).
        prompt_tokens: input length the plan sized for (-> TGI --max-input-tokens).
        kv_quant: the plan's KV-cache dtype (``fp16``/``q8``/``q4``).

    Raises:
        ValueError: if ``candidate.backend`` is not a known serving backend.
    """
    backend = candidate.backend
    if backend == "vllm":
        return _build_vllm(candidate, spec, context_length=context_length, kv_quant=kv_quant)
    if backend == "ollama":
        return _build_ollama(candidate, spec, context_length=context_length, kv_quant=kv_quant)
    if backend == "tgi":
        return _build_tgi(
            candidate,
            spec,
            context_length=context_length,
            prompt_tokens=prompt_tokens,
            kv_quant=kv_quant,
        )
    raise ValueError(f"no launch-command template for backend {backend!r}")
