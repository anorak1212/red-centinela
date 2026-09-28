"""Ensamble suave RF + KNN + SVM y umbral de decisión calibrado.

La probabilidad final es el promedio de: predict_proba de RF, predict_proba
de KNN y la decisión del LinearSVC escalada a [0,1]. El umbral se calibra
sobre un holdout estratificado del entrenamiento y se guarda en metadata.
"""

from __future__ import annotations

import numpy as np

from .data import MODEL_DIR


def svm_proba(svm, X: np.ndarray, scale: tuple[float, float]) -> np.ndarray:
    """Escala la función de decisión del LinearSVC a [0, 1]."""
    lo, hi = scale
    p = (svm.decision_function(X) - lo) / (hi - lo + 1e-9)
    return np.clip(p, 0.0, 1.0)


def proba_ensamble(rf, svm, knn, X: np.ndarray,
                   scale: tuple[float, float]) -> np.ndarray:
    """Probabilidad promedio del ensamble (RF, KNN, SVM escalado)."""
    p = np.column_stack([
        rf.predict_proba(X)[:, 1],
        knn.predict_proba(X)[:, 1],
        svm_proba(svm, X, scale),
    ])
    return p.mean(axis=1)


def predecir(modelos: dict, X: np.ndarray, umbral: float,
             scale: tuple[float, float]) -> np.ndarray:
    """Etiquetas binarias del ensamble aplicando el umbral calibrado."""
    p = proba_ensamble(modelos["rf"], modelos["svm"], modelos["knn"], X, scale)
    return (p >= umbral).astype(np.uint8), p


def cargar_modelos(dir_modelos=MODEL_DIR) -> dict:
    """Carga los 4 modelos + preprocesador + metadatos desde disco."""
    import json

    import joblib

    modelos = {nombre: joblib.load(dir_modelos / f"{nombre}.joblib")
               for nombre in ("rf", "svm", "knn", "iforest")}
    modelos["preprocessor"] = joblib.load(dir_modelos / "preprocessor.joblib")
    modelos["metadata"] = json.loads(
        (dir_modelos / "metadata.json").read_text(encoding="utf-8")
    )
    return modelos