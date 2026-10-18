"""Signed public facts are compared only after exact authentication and receiver trust."""

import base64
import copy
from dataclasses import asdict
import hashlib
import json
import os
from types import SimpleNamespace

import pytest

from chimeraforge import api
from chimeraforge.contrib import ContribError
from chimeraforge import signed_contribution as signed
from test_regression_gate import receipt, seal
from test_signed_contribution import PUBLIC, SEED
from test_signed_gate_payload import public_payload, resign

SECOND_SEED = b"2" * 32


def artifact(*, elapsed=1.0, ttft=2.0, serial=0, seed=SEED):
    value = receipt(elapsed=elapsed, ttft=ttft, serial=serial)
    value["execution"]["request"]["prompt_sha256"] = hashlib.sha256(b"hello").hexdigest()
    return api.sign_contribution(seal(value), seed)


def chosen(**changes):
    return api.RegressionPolicy(rules={"completed_token_rate_tps": 0.05}, **changes)


def gate(left=None, right=None, *, keys=(PUBLIC,), policy=None):
    from chimeraforge.signed_gate import gate_signed_contributions

    return gate_signed_contributions(
        [artifact()] if left is None else left,
        [artifact(elapsed=0.9)] if right is None else right,
        trusted_keys=keys,
        policy=chosen() if policy is None else policy,
    )


def flip_signature(value):
    result = (
        value.to_dict() if isinstance(value, signed.SignedContribution) else copy.deepcopy(value)
    )
    signature = bytearray(base64.b64decode(result["signature_base64"]))
    signature[0] ^= 1
    result["signature_base64"] = base64.b64encode(signature).decode()
    return result


def test_trusted_conditional_pass_reuses_native_wall_arithmetic_and_safe_defensive_report():
    result = gate(policy=chosen(fixed_controls={"device": "cpu"}))
    report = result.to_dict()
    assert isinstance(result, api.SignedContributionReceipt)
    assert (
        report["schema_version"] == 1 and report["kind"] == "chimeraforge.signed-contribution-gate"
    )
    assert report["status"] == "conditional_pass" and result.exit_code == 0
    metric = report["comparisons"][0]["metrics"]["completed_token_rate_tps"]
    assert metric["baseline"] == 12 and metric["candidate"] == pytest.approx(12 / 0.9)
    assert metric["state"] == "pass" and metric["unit"] == "tokens/second"
    assert report["baseline"][0]["signature_state"] == "valid"
    assert report["candidate"][0]["trust_state"] == "trusted_key"
    assert report["assurance"]["measurement_truth"] == "unverified"
    assert all(
        key not in json.dumps(report)
        for key in ("payload_base64", "public_payload", "individual_runs", "signature_base64")
    )
    report["comparisons"].clear()
    assert len(result.to_dict()["comparisons"]) == 1


def test_known_regression_joint_rules_are_not_averaged_away():
    result = gate(
        right=[artifact(elapsed=2, ttft=3)],
        policy=api.RegressionPolicy(rules={"completed_token_rate_tps": 0.05, "ttft_ms": 0.1}),
    ).to_dict()
    assert result["status"] == "regression" and result["exit_code"] == 1
    metrics = result["comparisons"][0]["metrics"]
    assert metrics["completed_token_rate_tps"]["regression_fraction"] == 0.5
    assert metrics["ttft_ms"]["regression_fraction"] == 0.5


def test_untrusted_pair_never_reaches_comparison_and_empty_trust_is_unavailable(monkeypatch):
    import chimeraforge.signed_gate as module

    monkeypatch.setattr(module, "_compare", lambda *a, **k: pytest.fail("untrusted comparison"))
    for keys in ((), (b"0" * 32,)):
        report = gate(keys=keys).to_dict()
        assert report["status"] == "inconclusive" and report["exit_code"] == 3
        assert report["comparisons"][0]["metrics"] == {}
        assert all(
            row["trust_state"] == "untrusted_key"
            for arm in ("baseline", "candidate")
            for row in report[arm]
        )


def test_all_auth_statuses_and_valid_pair_regression_survive_untrusted_other_slot():
    report = gate(
        [artifact(), artifact(elapsed=1.2)],
        [artifact(elapsed=2), artifact(elapsed=1.3, seed=SECOND_SEED)],
        policy=chosen(expected_replicates=2),
    ).to_dict()
    assert report["exit_code"] == 3 and len(report["candidate"]) == 2
    assert (
        report["comparisons"][0]["metrics"]["completed_token_rate_tps"]["regression_fraction"]
        == 0.5
    )
    assert report["comparisons"][1]["metrics"] == {}
    assert report["candidate"][1]["trust_state"] == "untrusted_key"


