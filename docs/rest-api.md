# Local planning API

```bash
chimeraforge serve --port 8765
curl -H 'Content-Type: application/json' \
  -d '{"model_size":"3b","hardware":"RTX 4080 12GB"}' \
  http://127.0.0.1:8765/v1/plan
```

This dependency-free adapter serves the [validated Python API](planning-api.md)
over loopback HTTP. Planning is offline by default. `--allow-network` explicitly
enables Hugging Face metadata resolution on the server. The network policy is
chosen at startup; requests cannot change it. Ctrl+C closes the listening socket.

- `GET /health`: process status and package identity.
- `GET /v1/hardware`: sourced bundled hardware records.
- `POST /v1/plan`: a JSON object of `PlanRequest` options; a versioned saved-plan
  artifact is returned directly. An empty candidate list means no feasible result.

Invalid requests produce JSON `{"error":{"status":400,"message":"..."}}`.
Unknown resources return 404 and unsupported methods return 405. The body is
limited to 64 KiB and model lists to 16 entries. Duplicate keys, nonfinite inputs,
mistyped fields, file paths (`models_path`, `quality_from`), credentials and
endpoint overrides are refused. `allow_network` is also startup-only. The API
does not quantize, deploy, run benchmarks, read arbitrary files or load plugins.

The server is a local process interface for scripts and editor integrations.
It requires a matching loopback Host header and refuses browser Origin/Referer
requests; it has no CORS surface or remote binding. It is not a hosted service or
an authenticated multi-user API. Requests are handled serially. See the Python
[HTTP server](https://docs.python.org/3/library/http.server.html) and
[server lifecycle](https://docs.python.org/3/library/socketserver.html) contracts.
