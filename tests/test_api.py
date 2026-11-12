"""Pruebas de la API REST: contratos, validación estricta y errores controlados."""

from __future__ import annotations

import pytest
from api.main import _disponible, app
from fastapi.testclient import TestClient

client = TestClient(app)

_HAY_MODELOS = _disponible()

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

_ATAQUE = {
    **_NORMAL, "protocol_type": "tcp", "service": "private", "flag": "S0",
    "src_bytes": 0, "dst_bytes": 0, "count": 511, "srv_count": 511,
    "serror_rate": 1.0, "srv_serror_rate": 1.0,
}


def _sin_traza(texto: str) -> bool:
    """Un error correcto no menciona archivos ni líneas de código."""
    prohibido = ("Traceback", ".py", "File \"", "line ")
    return not any(p in texto for p in prohibido)


# --------------------------------------------------------------------------
# Salud y metadatos
# --------------------------------------------------------------------------
def test_raiz_lista_endpoints():
    r = client.get("/")
    assert r.status_code == 200
    assert set(r.json()["endpoints"]) >= {"/health", "/predict", "/history"}


def test_health_estructura():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["modelos_disponibles"] == _HAY_MODELOS
    assert body["servicio"] == "red-centinela"
    assert "almacen" in body and "motor" in body["almacen"]
    assert "integridad_artefactos" in body


def test_health_cabeceras_seguridad():
    r = client.get("/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Cache-Control"] == "no-store"


def test_openapi_disponible():
    r = client.get("/openapi.json")
    assert r.status_code == 200
    rutas = r.json()["paths"]
    assert "/predict" in rutas and "/history" in rutas
    assert not any("prediccion" in p for p in rutas)


def test_metrics_responde_o_avisa():
    r = client.get("/metrics")
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        assert "binario_kddtest" in r.json()


def test_alertas_estado_no_expone_token():
    r = client.get("/alertas/estado")
    assert r.status_code == 200
    texto = r.text
    assert "configurado" in texto
    assert "bot" not in texto.lower() or "token" not in texto.lower()


def test_alerta_prueba_sin_credenciales_responde_409(monkeypatch):
    monkeypatch.delenv("REDCENTINELA_TELEGRAM_TOKEN", raising=False)
    monkeypatch.delenv("REDCENTINELA_TELEGRAM_CHAT_ID", raising=False)
    r = client.post("/alertas/prueba")
    assert r.status_code == 409
    assert "TELEGRAM" in r.json()["detail"]


def test_alerta_prueba_envia_cuando_esta_configurada(monkeypatch):
    from alertas import telegram

    monkeypatch.setenv("REDCENTINELA_TELEGRAM_TOKEN", "123:abc")
    monkeypatch.setenv("REDCENTINELA_TELEGRAM_CHAT_ID", "42")
    monkeypatch.setattr(
        telegram, "enviar_prueba",
        lambda: {"ok": True, "estado": "enviado", "message_id": 7},
    )
    r = client.post("/alertas/prueba")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "estado": "enviado", "message_id": 7}


# --------------------------------------------------------------------------
# Predicción
# --------------------------------------------------------------------------
@pytest.mark.skipif(not _HAY_MODELOS, reason="modelos no entrenados")
def test_predict_normal():
    r = client.post("/predict", json={"features": _NORMAL})
    assert r.status_code == 200
    body = r.json()
    assert body["etiqueta"] in ("normal", "ataque")
    assert 0.0 <= body["probabilidad_ataque"] <= 1.0
    assert body["clase"] in {"normal", "dos", "probe", "r2l", "u2r"}
    assert body["id"] > 0
    assert body["ts"].endswith("+00:00") or body["ts"].endswith("Z")


@pytest.mark.skipif(not _HAY_MODELOS, reason="modelos no entrenados")
def test_predict_ataque_evidente():
    r = client.post("/predict", json={"features": _ATAQUE})
    assert r.status_code == 200
    body = r.json()
    assert body["es_ataque"] is True
    assert body["probabilidad_ataque"] >= body["umbral"]


