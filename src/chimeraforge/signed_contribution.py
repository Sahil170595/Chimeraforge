"""Exact-byte Ed25519 envelopes; signatures, trust and measurement truth are separate."""

from __future__ import annotations

import base64
import binascii
import copy
from dataclasses import dataclass, field
import hashlib
from pathlib import Path
from types import ModuleType
from typing import Any, TYPE_CHECKING, cast

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm

from chimeraforge.bench.plan import PlanBenchmark
from chimeraforge.contrib import ContribError, quarantine_dir
from chimeraforge.signed_payload import (
    MAX_ENVELOPE_BYTES,
    MAX_KEY_BYTES,
    MAX_PAYLOAD_BYTES,
    MAX_TRUSTED_KEYS,
    fail,
    hash_json,
    held_json,
    json_bytes,
    load_benchmark,
    parse_json,
    project,
    sha,
    validate_payload,
)

KIND = "chimeraforge-signed-contribution"
DOMAIN = b"chimeraforge/signed-contribution/v2\x00ed25519\x00"
DOMAIN_LABEL = "chimeraforge/signed-contribution/v2"
PUBLIC_KEY_BYTES = 32
SIGNATURE_BYTES = 64
KEY_SEED_BYTES = 32


class SigningUnavailable(ContribError):
    """Optional crypto or platform support is unavailable, never a signature pass."""

    exit_code = 3


def crypto() -> tuple[
    type[Ed25519PrivateKey],
    type[Ed25519PublicKey],
    ModuleType,
    type[InvalidSignature],
    type[UnsupportedAlgorithm],
]:
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
            Ed25519PublicKey,
        )
        from cryptography.hazmat.primitives import serialization
        from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
    except ImportError:
        raise SigningUnavailable("signed operations require chimeraforge[sign]") from None
    return (
        Ed25519PrivateKey,
        Ed25519PublicKey,
        serialization,
        InvalidSignature,
        UnsupportedAlgorithm,
    )


def message(public_key: bytes, payload: bytes) -> bytes:
    return DOMAIN + public_key + len(payload).to_bytes(8, "big") + payload


def artifact_id(public_key: bytes, payload: bytes, signature: bytes) -> str:
    return hashlib.sha256(message(public_key, payload) + signature).hexdigest()


def _key_bytes(source: bytes | str | Path) -> tuple[bytes, tuple[Path, ...]]:
    from chimeraforge.plan_bundle import _read

    try:
        if isinstance(source, (str, Path)):
            path = Path(source).absolute()
            return _read(path, MAX_KEY_BYTES), (path,)
        if type(source) is bytes and 0 < len(source) <= MAX_KEY_BYTES:
            return source, ()
    except (ValueError, OSError, TypeError):
        fail("invalid bounded signing key")
    fail("invalid bounded signing key")


def _private(source: bytes | str | Path) -> tuple[Ed25519PrivateKey, tuple[Path, ...]]:
    Private, _, serialization, _, Unsupported = crypto()
    raw, paths = _key_bytes(source)
    try:
        key = (
            Private.from_private_bytes(raw)
            if len(raw) == KEY_SEED_BYTES
            else serialization.load_pem_private_key(raw, password=None)
        )
        if not isinstance(key, Private):
            fail("private key must be unencrypted Ed25519 raw32 or PKCS8 PEM")
        return cast("Ed25519PrivateKey", key), paths
    except Unsupported:
        raise SigningUnavailable("Ed25519 is unavailable on this crypto platform") from None
    except (ValueError, TypeError):
        fail("private key must be unencrypted Ed25519 raw32 or PKCS8 PEM")


