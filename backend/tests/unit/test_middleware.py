from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.middleware import add_middleware


def _app(max_bytes: int = 10) -> FastAPI:
    app = FastAPI()

    @app.post("/echo")
    def echo(payload: dict) -> dict:
        return payload

    add_middleware(app, max_request_bytes=max_bytes)
    return app


def test_body_size_limit_rejects_oversized_requests():
    client = TestClient(_app(max_bytes=10))

    response = client.post("/echo", content=b'{"value":"too large"}')

    assert response.status_code == 413
    body = response.json()
    assert body["error"]["code"] == "payload_too_large"
    assert body["error"]["context"]["max_bytes"] == 10


def test_body_size_limit_allows_small_requests():
    client = TestClient(_app(max_bytes=100))

    response = client.post("/echo", json={"value": "ok"})

    assert response.status_code == 200
    assert response.json() == {"value": "ok"}
