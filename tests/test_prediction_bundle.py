"""Private handoffs preserve original evidence bytes and never replace destinations."""

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from chimeraforge import api
from test_plan_bundle import source_plan
from test_prediction_score import frozen as frozen
from test_prediction_score import native, policy, seal


def functions():
    from chimeraforge.prediction_bundle import (
        create_prediction_bundle,
        score_prediction_bundle,
        verify_prediction_bundle,
    )

    return create_prediction_bundle, verify_prediction_bundle, score_prediction_bundle


def inputs(tmp_path, saved, *, receipts=None):
    plan = tmp_path / "original-plan.json"
    plan.write_bytes((json.dumps(saved.to_dict(), indent=3) + "\n\n").encode())
    chosen = tmp_path / "original-policy.json"
    chosen.write_bytes((json.dumps(policy(saved), indent=4) + "\n").encode())
    paths = []
    for index, data in enumerate([native(saved)] if receipts is None else receipts):
        path = tmp_path / f"original-receipt-{index}.json"
        path.write_bytes((json.dumps(data, indent=5) + "\n\n").encode())
        paths.append(path)
    return plan, chosen, paths


def comparable(report):
    return {key: value for key, value in report.items() if key not in ("created_at", "fingerprint")}


def test_pretty_original_bytes_and_single_scorer_semantics(frozen, tmp_path):
    create, verify, score = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    original = {path: path.read_bytes() for path in (plan, chosen, *receipts)}
    bundle = create(plan, receipts, policy=chosen, outdir=tmp_path / "bundle")
    direct = api.score_predictions(tmp_path / "bundle" / "plan", receipts, policy=chosen).to_dict()
    report = score(bundle).to_dict()
    assert comparable(report) == comparable(direct)
    assert (
        report["inputs"]["receipts"][0]["sha256"]
        == hashlib.sha256(original[receipts[0]]).hexdigest()
    )
    assert report["inputs"]["receipts"][0]["size_bytes"] == len(original[receipts[0]])
    assert (tmp_path / "bundle" / "plan" / "plan.json").read_bytes() == original[plan]
    assert (tmp_path / "bundle" / "policy.json").read_bytes() == original[chosen]
    assert (tmp_path / "bundle" / "receipts" / "0000.json").read_bytes() == original[receipts[0]]
    metadata = verify(tmp_path / "bundle").to_dict()
    assert metadata["kind"] == "chimeraforge.prediction-bundle-verification"
    assert metadata["status"] == "verified_content" and metadata["receipt_count"] == 1
    assert metadata["private_handoff"] is True
    assert str(tmp_path) not in json.dumps(metadata)
    assert "PRIVATE HANDOFF" in metadata["limits"]
    assert metadata["transport_bytes"] == report["inputs"]["total_bytes"] + len(
        bundle._manifest_bytes
    )
    metadata["files"].clear()
    assert bundle.to_dict()["files"]


@pytest.mark.parametrize("case", ["zero", "duplicates", "breach", "cpu", "extra"])
def test_full_negative_duplicate_extra_and_missing_populations_survive(frozen, tmp_path, case):
    create, _, score = functions()
    values = [] if case == "zero" else [native(frozen)]
    if case == "duplicates":
        values *= 2
    elif case == "breach":
        values = [native(frozen, durations=(250, 250, 250))]
    elif case == "cpu":
        for phase in ("serving_before", "serving_after"):
            values[0]["execution"][phase]["device"] = "cpu"
        seal(values[0])
    elif case == "extra":
        values.append(native(frozen, durations=(100, 125, 150)))
    plan, chosen, receipts = inputs(tmp_path, frozen, receipts=values)
    bundle = create(plan, receipts, policy=chosen, outdir=tmp_path / "bundle")
    report = score(bundle).to_dict()
    expected = api.score_predictions(
        tmp_path / "bundle" / "plan", receipts, policy=chosen
    ).to_dict()
    assert comparable(report) == comparable(expected)
    assert bundle.to_dict()["receipt_count"] == len(values)
    assert (tmp_path / "bundle" / "receipts").is_dir()
    assert report["exit_code"] == (1 if case == "breach" else 3)