def test_authentication_failure_precedes_untrusted_evidence_and_keeps_every_status():
    report = gate(
        [flip_signature(artifact()), artifact(elapsed=1.2)],
        [artifact(elapsed=2), artifact(elapsed=1.3, seed=SECOND_SEED)],
        policy=chosen(expected_replicates=2),
    ).to_dict()
    assert report["exit_code"] == 1 and report["status"] == "authentication_failed"
    assert report["baseline"][0]["signature_state"] == "invalid"
    assert report["candidate"][1]["trust_state"] == "untrusted_key"
    assert all(row["metrics"] == {} for row in report["comparisons"])


def test_invalid_signature_payload_is_not_parsed_to_seek_higher_malformed_precedence():
    malformed = resign({}, raw=b"PRIVATE not-json")
    report = gate([flip_signature(malformed)]).to_dict()
    assert report["exit_code"] == 1 and report["status"] == "authentication_failed"
    assert "PRIVATE" not in json.dumps(report)


def test_authenticated_malformed_payload_has_highest_precedence_even_after_bad_signature():
    data = public_payload()
    data["request"]["output_token_cap"] = 3
    with pytest.raises(ContribError):
        gate([flip_signature(artifact())], [resign(data)])


@pytest.mark.parametrize(
    "change",
    [
        "prompt",
        "characters",
        "options",
        "context",
        "cap",
        "profile",
        "lengths",
        "incomplete",
        "cache",
        "required_unknown",
    ],
)
def test_public_commitment_or_condition_incompatibilities_are_inconclusive(change):
    payload = public_payload()
    payload["execution"]["elapsed_seconds"] = 0.9
    policy = chosen()
    if change == "prompt":
        payload["request"]["prompt_sha256"] = "c" * 64
    elif change == "characters":
        payload["request"]["prompt_characters"] += 1
    elif change == "options":
        payload["request"]["options_sha256"] = "d" * 64
    elif change == "context":
        payload["request"]["context_length"] = payload["measurement"]["context_length"] = 4096
    elif change == "cap":
        payload["request"]["output_token_cap"] = 5
    elif change == "profile":
        payload["request"]["workload"] = payload["measurement"]["workload"] = "batch"
    elif change == "lengths":
        for row in payload["measurement"]["individual_runs"]:
            row["prompt_tokens"] = 9
    elif change == "incomplete":
        payload["execution"].update(requested_count=4, failed_count=1)
        payload["request"]["requested_count"] = payload["measurement"]["runs"] = 4
    elif change == "cache":
        for phase in ("before", "after"):
            payload["observed_controls"][phase]["prefix_cache"] = None
        for row in payload["measurement"]["individual_runs"]:
            row["cached_prompt_tokens"] = None
    else:
        policy = chosen(fixed_controls={"tensor_parallel": 1})
    if change in ("lengths", "cache"):
        from chimeraforge.bench.metrics import RunMetrics, aggregate_runs

        payload["measurement"]["aggregate"] = asdict(
            aggregate_runs([RunMetrics(**row) for row in payload["measurement"]["individual_runs"]])
        )
    report = gate(right=[resign(payload)], policy=policy).to_dict()
    assert report["exit_code"] == 3 and report["comparisons"][0]["blockers"]


@pytest.mark.parametrize("ttft", [0, -1])
def test_zero_or_native_negative_ttft_sentinel_with_positive_prefill_is_unavailable(ttft):
    payload = public_payload()
    for row in payload["measurement"]["individual_runs"]:
        row["ttft_ms"] = ttft
    from chimeraforge.bench.metrics import RunMetrics, aggregate_runs

    payload["measurement"]["aggregate"] = asdict(
        aggregate_runs([RunMetrics(**row) for row in payload["measurement"]["individual_runs"]])
    )
    report = gate(
        right=[resign(payload)], policy=api.RegressionPolicy(rules={"ttft_ms": 0.05})
    ).to_dict()
    assert report["exit_code"] == 3
    assert report["comparisons"][0]["metrics"]["ttft_ms"]["candidate"] is None


