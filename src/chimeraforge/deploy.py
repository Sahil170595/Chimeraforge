"""Export serving configuration without installing, starting or deploying an engine."""

from __future__ import annotations

import json
import plistlib
import re
import shlex
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from chimeraforge.api import PlanArtifact, PlanError, artifact_from_dict
from chimeraforge.planner.engine import Candidate
from chimeraforge.planner.constants import MAX_REPLICAS, PLAN_MODE_ONLINE
from chimeraforge.planner.launch import (
    OLLAMA_KV_CACHE_TYPE,
    RECOMMENDED_GPU_MEM_UTIL,
    SGLANG_DEFAULT_PORT,
    SGLANG_KV_CACHE_DTYPE,
    TGI_KV_CACHE_DTYPE,
    VLLM_KV_CACHE_DTYPE,
)
from chimeraforge.planner.resolver import ModelSpec, SOURCE_HF, SOURCE_OLLAMA
from chimeraforge.kubernetes_options import KubernetesOptions

FORMATS = ("compose", "systemd", "launchd", "modelfile", "kubernetes")
MAX_EXPORT_GPUS_PER_REPLICA = 64
MAX_GPU_IDENTIFIER_CHARS = 40
MAX_HOST_PORT = 65535
_GPU_ORDINAL = re.compile(r"0|[1-9][0-9]*")
_GPU_UUID = re.compile(r"GPU-[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", re.IGNORECASE)
_HF_BACKENDS = ("vllm", "sglang", "tgi")
_IMAGE_NAME = re.compile(r"[a-z0-9][a-z0-9._/:\-]*")
_IMAGE_TAG = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-]{0,127}")
_OLLAMA_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/:\-]*")
_DIGEST = re.compile(r"sha256:[a-fA-F0-9]{64}")
_NATIVE_DTYPES = {"FP16": "float16", "BF16": "bfloat16"}
_PORTS = {"vllm": 8000, "sglang": SGLANG_DEFAULT_PORT, "tgi": 80, "ollama": 11434}
_HOST_PORTS = {**_PORTS, "tgi": 8080}
_GPU_NOTE = (
    "Config only: GPU runtime, installed engine/image compatibility, model access and actual "
    "throughput/SLO attainment are not verified. Match the visible GPU(s) to the saved plan."
)


class DeploymentError(ValueError):
    """The selected plan cannot be represented faithfully by a deployment template."""


@dataclass(frozen=True)
class DeploymentExport:
    """Main config and required companion files, with explicit provisioning steps."""

    format: str
    backend: str
    content: str
    notes: list[str] = field(default_factory=list)
    provisioning: list[str] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _safe_text(value: str | None, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        or "<" in value
        or ">" in value
        or value.startswith("-")
    ):
        raise DeploymentError(
            f"{label} must be explicit, without placeholders or control characters"
        )
    return value


def _image(value: str | None) -> str:
    image = _safe_text(value, "image")
    if "@" in image:
        name, digest = image.rsplit("@", 1)
        valid = bool(_IMAGE_NAME.fullmatch(name) and _DIGEST.fullmatch(digest))
    else:
        name, sep, tag = image.rpartition(":")
        valid = bool(
            sep
            and _IMAGE_NAME.fullmatch(name)
            and _IMAGE_TAG.fullmatch(tag)
            and tag.lower() != "latest"
        )
    if not valid:
        raise DeploymentError("image requires an explicit non-latest tag or sha256 digest")
    return image


def _executable(value: str | None) -> str:
    path = _safe_text(value, "executable")
    if not path.startswith("/") or "\\" in path:
        raise DeploymentError(
            "executable must be the installed engine/interpreter's absolute POSIX path"
        )
    return path


