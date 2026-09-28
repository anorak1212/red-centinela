"""Cliente HTTP de la API Red Centinela para el tablero Streamlit.

El tablero NO carga los modelos: consume la API (diseño del E14). Usa
`requests` y expone funciones pequeñas y testeables.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

import requests

API_URL = os.environ.get("REDCENTINELA_API", "http://127.0.0.1:8000")
TIMEOUT = 15

# Columnas esperadas en los archivos CSV de carga (41 características).
COLUMNAS = [
    "duration", "protocol_type", "service", "flag",
    "src_bytes", "dst_bytes", "land", "wrong_fragment", "urgent", "hot",
    "num_failed_logins", "logged_in", "num_compromised", "root_shell",
    "su_attempted", "num_root", "num_file_creations", "num_shells",
    "num_access_files", "num_outbound_cmds", "is_host_login", "is_guest_login",
    "count", "srv_count", "serror_rate", "srv_serror_rate", "rerror_rate",
    "srv_rerror_rate", "same_srv_rate", "diff_srv_rate", "srv_diff_host_rate",
    "dst_host_count", "dst_host_srv_count", "dst_host_same_srv_rate",
    "dst_host_diff_srv_rate", "dst_host_same_src_port_rate",
    "dst_host_srv_diff_host_rate", "dst_host_serror_rate",
    "dst_host_srv_serror_rate", "dst_host_rerror_rate",
    "dst_host_srv_rerror_rate",
]
CATEGORICAS = {"protocol_type", "service", "flag"}


class ApiError(RuntimeError):
    """La API respondió con un error."""


def _url(ruta: str) -> str:
    return API_URL.rstrip("/") + ruta


def salud() -> dict:
    """Estado de la API y métricas del ensamble."""
    r = requests.get(_url("/health"), timeout=TIMEOUT)
    if r.status_code != 200:
        raise ApiError(f"/health -> {r.status_code}")
    return r.json()


def predecir(features: dict) -> dict:
    r = requests.post(_url("/predict"), json={"features": features}, timeout=TIMEOUT)
    if r.status_code != 200:
        raise ApiError(f"/predict -> {r.status_code}: {r.text[:200]}")
    return r.json()


def predecir_lote(filas: list[dict], tamano: int = 200) -> list[dict]:
    """Predice por lotes de `tamano` para no saturar la API."""
    resultados: list[dict] = []
    for i in range(0, len(filas), tamano):
        r = requests.post(
            _url("/predict/batch"),
            json={"items": [{"features": f} for f in filas[i : i + tamano]]},
            timeout=TIMEOUT * 3,
        )
        if r.status_code != 200:
            raise ApiError(f"/predict/batch -> {r.status_code}: {r.text[:200]}")
        resultados.extend(r.json()["resultados"])
    return resultados


def historial(limit: int = 200) -> list[dict]:
    r = requests.get(_url(f"/history?limit={int(limit)}"), timeout=TIMEOUT)
    if r.status_code != 200:
        raise ApiError(f"/history -> {r.status_code}")
    return r.json()["predicciones"]


def filas_desde_csv(ruta: str | Path, max_filas: int = 2_000) -> list[dict]:
    """Valida y convierte un CSV de tráfico en lista de features por fila."""
    ruta = Path(ruta)
    with ruta.open(newline="", encoding="utf-8-sig") as fh:
        lector = csv.DictReader(fh)
        if lector.fieldnames is None:
            raise ValueError("CSV vacío o sin encabezado")
        columnas = [c.strip() for c in lector.fieldnames]
        if columnas != COLUMNAS:
            faltan = set(COLUMNAS) - set(columnas)
            sobras = set(columnas) - set(COLUMNAS)
            detalle = []
            if faltan:
                detalle.append(f"faltan {len(faltan)} columnas")
            if sobras:
                detalle.append(f"{len(sobras)} columnas desconocidas")
            raise ValueError(f"Encabezado inválido: {', '.join(detalle)}")

        filas: list[dict] = []
        for numero, fila in enumerate(lector, start=1):
            if numero > max_filas:
                break
            limpia: dict = {}
            for col in COLUMNAS:
                valor = fila[col].strip()
                limpia[col] = valor if col in CATEGORICAS else float(valor)
            filas.append(limpia)
    return filas