def test_semantic_copies_ignore_source_signer_format_and_sample_order_but_not_population():
    payload = public_payload()
    rows = payload["measurement"]["individual_runs"]
    for index, row in enumerate(rows):
        row["ttft_ms"] = row["prompt_eval_duration_ms"] = index + 1.0
    from chimeraforge.bench.metrics import RunMetrics, aggregate_runs

    payload["measurement"]["aggregate"] = asdict(
        aggregate_runs([RunMetrics(**row) for row in rows])
    )
    duplicate = copy.deepcopy(payload)
    duplicate["source"] = {"sha256": "c" * 64, "fingerprint": "d" * 64, "scope": "held_file"}
    duplicate["measurement"]["individual_runs"].reverse()
    for row in duplicate["measurement"]["individual_runs"]:
        row["throughput_tps"] = int(row["throughput_tps"])
        row["cached_prompt_tokens"] = 0
    duplicate["execution"]["elapsed_seconds"] = 1
    duplicate["measurement"]["aggregate"] = asdict(
        aggregate_runs([RunMetrics(**row) for row in duplicate["measurement"]["individual_runs"]])
    )
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    second_public = (
        Ed25519PrivateKey.from_private_bytes(SECOND_SEED).public_key().public_bytes_raw()
    )
    report = gate(
        [resign(payload)],
        [resign(duplicate, raw=json.dumps(duplicate, indent=4).encode(), seed=SECOND_SEED)],
        keys=(PUBLIC, second_public),
    ).to_dict()
    assert report["exit_code"] == 3 and "duplicate_execution_payload" in report["blockers"]
    assert report["baseline"][0]["artifact_id"] != report["candidate"][0]["artifact_id"]
    assert report["baseline"][0]["evidence_sha256"] == report["candidate"][0]["evidence_sha256"]


@pytest.mark.parametrize("failure", ["missing", "oversize", "empty", "wrong_type"])
def test_key_admission_is_checked_before_optional_crypto(failure, tmp_path, monkeypatch):
    value = artifact()
    key = tmp_path / "key.pub"
    if failure != "missing":
        key.write_bytes(b"" if failure == "empty" else b"x" * (16 * 1024 + 1))
    keys = (object(),) if failure == "wrong_type" else (key,)
    monkeypatch.setattr(
        signed, "crypto", lambda: (_ for _ in ()).throw(signed.SigningUnavailable("unavailable"))
    )
    with pytest.raises(ContribError):
        gate([value], [value], keys=keys)


def test_missing_optional_crypto_is_unavailable_and_protects_all_held_paths(tmp_path, monkeypatch):
    left, right = artifact(), artifact(elapsed=0.9)
    key = tmp_path / "key.pub"
    key.write_bytes(PUBLIC)
    monkeypatch.setattr(
        signed, "crypto", lambda: (_ for _ in ()).throw(signed.SigningUnavailable("unavailable"))
    )
    result = gate([left], [right], keys=(key,))
    assert result.exit_code == 3 and all(
        row["signature_state"] == "unavailable" for row in result.to_dict()["baseline"]
    )
    alias = tmp_path / "alias.pub"
    os.link(key, alias)
    for path in (key, alias):
        with pytest.raises(ContribError):
            result.save(path)


def test_original_envelopes_keys_policy_read_once_and_occurrence_charged_before_clone(
    tmp_path, monkeypatch
):
    import chimeraforge.signed_gate_inputs as module

    original = artifact().to_dict()
    envelope, key, policy = (
        tmp_path / name for name in ("envelope.json", "key.pub", "policy.json")
    )
    raw = (json.dumps(original, indent=4) + "\n").encode()
    envelope.write_bytes(raw)
    key.write_bytes(PUBLIC)
    policy.write_text(json.dumps(asdict(chosen())))
    loader, calls = signed.load, []

    def counted(source, **kwargs):
        calls.append(source)
        return loader(source, **kwargs)

    monkeypatch.setattr(signed, "load", counted)
    result = gate([envelope], [envelope], keys=(key, key), policy=policy)
    report = result.to_dict()
    assert calls == [envelope]
    assert report["baseline"][0]["envelope_sha256"] == hashlib.sha256(raw).hexdigest()
    assert report["budgets"]["envelopes"]["charged_bytes"] == 2 * len(raw)
    for path in (envelope, key, policy):
        with pytest.raises(ContribError):
            result.save(path)
    monkeypatch.setattr(module, "MAX_TOTAL_ENVELOPE_BYTES", 2 * len(raw) - 1)
    clones = []
    monkeypatch.setattr(
        module, "copy", SimpleNamespace(deepcopy=lambda value: clones.append(value))
    )
    with pytest.raises(ContribError):
        gate([envelope], [envelope], keys=(key,), policy=policy)
    assert clones == []


@pytest.mark.parametrize(
    "expectation", ["https://secret.invalid", "/private/provider", "C:\\private\\provider"]
)
def test_nonpublic_policy_expectations_are_refused_without_echo(expectation):
    with pytest.raises(ContribError) as caught:
        gate(policy=chosen(fixed_controls={"model": expectation}))
    assert expectation not in str(caught.value)