def _model_identity(
    candidate: Candidate, spec: ModelSpec | None, model: str | None
) -> tuple[str, list[str]]:
    notes = []
    resolved = spec is not None and spec.source in (SOURCE_HF, SOURCE_OLLAMA)
    original = (
        candidate.model.removeprefix("ollama:")
        if candidate.backend == "ollama"
        else candidate.model
    )
    supplied = model.removeprefix("ollama:") if model and candidate.backend == "ollama" else model
    if supplied and resolved and supplied != original:
        raise DeploymentError("model differs from the resolved checkpoint; replan that model first")
    if resolved:
        identifier = _safe_text(original, "model")
    elif supplied:
        identifier = _safe_text(supplied, "model")
        notes.append(
            "Explicit model override replaces a registry/manual identity. The saved predictions "
            "remain about that size class; replan the concrete checkpoint to resolve its geometry."
        )
    else:
        raise DeploymentError(
            "model is not a resolved serving identity; supply --model or replan a concrete model"
        )
    if candidate.backend in _HF_BACKENDS:
        if resolved and spec is not None and spec.source != SOURCE_HF:
            raise DeploymentError(
                "model is an Ollama checkpoint, but this backend needs a Hugging Face "
                "checkpoint; replan"
            )
        if "/" not in identifier:
            raise DeploymentError(
                "model must identify a concrete Hugging Face repository or absolute checkpoint path"
            )
    elif candidate.backend == "ollama":
        if (
            not resolved
            or spec is None
            or spec.source != SOURCE_OLLAMA
            or not _OLLAMA_NAME.fullmatch(identifier)
        ):
            raise DeploymentError(
                "Ollama model needs a resolved tag and native quantization; "
                "replan with Ollama resolution"
            )
    else:
        raise DeploymentError(f"no deployment template for backend {candidate.backend!r}")
    native = spec.native_quant.upper() if spec and spec.native_quant else None
    quant = candidate.quant
    if candidate.backend == "ollama":
        if native != quant:
            raise DeploymentError(
                f"model's native quant {native!r} does not establish planned quant {quant!r}"
            )
    elif quant in _NATIVE_DTYPES:
        if native not in (None, "FP16", "BF16", "FP32"):
            raise DeploymentError(
                f"quantized checkpoint {native!r} cannot serve planned quant {quant!r}"
            )
    elif quant in ("AWQ", "GPTQ", "FP8"):
        if not resolved or spec is None or spec.source != SOURCE_HF or native != quant:
            raise DeploymentError(
                f"planned quant {quant} requires a resolved checkpoint with native quant {quant}"
            )
    else:
        raise DeploymentError(
            f"backend {candidate.backend} cannot faithfully express planned quant {quant}"
        )
    return identifier, notes


def _validate_fidelity(
    candidate: Candidate, spec: ModelSpec | None, inputs: dict, platform: str, format: str
) -> None:
    if type(candidate.n_agents) is not int or not 1 <= candidate.n_agents <= MAX_REPLICAS:
        raise DeploymentError(f"replica population must be between 1 and {MAX_REPLICAS}")
    if candidate.n_agents > 1 and (
        format not in ("compose", "kubernetes")
        or candidate.backend not in ("vllm", "sglang")
        or candidate.mode != PLAN_MODE_ONLINE
        or inputs["mode"] != PLAN_MODE_ONLINE
    ):
        raise DeploymentError("multi-replica export supports online vLLM/SGLang Compose only")
    if candidate.offload_fraction is None or candidate.offload_fraction != 0:
        raise DeploymentError(
            "CPU offload is not expressed by these templates; select a fully resident plan"
        )
    if candidate.lora_adapters:
        raise DeploymentError("adapter paths are unresolved; export of LoRA plans is unsupported")
    if candidate.effective_batch <= 0:
        raise DeploymentError("candidate batch must be positive")
    if min(candidate.tensor_parallel, candidate.pipeline_parallel) <= 0:
        raise DeploymentError("parallel degrees must be positive")
    if any(
        type(value) is not int or not 1 <= value <= MAX_EXPORT_GPUS_PER_REPLICA
        for value in (candidate.tensor_parallel, candidate.pipeline_parallel)
    ):
        raise DeploymentError(
            f"deployment export supports at most {MAX_EXPORT_GPUS_PER_REPLICA} GPUs per replica"
        )
    per_replica = candidate.tensor_parallel * candidate.pipeline_parallel
    if per_replica > MAX_EXPORT_GPUS_PER_REPLICA:
        raise DeploymentError(
            f"deployment export supports at most {MAX_EXPORT_GPUS_PER_REPLICA} GPUs per replica"
        )
    if candidate.gpus_total != candidate.n_agents * per_replica:
        raise DeploymentError("candidate GPU count does not equal replicas x TP x PP")
    if candidate.backend in _HF_BACKENDS and inputs["kv_quant"] == "q4":
        raise DeploymentError(
            "q4 KV is not faithfully represented by this backend's fp8 template; "
            "replan with q8 or fp16"
        )
    if candidate.backend == "ollama" and candidate.gpus_total != 1:
        raise DeploymentError("Ollama has no explicit TP/PP controls; select a one-GPU plan")
    if candidate.backend == "tgi" and candidate.pipeline_parallel != 1:
        raise DeploymentError("TGI has no pipeline-parallel template; select PP=1")
    if candidate.backend == "tgi" and inputs["context_length"] <= 1:
        raise DeploymentError("TGI requires context_length > 1 for a positive input-token limit")
    if spec and spec.recurrent_state_bytes_per_seq:
        raise DeploymentError(
            "saved recurrent-state metadata does not record the exact dtype; "
            "deployment export cannot reconstruct the served state pool faithfully"
        )
    if inputs["max_num_batched_tokens"] is not None and candidate.backend != "vllm":
        raise DeploymentError("chunked-prefill token budget is expressed only by the vLLM template")
    if inputs["prefix_cache_hit_rate"] and candidate.backend not in ("vllm", "sglang"):
        raise DeploymentError(
            "prefix-cache assumptions cannot be configured by this backend template"
        )
    if format == "compose" and (platform != "linux" or candidate.platform != "linux-cuda"):
        raise DeploymentError("Compose template supports Linux NVIDIA CUDA plans only")
    if format == "systemd":
        if platform != "linux" or candidate.platform != "linux-cuda" or candidate.backend == "tgi":
            raise DeploymentError(
                "systemd supports Linux CUDA vLLM/SGLang/Ollama user services only"
            )
    if format == "launchd" and (platform != "macos" or candidate.backend != "ollama"):
        raise DeploymentError("launchd template supports macOS Ollama plans only")
    if format == "modelfile" and candidate.backend != "ollama":
        raise DeploymentError("Modelfile format requires an Ollama candidate")