def declared_key_paths(sources: tuple[bytes | str | Path, ...]) -> tuple[Path, ...]:
    if type(sources) not in (tuple, list) or len(sources) > MAX_TRUSTED_KEYS:
        fail("trusted keys must be a bounded explicit collection")
    paths = []
    for source in sources:
        if isinstance(source, (str, Path)):
            paths.append(Path(source).absolute())
        elif type(source) is not bytes or not 0 < len(source) <= MAX_KEY_BYTES:
            fail("invalid bounded trusted public key")
    return tuple(paths)


def _trusted(sources: tuple[bytes | str | Path, ...]) -> tuple[list[bytes], tuple[Path, ...]]:
    declared_key_paths(sources)
    _, Public, serialization, _, Unsupported = crypto()
    values: list[bytes] = []
    paths: list[Path] = []
    for source in sources:
        raw, key_paths = _key_bytes(source)
        paths.extend(key_paths)
        try:
            key = (
                Public.from_public_bytes(raw)
                if len(raw) == PUBLIC_KEY_BYTES
                else serialization.load_pem_public_key(raw)
            )
            if not isinstance(key, Public):
                fail("trusted keys must be Ed25519 public raw32 or public PEM")
            values.append(key.public_bytes_raw())
        except Unsupported:
            raise SigningUnavailable("Ed25519 is unavailable on this crypto platform") from None
        except (ValueError, TypeError):
            fail("trusted keys must be Ed25519 public raw32 or public PEM")
    return values, tuple(paths)


def check_output(path: str | Path, protected: tuple[Path, ...]) -> None:
    from chimeraforge.plan_study import protect_output

    try:
        protect_output(path, protected)
        if Path(path).resolve().is_relative_to(quarantine_dir().resolve()):
            fail("signed receipts cannot write into planner contribution quarantine")
    except (ValueError, OSError, RuntimeError):
        fail("signed output cannot replace consumed inputs or quarantine")


@dataclass(frozen=True)
class SignedContribution:
    """Defensive signed artifact; no private key or private workload is retained."""

    _data: dict[str, Any] = field(repr=False)
    _protected_paths: tuple[Path, ...] = field(default=(), repr=False)

    @property
    def exit_code(self) -> int:
        return 0

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._data)

    def check_output(self, path: str | Path) -> None:
        check_output(path, self._protected_paths)

    def save(self, path: str | Path) -> None:
        from chimeraforge.api import PlanArtifact

        self.check_output(path)
        try:
            PlanArtifact(self.to_dict()).save(path)
        except (ValueError, OSError):
            fail("signed artifact output failed")


@dataclass(frozen=True)
class SignedContributionReceipt(SignedContribution):
    """Operation receipt is distinct from the signed artifact and cannot establish trust."""

    @property
    def exit_code(self) -> int:
        return cast(int, self._data["exit_code"])


def load(
    source: SignedContribution | dict[str, Any] | str | Path,
) -> tuple[dict[str, Any], bytes, tuple[Path, ...]]:
    paths = source._protected_paths if isinstance(source, SignedContribution) else ()
    data, raw, received = held_json(
        source.to_dict() if isinstance(source, SignedContribution) else source, MAX_ENVELOPE_BYTES
    )
    return data, raw, paths + received


