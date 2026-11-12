# Red Centinela

Plataforma modular de monitoreo y alerta de tráfico de red basada en aprendizaje
automático: detecta, clasifica y avisa. Presupuesto del proyecto: $0.00 MXN, solo
herramientas gratuitas y de código abierto.

Motor ML (Random Forest con dos cabezas más Isolation Forest de apoyo) sobre el
dataset público NSL-KDD, API REST en FastAPI, tablero en Streamlit, alertas por
Telegram y CLI de operación.

## Estado de los módulos

| Módulo | Carpeta | Qué hace | Estado |
|---|---|---|---|
| M1 Repositorio y EDA | `motor/`, `datasets/` | Carga y preprocesado de NSL-KDD, análisis exploratorio | En operación |
| M2 Motor ML | `motor/` | Random Forest binario y multiclase, Isolation Forest, umbral calibrado, evaluación sobre KDDTest+ | En operación |
| M3 API REST | `api/` | `/health`, `/predict`, `/predict/batch`, `/history`, `/metrics`, `/alertas/*` | En operación |
| M4 Tablero | `tablero/` | Cinco vistas: resumen, análisis, historial, métricas y ayuda | En operación |
| M5 Alertas | `alertas/` | Bot de Telegram con agrupación por ventana y confirmación real de envío | Código listo, falta token |
| M6 Despliegue | `render.yaml`, `cli/` | Servicio en Render, historial en Neon, tablero en Streamlit Cloud | Pendiente de cuentas |

## Resultados del modelo

Medido sobre KDDTest+, 22,544 filas que el modelo nunca vio al entrenar:

| Métrica | Valor |
|---|---|
| Macro-F1 binario | 0.7995 |
| Exactitud | 0.7998 |
| Precisión de ataque | 0.9689 |
| Recall de ataque | 0.6698 |
| AUC ROC | 0.9616 |
| Macro-F1 cinco clases | 0.4716 |

El criterio original pedía macro-F1 mayor o igual a 0.90. No se cumple, y no por
un error de implementación: KDDTest+ trae familias de ataque que no existen en
entrenamiento (recall de r2l 0.09, de u2r 0.18). El detalle, la comparación con
KDDTest-21 y la argumentación están en `docs/INFORME_METRICAS.md` y en
`docs/SOLICITUD_CAMBIO_PERF-003.md`. El holdout interno da 0.9992, pero no es una
prueba independiente y no se cita como cumplimiento.

## Arranque en local (Windows, PowerShell)

```powershell
git clone https://github.com/anorak1212/red-centinela.git
cd red-centinela
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 1) Dataset (24 MB, va a datasets/raw y no se versiona)
python scripts\download_nslkdd.py

# 2) Modelos (unos 2 minutos en esta máquina) y métricas
python -m cli train
python -m cli evaluate

# 3) API
python -m cli serve
# documentación interactiva: http://127.0.0.1:8000/docs

# 4) Tablero, en otra terminal
streamlit run tablero/app.py
# http://localhost:8501
```

Los artefactos entrenados pesan unos 80 MB y `datasets/raw` 24 MB: ninguno de los
dos está en Git. Un clon limpio necesita los pasos 1 y 2 antes de arrancar la API.

## Cómo se prueba

```powershell
ruff check .                                   # estilo y errores
python -m pytest -q                             # 123 pruebas
python -m coverage run -m pytest -q
python -m coverage report                       # 84 % con artefactos
python scripts\smoke_prod.py --api http://127.0.0.1:8000
```

`smoke_prod.py` hace un recorrido de humo contra la API que le indiques: arranque
en frío, `/health`, integridad de artefactos, predicción individual, lote de 150
filas etiquetadas, latencia p95 y comprobación del tablero. Sirve igual contra
localhost que contra el servicio desplegado.

Las pruebas que dependen de los modelos o del dataset se omiten solas si no
están. Medido en un clon sin artefactos: 69 % de cobertura. Con artefactos, en
esta máquina: 84 %.

## Variables de entorno

