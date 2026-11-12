"""Configuración común de las pruebas.

Se ejecuta antes de importar api.main, porque api.db resuelve la ruta de SQLite
al importarse. Cada sesión usa una base temporal y desactiva cualquier
DATABASE_URL del entorno, para no tocar jamás datos reales.

La tabla se crea aquí porque TestClient no ejecuta el ciclo de vida (lifespan)
de la aplicación, que es donde init_db() corre en producción.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
import pytest

_TMP = Path(tempfile.mkdtemp(prefix="redcentinela_tests_"))

os.environ["REDCENTINELA_DB"] = str(_TMP / "historial.db")
os.environ.pop("DATABASE_URL", None)
os.environ["REDCENTINELA_RATE_LIMIT"] = "100000"
os.environ.pop("REDCENTINELA_TELEGRAM_TOKEN", None)
os.environ.pop("REDCENTINELA_TELEGRAM_CHAT_ID", None)

from api.db import init_db

init_db()

@pytest.fixture(autouse=True)
def _restaurar_url_api():
    """Varias pruebas apuntan el cliente a una API muerta (:9). La URL vive en
    una variable de módulo, así que sin restaurarla las pruebas que corren
    después contra una API local real heredarían ese puerto."""
    from tablero import client

    original = client.API_URL
    yield
    client.API_URL = original
