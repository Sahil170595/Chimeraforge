"""Portable inputs retain producer provenance and cannot change between verify/use."""

import copy
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import os
import shutil

import pytest
from typer.testing import CliRunner

from chimeraforge import api
from chimeraforge.cli import app
from chimeraforge.planner.models import load_bundled_models


def source_plan(tmp_path, *, quality=True, implicit=False, monkeypatch=None):
    producer = tmp_path / "producer"
    producer.mkdir()
    corpus = producer / "coefficients.json"
    data = asdict(load_bundled_models())
    data["vram"]["overhead_factor"] = 1.123
    corpus.write_text(json.dumps(data), encoding="utf-8")
    harness = producer / "private-evaluation.json"
    harness.write_text(
        json.dumps(
            {
                "results": {"mmlu": {"acc,none": 0.83}},
                "n-samples": {"mmlu": 5000},
                "config": {"private_prompt": "must never appear in metadata"},
            }
        ),
        encoding="utf-8",
    )
    if implicit:
        monkeypatch.setattr("chimeraforge.planner.resolver.measured_corpus_path", lambda: corpus)
    saved = api.plan(
        api.PlanRequest(
            allow_network=False,
            models_path=None if implicit else str(corpus),
            quality_from=str(harness) if quality else None,
            budget=1e6,
        )
    )
    path = producer / "original-plan.json"
    saved.save(path)
    return path, corpus, harness


def create(path, output):
    return api.create_plan_bundle(path, output)


def manifest(directory):
    return json.loads((directory / "manifest.json").read_bytes())


def resign_plan(data):
    data["fingerprint"] = api._digest({k: v for k, v in data.items() if k != "fingerprint"})
    return data


def test_actual_handoff_without_producer_files_preserves_bytes_and_native_comparison(tmp_path):
    path, corpus, harness = source_plan(tmp_path)
    raw = path.read_bytes()
    original = api.check_plan(path).to_dict()
    created = create(path, tmp_path / "bundle")
    assert created.to_dict()["fingerprint"] == api.load_plan(path).to_dict()["fingerprint"]
    relocated = tmp_path / "receiving-host"
    shutil.move(str(tmp_path / "bundle"), relocated)
    corpus.unlink()
    harness.unlink()
    verified = api.verify_plan_bundle(relocated)
    report = api.check_plan_bundle(relocated).to_dict()
    assert report["exit_code"] == 0 and report["comparison"] == original["comparison"]
    assert path.read_bytes() == raw == (relocated / "plan.json").read_bytes()
    assert api.check_plan(path).to_dict()["exit_code"] == 1
    for role in ("corpus", "quality"):
        receipt = report["bundle"]["relocations"][role]
        assert receipt["state"] == "verified_content"
        assert receipt["producer"]["path"].startswith(str(path.parent))
        assert receipt["local"]["path"].startswith(str(relocated))
        assert receipt["producer"] != receipt["local"]
        assert report["components"][role]["before"] != report["components"][role]["after"]
    meta = verified.to_dict()
    assert meta["source_authentication"] == "unverified"
    assert "private_prompt" not in json.dumps(meta)
    meta["relocations"].clear()
    assert verified.to_dict()["relocations"]


def test_implicit_external_corpus_is_portable(tmp_path, monkeypatch):
    path, corpus, _ = source_plan(tmp_path, quality=False, implicit=True, monkeypatch=monkeypatch)
    create(path, tmp_path / "bundle")
    corpus.unlink()
    assert api.check_plan_bundle(tmp_path / "bundle").to_dict()["exit_code"] == 0


def test_verified_bytes_are_used_even_if_file_changes_after_verification(tmp_path, monkeypatch):
    path, corpus, harness = source_plan(tmp_path)
    directory = tmp_path / "bundle"
    create(path, directory)
    verified = api.verify_plan_bundle(directory)
    corpus.unlink()
    harness.unlink()
    (directory / "quality.json").write_text("not JSON")
    monkeypatch.setattr(
        "chimeraforge.planner.models.load_models", lambda *_: pytest.fail("path reread")
    )
    monkeypatch.setattr(
        "chimeraforge.planner.service.load_quality_file", lambda *_: pytest.fail("path reread")
    )
    # Checking an already verified object consumes held bytes, never the mutated path.
    assert api.check_plan_bundle(verified).to_dict()["exit_code"] == 0
    with pytest.raises(api.PlanError):
        api.verify_plan_bundle(directory)


