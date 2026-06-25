"""Model discovery: enumerate candidate models from Ollama and Hugging Face.

Given hardware + workload constraints, find models worth deploying by pulling
candidates from a live Ollama install (``/api/tags``) and/or the HF Hub
(top text-generation repos by downloads), resolving each to a ModelSpec, and
running them through the planner's gate search.

Network discovery (``fetch_*``) is separated from the pure orchestration
(``best_per_model``) so the ranking logic is unit-testable offline.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from chimeraforge.planner.engine import Candidate, enumerate_candidates
from chimeraforge.planner.models import PlannerModels
from chimeraforge.planner.resolver import (
    DEFAULT_OLLAMA_URL,
    ModelSpec,
    ResolverError,
    _cache_dir,
    _NETWORK_TIMEOUT_S,
    _httpx,
    resolve_spec,
)

log = logging.getLogger("chimeraforge.planner.discovery")

SOURCE_OLLAMA = "ollama"
SOURCE_HF = "hf"
SOURCE_CATALOG = "catalog"
DEFAULT_HF_LIMIT = 8


# -- Network discovery -------------------------------------------------


def fetch_ollama_tags(base_url: str = DEFAULT_OLLAMA_URL) -> list[str]:
    """List models installed in a local Ollama (``GET /api/tags``)."""
    httpx = _httpx()
    try:
        resp = httpx.get(base_url.rstrip("/") + "/api/tags", timeout=_NETWORK_TIMEOUT_S)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", []) if m.get("name")]
    except httpx.HTTPError as exc:
        raise ResolverError(f"could not list Ollama models at {base_url}: {exc}") from exc


def fetch_hf_text_generation(
    limit: int = DEFAULT_HF_LIMIT, hf_token: str | None = None
) -> list[str]:
    """List the most-downloaded text-generation repos on the HF Hub."""
    httpx = _httpx()
    headers = {"Authorization": f"Bearer {hf_token}"} if hf_token else {}
    url = (
        "https://huggingface.co/api/models"
        f"?pipeline_tag=text-generation&sort=downloads&direction=-1&limit={limit}"
    )
    try:
        resp = httpx.get(url, headers=headers, timeout=_NETWORK_TIMEOUT_S, follow_redirects=True)
        resp.raise_for_status()
        return [m["id"] for m in resp.json() if m.get("id")]
    except httpx.HTTPError as exc:
        raise ResolverError(f"could not list HF models: {exc}") from exc


def discover_identifiers(
    sources: list[str],
    *,
    ollama_url: str | None = None,
    hf_token: str | None = None,
    hf_limit: int = DEFAULT_HF_LIMIT,
) -> list[str]:
    """Collect candidate identifiers from the requested sources."""
    ids: list[str] = []
    if SOURCE_OLLAMA in sources:
        ids.extend(fetch_ollama_tags(ollama_url or DEFAULT_OLLAMA_URL))
    if SOURCE_HF in sources:
        ids.extend(fetch_hf_text_generation(hf_limit, hf_token))
    return ids


def resolve_many(
    identifiers: list[str],
    *,
    ollama_url: str | None = None,
    hf_token: str | None = None,
    allow_network: bool = True,
) -> tuple[dict[str, ModelSpec], list[tuple[str, str]]]:
    """Resolve identifiers to specs, collecting (identifier, error) for failures."""
    specs: dict[str, ModelSpec] = {}
    errors: list[tuple[str, str]] = []
    for ident in identifiers:
        try:
            specs[ident] = resolve_spec(
                ident,
                ollama_url=ollama_url,
                hf_token=hf_token,
                allow_network=allow_network,
            )
        except ResolverError as exc:
            log.warning("skipping '%s': %s", ident, exc)
            errors.append((ident, str(exc)))
    return specs, errors


# -- Pure orchestration ------------------------------------------------


def best_per_model(candidates: list[Candidate]) -> list[Candidate]:
    """Keep the single best (cheapest) candidate per model, order preserved.

    ``enumerate_candidates`` already sorts by (cost asc, quality desc), so the
    first occurrence of each model is its best deployment config.
    """
    seen: set[str] = set()
    out: list[Candidate] = []
    for c in candidates:
        if c.model not in seen:
            seen.add(c.model)
            out.append(c)
    return out


def suggest(
    models: PlannerModels,
    specs: dict[str, ModelSpec],
    *,
    hardware: str,
    request_rate: float,
    latency_slo: float,
    quality_target: float,
    budget: float,
    avg_tokens: int,
    context_length: int,
    safety_target: float | None = None,
) -> list[Candidate]:
    """Plan every resolved model and return the best config per model, ranked."""
    candidates = enumerate_candidates(
        models=models,
        target_models=list(specs.keys()),
        hardware=hardware,
        request_rate=request_rate,
        latency_slo=latency_slo,
        quality_target=quality_target,
        budget=budget,
        avg_tokens=avg_tokens,
        context_length=context_length,
        safety_target=safety_target,
        specs=specs,
    )
    return best_per_model(candidates)


# -- Live catalog ------------------------------------------------------
#
# A persistent index of resolved ModelSpecs, so `suggest --source catalog`
# ranks a curated set of known-good models offline (after one `catalog build`).


def _catalog_path() -> Path:
    """Path to the on-disk catalog index (sibling of the spec cache)."""
    return _cache_dir().parent / "catalog.json"


def load_seed_catalog() -> list[str]:
    """Read the bundled curated seed list of model identifiers."""
    import importlib.resources as pkg_resources

    data_dir = pkg_resources.files("chimeraforge.planner") / "data"
    with pkg_resources.as_file(data_dir / "model_catalog.json") as p:
        return json.loads(p.read_text(encoding="utf-8")).get("models", [])


def build_catalog(
    *,
    include_seed: bool = True,
    include_ollama: bool = False,
    ollama_url: str | None = None,
    hf_token: str | None = None,
) -> tuple[dict[str, ModelSpec], list[tuple[str, str]]]:
    """Resolve the catalog's models (seed +/- installed Ollama) and persist them.

    Returns (resolved specs, errors). Writes the index to ``_catalog_path()`` so
    later ``load_catalog()`` calls (and ``suggest --source catalog``) need no
    network.
    """
    ids: list[str] = []
    if include_seed:
        ids.extend(load_seed_catalog())
    if include_ollama:
        ids.extend(fetch_ollama_tags(ollama_url or DEFAULT_OLLAMA_URL))
    # De-dup preserving order.
    ids = list(dict.fromkeys(ids))

    specs, errors = resolve_many(ids, ollama_url=ollama_url, hf_token=hf_token)
    _write_catalog(specs)
    return specs, errors


def _write_catalog(specs: dict[str, ModelSpec]) -> None:
    path = _catalog_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"models": {k: v.to_dict() for k, v in specs.items()}}
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        log.warning("could not write catalog %s: %s", path, exc)


def load_catalog() -> dict[str, ModelSpec]:
    """Load the persisted catalog index (empty dict if not built yet)."""
    path = _catalog_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8")).get("models", {})
        return {k: ModelSpec.from_dict(v) for k, v in data.items()}
    except (ValueError, TypeError) as exc:
        log.warning("ignoring corrupt catalog %s: %s", path, exc)
        return {}