def test_original_quality_handoff_is_private_and_sources_are_not_metadata(tmp_path):
    create, verify, score = functions()
    plan, corpus, quality = source_plan(tmp_path)
    chosen = policy(api.load_plan(plan))
    bundle = create(plan, [], policy=chosen, outdir=tmp_path / "bundle")
    root = tmp_path / "bundle"
    assert (root / "plan" / "corpus.json").read_bytes() == corpus.read_bytes()
    assert (root / "plan" / "quality.json").read_bytes() == quality.read_bytes()
    assert b"private_prompt" in (root / "plan" / "quality.json").read_bytes()
    assert "private_prompt" not in json.dumps(bundle.to_dict())
    assert str(tmp_path) not in json.dumps(bundle.to_dict())
    assert score(verify(root)).exit_code == 3


def test_existing_plan_bundle_and_typed_policy_preserve_inner_manifest_bytes(frozen, tmp_path):
    create, _, score = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    inner = api.create_plan_bundle(plan, tmp_path / "inner")
    original = (tmp_path / "inner" / "manifest.json").read_bytes()
    for index, saved in enumerate((inner, tmp_path / "inner")):
        bundle = create(
            saved,
            receipts,
            policy=api.PredictionScorePolicy(**policy(frozen)),
            outdir=tmp_path / f"bundle{index}",
        )
        assert (tmp_path / f"bundle{index}" / "plan" / "manifest.json").read_bytes() == original
        assert score(bundle).exit_code == 0


def test_held_scoring_and_metadata_never_touch_filesystem_after_sources_deleted(
    frozen, tmp_path, monkeypatch
):
    create, verify, score = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    root = tmp_path / "bundle"
    create(plan, receipts, policy=chosen, outdir=root)
    moved = tmp_path / "relocated"
    root.rename(moved)
    held = verify(moved)
    shutil.rmtree(moved)
    for path in (plan, chosen, *receipts):
        path.unlink()
    for method in (
        "open",
        "read_bytes",
        "read_text",
        "exists",
        "is_dir",
        "stat",
        "lstat",
        "resolve",
        "iterdir",
    ):
        monkeypatch.setattr(
            Path, method, lambda *a, **k: pytest.fail("held operation touched filesystem")
        )
    assert held.to_dict()["status"] == "verified_content"
    assert score(held).exit_code == 0


@pytest.mark.parametrize(
    "mutation",
    [
        "extra_root",
        "extra_plan",
        "extra_receipt",
        "missing",
        "directory",
        "hash",
        "policy_hash",
        "order",
        "gap",
        "unsafe",
        "extra_field",
        "duplicate_json",
    ],
)
def test_closed_inventory_tamper_and_unsafe_members_are_rejected(frozen, tmp_path, mutation):
    create, verify, _ = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    root = tmp_path / "bundle"
    create(plan, receipts, policy=chosen, outdir=root)
    manifest = root / "manifest.json"
    data = json.loads(manifest.read_bytes())
    if mutation.startswith("extra_") and mutation != "extra_field":
        directory = {
            "extra_root": root,
            "extra_plan": root / "plan",
            "extra_receipt": root / "receipts",
        }[mutation]
        (directory / "unknown.json").write_bytes(b"private-data")
    elif mutation == "missing":
        (root / "policy.json").unlink()
    elif mutation == "directory":
        (root / "policy.json").unlink()
        (root / "policy.json").mkdir()
    elif mutation == "hash":
        (root / "receipts" / "0000.json").write_bytes(b"{}")
    elif mutation == "policy_hash":
        data["policy_sha256"] = "a" * 64
    elif mutation == "order":
        data["files"][0], data["files"][1] = data["files"][1], data["files"][0]
    elif mutation == "gap":
        data["files"][-1]["path"] = "receipts/0001.json"
    elif mutation == "unsafe":
        data["files"][-1]["path"] = "../private.json"
    elif mutation == "extra_field":
        data["private-field"] = "PRIVATE"
    elif mutation == "duplicate_json":
        manifest.write_bytes(b'{"PRIVATE":1,"PRIVATE":2}')
    if mutation not in (
        "duplicate_json",
        "missing",
        "directory",
        "hash",
    ) and not mutation.startswith("extra_"):
        manifest.write_bytes(json.dumps(data).encode())
    elif mutation == "extra_field":
        manifest.write_bytes(json.dumps(data).encode())
    with pytest.raises(api.PlanError) as caught:
        verify(root)
    assert "PRIVATE" not in str(caught.value)