def _hf_argv(
    candidate: Candidate, spec: ModelSpec | None, model: str, inputs: dict, host: str
) -> tuple[list[str], list[str]]:
    backend = candidate.backend
    context = str(inputs["context_length"])
    batch = str(candidate.effective_batch)
    notes = []
    if backend == "vllm":
        argv = [
            "vllm",
            "serve",
            model,
            "--host",
            host,
            "--port",
            "8000",
            "--max-model-len",
            context,
            "--max-num-seqs",
            batch,
            "--tensor-parallel-size",
            str(candidate.tensor_parallel),
            "--pipeline-parallel-size",
            str(candidate.pipeline_parallel),
            "--gpu-memory-utilization",
            str(RECOMMENDED_GPU_MEM_UTIL),
        ]
        notes.append(
            f"vLLM GPU memory utilization {RECOMMENDED_GPU_MEM_UTIL} is a starting point, "
            "not a derived capacity guarantee."
        )
        if inputs["max_num_batched_tokens"] is not None:
            argv += [
                "--max-num-batched-tokens",
                str(inputs["max_num_batched_tokens"]),
                "--enable-chunked-prefill",
            ]
        else:
            argv += ["--no-enable-chunked-prefill"]
        argv += [
            "--enable-prefix-caching"
            if inputs["prefix_cache_hit_rate"]
            else "--no-enable-prefix-caching"
        ]
    elif backend == "sglang":
        argv = [
            "python3",
            "-m",
            "sglang.launch_server",
            "--model-path",
            model,
            "--host",
            host,
            "--port",
            str(SGLANG_DEFAULT_PORT),
            "--context-length",
            context,
            "--max-running-requests",
            batch,
            "--tp-size",
            str(candidate.tensor_parallel),
            "--pp-size",
            str(candidate.pipeline_parallel),
            "--chunked-prefill-size",
            "-1",
        ]
        if not inputs["prefix_cache_hit_rate"]:
            argv += ["--disable-radix-cache"]
    else:
        argv = [
            "text-generation-launcher",
            "--model-id",
            model,
            "--hostname",
            host,
            "--port",
            "80",
            "--max-total-tokens",
            context,
            "--max-input-tokens",
            str(min(inputs["prompt_tokens"], inputs["context_length"] - 1)),
            "--max-concurrent-requests",
            batch,
            "--num-shard",
            str(candidate.tensor_parallel),
        ]
    if candidate.quant in _NATIVE_DTYPES:
        argv += ["--dtype", _NATIVE_DTYPES[candidate.quant]]
    else:
        argv += ["--quantize" if backend == "tgi" else "--quantization", candidate.quant.lower()]
    if inputs["kv_quant"] == "q8":
        dtype = {
            "vllm": VLLM_KV_CACHE_DTYPE,
            "sglang": SGLANG_KV_CACHE_DTYPE,
            "tgi": TGI_KV_CACHE_DTYPE,
        }[backend]
        argv += ["--kv-cache-dtype", dtype]
        notes.append(
            "The plan's q8 KV memory scale is mapped to backend FP8 KV; verify accuracy "
            "and any required KV scaling factors separately."
        )
    elif backend == "vllm":
        argv += ["--kv-cache-dtype", "float16"]
    elif candidate.quant != "FP16":
        raise DeploymentError(
            "this backend's implicit KV dtype does not establish the planned fp16 cache; replan q8"
        )
    if spec and spec.checkpoint:
        argv += ["--revision", spec.checkpoint["resolved_revision"]]
        notes.append(
            "HF commit is pinned; config bytes and declared LFS metadata do not verify "
            "downloaded/served weights or tokenizer bytes."
        )
    elif spec and spec.source == SOURCE_HF:
        notes.append(
            "Legacy HF metadata has no immutable revision binding; "
            "replan online to pin the checkpoint."
        )
    return argv, notes