@pytest.mark.parametrize(
    "mutation",
    [
        "traversal",
        "duplicate",
        "extra_role",
        "missing_role",
        "wrong_size",
        "wrong_hash",
        "bool_size",
        "extra_field",
        "fingerprint",
    ],
)
def test_manifest_mutations_are_rejected(tmp_path, mutation):
    path, _, _ = source_plan(tmp_path)
    directory = tmp_path / "bundle"
    create(path, directory)
    value = manifest(directory)
    if mutation == "traversal":
        value["files"][0]["path"] = "../original-plan.json"
    elif mutation == "duplicate":
        value["files"].append(copy.deepcopy(value["files"][0]))
    elif mutation == "extra_role":
        value["files"][0]["role"] = "arbitrary"
    elif mutation == "missing_role":
        value["files"].pop()
    elif mutation == "wrong_size":
        value["files"][0]["size_bytes"] += 1
    elif mutation == "wrong_hash":
        value["files"][0]["sha256"] = "0" * 64
    elif mutation == "bool_size":
        value["files"][0]["size_bytes"] = True
    elif mutation == "extra_field":
        value["untrusted"] = "value"
    else:
        value["plan_fingerprint"] = "0" * 64
    (directory / "manifest.json").write_text(json.dumps(value))
    with pytest.raises(api.PlanError):
        api.verify_plan_bundle(directory)


@pytest.mark.parametrize(
    "mutation",
    ["extra_file", "missing_file", "directory", "plan", "source_receipt", "parsed_digest"],
)
def test_membership_and_producer_semantics_are_rejected(tmp_path, mutation):
    path, _, _ = source_plan(tmp_path)
    directory = tmp_path / "bundle"
    create(path, directory)
    if mutation == "extra_file":
        (directory / "secret.txt").write_text("secret")
    elif mutation == "missing_file":
        (directory / "quality.json").unlink()
    elif mutation == "directory":
        (directory / "other").mkdir()
    else:
        value = json.loads((directory / "plan.json").read_bytes())
        if mutation == "plan":
            value["fingerprint"] = "0" * 64
        elif mutation == "source_receipt":
            value["result"]["replay_context"]["quality"]["input"]["sha256"] = "0" * 64
        else:
            value["result"]["replay_context"]["corpus"]["sha256"] = "0" * 64
            value["corpus_sha256"] = value["result"]["corpus_sha256"] = "0" * 64
        raw = json.dumps(value if mutation == "plan" else resign_plan(value)).encode()
        (directory / "plan.json").write_bytes(raw)
        spec = manifest(directory)
        row = next(r for r in spec["files"] if r["role"] == "plan")
        row.update(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        spec["plan_fingerprint"] = value["fingerprint"]
        (directory / "manifest.json").write_text(json.dumps(spec))
    with pytest.raises(api.PlanError):
        api.verify_plan_bundle(directory)


@pytest.mark.parametrize(
    "mutation", ["changed_input", "legacy", "missing_binding", "contributions"]
)
def test_create_refuses_unsupported_or_changed_source_before_writing(tmp_path, mutation):
    path, corpus, _ = source_plan(tmp_path)
    value = json.loads(path.read_bytes())
    if mutation == "changed_input":
        corpus.write_text("{}")
    elif mutation == "legacy":
        value["schema_version"] = 1
        value["result"].pop("replay_context")
    elif mutation == "missing_binding":
        value["result"]["replay_context"]["corpus"]["input"] = None
    else:
        value["inputs"]["use_contributions"] = True
        value["result"]["replay_context"]["contributions"].update(
            enabled=True, records=[{"id": "unsigned", "sha256": "a" * 64}]
        )
    path.write_text(json.dumps(resign_plan(value)))
    with pytest.raises(api.PlanError):
        create(path, tmp_path / "bundle")
    assert not (tmp_path / "bundle").exists()
    assert not list(tmp_path.glob(".bundle-*"))


def test_foreign_producer_paths_are_preserved_not_coerced(tmp_path):
    # A re-signed protocol fixture, not evidence of an actual foreign producer.
    path, _, _ = source_plan(tmp_path)
    directory = tmp_path / "bundle"
    create(path, directory)
    value = json.loads((directory / "plan.json").read_bytes())
    context = value["result"]["replay_context"]
    for role in ("corpus", "quality"):
        binding = context[role]["input"]
        old = binding["path"]
        foreign = "/producer/" + role + ".json"
        binding.update(path=foreign, path_flavor="posix")
        if role == "quality":
            for row in context[role]["scores"]["cells"].values():
                assert row["source"] == old
                row["source"] = foreign
            context[role]["aggregate"]["source"] = foreign
    raw = json.dumps(resign_plan(value)).encode()
    (directory / "plan.json").write_bytes(raw)
    spec = manifest(directory)
    spec["plan_fingerprint"] = value["fingerprint"]
    spec["files"][0].update(sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw))
    (directory / "manifest.json").write_text(json.dumps(spec))
    report = api.check_plan_bundle(directory).to_dict()
    assert report["exit_code"] == 0
    assert (
        report["bundle"]["relocations"]["quality"]["producer"]["path"] == "/producer/quality.json"
    )


