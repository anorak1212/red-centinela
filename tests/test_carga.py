"""Pruebas de carga y rendimiento (A32).

Dos niveles: el motor solo (sin red) y la API completa (requiere modelos
entrenados, se omite en CI). Los umbrales se fijaron con holgura de ~3x el
valor medido en el equipo del proyecto: deben fallar por una regresión real
de rendimiento, no por ruido de la máquina.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import joblib
import pytest
from api.main import _disponible
from conftest import entrenar_en, frame_sintetico
from motor.ensemble import predecir
from test_api import _NORMAL  # fila válida de 41 campos (módulo hermano)

_MODELOS = _disponible()


def _modelos_entrenados(tmp_path):
    """Entrena el pipeline con datos sintéticos y deja los artefactos en tmp."""
    entrenar_en(tmp_path, frame_sintetico(600, 42), frame_sintetico(300, 7))
    return {
        "rf": joblib.load(tmp_path / "rf.joblib"),
        "svm": joblib.load(tmp_path / "svm.joblib"),
        "knn": joblib.load(tmp_path / "knn.joblib"),
        "preprocessor": joblib.load(tmp_path / "preprocessor.joblib"),
        "metadata": (tmp_path / "metadata.json").exists(),
    }


def test_ensamble_procesa_5000_filas_en_menos_de_10s(tmp_path):
    """Prueba de carga del motor: preproceso + ensamble sobre 5000 filas.

    Umbral: 10 s (medido ~1 s en el equipo del proyecto). Un aumento de 10x
    del tiempo de inferencia rompe el requisito de alerta en tiempo casi
    real del M5 y debe fallar la prueba.
    """
    modelos = _modelos_entrenados(tmp_path)
    df = frame_sintetico(5000, semilla=99)

    t0 = time.perf_counter()
    X = modelos["preprocessor"].transform(df)
    yhat, proba = predecir(modelos, X, 0.5, (-1.0, 1.0))
    transcurrido = time.perf_counter() - t0

    assert X.shape[0] == 5000
    assert yhat.shape == (5000,)
    assert proba.shape == (5000,)
    assert transcurrido < 10.0, f"motor tardó {transcurrido:.2f}s (>10s)"


def test_preproceso_de_5000_filas_en_menos_de_2s(tmp_path):
    """El preproceso (one-hot + escalado) no debe volverse el cuello de botella."""
    modelos = _modelos_entrenados(tmp_path)
    df = frame_sintetico(5000, semilla=100)

    t0 = time.perf_counter()
    X = modelos["preprocessor"].transform(df)
    transcurrido = time.perf_counter() - t0

    assert X.shape == (5000, X.shape[1])
    assert transcurrido < 2.0, f"preproceso tardó {transcurrido:.2f}s (>2s)"


@pytest.mark.skipif(not _MODELOS, reason="modelos no entrenados")
def test_api_batch_de_50_predicciones_en_menos_de_30s():
    """Carga contra la API real: 50 predicciones en un solo lote."""
    from test_api import client as cliente_api

    items = [{"features": dict(_NORMAL)} for _ in range(50)]
    t0 = time.perf_counter()
    r = cliente_api.post("/predict/batch", json={"items": items})
    transcurrido = time.perf_counter() - t0

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["total"] == 50
    assert len(cuerpo["resultados"]) == 50
    assert transcurrido < 30.0, f"lote tardó {transcurrido:.2f}s (>30s)"


@pytest.mark.skipif(not _MODELOS, reason="modelos no entrenados")
def test_api_latencia_media_por_debajo_de_2s():
    """Diez predicciones sueltas; la media debe quedar por debajo de 2 s."""
    from test_api import client as cliente_api

    cliente_api.post("/predict", json={"features": _NORMAL})  # calentamiento
    tiempos = []
    for _ in range(10):
        t0 = time.perf_counter()
        r = cliente_api.post("/predict", json={"features": _NORMAL})
        tiempos.append(time.perf_counter() - t0)
        assert r.status_code == 200

    media = sum(tiempos) / len(tiempos)
    assert media < 2.0, f"latencia media {media:.2f}s (>2s)"


def test_cache_de_modelos_no_recarga_en_cada_peticion(tmp_path):
    """_cargar_modelos usa lru_cache: debe leer el disco una sola vez."""
    from api import main as api_main

    modelos = _modelos_entrenados(tmp_path)
    assert modelos["metadata"] is True
    with patch.object(api_main, "MODEL_DIR", tmp_path):
        api_main._cargar_modelos.cache_clear()
        primera = api_main._cargar_modelos()
        segunda = api_main._cargar_modelos()

    # Misma referencia => el lru_cache leyó el disco una sola vez.
    assert segunda is primera
