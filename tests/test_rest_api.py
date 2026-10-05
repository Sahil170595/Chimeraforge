import json
import threading

import httpx
import pytest


@pytest.fixture
def endpoint():
    from chimeraforge.rest_server import make_server

    server = make_server(port=0)
    worker = threading.Thread(target=server.serve_forever)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
        assert not worker.is_alive()


def test_actual_http_planning_matches_sdk(endpoint):
    from chimeraforge.api import plan, PlanRequest, artifact_from_dict

    response = httpx.post(endpoint + "/v1/plan", json={"model_size": "3b"})
    assert response.status_code == 200
    artifact = artifact_from_dict(response.json())
    expected = plan(PlanRequest(model_size="3b", allow_network=False))
    assert artifact.to_dict()["result"] == expected.to_dict()["result"]
    assert artifact.to_dict()["inputs"]["allow_network"] is False
    assert httpx.get(endpoint + "/health").json()["status"] == "ok"
    assert httpx.get(endpoint + "/v1/hardware").json()["hardware"]


@pytest.mark.parametrize(
    "payload",
    [
        {"request_rate": -1},
        {"avg_tokens": True},
        {"not_an_option": 1},
        {"models_path": "secret.json"},
        {"hf_token": "secret"},
        {"allow_network": True},
        {"ollama_url": "http://remote/"},
        {"models": ["ollama:remote"]},
        [],
        {"models": ["model"] * 17},
    ],
)
def test_invalid_or_nonportable_request_is_structured_error(endpoint, payload):
    response = httpx.post(endpoint + "/v1/plan", json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["message"]


def test_bad_http_payloads_fail_closed(endpoint):
    for content in ['{"budget":NaN}', '{"budget":1,"budget":2}', "{broken"]:
        response = httpx.post(
            endpoint + "/v1/plan", content=content, headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
    response = httpx.post(endpoint + "/v1/plan", content="{}")
    assert response.status_code == 415
    response = httpx.post(
        endpoint + "/v1/plan", json={}, headers={"Origin": "https://remote.example"}
    )
    assert response.status_code == 403
    response = httpx.get(endpoint + "/health", headers={"Host": "remote.example"})
    assert response.status_code == 403
    assert httpx.get(endpoint + "/no-such-resource").status_code == 404
    assert httpx.put(endpoint + "/v1/plan", json={}).status_code == 405


def test_server_refuses_public_binding():
    from chimeraforge.rest_server import make_server

    with pytest.raises(ValueError, match="loopback"):
        make_server(host="0.0.0.0", port=0)


def test_request_size_is_bounded(endpoint):
    response = httpx.post(
        endpoint + "/v1/plan", content=" " * 65537, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413