def test_cli_complete_create_verify_check_and_malformed_exit(tmp_path):
    path, corpus, harness = source_plan(tmp_path)
    runner = CliRunner()
    directory = tmp_path / "bundle"
    made = runner.invoke(app, ["bundle", "create", str(path), "--out", str(directory)])
    assert made.exit_code == 0, made.output
    corpus.unlink()
    harness.unlink()
    for command in ("verify", "check"):
        result = runner.invoke(app, ["bundle", command, str(directory), "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)
    result = runner.invoke(app, ["bundle", "check", str(tmp_path / "missing"), "--json"])
    assert result.exit_code == 2 and json.loads(result.output)["error"]


@pytest.mark.parametrize("role", ["plan.json", "corpus.json", "quality.json", "manifest.json"])
def test_bundle_rejects_actual_hardlinked_members(tmp_path, role):
    path, _, _ = source_plan(tmp_path)
    directory = tmp_path / "bundle"
    create(path, directory)
    os.link(directory / role, tmp_path / "alias")
    with pytest.raises(api.PlanError, match="links"):
        api.verify_plan_bundle(directory)


def test_bundle_rejects_symlink_member_or_directory(tmp_path):
    path, corpus, _ = source_plan(tmp_path)
    directory = tmp_path / "bundle"
    create(path, directory)
    (directory / "corpus.json").unlink()
    try:
        (directory / "corpus.json").symlink_to(corpus)
    except OSError:
        pytest.skip("OS does not permit symlinks; mandatory Linux CI exercises this")
    with pytest.raises(api.PlanError, match="links"):
        api.verify_plan_bundle(directory)
    alias = tmp_path / "alias"
    alias.symlink_to(directory, target_is_directory=True)
    with pytest.raises(api.PlanError, match="links"):
        api.verify_plan_bundle(alias)


def test_static_reparse_attribute_is_refused(tmp_path, monkeypatch):
    from chimeraforge import plan_bundle
    from types import SimpleNamespace
    import stat

    monkeypatch.setattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024, raising=False)
    monkeypatch.setattr(
        Path, "lstat", lambda _: SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=1024)
    )
    assert plan_bundle._links(tmp_path)


@pytest.mark.parametrize("interruption", [OSError, KeyboardInterrupt])
def test_atomic_write_failure_leaves_no_partial_bundle(tmp_path, monkeypatch, interruption):
    path, _, _ = source_plan(tmp_path)
    writer = Path.write_bytes

    def fail_after_first(self, data):
        if self.name == "corpus.json":
            raise interruption("injected failure")
        return writer(self, data)

    monkeypatch.setattr(Path, "write_bytes", fail_after_first)
    with pytest.raises(api.PlanError if interruption is OSError else KeyboardInterrupt):
        create(path, tmp_path / "bundle")
    assert not (tmp_path / "bundle").exists()
    assert not list(tmp_path.glob(".bundle-*"))


