"""Pruebas del motor de detección (preprocesador y ensamble)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from api.main import _disponible
from motor.data import CATEGORICAL, FEATURE_NAMES, NUMERIC_COLUMNS, load_raw
from motor.preprocess import Preprocessor


def _fila_sintetica() -> dict:
    """Una fila NSL-KDD válida de prueba (valores plausibles)."""
    fila = {c: 0.0 for c in NUMERIC_COLUMNS}
    fila["duration"] = 0.0
    fila["src_bytes"] = 200.0
    fila["dst_bytes"] = 500.0
    fila["protocol_type"] = "tcp"
    fila["service"] = "http"
    fila["flag"] = "SF"
    return fila


def test_preprocessor_forma():
    df = pd.DataFrame([_fila_sintetica(), _fila_sintetica()])
    pp = Preprocessor().fit(df)
    X = pp.transform(df)
    assert X.shape == (2, pp.n_features())
    assert len(pp.feature_names()) == pp.n_features()
    assert X.dtype == np.float32


def test_preprocessor_estable_entre_fit_y_transform():
    df = pd.DataFrame([_fila_sintetica()])
    pp = Preprocessor().fit(df)
    X1 = pp.transform(df)
    X2 = pp.transform(df)
    np.testing.assert_array_equal(X1, X2)


def test_columnas_correctas():
    assert len(FEATURE_NAMES) == 41
    assert len(NUMERIC_COLUMNS) == 38
    assert CATEGORICAL == ["protocol_type", "service", "flag"]


@pytest.mark.skipif(not _disponible(), reason="modelos no entrenados")
def test_ensamble_predice_binario():
    from motor.ensemble import cargar_modelos, predecir

    modelos = cargar_modelos()
    md = modelos["metadata"]
    df = load_raw("KDDTrain+.txt").head(200)
    X = modelos["preprocessor"].transform(df)
    yhat, proba = predecir(
        modelos, X, float(md["umbral_decision"]), tuple(md["svm_proba_scale"])
    )
    assert yhat.shape == (200,)
    assert set(np.unique(yhat)) <= {0, 1}
    assert proba.min() >= 0.0 and proba.max() <= 1.0