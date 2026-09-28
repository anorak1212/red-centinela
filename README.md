# Red Centinela

Plataforma modular de monitoreo y alerta de tráfico de red basada en aprendizaje automático: detecta, analiza y alerta sobre actividad maliciosa en la red.

**Arquitectura en una línea:** motor ML (entrenamiento e inferencia) + API REST FastAPI + tablero Streamlit + alertas Telegram + CLI, sobre dataset público NSL-KDD y con presupuesto de $0.00 MXN (solo herramientas gratuitas y de código abierto).

## Estado de los módulos

| Módulo | Carpeta | Descripción | Estado |
|---|---|---|---|
| M1 Motor ML | `motor/` | Pipeline de datos, entrenamiento (Random Forest, SVM, KNN), Isolation Forest no supervisado, evaluación y artefactos joblib | En construcción |
| M2 Ingesta de contexto | `datasets/` | Carga de datos de tráfico (NSL-KDD y CSV de prueba desde el tablero) | En construcción |
| M3 API REST | `api/` | FastAPI: `/health`, `/predict`, `/history` | Pendiente |
| M4 Tablero | `tablero/` | Streamlit: monitoreo en vivo e historial | Pendiente |
| M5 Alertas | `alertas/` | Bot de Telegram vía Bot API (HTTP REST) | Pendiente |
| M6 CLI | `cli/` | Operación local del motor y la API | Pendiente |

## Arranque (Windows)

```powershell
git clone https://github.com/anorak1212/red-centinela.git
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt && pytest
```

## Convenciones

- Python 3.11, PEP 8, formateador `black`, linter `ruff` (severidad E y F bloquean).
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