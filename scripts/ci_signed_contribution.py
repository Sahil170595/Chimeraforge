"""Installed signed exchange acceptance with explicitly synthetic HTTP replay facts."""

from __future__ import annotations

import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import threading

SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")


class Protocol(BaseHTTPRequestHandler):
    calls = 0

    def log_message(self, *args) -> None:
        pass

    def send(self, payload: dict) -> None:
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path == "/":
            raw = b"Ollama is running"
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        elif self.path == "/api/version":
            self.send({"version": "synthetic-protocol"})
        elif self.path in ("/api/tags", "/api/ps"):
            self.send(
                {
                    "models": [
                        {
                            "name": "synthetic-protocol:latest",
                            "digest": "a" * 64,
                            "context_length": 2048,
                            "size": 1,
                            "size_vram": 0,
                        }
                    ]
                }
            )
        else:
            self.send({})

    def do_POST(self) -> None:
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        body = json.loads(raw)
        if self.path == "/api/generate":
            assert body["prompt"] == "hello" and body["options"] == {
                "num_predict": 4,
                "num_ctx": 2048,
            }
            type(self).calls += 1
            self.send(
                {
                    "response": "SYNTHETIC PRIVATE COMPLETION",
                    "done": True,
                    "eval_count": 4,
                    "eval_duration": 100000000,
                    "prompt_eval_count": 8,
                    "prompt_eval_cached_count": 0,
                    "prompt_eval_duration": 2000000,
                    "total_duration": 102000000,
                }
            )
        else:
            self.send({"details": {"quantization_level": "Q4_K_M"}, "model_info": {}})


def accept(cwd: Path, env: dict, checkout: Path) -> dict:
    import chimeraforge
    from chimeraforge.contrib import build_contribution
    from chimeraforge.planner.replay import digest
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from ci_installed_acceptance import assert_installed_origin, run_cli
    from ci_regression_gate import protocol_receipt

    assert_installed_origin(chimeraforge.__file__, checkout)
    native = protocol_receipt(1.0)
    native["execution"]["request"]["prompt_sha256"] = hashlib.sha256(b"hello").hexdigest()
    native["fingerprint"] = digest({k: v for k, v in native.items() if k != "fingerprint"})
    source, private_key, trusted_key, workload, artifact = [
        cwd / name
        for name in (
            "signed-native.json",
            "synthetic-key.pem",
            "synthetic-public.pem",
            "private-signed.json",
            "signed-contribution.json",
        )
    ]
    key = Ed25519PrivateKey.from_private_bytes(SEED)
    source.write_text(json.dumps(native))
    private_key.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    trusted_key.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    workload.write_text(
        json.dumps({"prompt": "hello", "options": {"num_predict": 4, "num_ctx": 2048}})
    )
    signed = json.loads(
        run_cli(
            [
                "contribute",
                "sign",
                str(source),
                "--private-key",
                str(private_key),
                "--out",
                str(artifact),
                "--json",
            ],
            cwd,
            env,
        )
    )
    assert signed == json.loads(artifact.read_bytes()) and signed["schema_version"] == 2
    verify_args = ["contribute", "verify", str(artifact), "--format", "v2", "--json"]
    untrusted = json.loads(run_cli(verify_args, cwd, env, 3))
    verified = json.loads(run_cli([*verify_args, "--trusted-key", str(trusted_key)], cwd, env))
    assert untrusted["signature"]["state"] == verified["signature"]["state"] == "valid"
    assert (
        verified["trust"]["state"] == "trusted_key"
        and not untrusted["trust"]["embedded_key_is_trust"]
    )
    Protocol.calls = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), Protocol)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    try:
        replay_args = [
            "contribute",
            "replay",
            str(artifact),
            "--format",
            "v2",
            "--private-workload",
            str(workload),
            "--trusted-key",
            str(trusted_key),
            "--base-url",
            f"http://127.0.0.1:{server.server_port}",
            "--json",
        ]
        workload.write_text(
            json.dumps({"prompt": "wrong", "options": {"num_predict": 4, "num_ctx": 2048}})
        )
        mismatch = json.loads(run_cli(replay_args, cwd, env, 1))
        assert mismatch["private_binding"]["state"] == "mismatch" and Protocol.calls == 0
        workload.write_text(
            json.dumps({"prompt": "hello", "options": {"num_predict": 4, "num_ctx": 2048}})
        )
        replayed = json.loads(run_cli(replay_args, cwd, env))
        assert Protocol.calls == replayed["execution"]["successful_count"] == 3
        assert replayed["replay_equivalence"]["original_wire_options"] == "unverified"
        assert replayed["execution"]["count_state"] == "observed"
        assert "SYNTHETIC PRIVATE COMPLETION" not in json.dumps(replayed)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        assert not thread.is_alive()
    legacy_measurement = copy.deepcopy(native["measurement"])
    legacy_measurement["quant"] = "Q4_K_M"
    legacy_measurement["timestamp"] = "2026-10-12T00:00:00+00:00"
    legacy_measurement["environment"] = {
        "gpu_name": "synthetic-client",
        "gpu_memory_gb": 1,
        "gpu_driver": None,
        "cuda_version": None,
        "os": "synthetic",
        "platform": "synthetic",
        "backend_name": "ollama",
        "backend_version": "synthetic-protocol",
        "chimeraforge_version": chimeraforge.__version__,
    }
    legacy = cwd / "unsigned-core-fixture.json"
    legacy.write_text(json.dumps(build_contribution(legacy_measurement)))
    core_code = (
        "import builtins,json,sys; original=builtins.__import__; "
        "exec('def blocked(name,*args,**kwargs):\\n "
        'if name=="cryptography" or name.startswith("cryptography."): '
        'raise ImportError("blocked optional extra")\\n '
        "return original(name,*args,**kwargs)\\n'); builtins.__import__=blocked; "
        "from chimeraforge import api; from chimeraforge.contrib import verify_contribution; "
        "verify_contribution(json.load(open(sys.argv[2]))); "
        "result=api.verify_signed_contribution(sys.argv[1],trusted_keys=(sys.argv[3],)); "
        "assert result.exit_code==3; print(json.dumps({'v1':'PASS','v2_exit':result.exit_code}))"
    )
    probe = subprocess.run(
        [sys.executable, "-I", "-c", core_code, str(artifact), str(legacy), str(trusted_key)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert probe.returncode == 0, probe.stdout + probe.stderr
    assert json.loads(probe.stdout) == {"v1": "PASS", "v2_exit": 3}
    return {
        "scope": "explicitly synthetic installed HTTP/signature protocol, no model/hardware proof",
        "signed": signed,
        "verified": verified,
        "untrusted": untrusted,
        "private_mismatch": mismatch,
        "replay": replayed,
        "core_without_optional_crypto": json.loads(probe.stdout),
        "fixture_server_closed": True,
    }
