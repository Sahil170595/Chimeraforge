"""Signature/trust separation and private recorded-profile replay, never wire equivalence."""

from __future__ import annotations

import asyncio
import base64
import copy
from dataclasses import asdict
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from chimeraforge import api
from chimeraforge.contrib import ContribError
from test_regression_gate import receipt, seal

crypto = pytest.importorskip("cryptography")
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
PUBLIC = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")


def benchmark():
    value = receipt()
    value["execution"]["request"]["prompt_sha256"] = hashlib.sha256(b"hello").hexdigest()
    return seal(value)


def test_installed_sdk_matches_rfc8032_vector_one():
    key = Ed25519PrivateKey.from_private_bytes(SEED)
    expected = bytes.fromhex(
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555f"
        "b8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
    )
    assert key.public_key().public_bytes_raw() == PUBLIC and key.sign(b"") == expected


def test_signed_payload_is_private_and_embedded_key_never_establishes_trust():
    original = benchmark()
    original["measurement"]["warnings"] = ["PRIVATE COMPLETION token=secret"]
    original["execution"]["request"]["options"]["private-option"] = "PRIVATE OPTION"
    original["execution"]["endpoint"] = "http://user:secret@host/private"
    signed = api.sign_contribution(seal(original), SEED)
    envelope = signed.to_dict()
    payload = json.loads(base64.b64decode(envelope["payload_base64"]))
    assert envelope["schema_version"] == payload["schema_version"] == 2
    assert "PRIVATE" not in json.dumps(envelope) + json.dumps(payload)
    assert "secret" not in json.dumps(payload) and "options" not in payload["request"]
    assert api.verify_signed_contribution(signed).exit_code == 3
    verified = api.verify_signed_contribution(signed, trusted_keys=(PUBLIC,))
    assert verified.exit_code == 0 and verified.to_dict()["signature"]["state"] == "valid"
    assert verified.to_dict()["trust"]["state"] == "trusted_key"
    assert verified.to_dict()["assurance"]["measurement_truth"] == "unverified"
    envelope["signature_base64"] = "changed"
    assert signed.to_dict()["signature_base64"] != "changed"


@pytest.mark.parametrize("field", ["public_key_base64", "signature_base64", "payload_base64"])
def test_tamper_never_yields_signature_or_trust_pass(field):
    signed = api.sign_contribution(benchmark(), SEED).to_dict()
    value = bytearray(base64.b64decode(signed[field]))
    value[-1] ^= 1
    signed[field] = base64.b64encode(value).decode()
    assert api.verify_signed_contribution(signed, trusted_keys=(PUBLIC,)).exit_code == 1


def test_legacy_benchmark_cannot_be_upgraded_and_known_wrong_native_arithmetic_refused():
    with pytest.raises(ContribError):
        api.sign_contribution(benchmark()["measurement"], SEED)
    wrong = benchmark()
    for sample in wrong["measurement"]["individual_runs"]:
        sample["eval_duration_ms"] = 50.0
    from chimeraforge.bench.metrics import RunMetrics, aggregate_runs

    wrong["measurement"]["aggregate"] = asdict(
        aggregate_runs([RunMetrics(**row) for row in wrong["measurement"]["individual_runs"]])
    )
    wrong["execution"]["individual_runs"] = copy.deepcopy(wrong["measurement"]["individual_runs"])
    with pytest.raises(ContribError):
        api.sign_contribution(seal(wrong), SEED)


@pytest.mark.parametrize("profile", ["single", "batch", "server"])
@pytest.mark.asyncio
async def test_runner_failures_keep_counts_categories_without_provider_text(
    profile, caplog, monkeypatch
):
    from chimeraforge.bench import runner

    monkeypatch.setattr(runner.random, "expovariate", lambda *_: 0)
    backend = SimpleNamespace(
        generate=AsyncMock(side_effect=ValueError("SYNTHETIC_PRIVATE_PROVIDER_BODY"))
    )
    args = [backend, "mock-model", "mock-prompt", {}, 1]
    if profile != "single":
        args.append(1)
    if profile == "server":
        args.append(1.0)
    rows, warnings = await getattr(runner, "_run_" + profile)(*args)
    assert rows == [] and len(warnings) == 1 and "ValueError" in warnings[0]
    assert "SYNTHETIC_PRIVATE_PROVIDER_BODY" not in warnings[0] + caplog.text


