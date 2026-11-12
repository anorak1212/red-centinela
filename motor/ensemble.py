"""Ensamble y carga de artefactos del motor de detección.

El modelo de producción es un Random Forest con dos cabezas: una binaria
(normal contra ataque) y una multiclase de cinco clases (normal, dos, probe,
r2l, u2r). El Isolation Forest es apoyo no supervisado: no decide la etiqueta,
solo marca qué tan raro es un vector respecto del tráfico normal observado.

El ensamble RF + KNN + SVM se conserva para la comparativa del informe, no
para producción: KNN guarda los 125,973 vectores de entrenamiento y no cabe
en el plan gratuito de despliegue.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from .data import CLASSES, MODEL_DIR

MANIFEST = "manifiesto.json"


# --------------------------------------------------------------------------
# Probabilidades
# --------------------------------------------------------------------------
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
             scale: tuple[float, float] | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Etiquetas binarias del modelo de producción y su probabilidad.

    Si el diccionario trae las tres piezas del ensamble se usa el ensamble;
    si no, se usa el Random Forest binario, que es el modelo de producción.
    """
    if all(k in modelos for k in ("svm", "knn")) and scale is not None:
        p = proba_ensamble(modelos["rf"], modelos["svm"], modelos["knn"], X, scale)
    else:
        p = modelos["rf"].predict_proba(X)[:, 1]
    return (p >= umbral).astype(np.uint8), p


def predecir_multiclase(modelos: dict, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Clase predicha (índice de CLASSES) y matriz de probabilidades."""
    rf = modelos["rf_multi"]
    proba = rf.predict_proba(X)
    return proba.argmax(axis=1).astype(np.uint8), proba


def etiqueta_clase(indice: int) -> str:
    return CLASSES[int(indice)]


# --------------------------------------------------------------------------
# Integridad de artefactos
# --------------------------------------------------------------------------
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def construir_manifiesto(dir_modelos: Path = MODEL_DIR) -> dict:
    """Hash y tamaño de cada artefacto que la API carga.

    Cubre los `.joblib` y `metadata.json`. `metrics.json` queda fuera a
    propósito: es un informe derivado que `motor.evaluate` reescribe, y si
    entrara al manifiesto cualquier evaluación lo marcaría como alterado.
    """
    archivos = {}
    for p in sorted(Path(dir_modelos).glob("*.joblib")):
        archivos[p.name] = {"sha256": sha256(p), "bytes": p.stat().st_size}
    p = Path(dir_modelos) / "metadata.json"
    if p.exists():
        archivos[p.name] = {"sha256": sha256(p), "bytes": p.stat().st_size}
    return {"algoritmo": "sha256", "archivos": archivos}


def verificar_manifiesto(dir_modelos: Path = MODEL_DIR) -> dict:
    """Compara los artefactos en disco con el manifiesto guardado.

    Devuelve {"ok": bool, "detalle": {archivo: "ok" | "alterado" | "ausente"}}.
    No lanza excepción: el llamador decide si aborta.
    """
    dir_modelos = Path(dir_modelos)
    ruta = dir_modelos / MANIFEST
    if not ruta.exists():
        return {"ok": False, "detalle": {"manifiesto.json": "ausente"}}
    manifiesto = json.loads(ruta.read_text(encoding="utf-8"))
    detalle: dict[str, str] = {}
    for nombre, meta in manifiesto.get("archivos", {}).items():
        p = dir_modelos / nombre
        if not p.exists():
            detalle[nombre] = "ausente"
        elif sha256(p) != meta["sha256"]:
            detalle[nombre] = "alterado"
        else:
            detalle[nombre] = "ok"
    return {"ok": all(v == "ok" for v in detalle.values()), "detalle": detalle}


def cargar_modelos(dir_modelos: Path = MODEL_DIR, verificar: bool = False) -> dict:
    """Carga preprocesador, modelos y metadatos desde disco.

    Los bosques se cargan con `n_jobs=1`. No es un descuido: con 300 árboles y
    una sola fila, el reparto en hilos cuesta más que el trabajo útil. Medido en
    esta máquina, una predicción de un registro tarda 88 ms con un hilo y 193 ms
    con todos; con 150 filas sigue ganando un hilo (114 ms contra 208 ms).
    """
    import joblib

    dir_modelos = Path(dir_modelos)
    if verificar:
        estado = verificar_manifiesto(dir_modelos)
        if not estado["ok"]:
            raise RuntimeError(f"Artefactos alterados o ausentes: {estado['detalle']}")

    modelos = {}
    for nombre in ("rf", "rf_multi", "iforest"):
        p = dir_modelos / f"{nombre}.joblib"
        if p.exists():
            modelos[nombre] = joblib.load(p)
    for nombre in ("rf", "rf_multi"):
        if nombre in modelos and hasattr(modelos[nombre], "set_params"):
            modelos[nombre].set_params(n_jobs=1)
    modelos["preprocessor"] = joblib.load(dir_modelos / "preprocessor.joblib")
    modelos["metadata"] = json.loads(
        (dir_modelos / "metadata.json").read_text(encoding="utf-8")
    )
    modelos["manifiesto"] = verificar_manifiesto(dir_modelos)
    return modelos
