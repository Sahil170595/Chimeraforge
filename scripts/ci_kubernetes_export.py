"""Regenerable installed CLI/API Kubernetes declarations; no cluster or inference."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

IMAGES = {"vllm": "vllm/vllm-openai:v0.30.0", "sglang": "lmsysorg/sglang:v0.5.20"}


def accept(cwd: Path, env: dict, saved: Path, *, replicas: int) -> dict:
    from ci_installed_acceptance import run_cli
    from chimeraforge import api, deploy

    original = saved.read_bytes()
    artifact = api.load_plan(saved)
    data = artifact.to_dict()
    controls = []
    for backend in ("vllm", "sglang"):
        index = next(
            i
            for i, row in enumerate(data["result"]["candidates"])
            if row["backend"] == backend and row["quant"] == "FP16" and row["n_agents"] == replicas
        )
        candidate = artifact.candidate(index)
        prefix = f"cf-{backend}-n{replicas}"
        options = api.KubernetesOptions(
            name_prefix=prefix,
            node_selector={"operator.example/accelerator": "declared"},
        )
        content = deploy.export_deployment(
            artifact,
            format="kubernetes",
            image=IMAGES[backend],
            model=candidate.model,
            candidate_index=index,
            kubernetes=options,
        ).content
        output = cwd / f"kubernetes-{backend}-n{replicas}.json"
        common = [
            "--plan",
            str(saved),
            "--format",
            "kubernetes",
            "--image",
            IMAGES[backend],
            "--candidate-index",
            str(index),
            "--model",
            candidate.model,
            "--namespace",
            "default",
            "--name-prefix",
            prefix,
            "--node-selector",
            "operator.example/accelerator=declared",
        ]
        run_cli(["deploy", *common, "--out", str(output)], cwd, env)
        assert output.read_text(encoding="utf-8") == content
        direct = api.verify_deployment(
            saved,
            output,
            format="kubernetes",
            image=IMAGES[backend],
            model=candidate.model,
            candidate_index=index,
            kubernetes=options,
        )
        cli = json.loads(
            run_cli(["deploy-verify", *common, "--config", str(output), "--json"], cwd, env)
        )
        assert direct.exit_code == cli["exit_code"] == 0
        assert cli == json.loads(json.dumps(direct.to_dict()))
        manifest = json.loads(content)
        assert len(manifest["items"]) == 2 * replicas
        actual_gpu_requests = []
        for item in manifest["items"]:
            if item["kind"] == "Deployment":
                assert item["spec"]["replicas"] == 1
                container = item["spec"]["template"]["spec"]["containers"][0]
                assert container["resources"]["requests"] == container["resources"]["limits"]
                actual_gpu_requests.append(
                    int(container["resources"]["requests"]["nvidia.com/gpu"])
                )
        assert sum(actual_gpu_requests) == candidate.gpus_total
        changed = json.loads(content)
        changed["items"][0]["spec"]["template"]["spec"]["containers"][0]["image"] = (
            "private-canary/changed:1"
        )
        output.write_text(json.dumps(changed), encoding="utf-8")
        drift = api.verify_deployment(
            saved,
            output,
            format="kubernetes",
            image=IMAGES[backend],
            model=candidate.model,
            candidate_index=index,
            kubernetes=options,
        )
        drift_cli = json.loads(
            run_cli(["deploy-verify", *common, "--config", str(output), "--json"], cwd, env, 5)
        )
        assert drift.exit_code == drift_cli[
            "exit_code"
        ] == 5 and "private-canary" not in json.dumps(drift_cli)
        output.write_text(content, encoding="utf-8", newline="")
        refused = json.loads(
            run_cli(["deploy-verify", *common, "--config", str(saved), "--json"], cwd, env, 1)
        )
        assert refused["status"] == "invalid"
        controls.append(
            {
                "backend": backend,
                "original_replicas": replicas,
                "tensor_parallel": candidate.tensor_parallel,
                "pipeline_parallel": candidate.pipeline_parallel,
                "batch_per_replica": candidate.effective_batch,
                "objects": len(manifest["items"]),
                "desired_gpu_total": candidate.gpus_total,
                "image_intent": IMAGES[backend],
                "api_exit": direct.exit_code,
                "cli_exit": cli["exit_code"],
                "drift_exit": drift_cli["exit_code"],
                "source_alias_exit": refused["exit_code"],
                "cluster_or_image_executed": False,
            }
        )
        assert saved.read_bytes() == original
    return {
        "controls": controls,
        "source_sha256": hashlib.sha256(original).hexdigest(),
        "source_bytes_unchanged": True,
        "scope": (
            "offline CLI/API declaration consistency; no API admission, image, scheduling, "
            "GPU or inference qualification"
        ),
    }


def main() -> int:
    import argparse
    import os
    import tempfile
    from chimeraforge import __version__, api

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    args = parser.parse_args()
    controls = []
    with tempfile.TemporaryDirectory(prefix="cf-kubernetes-") as temporary:
        cwd = Path(temporary)
        for n, rate in ((1, 10), (3, 128)):
            saved = cwd / f"native-n{n}.json"
            api.plan(
                api.PlanRequest(
                    models=["ci/manual-fleet"],
                    overrides={"params_b": 3.0, "n_layers": 28, "n_kv_heads": 8, "d_head": 128},
                    hardware="RTX 4090 24GB",
                    platform="linux",
                    tensor_parallel=2,
                    request_rate=rate,
                    latency_slo=10000,
                    quality_target=0,
                    budget=1e8,
                    allow_network=False,
                )
            ).save(saved)
            controls.append(accept(cwd, dict(os.environ), saved, replicas=n))
    root = Path(__file__).resolve().parents[1]
    files = [
        Path(__file__),
        root / "src/chimeraforge/api.py",
        root / "src/chimeraforge/deploy.py",
        root / "src/chimeraforge/deployment_verify.py",
        root / "src/chimeraforge/kubernetes_options.py",
        root / "src/chimeraforge/kubernetes_export.py",
        root / "src/chimeraforge/commands/deploy.py",
        root / "src/chimeraforge/commands/deploy_verify.py",
        root / "scripts/ci_deploy_placement.py",
        root / "scripts/ci_kubernetes_admission.py",
    ]
    record = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "version": __version__,
        "evidence": (
            "source CLI/API offline controls; hosted installed and kind admission are separate"
        ),
        "result": controls,
        "source_sha256": {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in files
        },
    }
    args.record.parent.mkdir(parents=True, exist_ok=True)
    args.record.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"controls": sum(len(v["controls"]) for v in controls), "cluster": "not started"}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
