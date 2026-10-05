"""Local HTTP interface over the validated planning API, without optional dependencies."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, HTTPServer

from chimeraforge import __version__
from chimeraforge.api import PlanError, PlanRequest, plan
from chimeraforge.planner.hardware import GPU_DB

log = logging.getLogger(__name__)
MAX_BODY_BYTES = 64 * 1024
# Consume small rejected uploads before closing; never drain an unbounded body.
MAX_REJECT_DRAIN_BYTES = 2 * MAX_BODY_BYTES
MAX_MODELS = 16
READ_TIMEOUT_S = 10
DEFAULT_PORT = 8765
LOCAL_HOSTS = {"127.0.0.1", "localhost"}
LOCAL_ONLY_OPTIONS = {"models_path", "quality_from", "hf_token", "ollama_url", "allow_network"}


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise PlanError(f"duplicate request key: {key}")
        value[key] = item
    return value


def _constant(value):
    raise PlanError(f"nonfinite JSON number: {value}")


class PlanningServer(HTTPServer):
    """Serial, loopback-only server; callers own shutdown/server_close."""

    allow_network: bool = False


class PlanningHandler(BaseHTTPRequestHandler):
    server: PlanningServer
    server_version = "ChimeraForge"
    sys_version = ""

    def setup(self) -> None:
        self.request.settimeout(READ_TIMEOUT_S)
        super().setup()

    def log_message(self, format: str, *args) -> None:
        # Paths and payloads may contain private model identifiers.
        log.info("local planning HTTP request completed: %s", self.command)

    def _respond(self, status: int, data: dict) -> None:
        payload = json.dumps(data, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        if self.command != "HEAD":
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError) as exc:
                log.debug("local planning response client disconnected: %s", exc)

    def send_error(self, code: int, message=None, explain=None) -> None:
        self._respond(
            code, {"error": {"status": code, "message": message or "invalid HTTP request"}}
        )

    def _local_request(self) -> bool:
        allowed = {f"{host}:{self.server.server_port}" for host in LOCAL_HOSTS}
        if self.headers.get("Host") not in allowed:
            self.send_error(403, "Host must name this loopback server")
            return False
        if self.headers.get("Origin") or self.headers.get("Referer"):
            self.send_error(403, "browser-origin requests are not enabled on this local API")
            return False
        return True

    def do_GET(self) -> None:
        if not self._local_request():
            return
        if self.path == "/health":
            self._respond(200, {"status": "ok", "tool": "chimeraforge", "version": __version__})
        elif self.path == "/v1/hardware":
            self._respond(
                200,
                {
                    "schema_version": 1,
                    "hardware": {name: asdict(card) for name, card in GPU_DB.items()},
                },
            )
        else:
            self.send_error(404, "unknown planning resource")

    def do_POST(self) -> None:
        if not self._local_request():
            return
        if self.path != "/v1/plan":
            self.send_error(404, "unknown planning resource")
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
            self.send_error(415, "Content-Type must be application/json")
            return
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or self.headers.get("Transfer-Encoding"):
            self.send_error(400, "one Content-Length and no Transfer-Encoding are required")
            return
        try:
            size = int(lengths[0])
            if not 0 < size <= MAX_BODY_BYTES:
                # Drain a bounded rejected upload so its pending bytes do not
                # reset the TCP connection before the client reads the error.
                if 0 < size <= MAX_REJECT_DRAIN_BYTES:
                    self.rfile.read(size)
                self.send_error(413, f"JSON request must be between 1 and {MAX_BODY_BYTES} bytes")
                return
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise PlanError("incomplete JSON request")
            data = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
            if not isinstance(data, dict):
                raise PlanError("request must be a JSON object of PlanRequest options")
            forbidden = LOCAL_ONLY_OPTIONS.intersection(data)
            if forbidden:
                names = ", ".join(sorted(forbidden))
                raise PlanError(f"options are configured by the server, not HTTP: {names}")
            models = data.get("models")
            if isinstance(models, list):
                if len(models) > MAX_MODELS:
                    raise PlanError(f"at most {MAX_MODELS} models per request")
                if any(isinstance(model, str) and model.startswith("ollama:") for model in models):
                    raise PlanError(
                        "Ollama endpoint resolution is not exposed by the local REST API"
                    )
            request = PlanRequest(**data, allow_network=self.server.allow_network)
            artifact = plan(request)
        except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError) as exc:
            self.send_error(400, str(exc))
            return
        except TimeoutError as exc:
            log.debug("local planning request timed out: %s", exc)
            self.send_error(408, "request body timed out")
            return
        self._respond(200, artifact.to_dict())

    def do_PUT(self) -> None:
        self.send_error(405, "only GET and POST are supported")

    do_DELETE = do_PUT
    do_PATCH = do_PUT
    do_OPTIONS = do_PUT
    do_HEAD = do_PUT


def make_server(
    *, host: str = "127.0.0.1", port: int = DEFAULT_PORT, allow_network: bool = False
) -> PlanningServer:
    """Bind locally; external serving belongs to a separately operated gateway."""
    if host not in LOCAL_HOSTS:
        raise ValueError("the planning API binds to loopback (127.0.0.1 or localhost) only")
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("port must be between 0 and 65535")
    if type(allow_network) is not bool:
        raise ValueError("allow_network must be boolean")
    server = PlanningServer(("127.0.0.1", port), PlanningHandler)
    server.allow_network = allow_network
    return server
