"""Pruebas de seguridad (A32).

Cuatro frentes: inyección SQL sobre el historial, validación de entradas de
la API, ausencia de secretos hardcodeados en el repositorio y el canal de
alertas de Telegram (que no debe enviar nada sin configuración).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from alertas import telegram
from api import db
from api.main import app as api_app
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[1]
client = TestClient(api_app)

# Fila válida de 41 campos (la misma que usa tests/test_api.py).
_FILA = {
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

_PAYLOAD_SQL = "'; DROP TABLE predicciones; --"


# --- 1. Inyección SQL ------------------------------------------------------


def test_inyeccion_sql_no_destruye_el_historial(tmp_path):
    """El payload viaja como dato, no como sentencia (consultas parametrizadas)."""
    db_path = tmp_path / "seguridad.db"
    with patch.object(db, "DB_PATH", db_path):
        db.init_db()
        id1 = db.guardar_prediccion(
            es_ataque=True, probabilidad=0.97, modelo="ensamble(rf+knn+svm)",
            features={"service": _PAYLOAD_SQL, "nota": _PAYLOAD_SQL},
        )
        filas = db.historial(10)
        id2 = db.guardar_prediccion(
            es_ataque=False, probabilidad=0.10, modelo="ensamble(rf+knn+svm)",
            features={"service": "http"},
        )

    assert id2 == id1 + 1  # la tabla sigue viva tras el payload
    assert len(filas) == 1
    assert "DROP TABLE" in filas[0]["features"]
    assert filas[0]["es_ataque"] == 1
    assert json.loads(filas[0]["features"])["service"] == _PAYLOAD_SQL


def test_limit_de_historial_fuera_de_rango(tmp_path):
    """Query(ge=1, le=500) evita consultas abusivas al historial."""
    with patch.object(db, "DB_PATH", tmp_path / "limite.db"):
        db.init_db()
        for limite in (0, -5, 501, 10_000):
            r = client.get(f"/history?limit={limite}")
            assert r.status_code == 422, f"limit={limite} debió rechazarse"


def test_historial_limitado_sin_registros(tmp_path):
    with patch.object(db, "DB_PATH", tmp_path / "vacio.db"):
        db.init_db()
        r = client.get("/history?limit=5")
    assert r.status_code == 200
    assert r.json() == {"total": 0, "predicciones": []}


# --- 2. Validación de entradas de la API -----------------------------------


def _modelos_falsos(tmp_path):
    """MODEL_DIR 'disponible' sin modelos: la validación corre antes de cargar."""
    (tmp_path / "metadata.json").write_text("{}", encoding="utf-8")
    return patch("api.main.MODEL_DIR", tmp_path)


def test_predict_rechaza_campo_desconocido(tmp_path):
    with _modelos_falsos(tmp_path):
        fila = {**_FILA, "campo_raro": 1}
        r = client.post("/predict", json={"features": fila})
    assert r.status_code == 422
    assert "desconocidos" in r.json()["detail"]


def test_predict_rechaza_campo_faltante(tmp_path):
    with _modelos_falsos(tmp_path):
        fila = dict(_FILA)
        fila.pop("src_bytes")
        r = client.post("/predict", json={"features": fila})
    assert r.status_code == 422
    assert "faltan" in r.json()["detail"]


def test_predict_sin_modelos_devuelve_503(tmp_path):
    # metadata.json ausente => _disponible() False => 503 con instrucción.
    with patch("api.main.MODEL_DIR", tmp_path / "sin_modelos"):
        r = client.post("/predict", json={"features": _FILA})
    assert r.status_code == 503
    assert "motor.train" in r.json()["detail"]


def test_predict_tipo_de_dato_invalido():
    r = client.post("/predict", json={"features": ["no", "es", "dict"]})
    assert r.status_code == 422


def test_batch_vacio_no_falla():
    r = client.post("/predict/batch", json={"items": []})
    assert r.status_code == 200
    assert r.json() == {"total": 0, "resultados": []}


def test_health_sin_modelos_reporta_todo_apagado(tmp_path):
    with patch("api.main.MODEL_DIR", tmp_path / "sin_modelos"):
        r = client.get("/health")
    cuerpo = r.json()
    assert r.status_code == 200
    assert cuerpo["status"] == "ok"
    assert cuerpo["modelos_disponibles"] is False
    assert cuerpo["modelo"] is None
    assert cuerpo["metricas_ultimas"] is None


def test_openapi_es_accesible():
    """La documentación automática debe existir (usada en la demo)."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    rutas = r.json()["paths"]
    assert set(rutas) >= {"/health", "/predict", "/predict/batch", "/history"}