@pytest.mark.parametrize("mutation", ["outer", "member", "members_type", "protected", "directory"])
def test_forged_held_objects_revalidate_without_trusting_private_fields(frozen, tmp_path, mutation):
    create, _, score = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    bundle = create(plan, receipts, policy=chosen, outdir=tmp_path / "bundle")
    if mutation == "outer":
        bundle = replace(bundle, _manifest_bytes=b"{}")
    elif mutation == "member":
        bundle = replace(bundle, _members=bundle._members[:-1] + (("receipts/0000.json", b"{}"),))
    elif mutation == "members_type":
        bundle = replace(bundle, _members=list(bundle._members))
    elif mutation == "protected":
        bundle = replace(bundle, _protected_paths=("PRIVATE",))
    else:
        bundle = replace(bundle, _directory=Path("relative"))
    with pytest.raises(api.PlanError):
        bundle.to_dict()
    with pytest.raises(api.PlanError):
        score(bundle)


def test_every_creator_input_and_bundle_member_is_output_protected_including_later_alias(
    frozen, tmp_path
):
    create, _, score = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    bundle = create(plan, receipts, policy=chosen, outdir=tmp_path / "bundle")
    result = score(bundle)
    paths = [
        plan,
        chosen,
        *receipts,
        *(tmp_path / "bundle" / row["path"] for row in bundle.to_dict()["files"]),
        tmp_path / "bundle" / "manifest.json",
    ]
    for path in paths:
        with pytest.raises(api.PlanError):
            result.save(path)
    alias = tmp_path / "outside-alias.json"
    os.link(receipts[0], alias)
    with pytest.raises(api.PlanError):
        result.save(alias)
    with pytest.raises(api.PlanError):
        result.save(tmp_path / "bundle" / "new-output.json")


def test_transport_budget_includes_both_manifests_exact_boundary_and_one_over(
    frozen, tmp_path, monkeypatch
):
    from chimeraforge import prediction_bundle_inputs as module

    create, verify, _ = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    bundle = create(plan, receipts, policy=chosen, outdir=tmp_path / "first")
    total = bundle.to_dict()["transport_bytes"]
    raw_total = len(bundle._manifest_bytes) + sum(len(raw) for _, raw in bundle._members)
    assert total == raw_total
    monkeypatch.setattr(module, "MAX_TRANSPORT_BYTES", total)
    assert verify(tmp_path / "first").to_dict()["transport_bytes"] == total
    assert (
        create(plan, receipts, policy=chosen, outdir=tmp_path / "exact").to_dict()[
            "transport_bytes"
        ]
        == total
    )
    monkeypatch.setattr(module, "MAX_TRANSPORT_BYTES", total - 1)
    with pytest.raises(api.PlanError):
        verify(tmp_path / "first")
    with pytest.raises(api.PlanError):
        create(plan, receipts, policy=chosen, outdir=tmp_path / "over")
    assert not (tmp_path / "over").exists()


def test_repeated_sources_read_once_and_charge_each_ordered_occurrence(
    frozen, tmp_path, monkeypatch
):
    from chimeraforge import prediction_bundle_inputs as module

    create, _, score = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    read, calls = module._read, []

    def counted(path, limit, **kwargs):
        calls.append(path)
        return read(path, limit, **kwargs)

    monkeypatch.setattr(module, "_read", counted)
    bundle = create(plan, receipts * 2, policy=chosen, outdir=tmp_path / "bundle")
    assert calls.count(receipts[0]) == 1
    rows = score(bundle).to_dict()["rows"]
    assert len(rows) == 2 and all(row["state"] == "duplicate" for row in rows)
    assert bundle._members[-1][1] == bundle._members[-2][1] == receipts[0].read_bytes()


