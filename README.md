# Red Centinela

Plataforma modular de monitoreo y alerta de tráfico de red basada en aprendizaje
automático: detecta, clasifica y avisa. Presupuesto del proyecto: $0.00 MXN, solo
herramientas gratuitas y de código abierto.

Motor ML (Random Forest con dos cabezas más Isolation Forest de apoyo) sobre el
dataset público NSL-KDD, API REST en FastAPI, tablero en Streamlit, alertas por
Telegram y CLI de operación.

## Estado real (verificado)

| Módulo | Carpeta | Qué hace | Estado |
|---|---|---|---|
| M1 Repositorio y EDA | `motor/`, `datasets/` | Carga y preprocesado de NSL-KDD, análisis exploratorio, muestras versionadas | En operación |
| M2 Motor de detección | `motor/` | Random Forest binario y multiclase, Isolation Forest, umbral calibrado, evaluación sobre KDDTest+ | En operación (criterio macro-F1 no cumplido; ver métricas) |
| M3 API REST | `api/` | `/health`, `/metrics`, `/predict`, `/predict/batch`, `/history`, `/history/resumen`, `/alertas/estado`, `/alertas/prueba` | En operación |
| M4 Tablero | `tablero/` | 7 vistas: Resumen, Analizar, Historial, Modelo y métricas, Sistema, Ayuda, Configuración | En operación (acceso público del despliegue pendiente de ajuste manual) |
| M5 Alertas | `alertas/` | Bot de Telegram con agrupación por ventana y confirmación real de envío | Configurado en producción; envíos confirmados en el proceso actual según smoke (no permanente entre reinicios del contador en memoria) |
| M6 Despliegue y operación | `render.yaml`, `cli/`, `scripts/` | API en Render, historial en Neon/Postgres, tablero en Streamlit Cloud, smoke y utilidades | Desplegado; tablero no accesible públicamente sin login (303) |

**Despliegue conocido (URLs):**
- API: `https://red-centinela-api.onrender.com` (Render, plan gratuito; puede estar dormida)
- Tablero: `https://red-centinela.streamlit.app` (Streamlit Community Cloud; responde 303 a autenticación desde fuera, acceso público no verificable sin ajuste manual)

> Nota: hay mejoras de verificación y de conteos (`sin_familia`/`con_familia`, vista Sistema medida) implementadas y probadas en el repositorio local, pero **no desplegadas** mientras no se suban y desplieguen esos cambios.

## Resultados del modelo

Medido sobre KDDTest+, 22,544 filas que el modelo nunca vio al entrenar (`motor/models/metrics.json`):

| Métrica | Valor |
|---|---|
| Macro-F1 binario (KDDTest+) | 0.7995 |
| Exactitud | 0.7998 |
| Precisión de ataque | 0.9689 |
| Recall de ataque | 0.6698 |
| AUC ROC | 0.9616 |
| Macro-F1 cinco clases | 0.4716 |

El criterio original pedía macro-F1 mayor o igual a 0.90 (**PERF-003**). No se cumple, y no por
un error de implementación: KDDTest+ trae familias de ataque que no existen en
entrenamiento. El detalle y la argumentación están en `docs/INFORME_METRICAS.md` y en
`docs/SOLICITUD_CAMBIO_PERF-003.md`. El holdout interno no se cita como cumplimiento.

## Arranque en local (Windows, PowerShell)

```powershell
git clone https://github.com/anorak1212/red-centinela.git
cd red-centinela
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 1) Dataset (va a datasets/raw y no se versiona)
python scripts\download_nslkdd.py

# 2) Modelos y métricas (requiere dataset; genera artefactos en motor/models/)
python -m cli train
python -m cli evaluate

# 3) API
python -m cli serve
# documentación interactiva: http://127.0.0.1:8000/docs

# 4) Tablero, en otra terminal
streamlit run tablero/app.py
# http://localhost:8501
```

Los artefactos entrenados (~80 MB) y `datasets/raw` (~24 MB) no están en Git. Un clon
limpio necesita los pasos 1 y 2 antes de arrancar la API con modelos disponibles.

## Cómo se prueba

```powershell
ruff check .                                   # estilo y errores
python -m pytest -q                            # pruebas (algunas se omiten sin artefactos/dataset)
python -m coverage run -m pytest -q
python -m coverage report                      # umbral configurado en pyproject.toml (80 % con artefactos)
python -m scripts.smoke_prod --api http://127.0.0.1:8000
```

`scripts/smoke_prod.py` hace un recorrido de humo contra la API indicada: arranque en frío,
`/health`, integridad, `/metrics`, `POST /predict`, `POST /predict/batch` (muestra
configurable), verificación de `/history`, latencia p95 medida de `/predict` y comprobación
del tablero. Ejemplo contra producción (escribe en historial y, si hay ataques, puede
disparar alertas reales de Telegram según configuración):

```powershell
python -m scripts.smoke_prod --api https://red-centinela-api.onrender.com --tablero https://red-centinela.streamlit.app --muestra datasets/sample_trafico.csv --esperado-ataques 30 --latencia 20
```