@pytest.mark.parametrize("platform", ["missing_crypto", "unavailable_trusted_key"])
def test_unavailable_verification_protects_declared_key_aliases(tmp_path, monkeypatch, platform):
    import os
    import chimeraforge.signed_contribution as signed

    artifact = api.sign_contribution(benchmark(), SEED)
    trusted = tmp_path / "trusted.pub"
    trusted.write_bytes(PUBLIC)
    alias = tmp_path / "trusted-alias.pub"
    os.link(trusted, alias)

    def unavailable(*args, **kwargs):
        raise signed.SigningUnavailable("optional crypto unavailable")

    monkeypatch.setattr(
        signed, "crypto" if platform == "missing_crypto" else "_trusted", unavailable
    )
    result = api.verify_signed_contribution(artifact, trusted_keys=(trusted,))
    assert result.exit_code == 3
    for target in (trusted, alias):
        with pytest.raises(ContribError):
            result.check_output(target)
    assert trusted.read_bytes() == PUBLIC


@pytest.mark.asyncio
async def test_private_workload_mismatch_and_untrusted_signer_make_no_contact(monkeypatch):
    from chimeraforge.bench import runner

    def forbidden(*args, **kwargs):
        pytest.fail("receiver contacted endpoint before trusted private binding")

    monkeypatch.setattr(runner, "get_backend", forbidden)
    artifact = api.sign_contribution(benchmark(), SEED)
    for workload in (
        {"prompt": "wrong", "options": {"num_predict": 4, "num_ctx": 2048}},
        {"prompt": "hello", "options": {"num_predict": 4.0, "num_ctx": 2048}},
    ):
        result = await api.replay_signed_contribution(artifact, workload, trusted_keys=(PUBLIC,))
        assert result.exit_code == 1 and result.to_dict()["execution"]["attempted_count"] == 0
    untrusted = await api.replay_signed_contribution(
        artifact, {"prompt": "hello", "options": {"num_predict": 4, "num_ctx": 2048}}
    )
    assert untrusted.exit_code == 3


@pytest.mark.parametrize("failure", ["none", "partial", "all", "control", "cache"])
@pytest.mark.asyncio
async def test_recorded_profile_replay_retains_native_facts_and_refuses_partial_unknown_drift(
    monkeypatch, failure
):
    from test_contribution_review import ReplayBackend
    from chimeraforge.bench import runner

    backend = ReplayBackend(
        model="synthetic",
        fail=1 if failure == "partial" else 3 if failure == "all" else 0,
        device="gpu" if failure == "control" else "cpu",
    )
    observe = backend.observe_serving
    generate = backend.generate

    async def observed(model):
        return {**await observe(model), "prefix_cache": False}

    async def generated(model, prompt, options):
        row = await generate(model, prompt, options)
        row.cached_prompt_tokens = 2 if failure == "cache" else 0
        return row

    backend.observe_serving, backend.generate = observed, generated
    monkeypatch.setattr(runner, "get_backend", lambda *a, **kw: backend)
    artifact = api.sign_contribution(benchmark(), SEED)
    result = await api.replay_signed_contribution(
        artifact,
        {"prompt": "hello", "options": {"num_predict": 4, "num_ctx": 2048}},
        trusted_keys=(PUBLIC,),
    )
    expected = {"none": 0, "partial": 3, "all": 3, "control": 1, "cache": 1}[failure]
    assert result.exit_code == expected and backend.closed
    data = result.to_dict()
    assert data["execution"]["requested_count"] == 3 and len(backend.calls) == 3
    assert data["replay_equivalence"]["state"] == "current_recorded_profile_only"
    assert data["replay_equivalence"]["original_wire_options"] == "unverified"
    assert "secret" not in json.dumps(data) and "PRIVATE" not in json.dumps(data)
    if failure == "all":
        assert data["execution"]["failed_count"] == 3 and data["current"] is None