def test_existing_output_is_never_replaced(tmp_path):
    path, _, _ = source_plan(tmp_path)
    directory = tmp_path / "bundle"
    directory.mkdir()
    (directory / "keep").write_text("owned")
    with pytest.raises(api.PlanError):
        create(path, directory)
    assert (directory / "keep").read_text() == "owned"


def test_each_bundle_member_is_consumed_once_and_not_reread_by_check(tmp_path, monkeypatch):
    from chimeraforge import plan_bundle

    path, _, _ = source_plan(tmp_path)
    directory = tmp_path / "bundle"
    create(path, directory)
    read, calls = plan_bundle._read, []

    def counted(path, limit):
        calls.append(path.name)
        return read(path, limit)

    monkeypatch.setattr(plan_bundle, "_read", counted)
    verified = api.verify_plan_bundle(directory)
    assert sorted(calls) == ["corpus.json", "manifest.json", "plan.json", "quality.json"]
    assert api.check_plan_bundle(verified).to_dict()["exit_code"] == 0
    assert len(calls) == 4


def test_bundled_current_drift_is_separate_from_frozen_input_replay(tmp_path, monkeypatch):
    from chimeraforge.planner import models

    path = tmp_path / "plan.json"
    api.plan(api.PlanRequest(allow_network=False)).save(path)
    directory = tmp_path / "bundle"
    create(path, directory)
    current = models.load_bundled_models()
    current.vram.overhead_factor += 0.1
    monkeypatch.setattr(models, "load_bundled_models", lambda: current)
    report = api.check_plan_bundle(directory).to_dict()
    assert report["components"]["corpus"]["state"] == "unchanged"
    assert report["comparison"]["changed"] is False
    assert report["components"]["installed_bundled_corpus"]["state"] == "changed"
    assert report["exit_code"] == 1


def test_external_bundle_does_not_consume_unrelated_installed_corpus(tmp_path, monkeypatch):
    path, _, _ = source_plan(tmp_path)
    directory = tmp_path / "bundle"
    create(path, directory)
    monkeypatch.setattr(
        "chimeraforge.planner.models.load_bundled_models",
        lambda: pytest.fail("unrelated bundled corpus"),
    )
    report = api.check_plan_bundle(directory).to_dict()
    assert report["exit_code"] == 0
    assert "installed_bundled_corpus" not in report["components"]


def test_bound_bytes_and_parsed_quality_scores_must_both_match(tmp_path):
    path, _, _ = source_plan(tmp_path)
    value = json.loads(path.read_bytes())
    value["result"]["replay_context"]["quality"]["scores"]["cells"]["mmlu"]["score"] = 0.84
    value["result"]["replay_context"]["quality"]["aggregate"]["score"] = 0.84
    path.write_text(json.dumps(resign_plan(value)))
    with pytest.raises(api.PlanError, match="scores/source"):
        create(path, tmp_path / "bundle")


def test_size_limits_refuse_before_large_payload_read(tmp_path, monkeypatch):
    from chimeraforge import plan_bundle

    path, _, _ = source_plan(tmp_path)
    monkeypatch.setattr(plan_bundle, "MAX_INPUT_BYTES", 10)
    with pytest.raises(api.PlanError, match="bounded"):
        create(path, tmp_path / "bundle")
    assert not (tmp_path / "bundle").exists()


