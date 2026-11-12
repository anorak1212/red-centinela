"""Pruebas del motor de detección: preprocesador, artefactos y predicción."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from motor.data import (
    CATEGORICAL,
    CLASS_TO_INDEX,
    CLASSES,
    FAMILY,
    FEATURE_NAMES,
    MODEL_DIR,
    NUMERIC_COLUMNS,
    load_raw,
)
from motor.ensemble import cargar_modelos, etiqueta_clase, predecir, predecir_multiclase
from motor.preprocess import Preprocessor

_HAY_MODELOS = (MODEL_DIR / "manifiesto.json").exists()


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


# --------------------------------------------------------------------------
# Preprocesador
# --------------------------------------------------------------------------
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


def test_preprocessor_categoria_desconocida_no_falla():
    """Un servicio no visto se codifica como cero, no como excepción."""
    df_fit = pd.DataFrame([_fila_sintetica()])
    pp = Preprocessor().fit(df_fit)
    nueva = _fila_sintetica()
    nueva["service"] = "servicio_jamas_visto"
    X = pp.transform(pd.DataFrame([nueva]))
    assert X.shape == (1, pp.n_features())
    assert np.isfinite(X).all()


def test_preprocessor_requiere_fit():
    with pytest.raises(RuntimeError):
        Preprocessor().transform(pd.DataFrame([_fila_sintetica()]))


# --------------------------------------------------------------------------
# Contratos de datos
# --------------------------------------------------------------------------
def test_columnas_correctas():
    assert len(FEATURE_NAMES) == 41
    assert len(NUMERIC_COLUMNS) == 38
    assert CATEGORICAL == ["protocol_type", "service", "flag"]


def test_clases_canonicas():
    assert CLASSES == ["normal", "dos", "probe", "r2l", "u2r"]
    assert CLASS_TO_INDEX == {c: i for i, c in enumerate(CLASSES)}


def test_familias_solo_usan_las_cinco_clases():
    assert set(FAMILY.values()) == set(CLASSES)


def test_etiqueta_clase_ordinal():
    assert etiqueta_clase(0) == "normal"
    assert etiqueta_clase(4) == "u2r"


@pytest.mark.skipif(not (MODEL_DIR.parent.parent / "datasets/raw/KDDTest+.txt").exists(),
                    reason="falta KDDTest+")
def test_load_raw_agrega_y_multi_y_no_deja_sin_mapear():
    df = load_raw("KDDTest+.txt").head(500)
    assert {"family", "y_binary", "y_multi"} <= set(df.columns)
    assert not (df["family"] == "unknown").any()
    assert df["y_multi"].between(0, 4).all()


# --------------------------------------------------------------------------
# Artefactos
# --------------------------------------------------------------------------
@pytest.mark.skipif(not _HAY_MODELOS, reason="modelos no entrenados")
def test_manifiesto_coincide():
    from motor.ensemble import verificar_manifiesto

    estado = verificar_manifiesto(MODEL_DIR)
    assert estado["ok"], estado["detalle"]


@pytest.mark.skipif(not _HAY_MODELOS, reason="modelos no entrenados")
def test_manifiesto_detecta_alteracion(tmp_path):
    import shutil

    from motor.ensemble import construir_manifiesto, verificar_manifiesto

    for p in MODEL_DIR.glob("*.joblib"):
        shutil.copy2(p, tmp_path / p.name)
    for nombre in ("metadata.json", "metrics.json"):
        if (MODEL_DIR / nombre).exists():
            shutil.copy2(MODEL_DIR / nombre, tmp_path / nombre)
    manifiesto = construir_manifiesto(tmp_path)
    (tmp_path / "manifiesto.json").write_text(
        json.dumps(manifiesto), encoding="utf-8"
    )
    assert verificar_manifiesto(tmp_path)["ok"]

    victima = next(tmp_path.glob("*.joblib"))
    victima.write_bytes(victima.read_bytes() + b"alterado")
    estado = verificar_manifiesto(tmp_path)
    assert not estado["ok"]
    assert estado["detalle"][victima.name] == "alterado"


@pytest.mark.skipif(not _HAY_MODELOS, reason="modelos no entrenados")
def test_cargar_modelos_verifica_y_aborta_si_falta_manifiesto(tmp_path):
    with pytest.raises(RuntimeError):
        cargar_modelos(tmp_path, verificar=True)


@pytest.mark.skipif(not _HAY_MODELOS, reason="modelos no entrenados")
def test_metadata_declara_modelo_de_produccion():
    md = json.loads((MODEL_DIR / "metadata.json").read_text(encoding="utf-8"))
    assert md["modelo_produccion"] == "RandomForest"
    assert set(md["modelos"]) == {"rf", "rf_multi", "iforest"}
    assert 0.0 < float(md["umbral_decision"]) < 1.0
    assert md["clases"] == CLASSES


# --------------------------------------------------------------------------
# Predicción con artefactos reales
# --------------------------------------------------------------------------
@pytest.mark.skipif(
    not _HAY_MODELOS or not (MODEL_DIR.parent.parent / "datasets/raw/KDDTrain+.txt").exists(),
    reason="modelos no entrenados o NSL-KDD no descargado",
)
def test_prediccion_binaria_y_multiclase():
    modelos = cargar_modelos(MODEL_DIR, verificar=True)
    umbral = float(modelos["metadata"]["umbral_decision"])
    df = load_raw("KDDTrain+.txt").head(200)
    X = modelos["preprocessor"].transform(df)

    yhat, proba = predecir(modelos, X, umbral)
    idx, proba_multi = predecir_multiclase(modelos, X)

    assert yhat.shape == (200,)
    assert set(np.unique(yhat)) <= {0, 1}
    assert proba.min() >= 0.0 and proba.max() <= 1.0
    assert idx.shape == (200,)
    assert set(np.unique(idx)) <= set(range(5))
    assert proba_multi.shape == (200, 5)
    np.testing.assert_allclose(proba_multi.sum(axis=1), 1.0, atol=1e-5)


@pytest.mark.skipif(not _HAY_MODELOS, reason="modelos no entrenados")
def test_prediccion_una_sola_fila():
    modelos = cargar_modelos(MODEL_DIR, verificar=True)
    X = modelos["preprocessor"].transform(pd.DataFrame([_fila_sintetica()]))
    yhat, proba = predecir(modelos, X, float(modelos["metadata"]["umbral_decision"]))
    assert yhat.shape == (1,) and 0.0 <= float(proba[0]) <= 1.0
