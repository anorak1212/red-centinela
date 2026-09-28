# API REST (M3)

FastAPI + Uvicorn con persistencia SQLite del historial de predicciones.

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Estado de la API, modelos cargados, umbral y últimas métricas |
| POST | `/predict` | Predicción de una fila (`{"features": {41 campos}}`) |
| POST | `/predict/batch` | Predicción por lotes (`{"items": [...]}`) |
| GET | `/history?limit=N` | Últimas predicciones persistidas (máx. 500) |

El modelo productivo es el ensamble del motor (RF+KNN+SVM) con umbral calibrado.
La base SQLite vive en `api/data/redcentinela.db` (no versionada; `REDCENTINELA_DB` la cambia).

## Ejecutar

```powershell
uvicorn api.main:app --reload
```

Documentación interactiva: http://127.0.0.1:8000/docs

## Pruebas

```powershell
pytest tests/test_api.py -q
```

Los endpoints requieren modelos entrenados; si faltan, `/predict` responde 503 con la instrucción `python -m motor.train`.