def _ollama_env(candidate: Candidate, inputs: dict, host: str) -> dict[str, str]:
    env = {
        "OLLAMA_HOST": f"{host}:11434",
        "OLLAMA_NUM_PARALLEL": str(candidate.effective_batch),
        "OLLAMA_MAX_LOADED_MODELS": "1",
        "OLLAMA_CONTEXT_LENGTH": str(inputs["context_length"]),
        "OLLAMA_KV_CACHE_TYPE": "f16",
    }
    if inputs["kv_quant"] != "fp16":
        env.update(
            OLLAMA_FLASH_ATTENTION="1",
            OLLAMA_KV_CACHE_TYPE=OLLAMA_KV_CACHE_TYPE[inputs["kv_quant"]],
        )
    return env


def _systemd_arg(value: str) -> str:
    # systemd parses quoting, then expands specifiers (%) and variables ($).
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "$$")
    return '"' + escaped + '"'


def _compose_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace("$", "$$")
    if isinstance(value, list):
        return [_compose_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _compose_value(item) for key, item in value.items()}
    return value


def _device_selection(devices: list[str] | None, count: int) -> list[str] | None:
    if devices is None:
        return None
    if type(devices) is not list or not 1 <= len(devices) <= MAX_EXPORT_GPUS_PER_REPLICA:
        raise DeploymentError(
            f"GPU devices must be a nonempty list of at most {MAX_EXPORT_GPUS_PER_REPLICA} IDs"
        )
    if len(devices) != count:
        raise DeploymentError("GPU device cardinality must equal the saved candidate TP x PP")
    selected, namespaces = [], set()
    for device in devices:
        if type(device) is not str or len(device) > MAX_GPU_IDENTIFIER_CHARS:
            raise DeploymentError("GPU device IDs must be bounded strings")
        if _GPU_ORDINAL.fullmatch(device):
            namespaces.add("ordinal")
            selected.append(device)
        elif _GPU_UUID.fullmatch(device):
            namespaces.add("uuid")
            selected.append("GPU-" + device[4:].lower())
        else:
            raise DeploymentError(
                "GPU devices require canonical decimal ordinals or full GPU UUIDs"
            )
    if len(namespaces) != 1 or len(set(selected)) != len(selected):
        raise DeploymentError("GPU devices must use one namespace without duplicate IDs")
    return selected