@pytest.mark.parametrize(
    "bad",
    [
        {"requested_count": 3, "successful_count": True, "failed_count": 2},
        {"requested_count": 3, "successful_count": 3, "failed_count": 1},
        {"requested_count": 3, "successful_count": 1},
        {"requested_count": 3, "successful_count": 1, "failed_count": 1},
    ],
)
def test_invalid_counter_views_never_invent_zero_attempts_or_unstarted_counts(bad):
    from chimeraforge.signed_replay import _counts

    counts = _counts(bad, 3)
    assert counts["attempted_count"] is counts["not_started_count"] is None
    assert counts["count_state"] == "unavailable"


@pytest.mark.asyncio
async def test_current_num_ctx_injection_does_not_rewrite_signed_options_or_fake_drift(monkeypatch):
    from chimeraforge.bench import runner
    from test_contribution_review import ReplayBackend

    original = benchmark()
    original["execution"]["request"]["options"].pop("num_ctx")
    signed = api.sign_contribution(seal(original), SEED)
    before = signed.to_dict()
    backend = ReplayBackend(model="synthetic")
    observe, generate = backend.observe_serving, backend.generate

    async def observed(model):
        return {**await observe(model), "prefix_cache": False}

    async def generated(model, prompt, options):
        row = await generate(model, prompt, options)
        row.cached_prompt_tokens = 0
        return row

    backend.observe_serving, backend.generate = observed, generated
    monkeypatch.setattr(runner, "get_backend", lambda *a, **kw: backend)
    replayed = await api.replay_signed_contribution(
        signed, {"prompt": "hello", "options": {"num_predict": 4}}, trusted_keys=(PUBLIC,)
    )
    assert replayed.exit_code == 0 and len(backend.calls) == 3
    assert all(call[2] == {"num_predict": 4, "num_ctx": 2048} for call in backend.calls)
    assert signed.to_dict() == before
    assert replayed.to_dict()["replay_equivalence"]["original_wire_options"] == "unverified"


@pytest.mark.parametrize(
    "declared,observed,expected",
    [
        ("synthetic", "synthetic:latest", 0),
        ("synthetic", "synthetic:other", 1),
        ("synthetic:q4", "synthetic:q4:latest", 1),
    ],
)
@pytest.mark.asyncio
async def test_supported_ollama_aliases_only_match_without_rewriting_signed_facts(
    monkeypatch, declared, observed, expected
):
    from chimeraforge.bench import runner
    from test_contribution_review import ReplayBackend

    original = benchmark()
    original["measurement"]["model"] = declared
    for phase in ("serving_before", "serving_after"):
        original["execution"][phase]["model"] = observed
    artifact = api.sign_contribution(seal(original), SEED)
    before = artifact.to_dict()
    backend = ReplayBackend(model=observed)
    observe, generate = backend.observe_serving, backend.generate

    async def observed_metadata(model):
        return {**await observe(model), "prefix_cache": False}

    async def generated(model, prompt, options):
        row = await generate(model, prompt, options)
        row.cached_prompt_tokens = 0
        return row

    backend.observe_serving, backend.generate = observed_metadata, generated
    monkeypatch.setattr(runner, "get_backend", lambda *a, **kw: backend)
    result = await api.replay_signed_contribution(
        artifact,
        {"prompt": "hello", "options": {"num_predict": 4, "num_ctx": 2048}},
        trusted_keys=(PUBLIC,),
    )
    assert result.exit_code == expected and len(backend.calls) == 3
    assert artifact.to_dict() == before


