# AUDIT_REPORT.md

Auditoría de línea base del repositorio Red Centinela.

- Repositorio: `C:\Users\mateo\Downloads\RedCentinela\red-centinela`
- Rama: `main`, HEAD `9db686e`, 44 archivos versionados, 7 commits (2026-09-27 22:36 a 2026-09-28 00:22)
- Fecha de auditoría: 8 de noviembre de 2026
- Método: lectura de código con cita archivo:línea, inspección de git (`log -p --all`, `check-ignore`, `status`), inspección de artefactos y de la base SQLite. Sin escritura, sin instalación de paquetes.
- Alcance: M1 a M6, seguridad, pruebas, despliegue y evidencia documental.

## 1. Inventario real

| Ruta | Estado real |
|---|---|
| `motor/` | Código completo: `data.py`, `preprocess.py`, `train.py`, `ensemble.py`, `evaluate.py`. Artefactos en `motor/models/`: `rf.joblib` 29.3 MB, `knn.joblib` 62.5 MB, `iforest.joblib` 1.6 MB, `svm.joblib` 1.7 KB, `preprocessor.joblib` 2.3 KB. Los `.joblib` no están versionados |
| `api/` | `main.py` 4.9 KB y `db.py` 1.9 KB con código real. Base `api/data/redcentinela.db` con 73 predicciones entre 2026-09-28 y 2026-10-06: la API sí corrió |
| `tablero/` | `app.py` 7.4 KB con 3 pestañas (`st.tabs`, no multipágina) y `client.py` como cliente HTTP. Sin `.streamlit/config.toml`, sin tema propio, sin tutorial |
| `alertas/` | `telegram.py`, 38 líneas útiles. Envío real, sin agrupación, sin reintentos, no invocado desde la detección |
| `cli/` | Solo `README.md`. Cero código. El propio README dice "Pendiente" |
| `tests/` | 4 archivos, 14 pruebas, `.pytest_cache` con `lastfailed` vacío del 2026-10-06 |
| `datasets/` | `sample_trafico.csv` versionado (60 x 41). `raw/` 24.6 MB y `processed/` 73.9 MB ignorados |
| `docs/` | Solo arquitectura E14 en `.json`, `.mmd`, `.svg` |
| `colab/` y `resultados_colab/` | Notebook de 165 KB con 25 celdas y 2 PNG. Sin versionar (`??` en git status) |
| `.github/workflows/ci.yml` | Existe en disco, ignorado por `.gitignore:39`. Nunca llegó a GitHub |

## 2. Hallazgo crítico: las métricas no dicen lo que la documentación dice

`metrics.json` publica `macro_f1_binario_test: 0.7877`. La auditoría confirma el origen:

- `motor/evaluate.py:37`: `f1_score(yte, yhat, average="macro")` con `yte` binario (`y_binary = family != "normal"`, `motor/data.py:72`).
- El modelo es de dos clases. No existe clasificación de 5 clases en el repositorio. `family` es una columna descriptiva que solo se usa para el recall por familia (`motor/evaluate.py:43-51`).
- Búsqueda de `classification_report|average=` en todo el repositorio: solo las dos líneas de arriba. **No hay ninguna medición multiclase, ni buena ni mala.**

Consecuencia para PERF-003: si el criterio exige macro-F1 de 5 clases, hoy no hay incumplimiento documentado sino **ausencia de medición**. Y el `0.7877` no es weighted: es macro sobre dos clases, coherente con una exactitud de 0.7881 sobre un conjunto con 43.1 por ciento de normales.

Otros dos defectos metodológicos verificados:

- `motor/train.py:50-51`: la escala de `decision_function` del SVM se calcula con `Xtr`, que incluye el holdout usado para calibrar el umbral. Fuga menor, real.
- El `0.9984` de `metadata.json` es un holdout del mismo entrenamiento, no una prueba independiente, y se cita como cumplimiento de PERF-003. No lo es.
- `umbral_decision = 0.35` sale de una rejilla sobre el holdout de KDDTrain+ (`train.py:54-59`). Nunca se validó contra KDDTest+ ni hay tabla de sensibilidad.

Hallazgo nuevo: 31 filas de KDDTest+ usan etiquetas `named` (17) y `sendmail` (14) que no están en el diccionario `FAMILY` de `motor/data.py:21-38`. Caen en `family="unknown"`, se cuentan como ataque (correcto) pero desaparecen del recall por familia porque `motor/evaluate.py:47` solo recorre los códigos 1 a 4.

## 3. Estado por módulo

**M1 Motor.** Funcional, reproducible con semilla, sin hash ni manifiesto de artefactos. Afirmación no auditable: "estos son los modelos del informe". Isolation Forest se evalúa offline (AUC 0.9376, recall@10 por ciento 0.9965) y no participa en la predicción de producción: `motor/ensemble.py:36` solo usa rf, svm y knn.

**M2 Ingesta.** Solo CSV. `scripts/download_nslkdd.py:28-30` descarga sin verificar checksum, aunque `scripts/README.md` lo promete.

**M3 API.** Cuatro endpoints: `GET /health` (`api/main.py:85`), `POST /predict` (`:128`), `POST /predict/batch` (`:140`), `GET /history` (`:155`). `/docs` y `/openapi.json` habilitados por defecto. Pydantic laxo: `features: dict[str, float | int | str]` (`:72-75`); un `"abc"` en `src_bytes` pasa la validación y explota en `preprocess.py:46` con un 500 sin manejador global. Sin límite de tasa, sin tope de lote, sin CORS, sin tareas en segundo plano. Almacenamiento solo SQLite (`api/db.py:12`); Postgres y Neon no están implementados aunque E14 los declare.

