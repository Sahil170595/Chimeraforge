"""Bounded observations from documented serving APIs, never benchmark input labels."""

from __future__ import annotations

from dataclasses import asdict, fields
import json
import logging
import re
from typing import Any, TYPE_CHECKING
from urllib.parse import urlsplit, urlunsplit

import httpx

if TYPE_CHECKING:
    from chimeraforge.bench.backends.base import Backend

from chimeraforge.bench.metrics import now_iso
from chimeraforge.planner.replay import digest
from chimeraforge.planner.resolver import ResolverError, spec_from_ollama_show, spec_from_hf

logger = logging.getLogger(__name__)
METADATA_TIMEOUT_S = 10
MAX_METADATA_BYTES = 1024 * 1024
MAX_OBSERVATION_SECONDS = 4 * METADATA_TIMEOUT_S
DP_SCOPE = "serving engine configuration; not endpoint/load-balancer fleet inventory"
URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")


def sanitize_message(value: str) -> str:
    """Remove URL credentials/query values from persisted endpoint diagnostics."""

    def clean(match: re.Match) -> str:
        try:
            parsed = urlsplit(match.group())
            host = parsed.hostname or "redacted-endpoint"
            if ":" in host:
                host = f"[{host}]"
            port = f":{parsed.port}" if parsed.port else ""
            return urlunsplit((parsed.scheme, host + port, parsed.path, "", ""))
        except ValueError:
            return "[redacted-endpoint]"

    return URL_PATTERN.sub(clean, value)


