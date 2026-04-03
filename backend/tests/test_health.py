"""Tests for GET /health"""


def test_health_returns_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_health_response_schema(client):
    data = client.get("/health").json()
    assert data["status"] == "ok"
    assert "model" in data
    assert "version" in data


def test_health_model_name(client):
    data = client.get("/health").json()
    assert data["model"] == "PhysMamba"


def test_health_fast(client):
    """Health check must complete in under 500 ms."""
    import time
    start = time.time()
    client.get("/health")
    assert time.time() - start < 0.5