def test_hardlinks_and_symlinks_are_not_accepted_as_input_members(frozen, tmp_path):
    create, verify, _ = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    bundle = create(plan, receipts, policy=chosen, outdir=tmp_path / "bundle")
    member = tmp_path / "bundle" / "policy.json"
    os.link(member, tmp_path / "hardlink")
    with pytest.raises(api.PlanError):
        verify(tmp_path / "bundle")
    with pytest.raises(api.PlanError):
        create(plan, [member], policy=chosen, outdir=tmp_path / "other")
    assert bundle.to_dict()["status"] == "verified_content"


def test_existing_empty_and_nonempty_destinations_are_untouched(frozen, tmp_path):
    create, _, _ = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    for name in ("empty", "foreign"):
        target = tmp_path / name
        target.mkdir()
        if name == "foreign":
            (target / "owned-by-another").write_bytes(b"PRIVATE")
        before = list(target.iterdir())
        with pytest.raises(api.PlanError):
            create(plan, receipts, policy=chosen, outdir=target)
        assert list(target.iterdir()) == before


def test_manifest_is_last_and_interruption_removes_only_unchanged_owned_destination(
    frozen, tmp_path, monkeypatch
):
    from chimeraforge import prediction_bundle_publication as publication

    create, _, _ = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    original = publication._write_member
    calls = []

    def fail_second(owner, logical, raw):
        calls.append(logical)
        if len(calls) == 2:
            raise OSError("PRIVATE provider detail")
        return original(owner, logical, raw)

    monkeypatch.setattr(publication, "_write_member", fail_second)
    with pytest.raises(api.PlanError) as caught:
        create(plan, receipts, policy=chosen, outdir=tmp_path / "bundle")
    assert not (tmp_path / "bundle").exists()
    assert "PRIVATE" not in str(caught.value)
    monkeypatch.setattr(publication, "_write_member", original)
    order = []

    def record(owner, logical, raw):
        order.append(logical)
        return original(owner, logical, raw)

    monkeypatch.setattr(publication, "_write_member", record)
    create(plan, receipts, policy=chosen, outdir=tmp_path / "okay")
    assert order[-1] == "manifest.json"


def test_failure_with_foreign_added_member_preserves_entire_incomplete_destination(
    frozen, tmp_path, monkeypatch
):
    from chimeraforge import prediction_bundle_publication as publication

    create, verify, _ = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    target = tmp_path / "bundle"
    original = publication._write_member

    def intrude(owner, logical, raw):
        original(owner, logical, raw)
        (target / "foreign").write_bytes(b"PRIVATE")
        raise OSError("interrupted")

    monkeypatch.setattr(publication, "_write_member", intrude)
    with pytest.raises(api.PlanError, match="retained"):
        create(plan, receipts, policy=chosen, outdir=target)
    assert (target / "foreign").read_bytes() == b"PRIVATE"
    assert not (target / "manifest.json").exists()
    with pytest.raises(api.PlanError):
        verify(target)


def test_new_root_without_recordable_identity_is_retained_as_uncertain(
    frozen, tmp_path, monkeypatch
):
    from chimeraforge import prediction_bundle_publication as publication

    create, _, _ = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    original = publication._identity
    target = tmp_path / "bundle"

    def unavailable(path, *, directory):
        if path == target:
            raise OSError("identity unavailable")
        return original(path, directory=directory)

    monkeypatch.setattr(publication, "_identity", unavailable)
    with pytest.raises(api.PlanError, match="retained"):
        create(plan, receipts, policy=chosen, outdir=target)
    assert target.is_dir() and not list(target.iterdir())