@pytest.mark.parametrize("which", ["empty_arm", "large_arm", "large_keys", "list_keys"])
def test_closed_population_and_key_limits(which):
    left, keys = [artifact()], (PUBLIC,)
    if which == "empty_arm":
        left = []
    elif which == "large_arm":
        left *= 17
    elif which == "large_keys":
        keys *= 17
    else:
        keys = list(keys)
    with pytest.raises(ContribError):
        gate(left, keys=keys)


def refresh_payload(payload):
    from chimeraforge.bench.metrics import RunMetrics, aggregate_runs

    payload["measurement"]["aggregate"] = asdict(
        aggregate_runs([RunMetrics(**row) for row in payload["measurement"]["individual_runs"]])
    )
    return payload


def test_semantic_evidence_normalizes_observed_real_spellings_and_signed_zero():
    payload = public_payload()
    for phase in ("before", "after"):
        payload["observed_controls"][phase]["hardware.fp16_tflops"] = 64.0
        payload["observed_controls"][phase]["model_spec.recurrent_state_bytes_per_seq"] = 0.0
    duplicate = copy.deepcopy(payload)
    for phase in ("before", "after"):
        duplicate["observed_controls"][phase]["hardware.fp16_tflops"] = 64
        duplicate["observed_controls"][phase]["model_spec.recurrent_state_bytes_per_seq"] = -0.0
    result = gate([resign(payload)], [resign(duplicate)]).to_dict()
    assert result["exit_code"] == 3 and "duplicate_execution_payload" in result["blockers"]
    assert result["baseline"][0]["evidence_sha256"] == result["candidate"][0]["evidence_sha256"]


def test_duplicate_within_one_arm_blocks_without_erasing_valid_pair_fractions():
    result = gate(
        [artifact(), artifact()],
        [artifact(elapsed=0.9), artifact(elapsed=0.8)],
        policy=chosen(expected_replicates=2),
    ).to_dict()
    assert result["exit_code"] == 3 and "duplicate_execution_payload" in result["blockers"]
    assert len(result["comparisons"]) == 2
    assert all(
        row["metrics"]["completed_token_rate_tps"]["regression_fraction"] is not None
        for row in result["comparisons"]
    )


def test_extra_unpaired_population_is_consumed_verified_and_retained():
    result = gate([artifact(), artifact(elapsed=1.2)], [artifact(elapsed=0.9)]).to_dict()
    assert result["exit_code"] == 3 and "replicate_population" in result["blockers"]
    assert len(result["baseline"]) == 2 and len(result["comparisons"]) == 1
    assert result["baseline"][1]["signature_state"] == "valid"


def test_observed_disabled_cache_cannot_hide_positive_native_cache_counts():
    payload = public_payload()
    payload["execution"]["elapsed_seconds"] = 0.9
    for row in payload["measurement"]["individual_runs"]:
        row["cached_prompt_tokens"] = 1
    result = gate(right=[resign(refresh_payload(payload))]).to_dict()
    assert result["exit_code"] == 3
    assert "cache_contradiction" in result["comparisons"][0]["blockers"]


def test_unknown_actual_token_lengths_are_not_equated_to_positive_lengths():
    payload = public_payload()
    payload["execution"]["elapsed_seconds"] = 0.9
    for row in payload["measurement"]["individual_runs"]:
        row["prompt_tokens"] = None
    result = gate(right=[resign(refresh_payload(payload))]).to_dict()
    assert result["exit_code"] == 3
    assert "observed_token_lengths_unavailable" in result["comparisons"][0]["blockers"]


def test_held_public_key_path_is_read_once_and_sdk_accepts_public_pem(tmp_path, monkeypatch):
    import chimeraforge.signed_gate_inputs as module
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    pem = (
        Ed25519PrivateKey.from_private_bytes(SEED)
        .public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    )
    key = tmp_path / "trusted.pem"
    key.write_bytes(pem)
    read, calls = module._read, []

    def counted(path, limit):
        calls.append(path)
        return read(path, limit)

    monkeypatch.setattr(module, "_read", counted)
    result = gate(keys=(key, key))
    assert result.exit_code == 0 and calls == [key]
    assert result.to_dict()["budgets"]["keys"]["charged_bytes"] == 2 * len(pem)


