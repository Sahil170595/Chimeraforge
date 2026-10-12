"""Hub checkpoint receipts: consumed config bytes and declared weight metadata."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from urllib.parse import quote

HUB = "https://huggingface.co"
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
REVISION_RE = re.compile(r"[^\s\x00-\x1f\x7f:~^?*\[\\]+")
IDENTITY_FIELDS = {
    "version",
    "provider",
    "repo",
    "requested_revision",
    "resolved_revision",
    "captured_at",
    "config",
    "safetensors",
    "weights",
    "metadata_sha256",
    "weight_bytes_verified",
}
TIMEOUT_SECONDS = 15.0


def _weight_path(path) -> bool:
    # A .bin suffix alone also includes training_args/optimizer metadata.
    return isinstance(path, str) and (
        path.endswith(".safetensors")
        or bool(
            re.fullmatch(
                r"(?:.*/)?(?:pytorch_model(?:-\d+-of-\d+)?|adapter_model|model)\.bin", path
            )
        )
    )


def revision(value: str) -> str:
    """Validate a Hub ref without admitting URL credentials or command switches."""
    if (
        not isinstance(value, str)
        or not REVISION_RE.fullmatch(value)
        or value.startswith("-")
        or ".." in value
        or "@{" in value
        or any(part in ("", ".", "..") for part in value.split("/"))
    ):
        raise ValueError("HF revision must be a nonempty commit, branch or tag (not a URL)")
    return value


def revisions(values: dict[str, str] | None, models: list[str] | None) -> None:
    """Reject revisions for unselected or non-Hub targets before any resolution."""
    if values is None:
        return
    if not isinstance(values, dict):
        raise ValueError("model_revisions must map selected Hub model identifiers to revisions")
    for repo, value in values.items():
        if not isinstance(repo, str) or not REPO_RE.fullmatch(repo) or repo not in (models or []):
            raise ValueError("revisions apply only to selected Hugging Face org/model targets")
        revision(value)


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def facts(identity: dict) -> dict:
    """Identity facts exclude observation time and the alias used to obtain them."""
    return {
        key: copy.deepcopy(value)
        for key, value in identity.items()
        if key not in ("captured_at", "requested_revision")
    }


def _manifest(identity: dict) -> dict:
    return {key: identity[key] for key in ("repo", "resolved_revision", "safetensors", "weights")}


def _hash(value, pattern, label: str, *, optional: bool = False) -> None:
    if optional and value is None:
        return
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"invalid checkpoint {label}")


def _size(value, label: str) -> None:
    if value is not None and (type(value) is not int or value <= 0):
        raise ValueError(f"invalid checkpoint {label}")


def validate(identity: dict | None, *, repo: str, source: str) -> None:
    """Validate portable receipts, without upgrading declarations into file proof."""
    if identity is None:
        return  # Legacy, manual, registry and Ollama geometry has no Hub binding.
    if not isinstance(identity, dict) or set(identity) != IDENTITY_FIELDS:
        raise ValueError("invalid checkpoint identity fields")
    if type(identity["version"]) is not int or identity["version"] != 1:
        raise ValueError("unsupported checkpoint identity version")
    if identity["provider"] != "huggingface" or source != "hf" or identity["repo"] != repo:
        raise ValueError("checkpoint must bind the resolved HF repository")
    if not REPO_RE.fullmatch(repo):
        raise ValueError("invalid checkpoint repository")
    revision(identity["requested_revision"])
    _hash(identity["resolved_revision"], COMMIT_RE, "commit")
    if (
        COMMIT_RE.fullmatch(identity["requested_revision"])
        and identity["requested_revision"] != identity["resolved_revision"]
    ):
        raise ValueError("requested checkpoint commit differs from resolved commit")
    if (
        not isinstance(identity["captured_at"], str)
        or datetime.fromisoformat(identity["captured_at"]).tzinfo is None
    ):
        raise ValueError("checkpoint capture time must include a timezone")
    if identity["weight_bytes_verified"] is not False:
        raise ValueError("checkpoint metadata does not verify weight bytes")
    config = identity["config"]
    if (
        not isinstance(config, dict)
        or set(config) != {"path", "sha256", "git_blob_sha1"}
        or config["path"] != "config.json"
    ):
        raise ValueError("invalid checkpoint config receipt")
    _hash(config["sha256"], SHA256_RE, "config SHA256")
    _hash(config["git_blob_sha1"], COMMIT_RE, "config Git blob", optional=True)
    total = identity["safetensors"]
    _size(total, "safetensors total")
    if not isinstance(identity["weights"], list):
        raise ValueError("invalid checkpoint weight manifest")
    paths = []
    for row in identity["weights"]:
        if not isinstance(row, dict) or set(row) != {"path", "size", "git_blob_sha1", "lfs_sha256"}:
            raise ValueError("invalid checkpoint weight declaration")
        path = row["path"]
        if (
            not isinstance(path, str)
            or path.startswith(("/", "\\"))
            or "\\" in path
            or any(part in ("", ".", "..") for part in path.split("/"))
            or not _weight_path(path)
        ):
            raise ValueError("invalid checkpoint weight path")
        paths.append(path)
        _size(row["size"], "weight size")
        _hash(row["git_blob_sha1"], COMMIT_RE, "weight Git blob", optional=True)
        _hash(row["lfs_sha256"], SHA256_RE, "declared LFS SHA256", optional=True)
    if paths != sorted(set(paths)):
        raise ValueError("checkpoint weight paths must be unique and ordered")
    if identity["metadata_sha256"] != digest(_manifest(identity)):
        raise ValueError("checkpoint declared metadata fingerprint mismatch")


@dataclass(frozen=True)
class HFMetadata:
    config: dict
    params_b: float | None
    checkpoint: dict

    def __iter__(self):
        # Existing callers can still unpack config, params_b.
        yield self.config
        yield self.params_b


def model_info(httpx, repo: str, ref: str, token: str | None) -> dict:
    """Use the installed Hub SDK's public model_info revision/files_metadata API."""
    if not REPO_RE.fullmatch(repo):
        raise ValueError("HF repository must be org/model")
    revision(ref)
    response = httpx.get(
        f"{HUB}/api/models/{repo}/revision/{quote(ref, safe='')}",
        params={"blobs": True},
        headers={"Authorization": f"Bearer {token}"} if token else {},
        timeout=TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    if response.status_code in (401, 403):
        raise ValueError(f"HF repo '{repo}' is gated or inaccessible; set HF_TOKEN (or --hf-token)")
    if response.status_code == 404:
        raise ValueError(f"HF repo/revision '{repo}' not found or not accessible")
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("HF returned malformed model metadata")
    _hash(data.get("sha"), COMMIT_RE, "commit")
    if COMMIT_RE.fullmatch(ref) and data["sha"] != ref:
        raise ValueError("HF returned a different checkpoint commit")
    returned_repo = data.get("id", repo)
    if not isinstance(returned_repo, str) or returned_repo.casefold() != repo.casefold():
        raise ValueError("HF returned a different checkpoint repository")
    return data


def fetch(httpx, repo: str, token: str | None, ref: str = "main") -> HFMetadata:
    """Resolve one commit before config; weights are never downloaded by this API."""
    info = model_info(httpx, repo, ref, token)
    commit = info["sha"]
    response = httpx.get(
        f"{HUB}/{repo}/resolve/{commit}/config.json",
        headers={"Authorization": f"Bearer {token}"} if token else {},
        timeout=TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    response.raise_for_status()
    if response.headers.get("x-repo-commit", commit) != commit:
        raise ValueError("HF config response belongs to a different checkpoint commit")
    config = response.json()
    if not isinstance(config, dict):
        raise ValueError("HF config must be a JSON object")
    siblings = info.get("siblings", [])
    if not isinstance(siblings, list) or any(not isinstance(row, dict) for row in siblings):
        raise ValueError("HF returned malformed file declarations")
    config_rows = [row for row in siblings if row.get("rfilename") == "config.json"]
    if len(config_rows) > 1:
        raise ValueError("HF returned duplicate config declarations")
    blob = config_rows[0].get("blobId") if config_rows else None
    if blob is not None:
        actual_blob = hashlib.sha1(
            b"blob " + str(len(response.content)).encode() + b"\0" + response.content
        ).hexdigest()
        if blob != actual_blob:
            raise ValueError("HF config bytes differ from the declared checkpoint Git blob")
    weights = []
    for row in siblings:
        path = row.get("rfilename")
        if _weight_path(path):
            lfs = row.get("lfs") or {}
            if not isinstance(lfs, dict):
                raise ValueError("HF returned malformed LFS declarations")
            weights.append(
                {
                    "path": path,
                    "size": row.get("size"),
                    "git_blob_sha1": row.get("blobId"),
                    "lfs_sha256": lfs.get("sha256"),
                }
            )
    safetensors = info.get("safetensors") or {}
    if not isinstance(safetensors, dict):
        raise ValueError("HF returned malformed safetensors metadata")
    total = safetensors.get("total")
    identity = {
        "version": 1,
        "provider": "huggingface",
        "repo": repo,
        "requested_revision": ref,
        "resolved_revision": commit,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "path": "config.json",
            "sha256": hashlib.sha256(response.content).hexdigest(),
            "git_blob_sha1": blob,
        },
        "safetensors": total,
        "weights": sorted(weights, key=lambda row: row["path"]),
        "weight_bytes_verified": False,
    }
    identity["metadata_sha256"] = digest(_manifest(identity))
    validate(identity, repo=repo, source="hf")
    return HFMetadata(config, total / 1e9 if total is not None else None, identity)