@pytest.mark.skipif(not _HAY_MODELOS, reason="modelos no entrenados")
def test_predict_batch():
    payload = {"items": [{"features": _NORMAL}, {"features": _ATAQUE}]}
    r = client.post("/predict/batch", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert len(body["resultados"]) == 2
    assert body["ataques"] >= 1


def test_predict_batch_vacio_rechazado():
    r = client.post("/predict/batch", json={"items": []})
    assert r.status_code == 422
    assert _sin_traza(r.text)


def test_predict_batch_excede_limite():
    payload = {"items": [{"features": _NORMAL}] * 501}
    r = client.post("/predict/batch", json=payload)
    assert r.status_code == 422
    assert _sin_traza(r.text)


# --------------------------------------------------------------------------
# Validación: payloads malformados (SEG-007)
# --------------------------------------------------------------------------
def test_falta_un_campo():
    incompleto = dict(_NORMAL)
    incompleto.pop("service")
    r = client.post("/predict", json={"features": incompleto})
    assert r.status_code == 422
    assert any(e["campo"].endswith("service") for e in r.json()["errores"])


def test_campo_extra_rechazado():
    sobrado = dict(_NORMAL)
    sobrado["campo_inventado"] = 1
    r = client.post("/predict", json={"features": sobrado})
    assert r.status_code == 422
    assert _sin_traza(r.text)


def test_tipo_incorrecto():
    malo = dict(_NORMAL)
    malo["src_bytes"] = "mucho"
    r = client.post("/predict", json={"features": malo})
    assert r.status_code == 422
    assert _sin_traza(r.text)


def test_valor_negativo():
    malo = dict(_NORMAL)
    malo["src_bytes"] = -10
    r = client.post("/predict", json={"features": malo})
    assert r.status_code == 422
    assert _sin_traza(r.text)


def test_tasa_fuera_de_rango():
    malo = dict(_NORMAL)
    malo["serror_rate"] = 5.0
    r = client.post("/predict", json={"features": malo})
    assert r.status_code == 422
    assert _sin_traza(r.text)


def test_protocolo_invalido():
    malo = dict(_NORMAL)
    malo["protocol_type"] = "sctp"
    r = client.post("/predict", json={"features": malo})
    assert r.status_code == 422
    assert _sin_traza(r.text)


def test_cuerpo_sin_features():
    r = client.post("/predict", json={"otra_cosa": 1})
    assert r.status_code == 422
    assert _sin_traza(r.text)


def test_json_invalido():
    r = client.post(
        "/predict", content=b"{esto no es json",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422
    assert _sin_traza(r.text)


def test_cadena_desmedida_rechazada():
    malo = dict(_NORMAL)
    malo["service"] = "x" * 500
    r = client.post("/predict", json={"features": malo})
    assert r.status_code == 422
    assert _sin_traza(r.text)


def test_cuerpo_demasiado_grande():
    r = client.post(
        "/predict",
        content=b"0" * 2_500_000,
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 413
    assert _sin_traza(r.text)


# --------------------------------------------------------------------------
# Historial
# --------------------------------------------------------------------------
@pytest.mark.skipif(not _HAY_MODELOS, reason="modelos no entrenados")
def test_history_tras_predecir():
    client.post("/predict", json={"features": _NORMAL})
    r = client.get("/history?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    fila = body["predicciones"][0]
    assert {"id", "ts", "clase", "probabilidad_ataque", "origen"} <= set(fila)
    assert fila["origen"] == "api"


def test_history_limite_invalido():
    assert client.get("/history?limit=0").status_code == 422
    assert client.get("/history?limit=501").status_code == 422


def test_ruta_desconocida():
    r = client.get("/prediccion")
    assert r.status_code == 404
    assert _sin_traza(r.text)


@pytest.mark.skipif(not _HAY_MODELOS, reason="modelos no entrenados")
def test_resumen_historial():
    client.post("/predict", json={"features": _NORMAL})
    r = client.get("/history/resumen")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= body["ataques"]
    assert "por_clase" in body