def test_cleanup_rechecks_owned_bytes_immediately_before_each_unlink(frozen, tmp_path, monkeypatch):
    from chimeraforge import prediction_bundle_publication as publication

    create, _, _ = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    target = tmp_path / "bundle"
    writer, reader = publication._write_member, publication._read
    written = []
    read_count = []

    def stop_third(owner, logical, raw):
        if len(written) == 2:
            raise OSError("interrupted")
        writer(owner, logical, raw)
        written.append(target / logical)

    def change_earlier_member(path, limit):
        raw = reader(path, limit)
        read_count.append(path)
        if len(read_count) == 2:
            written[0].write_bytes(b"FOREIGN CHANGED CONTENT")
        return raw

    monkeypatch.setattr(publication, "_write_member", stop_third)
    monkeypatch.setattr(publication, "_read", change_earlier_member)
    with pytest.raises(api.PlanError, match="retained"):
        create(plan, receipts, policy=chosen, outdir=target)
    assert written[0].read_bytes() == b"FOREIGN CHANGED CONTENT"


@pytest.mark.parametrize("replacement", ["root", "member", "changed_bytes"])
def test_failure_never_cleans_substituted_or_mutated_ownership(
    frozen, tmp_path, monkeypatch, replacement
):
    from chimeraforge import prediction_bundle_publication as publication

    create, _, _ = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    target = tmp_path / "bundle"
    original = publication._write_member
    moved = tmp_path / "original-owned-directory"
    affected = []

    def substitute(owner, logical, raw):
        original(owner, logical, raw)
        if replacement == "root":
            target.rename(moved)
            target.mkdir()
            member = target / "foreign"
        else:
            member = target / logical
            if replacement == "member":
                member.unlink()
        member.write_bytes(b"FOREIGN")
        affected.append(member)
        raise OSError("interruption")

    monkeypatch.setattr(publication, "_write_member", substitute)
    with pytest.raises(api.PlanError, match="retained"):
        create(plan, receipts, policy=chosen, outdir=target)
    assert affected[0].read_bytes() == b"FOREIGN"
    if replacement == "root":
        assert moved.is_dir()


def test_destination_appearing_at_exclusive_claim_is_not_replaced(frozen, tmp_path, monkeypatch):
    create, _, _ = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    target = tmp_path / "bundle"
    mkdir = Path.mkdir

    def appear(path, *args, **kwargs):
        if path == target:
            mkdir(path)
            (path / "foreign").write_bytes(b"FOREIGN")
        return mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", appear)
    with pytest.raises(api.PlanError):
        create(plan, receipts, policy=chosen, outdir=target)
    assert (target / "foreign").read_bytes() == b"FOREIGN"


def test_partial_final_manifest_is_not_ready_and_uncertain_write_is_preserved(
    frozen, tmp_path, monkeypatch
):
    from chimeraforge import prediction_bundle_publication as publication

    create, verify, _ = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    target = tmp_path / "bundle"
    original = publication._write_member

    def partial(owner, logical, raw):
        if logical == "manifest.json":
            (owner.root / logical).write_bytes(raw[:10])
            owner.files[logical] = None
            raise OSError("interrupted write")
        return original(owner, logical, raw)

    monkeypatch.setattr(publication, "_write_member", partial)
    with pytest.raises(api.PlanError, match="retained"):
        create(plan, receipts, policy=chosen, outdir=target)
    assert (target / "manifest.json").read_bytes()
    with pytest.raises(api.PlanError):
        verify(target)


def test_repeated_budget_failure_does_not_read_again_or_publish(frozen, tmp_path, monkeypatch):
    from chimeraforge import prediction_bundle_inputs as module

    create, _, score = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    first = create(plan, receipts, policy=chosen, outdir=tmp_path / "first")
    scorer_total = score(first).to_dict()["inputs"]["total_bytes"]
    monkeypatch.setattr(
        module, "MAX_TRANSPORT_BYTES", scorer_total + len(receipts[0].read_bytes()) - 1
    )
    read, calls = module._read, []

    def counted(path, limit, **kwargs):
        calls.append(path)
        return read(path, limit, **kwargs)

    monkeypatch.setattr(module, "_read", counted)
    with pytest.raises(api.PlanError):
        create(plan, receipts * 2, policy=chosen, outdir=tmp_path / "over")
    assert calls.count(receipts[0]) == 1 and not (tmp_path / "over").exists()


