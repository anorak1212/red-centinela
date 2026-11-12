"""API REST de Red Centinela (M3).

Endpoints exactos:

    GET  /health          estado, versiones, integridad de artefactos, almacén
    POST /predict         una conexión NSL-KDD
    POST /predict/batch   hasta 500 conexiones en una petición
    GET  /history         últimas predicciones persistidas
    GET  /metrics         cifras de motor/models/metrics.json
    GET  /alertas/estado  si Telegram está configurado y cuántos envíos hubo

Ejecutar en local:

    uvicorn api.main:app --host 127.0.0.1 --port 8000

Controles aplicados (SEG-007): esquema Pydantic estricto por campo, límite de
cuerpo, límite de tasa por IP, CORS restringido por variable de entorno,
manejadores de excepción sin trazas y verificación SHA-256 de los artefactos.
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from functools import lru_cache

import pandas as pd
from fastapi import BackgroundTasks, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from motor.data import FEATURE_NAMES, MODEL_DIR
from motor.ensemble import (
    cargar_modelos,
    etiqueta_clase,
    predecir,
    predecir_multiclase,
    verificar_manifiesto,
)
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .db import (
    descripcion,
    guardar_resultado,
    init_db,
    listar_historial,
    marcar_alerta,
    resumen,
)
from .schemas import (
    BatchRequest,
    BatchResponse,
    HealthResponse,
    HistoryResponse,
    PredictRequest,
    PredictResponse,
)
from .security import (
    LimiteTasa,
    middleware_cabeceras,
    middleware_cuerpo,
    middleware_tasa,
)

MAX_CUERPO_BYTES = int(os.environ.get("REDCENTINELA_MAX_CUERPO", "2000000"))
LIMITE_PETICIONES = int(os.environ.get("REDCENTINELA_RATE_LIMIT", "120"))
VENTANA_TASA = float(os.environ.get("REDCENTINELA_RATE_WINDOW", "60"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        _sistema()
    except Exception:  # noqa: BLE001, S110 - /health responde aunque falte el modelo
        pass
    yield


app = FastAPI(
    title="Red Centinela API",
    description=(
        "Detección de tráfico de red anómalo con NSL-KDD. Modelo de producción: "
        "Random Forest con cabeza binaria (normal/ataque) y cabeza multiclase "
        "(normal, dos, probe, r2l, u2r); Isolation Forest como apoyo no supervisado."
    ),
    version=__version__,
    lifespan=lifespan,
)

_origenes = [
    o.strip()
    for o in os.environ.get(
        "REDCENTINELA_ORIGENES",
        "http://localhost:8501,http://127.0.0.1:8501",
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origenes,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.middleware("http")(middleware_cabeceras)
app.middleware("http")(middleware_cuerpo(MAX_CUERPO_BYTES))
app.middleware("http")(
    middleware_tasa(LimiteTasa(LIMITE_PETICIONES, VENTANA_TASA), ("/predict", "/predict/batch"))
)


# --------------------------------------------------------------------------
# Carga de modelos
# --------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _sistema() -> dict:
    modelos = cargar_modelos(MODEL_DIR, verificar=True)
    return {
        "modelos": modelos,
        "metadata": modelos["metadata"],
        "umbral": float(modelos["metadata"]["umbral_decision"]),
    }


def _disponible() -> bool:
    return (MODEL_DIR / "metadata.json").exists()


@lru_cache(maxsize=1)
def _integridad() -> dict:
    """Verifica los SHA-256 una sola vez.

    Hashear los 80 MB de artefactos cuesta ~300 ms: si se hiciera en cada
    /health, el chequeo de estado competiría con las predicciones y un sondeo
    cada 30 s gastaría CPU sin motivo. Se recalcula solo al arrancar o cuando
    se pide explícitamente con /health?reverificar=true.
    """
    return verificar_manifiesto(MODEL_DIR)


def _metricas() -> dict:
    ruta = MODEL_DIR / "metrics.json"
    if not ruta.exists():
        return {}
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def _resumen_metricas() -> dict:
    m = _metricas()
    if not m:
        return {}
    return {
        "binario_kddtest": m.get("binario_kddtest", {}),
        "multiclase_kddtest": m.get("multiclase_kddtest", {}),
        "kddtest21": m.get("kddtest21", {}),
        "recall_por_familia": m.get("recall_por_familia", {}),
        "iforest": m.get("iforest", {}),
        "generado": m.get("generado"),
    }


# --------------------------------------------------------------------------
# Manejadores de error: nunca se filtra una traza
# --------------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def _error_validacion(request: Request, exc: RequestValidationError):
    detalles = []
    for e in exc.errors()[:10]:
        campo = ".".join(str(p) for p in e.get("loc", ()) if p != "body")
        detalles.append({"campo": campo or "cuerpo", "motivo": e.get("msg", "inválido")})
    return JSONResponse(
        status_code=422,
        content={"detail": "Datos inválidos.", "errores": detalles},
    )


@app.exception_handler(StarletteHTTPException)
async def _error_http(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail if isinstance(exc.detail, str) else "Error."},
    )


@app.exception_handler(Exception)
async def _error_interno(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor. El incidente quedó registrado."},
    )


# --------------------------------------------------------------------------
# Predicción
# --------------------------------------------------------------------------
class _NoDisponible(RuntimeError):
    pass


def _avisos_categorias(pp, features: dict) -> list[str]:
    """Avisa cuando una categoría no existía en el entrenamiento."""
    avisos: list[str] = []
    for col in ("protocol_type", "service", "flag"):
        valor = str(features[col])
        if valor not in pp.cat_categories_[col]:
            avisos.append(
                f"{col}='{valor}' no apareció en el entrenamiento; "
                "se codificó como categoría desconocida."
            )
    return avisos


def _decidir(filas: list[dict], origen: str) -> list[dict]:
    """Clasifica una o varias filas en una sola pasada por el modelo.

    La transformación y las dos cabezas se ejecutan en lote aunque llegue una
    sola fila: es la misma ruta de código para /predict y /predict/batch, así
    que una prueba del lote cubre también la predicción individual.
    """
    if not _disponible():
        raise _NoDisponible("Modelos no entrenados. Ejecuta: python -m motor.train")
    sistema = _sistema()
    modelos = sistema["modelos"]
    umbral = sistema["umbral"]
    pp = modelos["preprocessor"]

    X = pp.transform(pd.DataFrame(filas)[FEATURE_NAMES])
    yhat, proba = predecir(modelos, X, umbral)
    idx, proba_multi = predecir_multiclase(modelos, X)

    resultados = []
    for i, features in enumerate(filas):
        es_ataque = bool(yhat[i])
        resultados.append(
            {
                "es_ataque": es_ataque,
                "etiqueta": "ataque" if es_ataque else "normal",
                "clase": etiqueta_clase(idx[i]),
                "probabilidad_ataque": round(float(proba[i]), 4),
                "probabilidad_clase": round(float(proba_multi[i][idx[i]]), 4),
                "modelo": "RandomForest",
                "version_modelo": str(modelos["metadata"].get("version", "desconocida")),
                "umbral": umbral,
                "origen": origen,
                "avisos": _avisos_categorias(pp, features),
            }
        )
    return resultados


def _predecir_una(features: dict, origen: str) -> dict:
    return _decidir([features], origen)[0]


def _persistir(resultado: dict, features: dict, ts: str) -> int:
    return guardar_resultado(
        es_ataque=resultado["es_ataque"],
        clase=resultado["clase"],
        probabilidad_ataque=resultado["probabilidad_ataque"],
        probabilidad_clase=resultado["probabilidad_clase"],
        modelo=resultado["modelo"],
        version_modelo=resultado["version_modelo"],
        origen=resultado["origen"],
        features=features,
        ts=ts,
    )


def _alertar_en_segundo_plano(id_prediccion: int, resultado: dict) -> None:
    """Tarea de fondo: no suma latencia al p95 de /predict."""
    if not resultado["es_ataque"]:
        return
    try:
        from alertas import telegram
    except Exception:  # noqa: BLE001
        marcar_alerta(id_prediccion, False)
        return
    estado = telegram.notificar(resultado)
    marcar_alerta(id_prediccion, bool(estado.get("ok")))


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
def raiz():
    return {
        "servicio": "red-centinela",
        "version": __version__,
        "endpoints": ["/health", "/predict", "/predict/batch", "/history", "/metrics",
                      "/alertas/estado", "/alertas/prueba"],
    }


@app.get("/health", response_model=HealthResponse)
def health(reverificar: bool = False):
    """Estado del servicio. `?reverificar=true` vuelve a hashear los artefactos."""
    if reverificar:
        _integridad.cache_clear()
    disponibles = _disponible()
    integridad = _integridad() if disponibles else {"ok": False}
    md = None
    if disponibles:
        try:
            md = _sistema()["metadata"]
        except Exception:  # noqa: BLE001
            md = None
    return {
        "status": "ok" if (disponibles and integridad.get("ok")) else "degradado",
        "servicio": "red-centinela",
        "version": __version__,
        "modelos_disponibles": disponibles,
        "integridad_artefactos": bool(integridad.get("ok")),
        "modelo": md.get("modelos") if md else None,
        "version_modelo": md.get("version") if md else None,
        "umbral_decision": md.get("umbral_decision") if md else None,
        "almacen": descripcion(),
        "metricas": _resumen_metricas(),
    }


@app.get("/metrics")
def metrics():
    m = _metricas()
    if not m:
        return JSONResponse(
            status_code=503,
            content={"detail": "metrics.json no existe. Ejecuta python -m motor.evaluate"},
        )
    return m


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest, tareas: BackgroundTasks):
    features = req.features.model_dump()
    try:
        resultado = _predecir_una(features, origen="api")
    except _NoDisponible as exc:
        return JSONResponse(status_code=503, content={"detail": str(exc)})
    except Exception:  # noqa: BLE001
        return JSONResponse(
            status_code=500, content={"detail": "No se pudo ejecutar la predicción."}
        )

    ts = datetime.now(UTC).isoformat(timespec="seconds")
    id_pred = _persistir(resultado, features, ts)
    tareas.add_task(_alertar_en_segundo_plano, id_pred, resultado)
    return {
        "id": id_pred,
        "ts": ts,
        "alerta": "en cola" if resultado["es_ataque"] else "no aplica",
        **resultado,
    }


@app.post("/predict/batch", response_model=BatchResponse)
def predict_batch(req: BatchRequest, tareas: BackgroundTasks):
    filas = [item.features.model_dump() for item in req.items]
    try:
        resultados = _decidir(filas, origen="api-lote")
    except _NoDisponible as exc:
        return JSONResponse(status_code=503, content={"detail": str(exc)})
    except Exception:  # noqa: BLE001
        return JSONResponse(
            status_code=500, content={"detail": "No se pudo ejecutar la predicción."}
        )

    salida = []
    for resultado, features in zip(resultados, filas, strict=True):
        ts = datetime.now(UTC).isoformat(timespec="seconds")
        id_pred = _persistir(resultado, features, ts)
        tareas.add_task(_alertar_en_segundo_plano, id_pred, resultado)
        salida.append({"id": id_pred, "ts": ts, "alerta": "en cola", **resultado})

    ataques = sum(1 for r in resultados if r["es_ataque"])
    return {"total": len(salida), "ataques": ataques, "resultados": salida}


@app.get("/history", response_model=HistoryResponse)
def history(limit: int = Query(50, ge=1, le=500)):
    filas = listar_historial(limit)
    return {"total": len(filas), "almacen": descripcion(), "predicciones": filas}


@app.get("/history/resumen")
def history_resumen():
    return resumen()


@app.get("/alertas/estado")
def alertas_estado():
    from alertas import telegram

    return telegram.estado()


@app.post("/alertas/prueba")
def alertas_prueba():
    """Dispara un mensaje de prueba real al chat configurado.

    Vive en la API y no en el tablero a propósito: el token del bot nunca sale
    del servicio, y el tablero desplegado en Streamlit Cloud no necesita
    credenciales de Telegram para probar la cadena.
    """
    from alertas import telegram

    if not telegram.configurado():
        return JSONResponse(
            status_code=409,
            content={"detail": "Faltan REDCENTINELA_TELEGRAM_TOKEN y "
                               "REDCENTINELA_TELEGRAM_CHAT_ID en el servicio."},
        )
    return telegram.enviar_prueba()
