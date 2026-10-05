"""Run the installed local API process from outside the checkout, without network resolution."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

from ci_installed_acceptance import assert_installed_origin


STARTUP_TIMEOUT_SECONDS = 20
STARTUP_POLL_SECONDS = 0.05
STARTUP_STACK_SECONDS = 15
CLI_BOOTSTRAP = (
    "import faulthandler, runpy; "
    f"faulthandler.dump_traceback_later({STARTUP_STACK_SECONDS}); "
    "runpy.run_module('chimeraforge', run_name='__main__')"
)


def wait_for_health(client, url, process, *, clock=time.monotonic, sleep=time.sleep):
    """Retry startup connection failures, with a fixed deadline and process diagnostics."""
    deadline = clock() + STARTUP_TIMEOUT_SECONDS
    while True:
        if process.poll() is not None:
            raise AssertionError(f"server exited: {process.communicate()}")
        try:
            return client.get(url + "/health")
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            if clock() >= deadline:
                raise AssertionError("installed API did not become ready") from exc
            sleep(STARTUP_POLL_SECONDS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--expect-version", required=True)
    args = parser.parse_args()
    import chimeraforge

    assert_installed_origin(chimeraforge.__file__, args.checkout)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="cf-api-installed-") as directory:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env["CHIMERAFORGE_CACHE"] = str(Path(directory) / "cache")
        process = subprocess.Popen(
            [sys.executable, "-I", "-c", CLI_BOOTSTRAP, "serve", "--port", str(port)],
            cwd=directory,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        accepted = False
        try:
            url = f"http://127.0.0.1:{port}"
            with httpx.Client(timeout=5, trust_env=False) as client:
                health = wait_for_health(client, url, process)
                assert health.status_code == 200 and health.json()["version"] == args.expect_version
                response = client.post(url + "/v1/plan", json={"model_size": "3b"})
                response.raise_for_status()
                artifact = response.json()
                from chimeraforge.api import artifact_from_dict

                artifact_from_dict(artifact)
                assert artifact["inputs"]["allow_network"] is False
                assert artifact["result"]["candidates"][0]["provenance"]
                invalid = client.post(url + "/v1/plan", json={"request_rate": -1})
                assert invalid.status_code == 400 and invalid.json()["error"]["message"]
                assert client.get(url + "/v1/hardware").json()["hardware"]
                print(json.dumps({"version": args.expect_version, "installed_api": "passed"}))
                accepted = True
        finally:
            process.terminate()
            try:
                output = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                output = process.communicate(timeout=5)
            if not accepted:
                print(f"Installed server diagnostics: {output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