@pytest.mark.parametrize("which", ["policy", "receipt"])
def test_malformed_original_json_is_refused_before_any_destination_write(frozen, tmp_path, which):
    create, _, _ = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    target = chosen if which == "policy" else receipts[0]
    target.write_bytes(b'{"PRIVATE":1,"PRIVATE":2}')
    with pytest.raises(api.PlanError) as caught:
        create(plan, receipts, policy=chosen, outdir=tmp_path / "bundle")
    assert "PRIVATE" not in str(caught.value) and not (tmp_path / "bundle").exists()


def test_scorer_held_raw_json_has_no_serialization_or_filesystem_path(frozen, monkeypatch):
    from chimeraforge import prediction_score as module

    raw = (json.dumps(native(frozen), indent=7) + "\n").encode()
    chosen = module._HeldJSON(json.dumps(policy(frozen)).encode())
    held = module._HeldJSON(raw)
    import chimeraforge.bench.gate_inputs as gate_inputs

    original = module.held_json

    def refuse_held(source, limit):
        if type(source) is not dict:
            pytest.fail("held raw JSON reached serialization")
        return original(source, limit)

    monkeypatch.setattr(module, "held_json", refuse_held)
    monkeypatch.setattr(gate_inputs.json, "dumps", lambda *a, **k: pytest.fail("serialization"))
    snapshot = module._Inputs()
    data, original_raw, label = snapshot.json(held, len(raw))
    assert data["kind"] == "chimeraforge.plan-benchmark" and original_raw is raw and label is None
    assert snapshot.total == len(raw)
    assert module._Inputs().json(chosen, len(chosen.raw))[1] == chosen.raw


def test_reparse_and_device_sources_are_refused(frozen, tmp_path, monkeypatch):
    from chimeraforge import plan_bundle

    create, _, _ = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    with pytest.raises(api.PlanError):
        create(plan, [Path(os.devnull)], policy=chosen, outdir=tmp_path / "device")
    linked = plan_bundle._links
    monkeypatch.setattr(plan_bundle, "_links", lambda path: path == receipts[0] or linked(path))
    with pytest.raises(api.PlanError):
        create(plan, receipts, policy=chosen, outdir=tmp_path / "reparse")


def test_symlink_bundle_directory_and_member_are_refused(frozen, tmp_path):
    create, verify, _ = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    target = tmp_path / "bundle"
    create(plan, receipts, policy=chosen, outdir=target)
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink unavailable: {type(exc).__name__}")
    with pytest.raises(api.PlanError):
        verify(alias)
    (target / "policy.json").unlink()
    (target / "policy.json").symlink_to(chosen)
    with pytest.raises(api.PlanError):
        verify(target)


@pytest.mark.skipif(
    os.name == "nt", reason="Windows uses inherited ACLs, not POSIX mode guarantees"
)
def test_private_modes_on_posix(frozen, tmp_path):
    import stat

    create, _, _ = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    target = tmp_path / "bundle"
    bundle = create(plan, receipts, policy=chosen, outdir=target)
    for path in (target, target / "plan", target / "receipts"):
        assert stat.S_IMODE(path.stat().st_mode) & 0o077 == 0
    for logical in ("manifest.json", *(row["path"] for row in bundle.to_dict()["files"])):
        assert stat.S_IMODE((target / logical).stat().st_mode) & 0o077 == 0


@pytest.mark.parametrize("intrusion", ["extra", "changed_member"])
def test_publication_rechecks_closed_inventory_and_written_bytes_before_readiness(
    frozen, tmp_path, monkeypatch, intrusion
):
    from chimeraforge import prediction_bundle_publication as publication

    create, _, _ = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    target = tmp_path / "bundle"
    writer = publication._write_member
    changed = []

    def change_without_raising(owner, logical, raw):
        writer(owner, logical, raw)
        if not changed:
            path = target / "foreign" if intrusion == "extra" else target / logical
            path.write_bytes(b"FOREIGN")
            changed.append(path)

    monkeypatch.setattr(publication, "_write_member", change_without_raising)
    with pytest.raises(api.PlanError, match="retained"):
        create(plan, receipts, policy=chosen, outdir=target)
    assert changed[0].read_bytes() == b"FOREIGN"
    assert not (target / "manifest.json").exists()