@pytest.mark.parametrize("format", ["auto", "v1", "v2"])
@pytest.mark.parametrize("command", ["verify", "replay"])
def test_structured_cli_malformed_inputs_never_echo_private_values(tmp_path, format, command):
    from typer.testing import CliRunner
    from chimeraforge.cli import app

    source = tmp_path / "malformed.json"
    source.write_text('{"schema_version":"SYNTHETIC_PRIVATE_FIELD_VALUE"}')
    args = ["contribute", command, str(source), "--format", format, "--json"]
    if command == "replay":
        args += ["--private-workload", str(tmp_path / "missing-private.json")]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 2
    assert json.loads(result.output)["error"]
    assert "SYNTHETIC_PRIVATE_FIELD_VALUE" not in result.output


def test_explicit_v2_missing_file_has_bounded_json_error(tmp_path):
    from typer.testing import CliRunner
    from chimeraforge.cli import app

    result = CliRunner().invoke(
        app,
        [
            "contribute",
            "replay",
            str(tmp_path / "missing.json"),
            "--format",
            "v2",
            "--private-workload",
            str(tmp_path / "missing-private.json"),
            "--json",
        ],
    )
    assert result.exit_code == 2 and json.loads(result.output)["error"]


def test_signed_cli_sign_verify_private_replay_and_all_input_aliases(tmp_path, monkeypatch):
    import os
    from cryptography.hazmat.primitives import serialization
    from typer.testing import CliRunner
    from chimeraforge.cli import app

    source, key, trusted, private, artifact = [
        tmp_path / name
        for name in ("native.json", "key.pem", "trusted.pem", "private.json", "signed.json")
    ]
    source.write_text(json.dumps(benchmark()))
    signing_key = Ed25519PrivateKey.from_private_bytes(SEED)
    key.write_bytes(
        signing_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    trusted.write_bytes(
        signing_key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    private.write_text(
        json.dumps({"prompt": "hello", "options": {"num_predict": 4, "num_ctx": 2048}})
    )
    runner = CliRunner()
    signed = runner.invoke(
        app,
        [
            "contribute",
            "sign",
            str(source),
            "--private-key",
            str(key),
            "--out",
            str(artifact),
            "--json",
        ],
    )
    assert signed.exit_code == 0, signed.output
    assert json.loads(signed.output) == json.loads(artifact.read_bytes())
    args = ["contribute", "verify", str(artifact), "--format", "v2", "--json"]
    assert runner.invoke(app, args).exit_code == 3
    verified = runner.invoke(app, [*args, "--trusted-key", str(trusted)])
    assert (
        verified.exit_code == 0 and json.loads(verified.output)["trust"]["state"] == "trusted_key"
    )
    from chimeraforge.bench import runner as benchmark_runner

    monkeypatch.setattr(
        benchmark_runner, "get_backend", lambda *a, **kw: pytest.fail("alias contacted backend")
    )
    aliases = []
    for path in (artifact, private, trusted):
        alias = tmp_path / (path.name + ".alias")
        os.link(path, alias)
        aliases.extend((path, alias))
    replay_args = [
        "contribute",
        "replay",
        str(artifact),
        "--format",
        "v2",
        "--private-workload",
        str(private),
        "--trusted-key",
        str(trusted),
        "--json",
    ]
    for path in aliases:
        before = path.read_bytes()
        refused = runner.invoke(app, [*replay_args, "--out", str(path)])
        assert refused.exit_code == 2 and json.loads(refused.output)["error"]
        assert path.read_bytes() == before
    for path in (source, key):
        original = path.read_bytes()
        refused = runner.invoke(
            app,
            [
                "contribute",
                "sign",
                str(source),
                "--private-key",
                str(key),
                "--out",
                str(path),
                "--json",
            ],
        )
        assert refused.exit_code == 2 and path.read_bytes() == original


@pytest.mark.parametrize("raw", [b"", b"x" * 31, b"x" * 33, b"PRIVATE invalid PEM"])
def test_wrong_private_key_lengths_and_pem_never_escape(raw):
    with pytest.raises(ContribError) as caught:
        api.sign_contribution(benchmark(), raw)
    assert "PRIVATE" not in str(caught.value)


@pytest.mark.parametrize(
    "mutation", ["domain", "algorithm", "duplicate", "nonfinite", "extra", "wrong-native"]
)
def test_signed_malformed_schema_and_semantics_are_rejected_without_rewrite(mutation):
    import chimeraforge.signed_contribution as signed

    envelope = api.sign_contribution(benchmark(), SEED).to_dict()
    if mutation in ("domain", "algorithm"):
        envelope[mutation] = "PRIVATE changed domain"
    else:
        raw = base64.b64decode(envelope["payload_base64"])
        payload = json.loads(raw)
        if mutation == "duplicate":
            raw = b'{"private-sentinel":1,"private-sentinel":2}'
        elif mutation == "nonfinite":
            raw = b'{"value":NaN}'
        else:
            if mutation == "extra":
                payload["PRIVATE key"] = "PRIVATE body"
            else:
                payload["measurement"]["individual_runs"][0]["eval_duration_ms"] = 50
            raw = json.dumps(payload).encode()
        signature = Ed25519PrivateKey.from_private_bytes(SEED).sign(signed.message(PUBLIC, raw))
        envelope.update(
            payload_base64=base64.b64encode(raw).decode(),
            signature_base64=base64.b64encode(signature).decode(),
            id=signed.artifact_id(PUBLIC, raw, signature),
        )
    with pytest.raises(ContribError) as caught:
        api.verify_signed_contribution(envelope, trusted_keys=(PUBLIC,))
    assert "PRIVATE" not in str(caught.value) and "private-sentinel" not in str(caught.value)


def test_signed_payload_exact_byte_format_is_verified_not_canonicalized():
    import chimeraforge.signed_contribution as signed

    envelope = api.sign_contribution(benchmark(), SEED).to_dict()
    payload = json.loads(base64.b64decode(envelope["payload_base64"]))
    pretty = json.dumps(payload, indent=2).encode()
    signature = Ed25519PrivateKey.from_private_bytes(SEED).sign(signed.message(PUBLIC, pretty))
    envelope.update(
        payload_base64=base64.b64encode(pretty).decode(),
        signature_base64=base64.b64encode(signature).decode(),
        id=signed.artifact_id(PUBLIC, pretty, signature),
    )
    assert api.verify_signed_contribution(envelope, trusted_keys=(PUBLIC,)).exit_code == 0
    compact = json.dumps(payload, separators=(",", ":")).encode()
    envelope["payload_base64"] = base64.b64encode(compact).decode()
    envelope["id"] = signed.artifact_id(PUBLIC, compact, signature)
    assert api.verify_signed_contribution(envelope, trusted_keys=(PUBLIC,)).exit_code == 1


@pytest.mark.parametrize("counter", ["bool", "missing", "undercount", "overcount"])
@pytest.mark.asyncio
async def test_bad_fresh_counter_views_remain_unavailable_with_no_invented_totals(
    monkeypatch, counter
):
    from chimeraforge.bench import runner
    from test_contribution_review import ReplayBackend

    backend = ReplayBackend(model="synthetic")
    monkeypatch.setattr(runner, "get_backend", lambda *a, **kw: backend)
    native_run = runner.run_benchmark

    async def changed(**kwargs):
        result = await native_run(**kwargs)
        evidence = kwargs["_evidence"]
        if counter == "bool":
            evidence.update(successful_count=True, failed_count=2)
        elif counter == "missing":
            evidence.pop("failed_count")
        elif counter == "undercount":
            evidence.update(successful_count=1, failed_count=1)
        else:
            evidence.update(successful_count=3, failed_count=1)
        return result

    monkeypatch.setattr(runner, "run_benchmark", changed)
    result = await api.replay_signed_contribution(
        api.sign_contribution(benchmark(), SEED),
        {"prompt": "hello", "options": {"num_predict": 4, "num_ctx": 2048}},
        trusted_keys=(PUBLIC,),
    )
    data = result.to_dict()
    assert result.exit_code == 3 and backend.closed and len(backend.calls) == 3
    assert data["execution"]["count_state"] == "unavailable"
    assert data["execution"]["attempted_count"] is data["execution"]["not_started_count"] is None


@pytest.mark.asyncio
async def test_original_partial_and_unknown_basis_never_qualify_replay(monkeypatch):
    from chimeraforge.bench import runner
    from chimeraforge.bench.metrics import RunMetrics, aggregate_runs
    from test_contribution_review import ReplayBackend

    original = benchmark()
    original["measurement"]["individual_runs"].pop()
    original["measurement"]["aggregate"] = asdict(
        aggregate_runs([RunMetrics(**row) for row in original["measurement"]["individual_runs"]])
    )
    original["execution"]["individual_runs"] = copy.deepcopy(
        original["measurement"]["individual_runs"]
    )
    original["execution"].update(successful_count=2, failed_count=1)
    monkeypatch.setattr(
        runner, "get_backend", lambda *a, **kw: pytest.fail("partial original contacted backend")
    )
    partial = await api.replay_signed_contribution(
        api.sign_contribution(seal(original), SEED),
        {"prompt": "hello", "options": {"num_predict": 4, "num_ctx": 2048}},
        trusted_keys=(PUBLIC,),
    )
    assert partial.exit_code == 3 and partial.to_dict()["execution"]["attempted_count"] == 0
    unknown = benchmark()
    for row in unknown["measurement"]["individual_runs"]:
        row["ttft_basis"] = "unknown"
    unknown["execution"]["individual_runs"] = copy.deepcopy(
        unknown["measurement"]["individual_runs"]
    )
    backend = ReplayBackend(model="synthetic")
    monkeypatch.setattr(runner, "get_backend", lambda *a, **kw: backend)
    unavailable = await api.replay_signed_contribution(
        api.sign_contribution(seal(unknown), SEED),
        {"prompt": "hello", "options": {"num_predict": 4, "num_ctx": 2048}},
        trusted_keys=(PUBLIC,),
    )
    assert unavailable.exit_code == 3 and backend.closed
    assert unavailable.to_dict()["comparison"]["metrics"]["decode_tps"]["raw_delta"] is None


def test_bounds_quarantine_exclusion_and_atomic_failure_preserve_sources(tmp_path, monkeypatch):
    from pathlib import Path
    import chimeraforge.signed_contribution as signed
    from chimeraforge.contrib import import_contribution, quarantine_dir, load_quarantine

    monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path / "cache"))
    artifact = api.sign_contribution(benchmark(), SEED)
    with pytest.raises(ContribError):
        api.verify_signed_contribution(artifact, trusted_keys=(PUBLIC,) * 17)
    target = tmp_path / "signed.json"
    artifact.save(target)
    with pytest.raises(ContribError):
        import_contribution(target)
    assert load_quarantine() == []
    with pytest.raises(ContribError):
        artifact.check_output(quarantine_dir() / "signed.json")
    monkeypatch.setattr(signed, "MAX_ENVELOPE_BYTES", 32)
    with pytest.raises(ContribError):
        api.verify_signed_contribution(target, trusted_keys=(PUBLIC,))
    output = tmp_path / "output.json"
    output.write_bytes(b"prior output")

    def failed(*args):
        raise OSError("fixture replacement refused")

    monkeypatch.setattr(Path, "replace", failed)
    with pytest.raises(ContribError):
        artifact.save(output)
    assert output.read_bytes() == b"prior output" and not list(tmp_path.glob("*.tmp"))