@pytest.mark.parametrize(
    "mutation",
    [
        "manifest_payload",
        "manifest_oversize",
        "manifest_duplicate",
        "manifest_hash",
        "input_missing",
        "input_duplicate",
        "input_extra",
        "input_oversize",
        "plan_oversize",
    ],
)
def test_constructed_bundle_objects_revalidate_all_held_manifest_and_bytes(tmp_path, mutation):
    path, _, _ = source_plan(tmp_path)
    saved = create(path, tmp_path / "bundle")
    if mutation == "manifest_payload":
        saved = replace(saved, _manifest_bytes=b'{"private_prompt":"unvalidated secret"}')
    elif mutation == "manifest_oversize":
        saved = replace(saved, _manifest_bytes=b" " * (64 * 1024 + 1))
    elif mutation in ("manifest_duplicate", "manifest_hash"):
        value = json.loads(saved._manifest_bytes)
        if mutation == "manifest_duplicate":
            value["files"].append(value["files"][0])
        else:
            value["files"][0]["sha256"] = "0" * 64
        saved = replace(saved, _manifest_bytes=json.dumps(value).encode())
    elif mutation == "input_missing":
        saved = replace(saved, _input_bytes=saved._input_bytes[:-1])
    elif mutation == "input_duplicate":
        saved = replace(saved, _input_bytes=saved._input_bytes + saved._input_bytes[:1])
    elif mutation == "input_extra":
        saved = replace(saved, _input_bytes=saved._input_bytes + (("other", b"{}"),))
    elif mutation == "input_oversize":
        saved = replace(saved, _input_bytes=(("corpus", b" " * (32 * 1024 * 1024 + 1)),))
    else:
        saved = replace(saved, _plan_bytes=b" " * (api.MAX_PLAN_BYTES + 1))
    for operation in (lambda: saved.to_dict(), lambda: api.check_plan_bundle(saved)):
        with pytest.raises(api.PlanError):
            operation()


def test_sdk_managed_packaged_hardlink_is_snapshotted_but_members_still_reject_links(
    tmp_path, monkeypatch
):
    from contextlib import contextmanager
    from chimeraforge import plan_bundle

    monkeypatch.setattr(
        "chimeraforge.planner.resolver.measured_corpus_path", lambda: tmp_path / "absent"
    )
    path = tmp_path / "plan.json"
    api.plan(api.PlanRequest(allow_network=False)).save(path)
    resource = plan_bundle.resources.files("chimeraforge.planner").joinpath(
        "data", "fitted_models.json"
    )
    packaged = tmp_path / "package-resource.json"
    packaged.write_bytes(resource.read_bytes())
    os.link(packaged, tmp_path / "uv-cache-alias")

    @contextmanager
    def sdk_file(_):
        yield packaged

    monkeypatch.setattr(plan_bundle.resources, "as_file", sdk_file)
    directory = tmp_path / "bundle"
    create(path, directory)
    assert api.verify_plan_bundle(directory).to_dict()["source_authentication"] == "unverified"
    os.link(directory / "corpus.json", tmp_path / "unsafe-member-alias")
    with pytest.raises(api.PlanError, match="links"):
        api.verify_plan_bundle(directory)


def test_verified_snapshot_never_resolves_or_relabels_its_captured_sources(tmp_path, monkeypatch):
    path, _, _ = source_plan(tmp_path)
    directory = tmp_path / "bundle"
    create(path, directory)
    saved = api.verify_plan_bundle(directory)
    before = saved.to_dict()
    resolve = Path.resolve
    calls = []

    def redirected(self, *args, **kwargs):
        if self.parent == directory:
            calls.append(self)
            return tmp_path / "new-target" / self.name
        return resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", redirected)
    assert saved.to_dict() == before
    assert api.check_plan_bundle(saved).to_dict()["bundle"] == before
    assert calls == []


