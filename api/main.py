"""API REST de Red Centinela.

Endpoints:
    GET  /health            estado de la API y de los modelos
    POST /predict           predicción de una fila de tráfico
    POST /predict/batch     predicción por lotes
    GET  /history?limit=N   últimas predicciones persistidas

Ejecutar:
    uvicorn api.main:app --reload
"""

from __future__ import annotations

import json
from functools import lru_cache

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from motor.data import FEATURE_NAMES, MODEL_DIR
from motor.ensemble import predecir
from pydantic import BaseModel, Field

from . import __version__
from .db import guardar_prediccion, historial, init_db

app = FastAPI(
    title="Red Centinela API",
    description="Detección de tráfico de red anómalo con NSL-KDD.",
    version=__version__,
)


# --------------------------------------------------------------------------
# Carga de modelos (una sola vez, caché)
# --------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _cargar_modelos() -> dict:
    def _car(nombre):
        return joblib.load(MODEL_DIR / f"{nombre}.joblib")

    metadata = json.loads((MODEL_DIR / "metadata.json").read_text(encoding="utf-8"))
    modelos = {
        "rf": _car("rf"), "svm": _car("svm"), "knn": _car("knn"),
        "iforest": _car("iforest"), "preprocessor": _car("preprocessor"),
        "metadata": metadata,
    }
    return modelos


def _disponible() -> bool:
    if not (MODEL_DIR / "metadata.json").exists():
        return False
    return all((MODEL_DIR / f"{nombre}.joblib").exists()
               for nombre in ("rf", "svm", "knn", "iforest", "preprocessor"))


def _sistema():
    modelos = _cargar_modelos()
    md = modelos["metadata"]
    return modelos, float(md["umbral_decision"]), tuple(md["svm_proba_scale"])


def _metricas() -> dict:
    path = MODEL_DIR / "metrics.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Esquemas
# --------------------------------------------------------------------------
class PredictRequest(BaseModel):
    features: dict[str, float | int | str] = Field(
        ..., description="Los 41 campos del NSL-KDD (duración, protocolo, bytes, tasas...)"
    )


class BatchRequest(BaseModel):
    items: list[PredictRequest]


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------
@app.get("/health")
def health():
    md = _sistema()[0]["metadata"] if _disponible() else None
    return {
        "status": "ok",
        "servicio": "red-centinela",
        "version": __version__,
        "modelos_disponibles": _disponible(),
        "modelo": md["modelos"] if md else None,
        "umbral_decision": md["umbral_decision"] if md else None,
        "metricas_ultimas": _metricas().get("ensamble"),
    }


def _predecir_fila(features: dict) -> dict:
    if not _disponible():
        raise HTTPException(
            503, "Modelos no entrenados: ejecuta 'python -m motor.train'"
        )
    faltan = set(FEATURE_NAMES) - set(features)
    sobras = set(features) - set(FEATURE_NAMES)
    if faltan or sobras:
        detalle = []
        if faltan:
            detalle.append(f"faltan {len(faltan)} campos")
        if sobras:
            detalle.append(f"{len(sobras)} campos desconocidos")
        raise HTTPException(422, f"Invalid features: {', '.join(detalle)}")

    fila = pd.DataFrame([features])[FEATURE_NAMES]
    modelos, umbral, scale = _sistema()
    X = modelos["preprocessor"].transform(fila)
    yhat, proba = predecir(modelos, X, umbral, scale)
    es_ataque = bool(yhat[0])
    return {
        "es_ataque": es_ataque,
        "etiqueta": "ataque" if es_ataque else "normal",
        "probabilidad_ataque": round(float(proba[0]), 4),
        "modelo": "ensamble(rf+knn+svm)",
        "umbral": umbral,
    }


@app.post("/predict")
def predict(req: PredictRequest):
    resultado = _predecir_fila(req.features)
    id_pred = guardar_prediccion(
        es_ataque=resultado["es_ataque"],
        probabilidad=resultado["probabilidad_ataque"],
        modelo=resultado["modelo"],
        features=req.features,
    )
    return {"id": id_pred, **resultado}


@app.post("/predict/batch")
def predict_batch(req: BatchRequest):
    if not req.items:
        return {"total": 0, "resultados": []}
    resultados = []
    for item in req.items:
        r = _predecir_fila(item.features)
        id_pred = guardar_prediccion(
            es_ataque=r["es_ataque"], probabilidad=r["probabilidad_ataque"],
            modelo=r["modelo"], features=item.features,
        )
        resultados.append({"id": id_pred, **r})
    return {"total": len(resultados), "resultados": resultados}


@app.get("/history")
def get_history(limit: int = Query(50, ge=1, le=500)):
    return {"total": len(historial(limit)), "predicciones": historial(limit)}


init_db()