# --- 3. Secretos en el repositorio -----------------------------------------


def test_no_hay_tokens_de_telegram_hardcodeados():
    # El patrón se arma por partes para que este archivo no se detecte a sí
    # mismo (formato: 8-10 dígitos, dos puntos, 35 caracteres de Alfabeto A).
    patron = re.compile(r"\b\d{8,10}:" + r"[A-Za-z0-9_-]{35}\b")
    sospechosos = []
    for extension in ("*.py", "*.md", "*.json", "*.yml", "*.yaml", "*.toml", "*.txt"):
        for ruta in REPO.rglob(extension):
            if ".git" in ruta.parts or "models" in ruta.parts:
                continue
            texto = ruta.read_text(encoding="utf-8", errors="ignore")
            if patron.search(texto):
                sospechosos.append(str(ruta.relative_to(REPO)))
    assert not sospechosos, f"Posibles secretos en: {sospechosos}"


def test_git_no_rastrea_archivos_sensibles():
    try:
        salida = subprocess.run(
            ["git", "ls-files"],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        pytest.skip("git no disponible en esta máquina")
    if salida.returncode != 0:
        pytest.skip("git ls-files falló (¿repo sin inicializar?)")

    prohibidos = [
        f for f in salida.stdout.splitlines()
        if f.endswith((".env", ".pem", ".key", ".db", "credentials.json"))
        or "secret" in f.lower()
    ]
    assert not prohibidos, f"Archivos sensibles versionados: {prohibidos}"


def test_secrets_de_github_no_estan_en_el_workflow():
    """El workflow no debe llevar tokens literales (se usan secrets:)."""
    workflow = REPO / ".github" / "workflows" / "ci.yml"
    if not workflow.exists():
        pytest.skip("workflow de CI no versionado todavía (pendiente de A31)")
    texto = workflow.read_text(encoding="utf-8")
    assert "ghp_" not in texto, "token personal de GitHub literal en el workflow"
    assert "gho_" not in texto, "token OAuth de GitHub literal en el workflow"


# --- 4. Canal de alertas (Telegram) ----------------------------------------


def test_telegram_no_envia_sin_configuracion(monkeypatch):
    monkeypatch.setattr(telegram, "TOKEN", "")
    monkeypatch.setattr(telegram, "CHAT_ID", "")
    assert telegram.configurado() is False
    r = telegram.enviar("hola")
    assert r["ok"] is False
    assert "M5 pendiente" in r["motivo"]


def test_telegram_envia_con_configuracion(monkeypatch):
    monkeypatch.setattr(telegram, "TOKEN", "12345678:ABCDEFGHIJKLMNOPQRSTUVWXYZabcde")
    monkeypatch.setattr(telegram, "CHAT_ID", "999")
    respuesta = Mock()
    respuesta.json.return_value = {"ok": True, "result": {"message_id": 7}}
    with patch.object(telegram.requests, "post", return_value=respuesta) as post:
        r = telegram.enviar("ataque detectado")

    assert r["ok"] is True
    url = post.call_args.args[0]
    assert url.startswith("https://api.telegram.org/bot12345678:")
    assert post.call_args.kwargs["json"]["chat_id"] == "999"
    assert post.call_args.kwargs["json"]["text"] == "ataque detectado"
    assert post.call_args.kwargs["timeout"] == 15
    respuesta.raise_for_status.assert_called_once()
