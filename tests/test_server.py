"""Tests for the PHALANX FastAPI Server."""

from fastapi.testclient import TestClient
from phalanx.server import app

client = TestClient(app)


def test_server_status():
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert "nvidia/nemotron-3-ultra" in str(data["models"])


def test_server_metadata_endpoints():
    res_p = client.get("/api/personas")
    assert res_p.status_code == 200
    assert len(res_p.json()) > 0

    res_s = client.get("/api/scenarios")
    assert res_s.status_code == 200
    assert len(res_s.json()) > 0

    res_gaps = client.get("/api/gaps")
    assert res_gaps.status_code == 200
    assert isinstance(res_gaps.json(), list)


def test_server_recon():
    res = client.get("/api/recon?query=test")
    assert res.status_code == 200
    data = res.json()
    assert "query" in data
    assert "findings" in data


def test_server_verify():
    res = client.get("/api/runs")
    assert res.status_code == 200
    runs = res.json()
    assert len(runs) > 0
    fight_id = runs[0]["transcript"]["fight_id"]

    res_v = client.post("/api/verify", json={"fight_id": fight_id})
    assert res_v.status_code == 200
    data = res_v.json()
    assert data["attack_neutralized"] is True
    assert "pre_patch" in data
    assert "post_patch" in data


def test_server_index_dashboard():
    res = client.get("/")
    assert res.status_code == 200
    assert "PHALANX" in res.text
    assert "Threat Radar" in res.text
    assert "Nebius Serverless Distributed Batch Grid" in res.text