def test_capture_reader_receives_remaining_budget_before_original_corpus_read(
    tmp_path, monkeypatch
):
    from chimeraforge import prediction_bundle_inputs as module

    create, _, _ = functions()
    plan, corpus, _ = source_plan(tmp_path, quality=False)
    monkeypatch.setattr(module, "MAX_TRANSPORT_BYTES", len(plan.read_bytes()) + 16)
    reader, seen = module._read, []

    def counted(path, limit, **kwargs):
        seen.append((path, limit))
        return reader(path, limit, **kwargs)

    monkeypatch.setattr(module, "_read", counted)
    with pytest.raises(api.PlanError):
        create(plan, [], policy=policy(api.load_plan(plan)), outdir=tmp_path / "over")
    assert (corpus, 16) in seen and not (tmp_path / "over").exists()


def test_creator_protects_original_corpus_harness_and_typed_bundle_roots(tmp_path):
    create, _, score = functions()
    plan, corpus, quality = source_plan(tmp_path)
    source = api.create_plan_bundle(plan, tmp_path / "source-bundle")
    chosen = policy(api.load_plan(plan))
    bare = create(plan, [], policy=chosen, outdir=tmp_path / "bare")
    for path in (plan, corpus, quality):
        with pytest.raises(api.PlanError):
            score(bare).save(path)
    typed = create(source, [], policy=chosen, outdir=tmp_path / "typed")
    for path in (
        tmp_path / "source-bundle" / "plan.json",
        tmp_path / "source-bundle" / "arbitrary.json",
    ):
        with pytest.raises(api.PlanError):
            score(typed).save(path)
    with pytest.raises(api.PlanError):
        create(source, [], policy=chosen, outdir=tmp_path / "source-bundle" / "nested-output")


def test_maximum_receipt_index_and_count_preserve_full_order(frozen, tmp_path):
    create, verify, _ = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    held = create(plan, receipts * 256, policy=chosen, outdir=tmp_path / "maximum")
    metadata = verify(tmp_path / "maximum").to_dict()
    assert metadata["receipt_count"] == 256
    assert metadata["files"][-1]["path"] == "receipts/0255.json"
    assert held._members[-1][1] == held._members[-256][1] == receipts[0].read_bytes()
    with pytest.raises(api.PlanError):
        create(plan, receipts * 257, policy=chosen, outdir=tmp_path / "excess")
    assert not (tmp_path / "excess").exists()


class InventoryScan:
    def __init__(self, names, *, poison=False, fault=False):
        self.names = iter(names)
        self.poison = poison
        self.fault = fault
        self.calls = 0
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def __iter__(self):
        return self

    def __next__(self):
        self.calls += 1
        try:
            name = next(self.names)
        except StopIteration:
            if self.poison:
                raise AssertionError("enumeration continued after unexpected entry") from None
            if self.fault:
                raise OSError("PRIVATE directory scan failure") from None
            raise
        return SimpleNamespace(name=name)