Las pruebas que dependen de modelos o dataset se omiten solas si no están presentes.

## Variables de entorno

| Variable | Para qué | Por omisión / nota |
|---|---|---|
| `DATABASE_URL` | PostgreSQL (Neon) para el historial persistente | vacío: SQLite local en `api/data/` (no persistente en Render) |
| `REDCENTINELA_DB` | Ruta alternativa del archivo SQLite | `api/data/redcentinela.db` |
| `REDCENTINELA_TELEGRAM_TOKEN` | Token del bot de Telegram | vacío: alertas desactivadas |
| `REDCENTINELA_TELEGRAM_CHAT_ID` | Chat destino de las alertas | vacío |
| `REDCENTINELA_RATE_LIMIT` | Peticiones por ventana y por IP en `/predict` | 120 (en `render.yaml` se define 240) |
| `REDCENTINELA_RATE_WINDOW` | Ventana del límite, en segundos | 60 |
| `REDCENTINELA_MAX_CUERPO` | Tamaño máximo del cuerpo, en bytes | 2000000 |
| `REDCENTINELA_ORIGENES` | Orígenes CORS separados por coma | localhost:8501 (en despliegue, origen del tablero) |
| `REDCENTINELA_API` | URL de la API que consume el tablero | `http://127.0.0.1:8000` |
| `REDCENTINELA_TABLERO_URL` | URL pública del tablero (la usa la vista Sistema para verificar DEPLOY-013) | vacío: no verificable |
| `REDCENTINELA_TABLERO_USUARIOS` | Usuarios del tablero (`usuario:rol:hash`, separados por comas; en Streamlit Cloud puede ir en Secrets) | vacío: acceso local sin este control según configuración |
| `REDCENTINELA_MODELOS_URL` | Paquete de artefactos para el build en la nube | vacío |
| `REDCENTINELA_MODELOS_SHA256` | SHA-256 esperado de ese paquete | vacío |

> No incluir secretos en el repositorio. En Streamlit Cloud las credenciales/URLs sensibles se configuran en Secrets.

## Despliegue ($0.00, sin tarjeta)

La API y el tablero son dos servicios distintos: el tablero solo consume HTTP y se
despliega con dependencias ligeras (`tablero/requirements.txt`).

1. **Artefactos.** `python scripts/empaquetar_artefactos.py` genera un `.tar.gz` con
   los archivos del modelo y su manifiesto. Se publica (p. ej. release de GitHub) y el
   build lo descarga con `scripts/descargar_artefactos.py`, que verifica el SHA-256 y el
   manifiesto antes de servir.
2. **API en Render.** `render.yaml` define el servicio (plan gratuito): arranque con
   `uvicorn api.main:app`, health check en `/health`. Se duerme tras ~15 minutos sin
   tráfico y el arranque en frío puede tardar decenas de segundos.
3. **Historial en Neon.** `DATABASE_URL` debe apuntar a PostgreSQL (Neon). Sin ella la
   API usa SQLite, que en Render no persiste entre reinicios/despliegues.
4. **Tablero en Streamlit Community Cloud.** Archivo principal `tablero/app.py`,
   dependencias `tablero/requirements.txt`, y `REDCENTINELA_API` apuntando a la API de
   Render. Definir también `REDCENTINELA_TABLERO_URL` y `REDCENTINELA_TABLERO_USUARIOS`
   según corresponda.

### Antes de la defensa (despertar Render)

En el plan gratuito la API puede estar dormida. Antes de demostrar:
- Abrir `https://red-centinela-api.onrender.com/health` en el navegador o usar el botón
  **“Despertar servicio”** de la barra lateral del tablero, que sondea `/health` hasta
  ~90 s.
- Esperar a que `/health` responda `status: ok` e `integridad_artefactos: true` antes de
  iniciar la demo (evita latencias de arranque en frío y falsos negativos en la verificación).

## CI

`.github/workflows/ci.yml` está versionado. En su estado actual puede no terminar en
verde tal como está configurado (dependencias/umbral/artefactos no versionados). Existen
propuestas en `docs/propuestas/ci.yml` y `docs/propuestas/respaldo.yml` (CI corregido y
respaldo semanal cifrado de Neon), pendientes de activación: modificar/añadir workflows
en `.github/workflows/` requiere un token con permiso `workflow` y los pasos manuales
correspondientes (secretos, etc.).

## Convenciones

- Python 3.12, PEP 8, `ruff` para estilo y errores.
- Ramas: `final` para el trabajo de cierre, `main` solo recibe merges con ruff,
  pruebas y cobertura en verde.
- Commits con prefijo: `feat:`, `fix:`, `test:`, `ci:`, `chore:`.
- Sin secretos en el repositorio: todo entra por variables de entorno.
- Los nombres de endpoints e identificadores (FUN, ALERT, DEPLOY, PERF, M1-M6) no se
  renombran: están fijados por el diseño del entregable 14.

## Créditos

Proyecto académico de Gestión de Proyectos, UAEMéx. Alumno: Mateo Jiménez Pérez.
Profesor: Juan Carlos Escobar González. Licencia MIT, ver `LICENSE`.
