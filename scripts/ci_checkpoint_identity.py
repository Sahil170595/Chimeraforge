"""Installed checkpoint loop: offline protocol fixture or anonymous Hub metadata only."""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import httpx

HF_REPO = "HuggingFaceTB/SmolLM2-135M-Instruct"
HF_COMMIT = "12fd25f77366fa6b3b4b768ec3050bf629380bac"
HF_WEIGHT_DECLARATION = "5af571cbf074e6d21a03528d2330792e532ca608f24ac70a143f6b369968ab8c"
FIXTURE_REPO = "ci/checkpoint-fixture"
FIXTURE_COMMIT = "a" * 40


def seed(*, live: bool) -> dict:
    """Populate the installed resolver cache from consumed metadata, never weights."""
    import chimeraforge
    from chimeraforge.planner import checkpoint, resolver

    repo, commit = (HF_REPO, HF_COMMIT) if live else (FIXTURE_REPO, FIXTURE_COMMIT)
    if live:
        # Explicit None at the fetch boundary: anonymous; no environment token lookup.
        metadata = resolver.fetch_hf(repo, hf_token=None, revision=commit)
        assert metadata.checkpoint["weights"]
        assert (
            next(
                row for row in metadata.checkpoint["weights"] if row["path"] == "model.safetensors"
            )["lfs_sha256"]
            == HF_WEIGHT_DECLARATION
        )
    else:
        config = json.dumps(
            {
                "model_type": "llama",
                "num_hidden_layers": 8,
                "num_attention_heads": 8,
                "num_key_value_heads": 4,
                "hidden_size": 512,
                "vocab_size": 32000,
            }
        ).encode()
        blob = hashlib.sha1(b"blob " + str(len(config)).encode() + b"\0" + config).hexdigest()
        info = {
            "id": repo,
            "sha": commit,
            "safetensors": {"total": 100000000},
            "siblings": [
                {"rfilename": "config.json", "size": len(config), "blobId": blob},
                {
                    "rfilename": "model.safetensors",
                    "size": 200000000,
                    "blobId": "b" * 40,
                    "lfs": {"sha256": "c" * 64},
                },
            ],
        }

        def get(url, **kwargs):
            request = httpx.Request("GET", url)
            if "/api/models/" in url:
                return httpx.Response(200, json=info, request=request)
            assert url.endswith(f"/resolve/{commit}/config.json")
            return httpx.Response(
                200, content=config, headers={"x-repo-commit": commit}, request=request
            )

        metadata = checkpoint.fetch(SimpleNamespace(get=get), repo, None, commit)
    spec = replace(
        resolver.spec_from_hf(repo, metadata.config, metadata.params_b),
        checkpoint=metadata.checkpoint,
    )
    resolver._cache_store(repo, spec, commit)
    return {
        "origin": chimeraforge.__file__,
        "repo": repo,
        "commit": commit,
        "checkpoint": metadata.checkpoint,
        "scope": "anonymous real Hub metadata/config only" if live else "offline protocol fixture",
    }


def select_candidate(data: dict) -> int:
    """Choose a saved supported resident candidate rather than assuming rank zero."""
    return next(
        i
        for i, row in enumerate(data["result"]["candidates"])
        if row["backend"] == "vllm"
        and row["quant"] == "FP16"
        and row["n_agents"] == row["tensor_parallel"] == row["pipeline_parallel"] == 1
        and row["offload_fraction"] == 0
    )


def validate(observation: dict, data: dict, checked: dict, compose: dict) -> None:
    """Refuse a lost pin or a metadata receipt promoted into serving/file proof."""
    repo, commit = observation["repo"], observation["commit"]
    assert data["inputs"]["model_revisions"] == {repo: commit}
    spec = data["result"]["specs"][repo]
    assert spec["source"] == "hf"
    assert spec["checkpoint"] == observation["checkpoint"]
    assert spec["checkpoint"]["resolved_revision"] == commit
    assert spec["checkpoint"]["weight_bytes_verified"] is False
    assert data["result"]["replay_context"]["model_specs"][repo] == spec
    assert checked["fingerprint"] == data["fingerprint"]
    assert checked["exit_code"] == 0
    view = checked["checkpoint_view"][repo]
    assert view["pinned_metadata"]["state"] == "unchanged"
    assert view["requested_ref"]["state"] == "unchanged"
    assert view["served_weights"]["state"] == "unverified"
    command = compose["services"]["inference"]["command"]
    assert command.count("--revision") == 1
    assert command[command.index("--revision") + 1] == commit


def accept(cwd: Path, env: dict, checkout: Path, *, live: bool = False) -> dict:
    """Exercise actual isolated installed CLI save/check/export with bounded metadata."""
    from ci_installed_acceptance import assert_installed_origin, run_cli

    env = {key: value for key, value in env.items() if key not in ("HF_TOKEN", "PYTHONPATH")}
    process = subprocess.run(
        [
            sys.executable,
            "-I",
            str(Path(__file__).resolve()),
            "--seed",
            *(["--live"] if live else []),
        ],
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=90,
    )
    observation = json.loads(process.stdout)
    assert_installed_origin(observation["origin"], checkout)
    saved, exported = cwd / "checkpoint-plan.json", cwd / "checkpoint-compose.json"
    run_cli(
        [
            "plan",
            "--model",
            observation["repo"],
            "--revision",
            observation["commit"],
            "--platform",
            "linux",
            "--hardware",
            "RTX 4080 12GB",
            "--request-rate",
            "0.01",
            "--quality-target",
            "0",
            "--budget",
            "100000",
            "--no-network",
            "--json",
            "--save",
            str(saved),
        ],
        cwd,
        env,
    )
    original = saved.read_bytes()
    data = json.loads(original)
    checked = json.loads(run_cli(["check", str(saved), "--json"], cwd, env))
    index = select_candidate(data)
    run_cli(
        [
            "deploy",
            "--plan",
            str(saved),
            "--format",
            "compose",
            "--out",
            str(exported),
            "--candidate-index",
            str(index),
            "--image",
            "vllm/vllm-openai:v0.30.0",
        ],
        cwd,
        env,
    )
    validate(observation, data, checked, json.loads(exported.read_text()))
    if live:
        refreshed = json.loads(run_cli(["check", str(saved), "--network", "--json"], cwd, env))
        validate(observation, data, refreshed, json.loads(exported.read_text()))
    assert saved.read_bytes() == original
    return {
        **observation,
        "candidate_index": index,
        "fingerprint": data["fingerprint"],
        "saved_bytes_unchanged": True,
        "installed_cli_plan_check_deploy": "passed",
        "explicit_network_check": "passed" if live else "not used",
        "weights_downloaded": False,
        "server_loaded_identity": "unverified",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", action="store_true", required=True)
    parser.add_argument("--live", action="store_true")
    options = parser.parse_args()
    print(json.dumps(seed(live=options.live), allow_nan=False))
