"""Pruebas de las alertas de Telegram.

La entrega real no se prueba aquí: eso exige token, chat y un envío de verdad, y
queda registrado como evidencia aparte. Estas pruebas verifican la lógica de
agrupación y que nunca se declare una entrega que no ocurrió.
"""

from __future__ import annotations

import pytest
from alertas import telegram


@pytest.fixture(autouse=True)
def _sin_credenciales(monkeypatch):
    monkeypatch.delenv("REDCENTINELA_TELEGRAM_TOKEN", raising=False)
    monkeypatch.delenv("REDCENTINELA_TELEGRAM_CHAT_ID", raising=False)
    telegram._pendientes.clear()
    telegram._ultimo_envio = 0.0
    yield
    telegram._pendientes.clear()
    telegram._ultimo_envio = 0.0


def _resultado() -> dict:
    return {
        "clase": "dos",
        "probabilidad_ataque": 0.93,
        "modelo": "RandomForest",
        "version_modelo": "1.0.0",
    }


def test_sin_credenciales_no_esta_configurado():
    assert telegram.configurado() is False


def test_notificar_sin_credenciales_no_simula_entrega():
    estado = telegram.notificar(_resultado())
    assert estado["ok"] is False
    assert estado["estado"] == "no configurado"
    assert telegram._pendientes == []


def test_enviar_prueba_sin_credenciales():
    resultado = telegram.enviar_prueba()
    assert resultado["ok"] is False
    assert resultado["estado"] == "no configurado"


def test_estado_publico_no_expone_token(monkeypatch):
    monkeypatch.setenv("REDCENTINELA_TELEGRAM_TOKEN", "123:secreto")
    monkeypatch.setenv("REDCENTINELA_TELEGRAM_CHAT_ID", "42")
    info = telegram.estado()
    assert info["configurado"] is True
    assert "secreto" not in str(info)


def test_formatear_incluye_clase_y_probabilidad():
    texto = telegram.formatear(_resultado())
    assert "DOS" in texto
    assert "0.93" in texto
    assert "RandomForest" in texto


def test_configurado_con_ambas_variables(monkeypatch):
    monkeypatch.setenv("REDCENTINELA_TELEGRAM_TOKEN", "1:x")
    monkeypatch.setenv("REDCENTINELA_TELEGRAM_CHAT_ID", "7")
    assert telegram.configurado() is True


def test_configurado_exige_las_dos(monkeypatch):
    monkeypatch.setenv("REDCENTINELA_TELEGRAM_TOKEN", "1:x")
    assert telegram.configurado() is False


class _RespuestaFalsa:
    def __init__(self, status: int, cuerpo: dict) -> None:
        self.status_code = status
        self._cuerpo = cuerpo

    def json(self) -> dict:
        return self._cuerpo


def test_exito_solo_con_ok_true(monkeypatch):
    monkeypatch.setenv("REDCENTINELA_TELEGRAM_TOKEN", "1:x")
    monkeypatch.setenv("REDCENTINELA_TELEGRAM_CHAT_ID", "7")
    monkeypatch.setattr(
        telegram.requests, "post",
        lambda *a, **k: _RespuestaFalsa(200, {"ok": True, "result": {"message_id": 5}}),
    )
    assert telegram.enviar_prueba()["ok"] is True


def test_200_sin_ok_true_es_fallo(monkeypatch):
    monkeypatch.setenv("REDCENTINELA_TELEGRAM_TOKEN", "1:x")
    monkeypatch.setenv("REDCENTINELA_TELEGRAM_CHAT_ID", "7")
    monkeypatch.setattr(
        telegram.requests, "post",
        lambda *a, **k: _RespuestaFalsa(200, {"ok": False, "description": "chat not found"}),
    )
    resultado = telegram.enviar_prueba()
    assert resultado["ok"] is False
    assert resultado["estado"] == "rechazado"


def test_error_http_es_fallo(monkeypatch):
    monkeypatch.setenv("REDCENTINELA_TELEGRAM_TOKEN", "1:x")
    monkeypatch.setenv("REDCENTINELA_TELEGRAM_CHAT_ID", "7")
    monkeypatch.setattr(
        telegram.requests, "post", lambda *a, **k: _RespuestaFalsa(401, {"ok": False})
    )
    assert telegram.enviar_prueba()["ok"] is False


def test_error_de_red_no_expone_la_url(monkeypatch):
    monkeypatch.setenv("REDCENTINELA_TELEGRAM_TOKEN", "1:x")
    monkeypatch.setenv("REDCENTINELA_TELEGRAM_CHAT_ID", "7")

    def _explota(*a, **k):
        raise telegram.requests.ConnectionError("https://api.telegram.org/bot1:x/fallo")

    monkeypatch.setattr(telegram.requests, "post", _explota)
    resultado = telegram.enviar_prueba()
    assert resultado["ok"] is False
    assert "1:x" not in str(resultado)


def test_agrupacion_envia_la_primera_de_inmediato(monkeypatch):
    monkeypatch.setenv("REDCENTINELA_TELEGRAM_TOKEN", "1:x")
    monkeypatch.setenv("REDCENTINELA_TELEGRAM_CHAT_ID", "7")
    enviados: list[str] = []

    def _post(url, json=None, timeout=None):
        enviados.append(json["text"])
        return _RespuestaFalsa(200, {"ok": True, "result": {"message_id": 1}})

    monkeypatch.setattr(telegram.requests, "post", _post)
    monkeypatch.setattr(telegram, "_asegurar_hilo", lambda: None)

    primero = telegram.notificar(_resultado())
    assert primero["estado"] == "enviado"
    assert len(enviados) == 1

    segundo = telegram.notificar(_resultado())
    assert segundo["estado"] == "agrupada"
    assert len(enviados) == 1  # sigue en la cola, no se envió aún