| Variable | Para qué | Por omisión |
|---|---|---|
| `DATABASE_URL` | PostgreSQL (Neon) para el historial | vacío: SQLite local en `api/data/` |
| `REDCENTINELA_DB` | Ruta alternativa del archivo SQLite | `api/data/redcentinela.db` |
| `REDCENTINELA_TELEGRAM_TOKEN` | Token del bot | vacío: alertas desactivadas |
| `REDCENTINELA_TELEGRAM_CHAT_ID` | Chat destino de las alertas | vacío |
| `REDCENTINELA_RATE_LIMIT` | Peticiones por ventana y por IP en `/predict` | 120 |
| `REDCENTINELA_RATE_WINDOW` | Ventana del límite, en segundos | 60 |
| `REDCENTINELA_MAX_CUERPO` | Tamaño máximo del cuerpo, en bytes | 2000000 |
| `REDCENTINELA_ORIGENES` | Orígenes CORS separados por coma | localhost:8501 |
| `REDCENTINELA_API` | URL de la API que consume el tablero | `http://127.0.0.1:8000` |
| `REDCENTINELA_MODELOS_URL` | Paquete de artefactos para el build en la nube | vacío |
| `REDCENTINELA_MODELOS_SHA256` | SHA-256 esperado de ese paquete | vacío |

## Despliegue ($0.00, sin tarjeta)

La API y el tablero son dos servicios distintos, a propósito: el tablero solo
consume HTTP, así que se despliega con tres dependencias y no arrastra 80 MB de
modelos.

1. Artefactos. `python scripts\empaquetar_artefactos.py` genera un `.tar.gz` de
   17 MB con los cinco archivos y su manifiesto. Se sube como release de GitHub y
   el build lo baja con `scripts\descargar_artefactos.py`, que verifica el
   SHA-256 y el manifiesto antes de servir nada.
2. API en Render. El blueprint `render.yaml` define el servicio: plan gratuito,
   arranque con `uvicorn api.main:app`, health check en `/health`. Se duerme a los
   15 minutos sin tráfico y despierta en unos 50 segundos.
3. Historial en Neon. Se copia la cadena de conexión en `DATABASE_URL`. Sin ella
   el servicio usaría SQLite, que en Render se borra en cada despliegue.
4. Tablero en Streamlit Community Cloud. Archivo principal `tablero/app.py`,
   dependencias `tablero/requirements.txt`, y `REDCENTINELA_API` apuntando a la
   API de Render.
5. Arranque en frío. En la barra lateral del tablero, "Despertar servicio" sondea
   `/health` hasta 90 segundos. Se usa antes de la demo, no durante.

Costos: Render free, Neon free, Streamlit Cloud free y GitHub Actions free. Todo
con límites de uso, ninguno con tarjeta.

## CI

`.github/workflows/ci.yml` corre ruff, pytest con cobertura y pip-audit; hay un
segundo flujo, `respaldo.yml`, que hace un `pg_dump` semanal cifrado del historial.
Los dos están escritos pero no versionados: el token de GitHub del proyecto no
tiene el permiso `workflow`, así que `.github/` sigue en `.gitignore`. Para
activarlos hay que crear un token con ese permiso, borrar esa línea y hacer commit.

## Convenciones

- Python 3.12, PEP 8, `ruff` para estilo y errores.
- Ramas: `final` para el trabajo de cierre, `main` solo recibe merges con ruff,
  pruebas y cobertura en verde.
- Commits con prefijo: `feat:`, `fix:`, `test:`, `ci:`, `chore:`.
- Sin secretos en el repositorio: todo entra por variables de entorno.
- Los nombres de los endpoints y los identificadores (FUN, ALERT, DEPLOY, M1-M6)
  no se renombran: están fijados por el diseño del entregable 14.

## Demo

Enlaces pendientes de las cuentas de Render, Neon y Streamlit Cloud. Se publican
aquí al desplegar (DEPLOY-013).

## Créditos

Proyecto académico de Gestión de Proyectos, UAEMéx. Alumno: Mateo Jiménez Pérez.
Profesor: Juan Carlos Escobar González. Licencia MIT, ver `LICENSE`.
