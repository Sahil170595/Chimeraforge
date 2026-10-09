"""Immutable Hub metadata, artifact compatibility and serving revision contracts."""

import copy
import hashlib
import json
from dataclasses import replace

import httpx
import pytest
from typer.testing import CliRunner

from chimeraforge import api
from chimeraforge.cli import app
from chimeraforge.planner import resolver

REPO = "test/checkpoint"
COMMIT = "a" * 40
NEXT = "b" * 40
CONFIG = {
    "model_type": "llama",
    "num_hidden_layers": 8,
    "num_attention_heads": 8,
    "num_key_value_heads": 4,
    "hidden_size": 512,
    "vocab_size": 32000,
}
RAW = json.dumps(CONFIG).encode()
BLOB = hashlib.sha1(b"blob " + str(len(RAW)).encode() + b"\0" + RAW).hexdigest()


def hub(monkeypatch, tmp_path, *, commit=COMMIT, config=RAW, info_changes=None):
    """Actual HTTPX response parsing without files, weights or remote traffic."""
    monkeypatch.setenv("CHIMERAFORGE_CACHE", str(tmp_path / "cache"))
    calls = []
    metadata = {
        "id": REPO,
        "sha": commit,
        "safetensors": {"total": 100000000},
        "siblings": [
            {"rfilename": "config.json", "size": len(RAW), "blobId": BLOB},
            {
                "rfilename": "model.safetensors",
                "size": 200000000,
                "blobId": "c" * 40,
                "lfs": {"sha256": "d" * 64, "size": 200000000},
            },
        ],
    }
    metadata.update(info_changes or {})

    def get(url, **kwargs):
        calls.append((url, kwargs))
        request = httpx.Request("GET", url)
        if "/api/models/" in url:
            return httpx.Response(200, json=metadata, request=request)
        assert f"/resolve/{commit}/config.json" in url, "mutable config fetch"
        return httpx.Response(
            200, content=config, headers={"x-repo-commit": commit}, request=request
        )

    monkeypatch.setattr(httpx, "get", get)
    return calls


def saved(monkeypatch, tmp_path, **options):
    hub(monkeypatch, tmp_path)
    return api.plan(api.PlanRequest(models=[REPO], quality_target=0, budget=100000, **options))


def test_main_is_resolved_once_before_config_and_weights(monkeypatch, tmp_path):
    calls = hub(monkeypatch, tmp_path)
    spec = resolver.resolve_spec(REPO, use_cache=False)
    identity = spec.checkpoint
    assert calls[0][0].endswith("/revision/main")
    assert len(calls) == 2
    assert identity["resolved_revision"] == COMMIT
    assert identity["requested_revision"] == "main"
    assert identity["config"]["sha256"] == hashlib.sha256(RAW).hexdigest()
    assert identity["weights"][0]["lfs_sha256"] == "d" * 64
    assert identity["weight_bytes_verified"] is False


def test_known_declared_metadata_change_at_bound_commit_is_actionable(monkeypatch, tmp_path):
    artifact = saved(monkeypatch, tmp_path, model_revisions={REPO: COMMIT})
    original = artifact.to_dict()
    declarations = copy.deepcopy(original["result"]["specs"][REPO]["checkpoint"]["weights"])
    row = declarations[0]
    hub(
        monkeypatch,
        tmp_path,
        info_changes={
            "siblings": [
                {"rfilename": "config.json", "size": len(RAW), "blobId": BLOB},
                {
                    "rfilename": row["path"],
                    "size": row["size"],
                    "blobId": row["git_blob_sha1"],
                    "lfs": {"sha256": "e" * 64},
                },
            ]
        },
    )
    checked = api.check_plan(artifact, allow_network=True).to_dict()
    view = checked["checkpoint_view"][REPO]
    assert checked["exit_code"] == 1
    assert view["pinned_metadata"]["state"] == "changed"
    assert view["served_weights"]["state"] == "unverified"
    assert artifact.to_dict() == original


def test_revision_measure_refuses_before_ollama_contact(monkeypatch):
    from chimeraforge import measure

    async def forbidden(*args, **kwargs):
        pytest.fail("revision cannot be attested by an Ollama measurement")

    monkeypatch.setattr(measure, "measure_model", forbidden)
    result = CliRunner().invoke(app, ["plan", "--model", REPO, "--revision", "main", "--measure"])
    assert result.exit_code == 1
    assert "cannot attest" in result.stdout


