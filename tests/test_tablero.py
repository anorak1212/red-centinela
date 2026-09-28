"""Pruebas del cliente del tablero (parseo de CSV y contratos de API)."""

from __future__ import annotations

from pathlib import Path

import pytest
from tablero.client import COLUMNAS, ApiError, filas_desde_csv, salud

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "datasets" / "sample_trafico.csv"


def test_columnas_esperadas():
    assert len(COLUMNAS) == 41
    assert set(COLUMNAS) >= {"protocol_type", "service", "flag"}


@pytest.mark.skipif(not SAMPLE.exists(), reason="falta datasets/sample_trafico.csv")
def test_filas_desde_csv_archivo_valido():
    filas = filas_desde_csv(SAMPLE)
    assert len(filas) >= 50
    assert set(filas[0].keys()) == set(COLUMNAS)
    assert isinstance(filas[0]["protocol_type"], str)
    assert isinstance(filas[0]["duration"], float)


def test_filas_desde_csv_rechaza_encabezado_invalido(tmp_path):
    malo = tmp_path / "malo.csv"
    malo.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
    with pytest.raises(ValueError):
        filas_desde_csv(malo)


def _api_disponible() -> bool:
    try:
        return salud().get("status") == "ok"
    except ApiError:
        return False


@pytest.mark.skipif(not _api_disponible(), reason="API no disponible")
def test_health_contra_api():
    body = salud()
    assert body["status"] == "ok"