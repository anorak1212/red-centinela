"""Alertas de Red Centinela (M5).

Fase E5: bot de Telegram vía Bot API (HTTP REST). Hasta que el bot tenga
token y chat id (variables REDCENTINELA_TELEGRAM_TOKEN y
REDCENTINELA_TELEGRAM_CHAT_ID), `enviar()` responde sin enviar nada.
"""

from __future__ import annotations

import os

import requests

TOKEN = os.environ.get("REDCENTINELA_TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("REDCENTINELA_TELEGRAM_CHAT_ID", "")
API_BASE = "https://api.telegram.org"


def configurado() -> bool:
    return bool(TOKEN and CHAT_ID)


def enviar(mensaje: str) -> dict:
    """Envía un mensaje al chat configurado. Devuelve el resultado."""
    if not configurado():
        return {
            "ok": False,
            "motivo": "M5 pendiente: define REDCENTINELA_TELEGRAM_TOKEN y "
                      "REDCENTINELA_TELEGRAM_CHAT_ID (fase E5 del cronograma).",
        }
    r = requests.post(
        f"{API_BASE}/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": mensaje},
        timeout=15,
    )
    r.raise_for_status()
    return {"ok": True, "telegram": r.json()}