"""Pruebas de la API REST (FastAPI TestClient)."""

from __future__ import annotations

import pytest
from api.main import app
from fastapi.testclient import TestClient
from motor.data import MODEL_DIR

client = TestClient(app)

_MODELOS = (MODEL_DIR / "metadata.json").exists()

_NORMAL = {
    "duration": 0, "protocol_type": "tcp", "service": "http", "flag": "SF",
    "src_bytes": 491, "dst_bytes": 0, "land": 0, "wrong_fragment": 0,
    "urgent": 0, "hot": 0, "num_failed_logins": 0, "logged_in": 0,
    "num_compromised": 0, "root_shell": 0, "su_attempted": 0, "num_root": 0,
    "num_file_creations": 0, "num_shells": 0, "num_access_files": 0,
    "num_outbound_cmds": 0, "is_host_login": 0, "is_guest_login": 0,
    "count": 2, "srv_count": 2, "serror_rate": 0.0, "srv_serror_rate": 0.0,
    "rerror_rate": 0.0, "srv_rerror_rate": 0.0, "same_srv_rate": 1.0,
    "diff_srv_rate": 0.0, "srv_diff_host_rate": 0.0, "dst_host_count": 150,
    "dst_host_srv_count": 25, "dst_host_same_srv_rate": 0.17,
    "dst_host_diff_srv_rate": 0.03, "dst_host_same_src_port_rate": 0.17,
    "dst_host_srv_diff_host_rate": 0.0, "dst_host_serror_rate": 0.0,
    "dst_host_srv_serror_rate": 0.0, "dst_host_rerror_rate": 0.05,
    "dst_host_srv_rerror_rate": 0.0,
}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["modelos_disponibles"] == _MODELOS


@pytest.mark.skipif(not _MODELOS, reason="modelos no entrenados")
def test_predict_normal():
    r = client.post("/predict", json={"features": _NORMAL})
    assert r.status_code == 200
    body = r.json()
    assert body["etiqueta"] in ("normal", "ataque")
    assert 0.0 <= body["probabilidad_ataque"] <= 1.0
    assert body["id"] > 0


@pytest.mark.skipif(not _MODELOS, reason="modelos no entrenados")
def test_predict_faltan_campos():
    incompleto = dict(_NORMAL)
    incompleto.pop("service")
    r = client.post("/predict", json={"features": incompleto})
    assert r.status_code == 422


@pytest.mark.skipif(not _MODELOS, reason="modelos no entrenados")
def test_history():
    client.post("/predict", json={"features": _NORMAL})
    r = client.get("/history?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert "predicciones" in body