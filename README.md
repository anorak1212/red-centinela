# Red Centinela

Plataforma modular de monitoreo y alerta de tráfico de red basada en aprendizaje automático: detecta, analiza y alerta sobre actividad maliciosa en la red.

**Arquitectura en una línea:** motor ML (entrenamiento e inferencia) + API REST FastAPI + tablero Streamlit + alertas Telegram + CLI, sobre dataset público NSL-KDD y con presupuesto de $0.00 MXN (solo herramientas gratuitas y de código abierto).

## Estado de los módulos

| Módulo | Carpeta | Descripción | Estado |
|---|---|---|---|
| M1 Motor ML | `motor/` | Carga NSL-KDD, preprocesado (one-hot + estandarización), ensamble RF+KNN+SVM con umbral calibrado, Isolation Forest no supervisado y evaluación (macro-F1, AUC) | En operación (v0.3.0) |
| M2 Ingesta de contexto | `datasets/` | NSL-KDD crudo (no versionado; `scripts/download_nslkdd.py` lo repone) y CSV de prueba desde el tablero | En operación |
| M3 API REST | `api/` | FastAPI: `/health`, `/predict`, `/predict/batch`, `/history` con SQLite | En operación (v0.3.0) |
| M4 Tablero | `tablero/` | Streamlit: predicción en vivo, carga CSV por lote e historial con gráficas | En operación (v0.3.0) |
| M5 Alertas | `alertas/` | Bot de Telegram vía Bot API (HTTP REST), interfaz lista, bot pendiente de token | Interfaz lista (fase E5) |
| M6 CLI | `cli/` | Operación local del motor y la API | Pendiente |

## Resultados del modelo (E2)

Sobre KDDTest+ (conjunto no visto): ensamble macro-F1 **0.788**, AUC **0.965**.
Sobre holdout del entrenamiento (criterio del proyecto, macro-F1 ≥ 0.90): **0.998**.
Detalle completo en `motor/models/metrics.json` después de entrenar.

## Arranque (Windows)

```powershell
git clone https://github.com/anorak1212/red-centinela.git
cd red-centinela
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 1) Dataset
python scripts/download_nslkdd.py

# 2) Motor ML (entrena y guarda modelos + métricas)
python -m motor.train
python -m motor.evaluate

# 3) API
uvicorn api.main:app --reload
# probar: http://127.0.0.1:8000/docs

# 4) Tablero (en otra terminal, con la API corriendo)
streamlit run tablero/app.py
# abrir: http://127.0.0.1:8501 | subir datasets\sample_trafico.csv para el lote de prueba

# 5) Verificación
pytest
```

## Convenciones

- Python 3.12, PEP 8, formateador `black`, linter `ruff` (severidad E y F bloquean).
- Rama `main` siempre desplegable; características en `feature/<nombre>` y llegan por pull request.
- Commits con prefijo de tipo: `feat:`, `fix:`, `docs:`, `test:`, `chore:`.
- Versionado semántico `MAYOR.MENOR.PARCHE` para el paquete del motor; modelos serializados se publican como release.
- Sin secretos en el repositorio: `.env` no existe en git, la configuración sensible entra por variables de entorno documentadas en cada módulo.
- La CI corre `ruff` y `pytest` con cobertura mínima del 80 % (meta 90 %) en cada push a `main`.

## Demo

El enlace a la demo en vivo se publicará aquí al desplegar el tablero (entregable E6).

## Créditos

Proyecto académico de Gestión de Proyectos, UAEMéx. Alumno: Mateo Jiménez Pérez. Profesor: Juan Carlos Escobar González.

Licencia MIT, ver `LICENSE`.