**M4 Tablero.** Sin datos ficticios. Existe hardcodeo funcional: el desplegable de `service` ofrece 13 de las 70 categorías que el modelo conoce (`tablero/app.py:32-33` frente a `metadata.json:146-216`). Si la API no responde, `SystemExit` (`app.py:58`).

**M5 Alertas.** Token por entorno, nunca en código (`alertas/telegram.py:14-15`). Devuelve éxito solo con respuesta 200. **No hay llamada desde la detección**: una anomalía nunca dispara alerta automática; el único disparo es un botón manual del tablero (`app.py:69-81`).

**M6 CLI.** Inexistente.

## 4. Seguridad

- Sin secretos en el código ni en el historial completo de git (barrido de `TOKEN|SECRET|PASSWORD|postgres://|npg_|sk-|api_key|Bearer` sobre `git log -p --all`: solo texto documental y `os.environ.get`).
- `.env`, `.db`, `.joblib`, `.npy` y `.coverage` nunca se versionaron.
- `.github/` ignorado por `.gitignore:39`.
- API pública sin autenticación, sin CORS, sin límite de tasa y sin tope de cuerpo. En Render queda abierta a cualquiera con la URL.

## 5. Reproducibilidad: la brecha más grave

El entorno de la máquina no puede ejecutar el proyecto:

- `C:\Users\mateo\Downloads\.venv` es Python 3.14.3 y solo tiene `joblib`, `numpy` y `requests`. Sin scikit-learn, pandas, fastapi, streamlit, pytest, ruff ni coverage.
- `python -m pytest --version` responde "No module named pytest".
- No existe venv dentro del repositorio.
- Disponibles en el sistema: Python 3.12 (requerido por `pyproject.toml`), 3.13 y 3.14.

Un clon limpio del repositorio no arranca: necesita descargar 24.6 MB de datos y reentrenar porque los `.joblib` están fuera de git.

## 6. Requisitos afectados

| ID | Estado real | Evidencia | Brecha |
|---|---|---|---|
| FUN-001 | COMPLETED | `motor/preprocess.py`, `metadata.json:3` | Sin hash de artefactos |
| FUN-002 | PARTIAL | `family` calculada en `data.py:21-38,71` | 2 etiquetas sin mapear; sin modelo multiclase |
| PERF-003 | UNVERIFIED | `evaluate.py:37` | Lo medido es binario; el criterio multiclase no se ha medido |
| FUN-004 | PARTIAL | `api/main.py:128` | Sin validación numérica real |
| API-005 | PARTIAL | `api/main.py:155` | Sin tope de lote ni de tasa |
| PERF-006 | UNVERIFIED | No hay prueba de carga | p50 y p95 inexistentes |
| SEG-007 | PARTIAL | `api/main.py` sin handlers | 500 con traza potencial ante tipo inválido |
| DASH-008 | UNVERIFIED | `tablero/app.py` | No se ha cronometrado |
| DASH-009 | UNVERIFIED | Sin despliegue | Sin bitácora de disponibilidad |
| ALERT-010 | BROKEN | `alertas/telegram.py` | No conectado a la detección, sin telemetría |
| DATA-011 | PARTIAL | `api/db.py:12` | SQLite local; sin Postgres ni persistencia en la nube |
| DOC-012 | PARTIAL | `README.md`, `GUIA_DE_USO.txt` | Sin manual, sin arranque de un comando |
| DEPLOY-013 | MISSING | Sin URL pública | Nada desplegado |
| UX-014 | COMPLETED (excluido) | Sin autenticación por diseño | Aceptado explícitamente |
| RED-015 | PARTIAL | `tablero/client.py:15` | Todo apunta a 127.0.0.1 |

## 7. No verificado en esta auditoría

- El valor numérico de 0.7877 y 0.9652 por recálculo: no hay scikit-learn en ningún intérprete disponible y no se instaló nada.
- El arranque real de la API y la existencia en runtime de `/docs`.
- Si `requirements.txt` instala limpio: la línea 19 declara `httpx2==2.13.1`, y `TestClient` de FastAPI importa `httpx`.
- Cuántas de las 14 pruebas se saltaron en la corrida del 6 de octubre.

## 8. Brechas ordenadas por impacto para la defensa del 18 de noviembre

1. Nada es reproducible hoy en esta máquina (sección 5).
2. Cero despliegue y cero URLs públicas.
3. CI inexistente en GitHub por el permiso `workflow` del token.
4. Las 14 pruebas no están aprobadas hoy de forma reproducible.
5. PERF-003 mal medido: no existe la medición de 5 clases.
6. M5 no dispara alertas automáticas y no tiene telemetría de entrega.
7. M6 vacío.
8. API frágil para una demo en vivo.
9. Sin integridad de artefactos (hash o manifiesto).
10. Evidencia de M2 fuera de git: notebook y gráficas sin versionar.
11. Inconsistencias documentales: el notebook exporta `TELEGRAM_BOT_TOKEN` cuando el código lee `REDCENTINELA_TELEGRAM_TOKEN`; README y guía publican "macro-F1 0.788" sin la palabra "binario".