def test_verified_snapshot_retains_locations_after_real_directory_link_replacement(tmp_path):
    import subprocess
    import sys

    path, _, _ = source_plan(tmp_path)
    directory = tmp_path / "bundle"
    create(path, directory)
    saved = api.verify_plan_bundle(directory)
    before = saved.to_dict()
    moved = tmp_path / "moved"
    directory.rename(moved)
    if sys.platform == "win32":

        def quoted(value):
            return "'" + str(value).replace("'", "''") + "'"

        command = (
            "New-Item -ItemType Junction -Path "
            + quoted(directory)
            + " -Target "
            + quoted(moved)
            + " | Out-Null"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
    else:
        directory.symlink_to(moved, target_is_directory=True)
    try:
        assert saved.to_dict() == before
        assert api.check_plan_bundle(saved).to_dict()["bundle"] == before
        with pytest.raises(api.PlanError, match="links"):
            api.verify_plan_bundle(directory)
    finally:
        # Remove only the task-owned link, never its moved target tree.
        directory.rmdir() if sys.platform == "win32" else directory.unlink()


@pytest.mark.parametrize(
    "payload",
    [
        [],
        None,
        "not a corpus",
        42,
        *(
            {key: []}
            for key in ("vram", "throughput", "scaling", "quality", "cost", "latency", "safety")
        ),
    ],
)
def test_malformed_selfconsistent_corpus_has_domain_error_on_disk_held_and_cli(tmp_path, payload):
    path, _, _ = source_plan(tmp_path)
    directory = tmp_path / "bundle"
    saved = create(path, directory)
    raw = json.dumps(payload).encode()
    data = json.loads(saved._plan_bytes)
    data["result"]["replay_context"]["corpus"]["input"]["sha256"] = hashlib.sha256(raw).hexdigest()
    raw_plan = json.dumps(resign_plan(data)).encode()
    spec = json.loads(saved._manifest_bytes)
    spec["plan_fingerprint"] = data["fingerprint"]
    for row in spec["files"]:
        value = raw if row["role"] == "corpus" else raw_plan if row["role"] == "plan" else None
        if value is not None:
            row.update(sha256=hashlib.sha256(value).hexdigest(), size_bytes=len(value))
    raw_manifest = json.dumps(spec).encode()
    held = replace(
        saved,
        _plan_bytes=raw_plan,
        _manifest_bytes=raw_manifest,
        _input_bytes=tuple(
            (role, raw if role == "corpus" else value) for role, value in saved._input_bytes
        ),
    )
    for operation in (held.to_dict, lambda: api.check_plan_bundle(held)):
        with pytest.raises(api.PlanError):
            operation()
    (directory / "corpus.json").write_bytes(raw)
    (directory / "plan.json").write_bytes(raw_plan)
    (directory / "manifest.json").write_bytes(raw_manifest)
    with pytest.raises(api.PlanError):
        api.verify_plan_bundle(directory)
    result = CliRunner().invoke(app, ["bundle", "verify", str(directory), "--json"])
    assert result.exit_code == 2 and json.loads(result.output)["error"]


def test_malformed_quality_timestamp_preserves_domain_errors_for_held_disk_cli(tmp_path):
    path, _, _ = source_plan(tmp_path)
    directory = tmp_path / "bundle"
    saved = create(path, directory)
    bad = json.dumps(
        {
            "results": {"mmlu": {"acc,none": 0.83}},
            "n-samples": {"mmlu": 5000},
            "date": 1e300,
        }
    ).encode()
    data = json.loads(saved._plan_bytes)
    data["result"]["replay_context"]["quality"]["input"]["sha256"] = hashlib.sha256(bad).hexdigest()
    raw_plan = json.dumps(resign_plan(data)).encode()
    spec = json.loads(saved._manifest_bytes)
    spec["plan_fingerprint"] = data["fingerprint"]
    for row in spec["files"]:
        value = bad if row["role"] == "quality" else raw_plan if row["role"] == "plan" else None
        if value is not None:
            row.update(sha256=hashlib.sha256(value).hexdigest(), size_bytes=len(value))
    raw_manifest = json.dumps(spec).encode()
    held = replace(
        saved,
        _plan_bytes=raw_plan,
        _manifest_bytes=raw_manifest,
        _input_bytes=tuple(
            (role, bad if role == "quality" else value) for role, value in saved._input_bytes
        ),
    )
    for operation in (held.to_dict, lambda: api.check_plan_bundle(held)):
        with pytest.raises(api.PlanError):
            operation()
    (directory / "quality.json").write_bytes(bad)
    (directory / "plan.json").write_bytes(raw_plan)
    (directory / "manifest.json").write_bytes(raw_manifest)
    with pytest.raises(api.PlanError):
        api.verify_plan_bundle(directory)
    result = CliRunner().invoke(app, ["bundle", "check", str(directory), "--json"])
    assert result.exit_code == 2 and json.loads(result.output)["error"]