def test_requested_revision_is_url_encoded_and_never_config_ref(monkeypatch, tmp_path):
    calls = hub(monkeypatch, tmp_path)
    spec = resolver.resolve_spec(REPO, hf_revision="refs/pr/12", use_cache=False)
    assert calls[0][0].endswith("/revision/refs%2Fpr%2F12")
    assert spec.checkpoint["resolved_revision"] == COMMIT


@pytest.mark.parametrize("commit", [None, "main", "a" * 39, "g" * 40])
def test_unbound_commit_refused_before_config(monkeypatch, tmp_path, commit):
    calls = hub(monkeypatch, tmp_path, commit=commit)
    with pytest.raises(resolver.ResolverError, match="commit"):
        resolver.resolve_spec(REPO, use_cache=False)
    assert len(calls) == 1


def test_config_blob_mismatch_refused(monkeypatch, tmp_path):
    hub(monkeypatch, tmp_path, config=RAW + b" ")
    with pytest.raises(resolver.ResolverError, match="config"):
        resolver.resolve_spec(REPO, use_cache=False)


def test_nonweight_binary_metadata_is_not_reported_as_weight(monkeypatch, tmp_path):
    hub(
        monkeypatch,
        tmp_path,
        info_changes={
            "siblings": [
                {"rfilename": "config.json", "size": len(RAW), "blobId": BLOB},
                {"rfilename": "training_args.bin", "size": 6520, "blobId": "c" * 40},
                {"rfilename": "pytorch_model-00001-of-00002.bin", "size": 200, "blobId": "d" * 40},
            ]
        },
    )
    spec = resolver.resolve_spec(REPO, use_cache=False)
    assert [row["path"] for row in spec.checkpoint["weights"]] == [
        "pytorch_model-00001-of-00002.bin"
    ]


def test_explicit_pin_not_replaced_by_different_cached_ref(monkeypatch, tmp_path):
    hub(monkeypatch, tmp_path)
    first = resolver.resolve_spec(REPO)
    assert resolver.resolve_spec(REPO, hf_revision=COMMIT, allow_network=False) == replace(
        first, checkpoint={**first.checkpoint, "requested_revision": COMMIT}
    )
    with pytest.raises(resolver.ResolverError):
        resolver.resolve_spec(REPO, hf_revision=NEXT, allow_network=False)


@pytest.mark.parametrize(
    "options",
    [
        {"models": ["llama3.2-3b"], "model_revisions": {"llama3.2-3b": COMMIT}},
        {"models": [REPO], "model_revisions": {"other/repo": COMMIT}},
        {"models": [REPO], "model_revisions": {REPO: ""}},
        {"models": [REPO], "model_revisions": {REPO: "https://secret@host/"}},
    ],
)
def test_request_revision_scope_is_validated(options):
    with pytest.raises(api.PlanError):
        api.PlanRequest(**options).validate()


def test_plan_roundtrip_binds_consumed_checkpoint_and_omits_token(monkeypatch, tmp_path):
    artifact = saved(monkeypatch, tmp_path, model_revisions={REPO: COMMIT}, hf_token="secret-value")
    path = tmp_path / "plan.json"
    artifact.save(path)
    loaded = api.load_plan(path)
    assert loaded.spec(REPO).checkpoint["resolved_revision"] == COMMIT
    assert (
        loaded.to_dict()["result"]["replay_context"]["model_specs"][REPO]["checkpoint"]
        == loaded.spec(REPO).checkpoint
    )
    assert "secret-value" not in path.read_text()


def test_offline_check_never_contacts_hub_and_marks_alias_unknown(monkeypatch, tmp_path):
    artifact = saved(monkeypatch, tmp_path)
    before = artifact.to_dict()
    monkeypatch.setattr(httpx, "get", lambda *a, **k: pytest.fail("offline check contacted Hub"))
    checked = api.check_plan(artifact).to_dict()
    checkpoint = checked["checkpoint_view"][REPO]
    assert checkpoint["pinned_metadata"]["state"] == "unchanged"
    assert checkpoint["requested_ref"]["state"] == "unverified"
    assert checkpoint["served_weights"]["state"] == "unverified"
    assert checked["exit_code"] == 0
    assert artifact.to_dict() == before


