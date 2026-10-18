"""Re-signed native contradictions remain malformed despite valid cryptographic authentication."""

import base64
from dataclasses import asdict
import json

import pytest

from chimeraforge import api
from chimeraforge.bench.metrics import RunMetrics, aggregate_runs
from chimeraforge.contrib import ContribError
from chimeraforge import signed_contribution as signed
from test_signed_contribution import PUBLIC, SEED, benchmark


def resign(data, *, raw=None, seed=SEED):
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    encoded = (
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode() if raw is None else raw
    )
    key = Ed25519PrivateKey.from_private_bytes(seed)
    public = key.public_key().public_bytes_raw()
    signature = key.sign(signed.message(public, encoded))
    return {
        "schema_version": 2,
        "kind": signed.KIND,
        "algorithm": "ed25519",
        "domain": signed.DOMAIN_LABEL,
        "public_key_base64": base64.b64encode(public).decode(),
        "payload_base64": base64.b64encode(encoded).decode(),
        "signature_base64": base64.b64encode(signature).decode(),
        "id": signed.artifact_id(public, encoded, signature),
    }


def public_payload():
    artifact = api.sign_contribution(benchmark(), SEED).to_dict()
    return json.loads(base64.b64decode(artifact["payload_base64"]))


@pytest.mark.parametrize("engine", ["ollama", "vllm", "tgi", "sglang"])
def test_resigned_supported_ttft_prefill_contradiction_is_refused(engine):
    payload = public_payload()
    payload["measurement"]["backend"] = engine
    for phase in ("before", "after"):
        payload["observed_controls"][phase]["backend"] = engine
    for row in payload["measurement"]["individual_runs"]:
        row["ttft_ms"] = 9
        row["ttft_basis"] = (
            "server-prefill-duration" if engine == "ollama" else "client-stream-first-content"
        )
        row["throughput_tps"] = 40 if engine == "ollama" else 30
    payload["measurement"]["aggregate"] = asdict(
        aggregate_runs([RunMetrics(**row) for row in payload["measurement"]["individual_runs"]])
    )
    with pytest.raises(ContribError):
        api.verify_signed_contribution(resign(payload), trusted_keys=(PUBLIC,))


def test_resigned_generated_counts_above_explicit_public_cap_are_refused():
    payload = public_payload()
    payload["request"]["output_token_cap"] = 3
    with pytest.raises(ContribError):
        api.verify_signed_contribution(resign(payload), trusted_keys=(PUBLIC,))


def test_unsigned_cap_validation_boundary_is_unchanged_but_signing_cannot_accept_contradiction():
    from chimeraforge.bench.gate_inputs import load_receipt
    from test_regression_gate import seal

    source = benchmark()
    source["execution"]["request"]["options"]["num_predict"] = 3
    source = seal(source)
    assert load_receipt(source)["samples"][0].tokens_generated == 4
    with pytest.raises(ContribError):
        api.sign_contribution(source, SEED)


@pytest.mark.parametrize(
    "field", ["eval_duration_ms", "prompt_eval_duration_ms", "total_duration_ms"]
)
def test_negative_physical_timings_follow_existing_native_refusal(field):
    payload = public_payload()
    for row in payload["measurement"]["individual_runs"]:
        row[field] = -1
    with pytest.raises(ContribError):
        api.verify_signed_contribution(resign(payload), trusted_keys=(PUBLIC,))