def safe_observation(raw: dict) -> dict:
    """Persist capability facts through a whitelist, including plugin observations."""
    from chimeraforge.planner.hardware import GPUSpec
    from chimeraforge.planner.resolver import ModelSpec

    allowed = set(observation()) | {
        "loaded_bytes",
        "loaded_gpu_bytes",
        "configuration_sha256",
        "router_max_total_tokens",
        "router_max_input_tokens",
        "weight_version_label",
        "execution_engine",
    }
    result = {key: raw[key] for key in allowed if key in raw}
    for key, cls in (("model_spec", ModelSpec), ("hardware", GPUSpec)):
        value = result.get(key)
        if isinstance(value, dict):
            names = {item.name for item in fields(cls)}
            result[key] = {name: value[name] for name in names if name in value}
        elif value is not None:
            result[key] = None

    def clean(value: Any) -> Any:
        if isinstance(value, str):
            return sanitize_message(value)
        if isinstance(value, dict):
            return {key: clean(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [clean(item) for item in value]
        return value

    return clean(result)


async def observe_backend(backend: Backend, model: str) -> dict:
    import asyncio

    observer = getattr(backend, "observe_serving", None)
    if observer is None:
        return {"source": "serving metadata capability unavailable"}
    try:
        result = await asyncio.wait_for(observer(model), MAX_OBSERVATION_SECONDS)
        if not isinstance(result, dict):
            raise ValueError("serving observation must be an object")
        return safe_observation(result)
    except Exception as exc:
        logger.warning(
            "serving metadata observation unavailable (%s): %s",
            type(exc).__name__,
            sanitize_message(str(exc)),
        )
        return {
            "source": "serving metadata capability unavailable",
            "limitations": [type(exc).__name__],
        }


async def metadata(
    client: httpx.AsyncClient, method: str, url: str, payload: dict | None = None
) -> dict:
    chunks = []
    size = 0
    async with client.stream(method, url, json=payload, timeout=METADATA_TIMEOUT_S) as response:
        response.raise_for_status()
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > MAX_METADATA_BYTES:
                raise ValueError("serving metadata exceeds size limit")
            chunks.append(chunk)
    body = json.loads(b"".join(chunks))
    if not isinstance(body, dict):
        raise ValueError("serving metadata must be a JSON object")
    return body


async def optional_metadata(
    client: httpx.AsyncClient, method: str, url: str, payload: dict | None = None
) -> tuple[dict, str | None]:
    try:
        return await metadata(client, method, url, payload), None
    except (httpx.HTTPError, ValueError) as exc:
        logger.debug(
            "serving metadata %s unavailable: %s", sanitize_message(url), sanitize_message(str(exc))
        )
        return {}, f"{method} {url.split('?', 1)[0].rsplit('/', 1)[-1]}: {type(exc).__name__}"


def observation() -> dict:
    return {
        "backend": None,
        "version": None,
        "model": None,
        "model_digest": None,
        "quant": None,
        "context_length": None,
        "tensor_parallel": None,
        "pipeline_parallel": None,
        "replicas": None,
        "serving_data_parallel_size": None,
        "serving_data_parallel_scope": DP_SCOPE,
        "hardware": None,
        "device": None,
        "prefix_cache": None,
        "model_spec": None,
        "source": None,
        "captured_at": now_iso(),
        "limitations": [],
    }


def positive_int(value: Any) -> int | None:
    return value if type(value) is int and value > 0 else None


def object_value(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def rows(value: Any) -> list:
    return value if isinstance(value, list) else []


def quant_name(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    from chimeraforge.planner.constants import QUANT_LEVELS

    name = {"F16": "FP16", "FLOAT16": "FP16", "TORCH.FLOAT16": "FP16"}.get(
        value.upper(), value.upper()
    )
    return name if name in QUANT_LEVELS else None


def _ollama_name(value: str) -> str:
    value = value.removeprefix("ollama:")
    return value if ":" in value else value + ":latest"


async def observe_ollama(client: httpx.AsyncClient, url: str, model: str) -> dict:
    """Ollama0.35.1 /show architecture differs from /ps active context/device."""
    result = observation()
    responses = {}
    for key, method, endpoint, payload in (
        ("show", "POST", "/api/show", {"model": model}),
        ("tags", "GET", "/api/tags", None),
        ("ps", "GET", "/api/ps", None),
        ("version", "GET", "/api/version", None),
    ):
        responses[key], error = await optional_metadata(client, method, url + endpoint, payload)
        if error:
            result["limitations"].append(error)
    show, tags, running = responses["show"], responses["tags"], responses["ps"]
    result["version"] = responses["version"].get("version")
    result["backend"] = (
        "ollama" if isinstance(result["version"], str) and result["version"] else None
    )
    result["quant"] = quant_name(object_value(show.get("details")).get("quantization_level"))
    for row in rows(tags.get("models")):
        if isinstance(row, dict) and _ollama_name(str(row.get("name", ""))) == _ollama_name(model):
            result["model"] = row["name"]
            result["model_digest"] = row.get("digest")
            break
    for row in rows(running.get("models")):
        if isinstance(row, dict) and _ollama_name(str(row.get("name", ""))) == _ollama_name(model):
            result["model"] = row["name"]
            result["model_digest"] = row.get("digest")
            result["context_length"] = positive_int(row.get("context_length"))
            result["loaded_bytes"] = positive_int(row.get("size"))
            result["loaded_gpu_bytes"] = (
                row.get("size_vram") if type(row.get("size_vram")) is int else None
            )
            if result["loaded_bytes"] is not None and result["loaded_gpu_bytes"] is not None:
                result["device"] = "gpu" if result["loaded_gpu_bytes"] > 0 else "cpu"
            break
    if show and isinstance(show.get("details"), dict) and isinstance(show.get("model_info"), dict):
        try:
            result["model_spec"] = asdict(spec_from_ollama_show(model, show))
        except (ResolverError, ValueError, TypeError) as exc:
            logger.debug("Ollama geometry unavailable: %s", exc)
            result["limitations"].append("Ollama metadata cannot bind full model geometry")
    result["source"] = "Ollama /api/show, /api/tags, /api/ps, /api/version"
    result["limitations"].append(
        "Ollama wrapper does not attest llama.cpp version, TP/PP or GPU identity"
    )
    return result


async def observe_vllm(client: httpx.AsyncClient, url: str, model: str) -> dict:
    """Read the supported0.30.0 structured server_info format; never evaluate text."""
    result = observation()
    version, error = await optional_metadata(client, "GET", url + "/version")
    result["version"] = version.get("version")
    result["backend"] = "vllm" if isinstance(result["version"], str) and result["version"] else None
    models, error = await optional_metadata(client, "GET", url + "/v1/models")
    if any(isinstance(row, dict) and row.get("id") == model for row in rows(models.get("data"))):
        result["model"] = model
    info, error = await optional_metadata(client, "GET", url + "/server_info?config_format=json")
    if error:
        result["limitations"].append(error)
    config = info.get("vllm_config")
    if isinstance(config, dict):
        model_config = object_value(config.get("model_config"))
        parallel = object_value(config.get("parallel_config"))
        result["quant"] = quant_name(model_config.get("quantization") or model_config.get("dtype"))
        result["context_length"] = positive_int(model_config.get("max_model_len"))
        result["tensor_parallel"] = positive_int(parallel.get("tensor_parallel_size"))
        result["pipeline_parallel"] = positive_int(parallel.get("pipeline_parallel_size"))
        result["serving_data_parallel_size"] = positive_int(parallel.get("data_parallel_size"))
        cache = object_value(config.get("cache_config")).get("enable_prefix_caching")
        result["prefix_cache"] = cache if type(cache) is bool else None
        device = object_value(config.get("device_config")).get("device")
        result["device"] = "cpu" if device == "cpu" else "gpu" if device == "cuda" else None
        hf_config = model_config.get("hf_config")
        if isinstance(hf_config, dict):
            try:
                result["model_spec"] = asdict(spec_from_hf(model, hf_config, None))
            except (ResolverError, ValueError, TypeError) as exc:
                logger.debug("vLLM geometry unavailable: %s", exc)
                result["limitations"].append("vLLM metadata cannot bind full model geometry")
        result["configuration_sha256"] = digest(
            {
                key: result[key]
                for key in (
                    "quant",
                    "context_length",
                    "tensor_parallel",
                    "pipeline_parallel",
                    "serving_data_parallel_size",
                    "prefix_cache",
                    "device",
                )
            }
        )
    else:
        result["limitations"].append("structured vLLM server configuration unavailable")
    result["source"] = "vLLM /version, /v1/models, /server_info?config_format=json"
    result["limitations"].append(
        "server GPU name alone does not bind capacity/geometry or immutable weights"
    )
    return result


async def observe_tgi(client: httpx.AsyncClient, url: str, model: str) -> dict:
    """TGI3.3.7 Info exposes identity and router limits, not quant/TP/GPU config."""
    result = observation()
    info, error = await optional_metadata(client, "GET", url + "/info")
    if error:
        result["limitations"].append(error)
    result["version"] = info.get("version")
    result["backend"] = "tgi" if isinstance(result["version"], str) and result["version"] else None
    result["model"] = info.get("model_id")
    result["model_digest"] = info.get("model_sha")
    result["router_max_total_tokens"] = positive_int(info.get("max_total_tokens"))
    result["router_max_input_tokens"] = positive_int(info.get("max_input_tokens"))
    result["source"] = "TGI /info (v3.3.7 Info schema)"
    result["limitations"].append(
        "Router token limits do not attest active model context, quant, TP/PP or GPU identity"
    )
    return result


async def observe_sglang(client: httpx.AsyncClient, url: str, model: str) -> dict:
    """Whitelist SGLang0.5.20 resolved config and current model identity."""
    result = observation()
    info, error = await optional_metadata(client, "GET", url + "/server_info")
    if error:
        info, error = await optional_metadata(client, "GET", url + "/get_server_info")
    if error:
        result["limitations"].append(error)
    current, error = await optional_metadata(client, "GET", url + "/model_info")
    if error:
        result["limitations"].append(error)
    result["version"] = info.get("version")
    result["backend"] = (
        "sglang" if isinstance(result["version"], str) and result["version"] else None
    )
    result["model"] = current.get("served_model_name")
    result["weight_version_label"] = current.get("weight_version")
    result["quant"] = quant_name(info.get("quantization") or info.get("dtype"))
    result["context_length"] = positive_int(info.get("context_length"))
    result["tensor_parallel"] = positive_int(info.get("tp_size"))
    result["pipeline_parallel"] = positive_int(info.get("pp_size"))
    result["serving_data_parallel_size"] = positive_int(info.get("dp_size"))
    cache_disabled = info.get("disable_radix_cache")
    result["prefix_cache"] = not cache_disabled if type(cache_disabled) is bool else None
    device = info.get("device")
    result["device"] = "cpu" if device == "cpu" else "gpu" if device in ("cuda", "hip") else None
    result["source"] = "SGLang /server_info resolved config and /model_info current identity"
    result["limitations"].append(
        "Weight version label is not an immutable digest; config does not attest GPU geometry"
    )
    return result