def test_network_check_reports_moving_alias_without_substitution(monkeypatch, tmp_path):
    artifact = saved(monkeypatch, tmp_path)
    old_get = httpx.get

    def get(url, **kwargs):
        response = old_get(url, **kwargs)
        if url.endswith("/revision/main"):
            data = response.json()
            data["sha"] = NEXT
            return httpx.Response(200, json=data, request=response.request)
        return response

    monkeypatch.setattr(httpx, "get", get)
    checked = api.check_plan(artifact, allow_network=True).to_dict()
    assert checked["checkpoint_view"][REPO]["requested_ref"]["state"] == "changed"
    assert checked["checkpoint_view"][REPO]["pinned_metadata"]["state"] == "unchanged"
    assert checked["exit_code"] == 1
    assert artifact.spec(REPO).checkpoint["resolved_revision"] == COMMIT


@pytest.mark.parametrize("backend", ["vllm", "tgi", "sglang"])
def test_deployment_and_launch_emit_resolved_commit(monkeypatch, tmp_path, backend):
    from chimeraforge.deploy import export_deployment
    from chimeraforge.planner.launch import build_launch_command

    artifact = saved(monkeypatch, tmp_path)
    candidates = [
        artifact.candidate(i) for i in range(len(artifact.to_dict()["result"]["candidates"]))
    ]
    index = next(
        i
        for i, row in enumerate(candidates)
        if row.backend == backend and row.quant == "FP16" and row.n_agents == 1
    )
    deployment = export_deployment(
        artifact, format="compose", candidate_index=index, image="test/image:1"
    )
    assert COMMIT in deployment.content
    assert "--revision" in deployment.content
    launch = build_launch_command(candidates[index], artifact.spec(REPO), context_length=2048)
    assert f"--revision {COMMIT}" in launch.command


def test_ollama_launch_cannot_discard_checkpoint_pin(monkeypatch, tmp_path):
    from chimeraforge.planner.launch import build_launch_command

    artifact = saved(monkeypatch, tmp_path)
    candidate = replace(artifact.candidate(), backend="ollama")
    with pytest.raises(ValueError, match="revision|checkpoint"):
        build_launch_command(candidate, artifact.spec(REPO), context_length=2048)


def test_legacy_v2_loads_without_new_fields(monkeypatch, tmp_path):
    data = api.plan(api.PlanRequest(allow_network=False)).to_dict()
    data["inputs"].pop("model_revisions", None)
    for section in (data["result"]["specs"], data["result"]["replay_context"]["model_specs"]):
        for row in section.values():
            row.pop("checkpoint", None)
    data["fingerprint"] = api._digest({k: v for k, v in data.items() if k != "fingerprint"})
    assert api.artifact_from_dict(data).to_dict() == data


@pytest.mark.parametrize("mutation", ["revision", "hash", "weight-proof", "extra", "repo"])
def test_resigned_malformed_checkpoint_refused(monkeypatch, tmp_path, mutation):
    data = saved(monkeypatch, tmp_path).to_dict()
    identity = data["result"]["specs"][REPO]["checkpoint"]
    if mutation == "revision":
        identity["resolved_revision"] = "main"
    elif mutation == "hash":
        identity["config"]["sha256"] = "bad"
    elif mutation == "weight-proof":
        identity["weight_bytes_verified"] = True
    elif mutation == "extra":
        identity["hf_token"] = "secret"
    else:
        identity["repo"] = "other/repo"
    data["result"]["replay_context"]["model_specs"][REPO]["checkpoint"] = copy.deepcopy(identity)
    data["fingerprint"] = api._digest({k: v for k, v in data.items() if k != "fingerprint"})
    with pytest.raises(api.PlanError):
        api.artifact_from_dict(data)


def test_public_cli_revision_and_check(monkeypatch, tmp_path):
    hub(monkeypatch, tmp_path)
    path = tmp_path / "plan.json"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "plan",
            "--model",
            REPO,
            "--revision",
            COMMIT,
            "--quality-target",
            "0",
            "--budget",
            "100000",
            "--save",
            str(path),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    checked = runner.invoke(app, ["check", str(path), "--json"])
    assert checked.exit_code == 0, checked.output
    assert (
        json.loads(checked.output)["checkpoint_view"][REPO]["pinned_metadata"]["state"]
        == "unchanged"
    )