def _decode(data: dict[str, Any]) -> tuple[bytes, bytes, bytes]:
    if (
        set(data)
        != {
            "schema_version",
            "kind",
            "algorithm",
            "domain",
            "public_key_base64",
            "payload_base64",
            "signature_base64",
            "id",
        }
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 2
        or data["kind"] != KIND
        or data["algorithm"] != "ed25519"
        or data["domain"] != DOMAIN_LABEL
        or not sha(data["id"])
    ):
        fail()
    result = []
    for key, maximum in (
        ("public_key_base64", PUBLIC_KEY_BYTES),
        ("payload_base64", MAX_PAYLOAD_BYTES),
        ("signature_base64", SIGNATURE_BYTES),
    ):
        encoded = data[key]
        if type(encoded) is not str or not 0 < len(encoded) <= ((maximum + 2) // 3) * 4:
            fail()
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            fail()
        if (
            not 0 < len(raw) <= maximum
            or key != "payload_base64"
            and len(raw) != maximum
            or base64.b64encode(raw).decode() != encoded
        ):
            fail()
        result.append(raw)
    return result[0], result[1], result[2]


def result(
    data: dict,
    code: int,
    signature: str,
    trust: str,
    paths: tuple[Path, ...],
    *,
    payload: dict | None = None,
    status: str | None = None,
) -> SignedContributionReceipt:
    public, raw, _ = _decode(data)
    report = {
        "schema_version": 2,
        "kind": "chimeraforge.signed-contribution-verification",
        "contribution": {
            "id": data["id"],
            "payload_sha256": hashlib.sha256(raw).hexdigest(),
            "public_payload": payload,
        },
        "signature": {
            "state": signature,
            "algorithm": "ed25519",
            "public_key_sha256": hashlib.sha256(public).hexdigest(),
        },
        "trust": {
            "state": trust,
            "embedded_key_is_trust": False,
            "authenticates_producer_key": code == 0,
            "changes_quarantine": False,
            "changes_planner_corpus": False,
        },
        "status": status or {0: "verified", 1: "invalid", 3: "unavailable"}[code],
        "exit_code": code,
        "assurance": {
            "measurement_truth": "unverified",
            "original_hardware": "unverified",
            "served_weights": "unverified",
            "producer_identity_beyond_trusted_key": "unverified",
        },
    }
    report["fingerprint"] = hash_json(report)
    return SignedContributionReceipt(report, paths)


def sign(
    source: PlanBenchmark | dict | str | Path, private_key: bytes | str | Path
) -> SignedContribution:
    try:
        view = load_benchmark(source)
        payload = json_bytes(project(view))
        if len(payload) > MAX_PAYLOAD_BYTES:
            fail()
        key, key_paths = _private(private_key)
        public = key.public_key().public_bytes_raw()
        signature = key.sign(message(public, payload))
    except SigningUnavailable:
        raise
    except (ValueError, KeyError, TypeError, RecursionError):
        fail("invalid current native receipt or signing key")
    data = {
        "schema_version": 2,
        "kind": KIND,
        "algorithm": "ed25519",
        "domain": DOMAIN_LABEL,
        "public_key_base64": base64.b64encode(public).decode(),
        "payload_base64": base64.b64encode(payload).decode(),
        "signature_base64": base64.b64encode(signature).decode(),
        "id": artifact_id(public, payload, signature),
    }
    paths = ((view["path"],) if view["path"] is not None else ()) + key_paths
    return SignedContribution(data, paths)


def verify(
    source: SignedContribution | dict | str | Path,
    *,
    trusted_keys: tuple[bytes | str | Path, ...] = (),
) -> SignedContributionReceipt:
    data, _, paths = load(source)
    paths += declared_key_paths(trusted_keys)
    public, raw, signature = _decode(data)
    try:
        _, Public, _, InvalidSignature, Unsupported = crypto()
        trusted, key_paths = _trusted(trusted_keys)
        paths += key_paths
        try:
            Public.from_public_bytes(public).verify(signature, message(public, raw))
        except InvalidSignature:
            return result(data, 1, "invalid", "unverified", paths)
        except Unsupported:
            raise SigningUnavailable("Ed25519 is unavailable on this crypto platform") from None
        if artifact_id(public, raw, signature) != data["id"]:
            return result(data, 1, "invalid", "unverified", paths, status="artifact_id_mismatch")
        payload = parse_json(raw)
        validate_payload(payload)
    except SigningUnavailable:
        return result(data, 3, "unavailable", "unavailable", paths)
    except (ValueError, TypeError, KeyError, RecursionError):
        fail()
    return result(
        data,
        0 if public in trusted else 3,
        "valid",
        "trusted_key" if public in trusted else "untrusted_key",
        paths,
        payload=payload,
    )