@pytest.mark.parametrize(
    "site",
    ["source", "verify_root", "verify_plan", "verify_receipts", "cleanup_root", "cleanup_plan"],
)
def test_inventory_stops_at_first_unexpected_entry_and_closes_scan(
    frozen, tmp_path, monkeypatch, site
):
    from chimeraforge import prediction_bundle_inputs as module
    from chimeraforge import prediction_bundle_publication as publication

    create, verify, _ = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    root = tmp_path / "bundle"
    source = tmp_path / "source"
    api.create_plan_bundle(plan, source)
    create(plan, receipts, policy=chosen, outdir=root)
    target = {
        "source": source,
        "verify_root": root,
        "verify_plan": root / "plan",
        "verify_receipts": root / "receipts",
        "cleanup_root": root,
        "cleanup_plan": root / "plan",
    }[site]
    probe = InventoryScan(["PRIVATE-unexpected"], poison=True)
    iterdir, scandir = Path.iterdir, module.os.scandir

    def legacy(path):
        return probe if path == target else iterdir(path)

    def stream(path):
        return probe if Path(path) == target else scandir(path)

    monkeypatch.setattr(Path, "iterdir", legacy)
    monkeypatch.setattr(module.os, "scandir", stream)
    if site.startswith("cleanup"):
        owner = publication._Owner(
            root, created=True, identity=publication._identity(root, directory=True)
        )
        owner.directories = {
            name: publication._identity(root / name, directory=True)
            for name in ("plan", "receipts")
        }
        owner.files = {"manifest.json": None, "policy.json": None}
        assert publication._cleanup(owner) is False
        assert root.is_dir()
    else:
        with pytest.raises(api.PlanError) as caught:
            if site == "source":
                create(source, receipts, policy=chosen, outdir=tmp_path / "out")
            else:
                verify(root)
        assert "PRIVATE" not in str(caught.value)
    assert probe.calls == 1 and probe.closed is True


@pytest.mark.parametrize(
    "case", ["valid", "empty", "missing", "unknown", "duplicate", "count", "fault"]
)
def test_streamed_inventory_has_exact_membership_and_bounded_consumption(case, monkeypatch):
    from chimeraforge import prediction_bundle_inputs as module

    expected = set() if case == "empty" else {"a", "b"}
    names = {
        "valid": ["b", "a"],
        "empty": [],
        "missing": ["a"],
        "unknown": ["PRIVATE"],
        "duplicate": ["a", "a"],
        "count": ["a", "b", "PRIVATE"],
        "fault": ["a"],
    }[case]
    probe = InventoryScan(
        names, poison=case in ("unknown", "duplicate", "count"), fault=case == "fault"
    )
    monkeypatch.setattr(module.os, "scandir", lambda path: probe)
    monkeypatch.setattr(
        Path, "iterdir", lambda *args: pytest.fail("Path.iterdir materializes directory")
    )
    if case in ("valid", "empty"):
        module.check_inventory(Path("fixed-directory"), expected)
    else:
        with pytest.raises(api.PlanError) as caught:
            module.check_inventory(Path("fixed-directory"), expected)
        assert "PRIVATE" not in str(caught.value)
    assert probe.closed is True
    assert (
        probe.calls
        == {
            "valid": 3,
            "empty": 1,
            "missing": 2,
            "unknown": 1,
            "duplicate": 2,
            "count": 3,
            "fault": 2,
        }[case]
    )


def test_valid_source_verification_and_publication_never_use_path_iterdir(
    frozen, tmp_path, monkeypatch
):
    create, verify, _ = functions()
    plan, chosen, receipts = inputs(tmp_path, frozen)
    source = tmp_path / "source"
    api.create_plan_bundle(plan, source)
    monkeypatch.setattr(Path, "iterdir", lambda *a: pytest.fail("unbounded Path.iterdir"))
    result = create(source, receipts, policy=chosen, outdir=tmp_path / "bundle")
    assert result.to_dict()["receipt_count"] == 1
    assert verify(tmp_path / "bundle").to_dict()["status"] == "verified_content"


def test_cleanup_scan_failure_closes_iterator_and_retains_owned_root(tmp_path, monkeypatch):
    from chimeraforge import prediction_bundle_inputs as module
    from chimeraforge import prediction_bundle_publication as publication

    target = tmp_path / "owned"
    target.mkdir()
    owner = publication._Owner(
        target, created=True, identity=publication._identity(target, directory=True)
    )
    probe = InventoryScan([], fault=True)
    monkeypatch.setattr(module.os, "scandir", lambda *a: probe)
    assert publication._cleanup(owner) is False
    assert probe.closed is True and probe.calls == 1 and target.is_dir()