def _replica_device_selection(
    candidate: Candidate, groups: list[list[str]] | None
) -> list[list[str]]:
    if candidate.n_agents == 1:
        raise DeploymentError("replica matrices require a multi-replica saved candidate")
    if type(groups) is not list or len(groups) != candidate.n_agents:
        raise DeploymentError("each saved replica requires an explicit GPU group")
    selected = []
    for group in groups:
        if type(group) is not list:
            raise DeploymentError("each replica GPU group must be a list of device IDs")
        canonical = _device_selection(
            group, candidate.tensor_parallel * candidate.pipeline_parallel
        )
        assert canonical is not None
        selected.append(canonical)
    namespaces = {"uuid" if row[0].startswith("GPU-") else "ordinal" for row in selected}
    all_ids = [device for row in selected for device in row]
    if len(namespaces) != 1 or len(set(all_ids)) != len(all_ids):
        raise DeploymentError(
            "replica GPU groups must be globally disjoint in one namespace; no duplicate IDs"
        )
    return selected


def _replica_layout(
    candidate: Candidate,
    groups: list[list[str]] | None,
    ports: list[int] | None,
) -> tuple[list[list[str]], list[int]] | None:
    if candidate.n_agents == 1:
        if groups is not None or ports is not None:
            raise DeploymentError("replica matrices require a multi-replica saved candidate")
        return None
    if (
        type(groups) is not list
        or type(ports) is not list
        or len(groups) != candidate.n_agents
        or len(ports) != candidate.n_agents
    ):
        raise DeploymentError("each saved replica requires an explicit GPU group and host port")
    selected = _replica_device_selection(candidate, groups)
    if any(type(port) is not int or not 1 <= port <= MAX_HOST_PORT for port in ports):
        raise DeploymentError("each replica host port must be an integer between 1 and 65535")
    if len(set(ports)) != len(ports):
        raise DeploymentError("replica host ports must be distinct")
    return selected, ports[:]


def _compose_service(
    candidate: Candidate,
    argv: list[str],
    env: dict[str, str],
    image: str,
    fingerprint: str,
    devices: list[str] | None,
    host_port: int | None,
) -> dict[str, Any]:
    entry_length = {"vllm": 2, "sglang": 3, "tgi": 1, "ollama": 2}[candidate.backend]
    reservation: dict[str, Any] = {"driver": "nvidia"}
    if devices is None:
        reservation["count"] = candidate.gpus_total
    else:
        reservation["device_ids"] = devices
    reservation["capabilities"] = ["gpu"]
    published_port = host_port if host_port is not None else _HOST_PORTS[candidate.backend]
    service: dict[str, Any] = {
        "image": image,
        "entrypoint": argv[:entry_length],
        "ports": [f"127.0.0.1:{published_port}:{_PORTS[candidate.backend]}"],
        "restart": "unless-stopped",
        "init": True,
        "labels": {"org.chimeraforge.plan-fingerprint": fingerprint},
        "deploy": {"resources": {"reservations": {"devices": [reservation]}}},
    }
    if argv[entry_length:]:
        service["command"] = argv[entry_length:]
    if env:
        service["environment"] = env
    if candidate.backend == "ollama":
        service["volumes"] = [
            "ollama-models:/root/.ollama",
            "./Modelfile:/etc/chimeraforge/Modelfile:ro",
        ]
    else:
        service["shm_size"] = "1gb"
    return service


