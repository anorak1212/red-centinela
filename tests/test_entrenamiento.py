"""Pruebas del pipeline de entrenamiento, empaquetado y evaluación.

Cubren A24 (entrenamiento), A25 (empaquetado) y A27 (evaluación) con datos
sintéticos, de modo que sirven también como prueba de regresión en CI sin
descargar NSL-KDD. Verifican además que el pipeline escribe SOLO en
tmp_path y no toca motor/models/ ni datasets/processed/ del repositorio.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import numpy as np
import pytest
from conftest import entrenar_en, frame_sintetico
from motor import data as data_mod
from motor import evaluate
from motor.data import CATEGORICAL, NUMERIC_COLUMNS


def test_entrena_empaqueta_y_calibra(tmp_path):
    train_df = frame_sintetico(600, semilla=42)
    test_df = frame_sintetico(300, semilla=7)
    entrenar_en(tmp_path, train_df, test_df)

    # Los seis artefactos del empaquetado (A25).
    for nombre in ("rf", "svm", "knn", "iforest", "preprocessor", "metadata"):
        sufijo = ".json" if nombre == "metadata" else ".joblib"
        assert (tmp_path / f"{nombre}{sufijo}").exists(), nombre

    # La caché NumPy también queda en el directorio redirigido.
    assert (tmp_path / "processed" / "train.X.npy").exists()
    assert (tmp_path / "processed" / "test.y.npy").exists()

    meta = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
    cats = sum(len(set(train_df[c])) for c in CATEGORICAL)
    assert meta["dataset_train"] == "NSL-KDD KDDTrain+"
    assert meta["dataset_test"] == "NSL-KDD KDDTest+"
    assert meta["filas_train"] == 600 and meta["filas_test"] == 300
    assert meta["n_features"] == cats + len(NUMERIC_COLUMNS)
    assert len(meta["feature_names"]) == meta["n_features"]
    assert meta["modelos"][0] == "ensamble(rf+knn+svm)"

    # Umbral calibrado dentro del rango de búsqueda y coherente.
    assert 0.30 <= meta["umbral_decision"] <= 0.69
    assert meta["svm_proba_scale"][0] <= meta["svm_proba_scale"][1]
    assert 0.0 <= meta["macro_f1_holdout"] <= 1.0
    # El conjunto sintético es separable a propósito: un holdout por debajo
    # de 0.70 indicaría que la calibración o el ensamble están rotos.
    assert meta["macro_f1_holdout"] >= 0.70


def test_evalua_y_genera_metrics(tmp_path):
    train_df = frame_sintetico(600, semilla=42)
    test_df = frame_sintetico(300, semilla=7)
    entrenar_en(tmp_path, train_df, test_df)
    meta = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))

    rng = np.random.default_rng(0)
    Xte = rng.normal(0.0, 1.0, (300, meta["n_features"])).astype(np.float32)
    yte = (np.arange(300) % 3 != 0).astype(int)  # ambas clases presentes

    with (
        patch.object(evaluate, "MODEL_DIR", tmp_path),
        patch.object(evaluate, "ensure_processed", return_value=(Xte, yte)),
        patch.object(evaluate, "load_raw", new=lambda nombre: test_df),
    ):
        evaluate.main()

    ruta = tmp_path / "metrics.json"
    assert ruta.exists()
    metricas = json.loads(ruta.read_text(encoding="utf-8"))

    assert set(metricas) >= {"ensamble", "iforest", "macro_f1_holdout_train"}
    ens = metricas["ensamble"]
    assert 0.0 <= ens["accuracy_test"] <= 1.0
    assert 0.0 <= ens["macro_f1_binario_test"] <= 1.0
    assert 0.0 <= ens["auc_roc_test"] <= 1.0
    assert set(ens["recall_por_familia"]) <= {"dos", "probe", "r2l", "u2r"}
    assert len(ens["recall_por_familia"]) >= 1
    assert 0.0 <= metricas["iforest"]["auc_roc"] <= 1.0
    assert 0.0 <= metricas["iforest"]["recall_ataques_top10"] <= 1.0
    assert "PERF-003" in metricas["nota"]


# --- rutas de error de la capa de datos -----------------------------------


def test_load_raw_archivo_inexistente(tmp_path):
    with (
        patch.object(data_mod, "RAW_DIR", tmp_path),
        pytest.raises(FileNotFoundError, match="Descarga NSL-KDD"),
    ):
        data_mod.load_raw("KDDTrain+.txt")


def test_load_raw_estructura_valida_y_familias(tmp_path):
    # 43 columnas en el orden oficial; la segunda etiqueta no está en FAMILY
    # para ejercitar el fillna("unknown") del mapeo de familias.
    filas = [
        ",".join(["0"] * 38 + ["tcp", "http", "SF", "normal", "10"]),
        ",".join(["0"] * 38 + ["udp", "ftp", "S0", "ataque_inventado", "20"]),
    ]
    (tmp_path / "KDDTrain+.txt").write_text("\n".join(filas) + "\n", encoding="utf-8")
    with patch.object(data_mod, "RAW_DIR", tmp_path):
        df = data_mod.load_raw("KDDTrain+.txt")
    assert df.shape == (2, 45)
    assert df.loc[0, "family"] == "normal"
    assert df.loc[0, data_mod.TARGET] == 0
    assert df.loc[1, "family"] == "unknown"
    assert df.loc[1, data_mod.TARGET] == 1


def test_ensure_processed_sin_cache(tmp_path):
    with (
        patch.object(data_mod, "PROC_DIR", tmp_path),
        pytest.raises(FileNotFoundError, match="motor.train"),
    ):
        data_mod.ensure_processed("train")


def test_ensure_processed_reutiliza_cache(tmp_path):
    x = np.arange(12, dtype=np.float32).reshape(3, 4)
    y = np.array([0, 1, 1], dtype=int)
    np.save(tmp_path / "train.X.npy", x)
    np.save(tmp_path / "train.y.npy", y)
    with patch.object(data_mod, "PROC_DIR", tmp_path):
        x2, y2 = data_mod.ensure_processed("train")
    np.testing.assert_array_equal(x2, x)
    np.testing.assert_array_equal(y2, y)


def test_preprocessor_exige_fit_previo():
    from motor.preprocess import Preprocessor

    df = frame_sintetico(5)
    with pytest.raises(RuntimeError, match="fit"):
        Preprocessor().transform(df)