@pytest.mark.parametrize("failure", ["policy", "envelope", "payload", "native_count"])
def test_structural_byte_and_population_limits_are_checked_without_comparisons(
    failure, tmp_path, monkeypatch
):
    import chimeraforge.signed_gate_inputs as module

    value = artifact()
    policy = chosen()
    left = [value]
    if failure == "policy":
        target = tmp_path / "policy.json"
        target.write_bytes(json.dumps(asdict(policy)).encode() + b" " * (64 * 1024))
        policy = target
    elif failure == "envelope":
        monkeypatch.setattr(module, "MAX_ENVELOPE_BYTES", 100)
    elif failure == "payload":
        monkeypatch.setattr(signed, "MAX_PAYLOAD_BYTES", 100)
    else:
        payload = public_payload()
        payload["measurement"]["individual_runs"] = [
            payload["measurement"]["individual_runs"][0]
        ] * 1001
        payload["measurement"]["runs"] = payload["request"]["requested_count"] = 1001
        payload["execution"].update(requested_count=1001, successful_count=1001)
        left = [resign(payload)]
    if failure != "native_count":
        monkeypatch.setattr(
            signed, "crypto", lambda: pytest.fail("crypto ran before bounded admission")
        )
    with pytest.raises(ContribError):
        gate(left, [value], policy=policy)


def test_exact_envelope_occurrence_budget_and_one_byte_over(tmp_path, monkeypatch):
    import chimeraforge.signed_gate_inputs as module

    paths = [tmp_path / name for name in ("baseline.json", "candidate.json")]
    for path, value in zip(paths, (artifact(), artifact(elapsed=0.9))):
        path.write_bytes((json.dumps(value.to_dict(), indent=3) + "\n").encode())
    total = sum(path.stat().st_size for path in paths)
    monkeypatch.setattr(module, "MAX_TOTAL_ENVELOPE_BYTES", total)
    assert gate([paths[0]], [paths[1]]).exit_code == 0
    monkeypatch.setattr(module, "MAX_TOTAL_ENVELOPE_BYTES", total - 1)
    with pytest.raises(ContribError):
        gate([paths[0]], [paths[1]])


def test_supported_maximum_arm_and_trust_collection_are_not_truncated():
    result = gate(
        [artifact(elapsed=1 + index * 0.02) for index in range(16)],
        [artifact(elapsed=0.5 + index * 0.02) for index in range(16)],
        policy=chosen(expected_replicates=16),
        keys=(PUBLIC,) * 16,
    ).to_dict()
    assert result["exit_code"] == 0 and len(result["comparisons"]) == 16
    assert len(result["baseline"]) == len(result["candidate"]) == 16


def test_computable_artifact_identity_failure_precedes_missing_crypto_without_payload_parse(
    monkeypatch,
):
    left, right = artifact().to_dict(), artifact(elapsed=0.9)
    left["id"] = "0" * 64
    monkeypatch.setattr(
        signed, "crypto", lambda: (_ for _ in ()).throw(signed.SigningUnavailable("unavailable"))
    )
    result = gate([left], [right]).to_dict()
    assert result["status"] == "authentication_failed" and result["exit_code"] == 1
    assert result["baseline"][0]["verification_status"] == "artifact_id_mismatch"
    assert result["baseline"][0]["signature_state"] == "unavailable"
    assert result["candidate"][0]["signature_state"] == "unavailable"
    assert result["comparisons"][0]["metrics"] == {}


@pytest.mark.parametrize(
    "field,default",
    [("cached_prompt_tokens", None), ("prompt_tokens", None), ("ttft_basis", "unknown")],
)
def test_signed_semantic_duplicates_canonicalize_all_accepted_optional_native_defaults(
    field, default
):
    payload = public_payload()
    for row in payload["measurement"]["individual_runs"]:
        row[field] = default
    refresh_payload(payload)
    omitted = copy.deepcopy(payload)
    for row in omitted["measurement"]["individual_runs"]:
        del row[field]
    refresh_payload(omitted)
    baseline, candidate = resign(payload), resign(omitted)
    assert api.verify_signed_contribution(baseline, trusted_keys=(PUBLIC,)).exit_code == 0
    assert api.verify_signed_contribution(candidate, trusted_keys=(PUBLIC,)).exit_code == 0
    report = gate([baseline], [candidate]).to_dict()
    assert report["exit_code"] == 3
    assert "duplicate_execution_payload" in report["blockers"]
    assert report["baseline"][0]["evidence_sha256"] == report["candidate"][0]["evidence_sha256"]


def test_public_native_sample_extras_are_still_closed_and_rejected():
    payload = public_payload()
    payload["measurement"]["individual_runs"][0]["PRIVATE-extra"] = "PRIVATE body"
    with pytest.raises(ContribError) as caught:
        gate(right=[resign(payload)])
    assert "PRIVATE" not in str(caught.value)