def export_deployment(
    artifact: PlanArtifact,
    *,
    format: str,
    model: str | None = None,
    image: str | None = None,
    candidate_index: int = 0,
    executable: str | None = None,
    output_path: str | Path | None = None,
    gpu_devices: list[str] | None = None,
    host_port: int | None = None,
    replica_gpu_devices: list[list[str]] | None = None,
    replica_host_ports: list[int] | None = None,
    kubernetes: KubernetesOptions | None = None,
) -> DeploymentExport:
    """Render a supported saved candidate; refused assumptions never become placeholders."""
    if format not in FORMATS:
        raise DeploymentError(f"format must be one of {', '.join(FORMATS)}")
    if image is not None and format not in ("compose", "kubernetes"):
        raise DeploymentError("image override applies only to Compose format")
    if kubernetes is not None and format != "kubernetes":
        raise DeploymentError("Kubernetes options apply only to Kubernetes format")
    if format == "kubernetes" and (type(candidate_index) is not int or candidate_index < 0):
        raise DeploymentError("Kubernetes candidate selection requires a nonnegative integer")
    if executable is not None and format not in ("systemd", "launchd"):
        raise DeploymentError("executable override applies only to systemd or launchd format")
    if replica_gpu_devices is not None or replica_host_ports is not None:
        if format != "compose":
            raise DeploymentError("replica layout options apply only to Compose format")
        if gpu_devices is not None or host_port is not None:
            raise DeploymentError("singular device/port options cannot mix with replica matrices")
    if gpu_devices is not None and format not in ("compose", "systemd"):
        raise DeploymentError("GPU device selection applies only to Compose or systemd format")
    if host_port is not None:
        if format != "compose":
            raise DeploymentError("host port override applies only to Compose format")
        if type(host_port) is not int or not 1 <= host_port <= MAX_HOST_PORT:
            raise DeploymentError("host port must be an integer between 1 and 65535")
    try:
        artifact = artifact_from_dict(artifact.to_dict())
        candidate = artifact.candidate(candidate_index)
        spec = artifact.spec(candidate.model)
    except (PlanError, TypeError, AttributeError) as exc:
        raise DeploymentError(str(exc)) from exc
    data = artifact.to_dict()
    inputs = data["inputs"]
    inputs["kv_quant"] = inputs["kv_quant"].lower()
    if format == "kubernetes" and (
        candidate.backend not in ("vllm", "sglang")
        or candidate.mode != PLAN_MODE_ONLINE
        or inputs["mode"] != PLAN_MODE_ONLINE
        or data["result"]["platform"] != "linux"
        or candidate.platform != "linux-cuda"
    ):
        raise DeploymentError("Kubernetes export requires online Linux CUDA vLLM/SGLang")
    _validate_fidelity(candidate, spec, inputs, data["result"]["platform"], format)
    if format == "kubernetes":
        from chimeraforge.kubernetes_options import admit_options
        from chimeraforge.kubernetes_export import render

        options = admit_options(kubernetes, data["fingerprint"], candidate_index)
        identifier, identity_notes = _model_identity(candidate, spec, model)
        argv, engine_notes = _hf_argv(candidate, spec, identifier, inputs, "0.0.0.0")
        content = render(
            candidate, argv, _image(image), data["fingerprint"], candidate_index, options
        )
        return DeploymentExport(
            format,
            candidate.backend,
            content,
            [
                *candidate.warnings,
                *identity_notes,
                *engine_notes,
                "Kubernetes declarations only: scheduler labels, GPU requests and memory emptyDir "
                "do not verify plugin/driver availability, fit, image/model access, "
                "physical identities, executed argv, readiness, independent capacity or SLOs. "
                "Each logical member may be replaced.",
            ],
            [
                "Review namespace, image access, node labels and GPU plugin "
                "before applying explicitly."
            ],
        )
    layout = _replica_layout(candidate, replica_gpu_devices, replica_host_ports)
    devices = _device_selection(gpu_devices, candidate.gpus_total)
    identifier, identity_notes = _model_identity(candidate, spec, model)
    fingerprint = data["fingerprint"]
    notes = [_GPU_NOTE, *candidate.warnings, *identity_notes]
    if devices is not None:
        notes.append(
            "Explicit GPU selection is a requested declaration; device availability, hardware "
            "and topology are not verified. Compose ordering is a declaration, not observed "
            "CUDA rank mapping; host ordinals are not copied into container CUDA_VISIBLE_DEVICES."
            if format == "compose"
            else "CUDA_VISIBLE_DEVICES requests application device ordering; device availability, "
            "hardware and topology are not verified."
        )
    if layout is not None:
        notes.append(
            "Homogeneous saved serving settings are rendered as independent named services; "
            "a router, scaler and observed independent GPU capacity are not provided or verified. "
            "Target each loopback endpoint explicitly. Device availability/model/topology and "
            "CUDA rank mapping are unverified; host ordinals are not copied into "
            "container CUDA visibility."
        )
    provisioning = []
    files = {}
    destination = Path(output_path).resolve() if output_path is not None else None
    compose = "docker compose"
    if destination is not None:
        compose += " -f " + shlex.quote(_safe_text(str(destination), "output path"))
    host = "0.0.0.0" if format == "compose" else "127.0.0.1"
    env: dict[str, str] = {}
    if candidate.backend == "ollama":
        argv = ["ollama", "serve"]
        env = _ollama_env(candidate, inputs, host)
        model_name = "chimeraforge-" + fingerprint[:16]
        modelfile = (
            f"# Saved plan {fingerprint}\nFROM {identifier}\n"
            f"PARAMETER num_ctx {inputs['context_length']}\n"
        )
        files["Modelfile"] = modelfile
        if format == "compose":
            prefix = f"{compose} exec inference ollama"
            path = "/etc/chimeraforge/Modelfile"
        else:
            prefix, path = "ollama", "./Modelfile"
            if destination is not None:
                path = str(
                    destination if format == "modelfile" else destination.parent / "Modelfile"
                )
        provisioning += [
            f"After the daemon is running: {prefix} pull {shlex.quote(identifier)}",
            f"Then: {prefix} create {model_name} -f {shlex.quote(path)}",
            f"Use model {model_name} in client requests; do not override options.num_ctx.",
        ]
        notes.append(
            "Ollama serve starts a daemon; it does not pull or load the planned model. "
            "Provisioning is required."
        )
    else:
        argv, engine_notes = _hf_argv(candidate, spec, identifier, inputs, host)
        notes += engine_notes
    if format == "compose":
        pinned_image = _image(image)
        services = {}
        if layout is None:
            services["inference"] = _compose_service(
                candidate,
                argv,
                env,
                pinned_image,
                fingerprint,
                devices,
                host_port,
            )
        else:
            groups, ports = layout
            for index, (group, port) in enumerate(zip(groups, ports), 1):
                service = _compose_service(
                    candidate, argv, env, pinned_image, fingerprint, group, port
                )
                service["labels"].update(
                    {
                        "org.chimeraforge.replica-index": str(index),
                        "org.chimeraforge.replica-count": str(candidate.n_agents),
                    }
                )
                services[f"inference-{index}"] = service
        config: dict[str, Any] = {"services": services}
        if candidate.backend == "ollama":
            config["volumes"] = {"ollama-models": {}}
        # JSON is a YAML subset, avoiding an optional runtime PyYAML dependency.
        content = json.dumps(_compose_value(config), indent=2) + "\n"
        provisioning[:0] = [
            f"Validate the config: {compose} config",
            f"Then start it: {compose} up -d",
        ]
    elif format == "systemd":
        argv[0] = _executable(executable)
        env["CUDA_VISIBLE_DEVICES"] = ",".join(
            devices
            if devices is not None
            else [str(index) for index in range(candidate.gpus_total)]
        )
        content = (
            f"# Saved plan {fingerprint}\n[Unit]\n"
            f"Description=ChimeraForge {candidate.backend} inference\n"
            "After=network.target\n\n[Service]\nType=simple\n"
        )
        content += "".join(
            f"Environment={_systemd_arg(key + '=' + value)}\n" for key, value in env.items()
        )
        content += (
            "ExecStart="
            + " ".join(_systemd_arg(value) for value in argv)
            + "\nRestart=on-failure\n\n[Install]\nWantedBy=default.target\n"
        )
        provisioning.insert(
            0,
            "Install as a per-user service in ~/.config/systemd/user/; verify with "
            "systemd-analyze --user verify, then systemctl --user daemon-reload "
            "and start the unit.",
        )
    elif format == "launchd":
        argv[0] = _executable(executable)
        content = plistlib.dumps(
            {
                "Label": "org.chimeraforge.inference",
                "ProgramArguments": argv,
                "EnvironmentVariables": env,
                "RunAtLoad": True,
                "KeepAlive": True,
                "ChimeraForgePlanFingerprint": fingerprint,
            },
            sort_keys=False,
        ).decode("utf-8")
        provisioning.insert(
            0,
            "Validate with plutil -lint; install as a per-user LaunchAgent and load it with "
            "launchctl bootstrap gui/$(id -u) <absolute-plist-path>. "
            "Quit any existing Ollama daemon first.",
        )
    else:
        content = files.pop("Modelfile")
        assignments = " ".join(shlex.quote(key + "=" + value) for key, value in env.items())
        provisioning.insert(
            0, f"Start a dedicated daemon with these required settings: {assignments} ollama serve"
        )
    return DeploymentExport(format, candidate.backend, content, notes, provisioning, files)