def test_v1_cannot_claim_explicit_revision_without_checkpoint():
    data = api.plan(api.PlanRequest(allow_network=False)).to_dict()
    data["schema_version"] = 1
    data["result"].pop("replay_context")
    data["inputs"]["models"] = [REPO]
    data["inputs"]["model_revisions"] = {REPO: COMMIT}
    data["result"]["target_models"] = [REPO]
    data["result"]["specs"] = {REPO: resolver.spec_from_hf(REPO, CONFIG, 0.1).to_dict()}
    data["result"]["candidates"] = []
    data["result"]["frontier"] = None
    data["fingerprint"] = api._digest({k: v for k, v in data.items() if k != "fingerprint"})
    with pytest.raises(api.PlanError, match="revision"):
        api.artifact_from_dict(data)


@pytest.mark.parametrize(
    "fields",
    [
        {"id": None},
        {"siblings": "bad"},
        {"safetensors": []},
        {"safetensors": {"total": True}},
        {"safetensors": {"total": 1.5}},
    ],
)
def test_malformed_hub_metadata_is_domain_error(monkeypatch, tmp_path, fields):
    hub(monkeypatch, tmp_path, info_changes=fields)
    with pytest.raises(resolver.ResolverError):
        resolver.resolve_spec(REPO, use_cache=False)


def test_explicit_commit_cannot_resolve_to_another_commit(monkeypatch, tmp_path):
    calls = hub(monkeypatch, tmp_path, commit=NEXT)
    with pytest.raises(resolver.ResolverError, match="different.*commit"):
        resolver.resolve_spec(REPO, hf_revision=COMMIT, use_cache=False)
    assert len(calls) == 1


def test_cache_key_collision_does_not_substitute_other_model(monkeypatch, tmp_path):
    hub(monkeypatch, tmp_path)
    other = resolver.spec_from_hf("test_check/point", CONFIG, 0.1)
    resolver._cache_store("test_check/point", other)
    assert resolver._cache_load("test/check_point") is None


def test_fresh_same_pin_does_not_change_due_to_capture_clock(monkeypatch, tmp_path):
    artifact = saved(monkeypatch, tmp_path, model_revisions={REPO: COMMIT})
    checked = api.check_plan(artifact, allow_network=True).to_dict()
    assert checked["checkpoint_view"][REPO]["pinned_metadata"]["state"] == "unchanged"
    assert checked["exit_code"] == 0


def test_cache_unavailable_is_not_weight_or_alias_proof(monkeypatch, tmp_path):
    artifact = saved(monkeypatch, tmp_path)
    monkeypatch.setattr(resolver, "_cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: pytest.fail("offline network"))
    checked = api.check_plan(artifact).to_dict()
    assert checked["checkpoint_view"][REPO]["pinned_metadata"]["state"] == "unverified"
    assert checked["exit_code"] == 0


@pytest.mark.parametrize(
    "selections",
    [
        [COMMIT, NEXT],
        [f"other/repo={COMMIT}"],
        ["https://user:secret@host/path"],
    ],
)
def test_bad_cli_revisions_refused_without_contact(monkeypatch, selections):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: pytest.fail("invalid input contacted Hub"))
    args = ["plan", "--model", REPO, "--json"]
    for selection in selections:
        args += ["--revision", selection]
    result = CliRunner().invoke(app, args)
    assert result.exit_code != 0
    assert "Traceback" not in result.output


def test_network_cli_opt_in_does_not_persist_auth(monkeypatch, tmp_path):
    artifact = saved(monkeypatch, tmp_path, model_revisions={REPO: COMMIT})
    path = tmp_path / "saved.json"
    artifact.save(path)
    before = path.read_bytes()
    result = CliRunner().invoke(
        app, ["check", str(path), "--network", "--hf-token", "secret", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert "secret" not in result.output
    assert path.read_bytes() == before


def test_legacy_unknown_checkpoint_enrichment_is_not_known_change(monkeypatch, tmp_path):
    artifact = saved(monkeypatch, tmp_path)
    spec = artifact.spec(REPO)
    data = artifact.to_dict()
    for section in (data["result"]["specs"], data["result"]["replay_context"]["model_specs"]):
        section[REPO].pop("checkpoint")
    data["inputs"].pop("model_revisions")
    data["fingerprint"] = api._digest({k: v for k, v in data.items() if k != "fingerprint"})
    legacy = api.artifact_from_dict(data)
    monkeypatch.setattr(resolver, "resolve_spec", lambda *args, **kwargs: spec)
    checked = api.check_plan(legacy).to_dict()
    assert checked["resolution_view"][REPO]["state"] == "unchanged"
    assert checked["checkpoint_view"][REPO]["pinned_metadata"]["state"] == "unverified"
    assert checked["exit_code"] == 0
