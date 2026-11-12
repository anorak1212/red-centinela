# Suite de pruebas

123 pruebas que no necesitan red ni el dataset completo. Las que dependen de los
artefactos entrenados (80 MB, fuera de Git) se omiten solas en un clon limpio.

## Cómo se corre

```powershell
pip install -r requirements.txt
pip install -r requirements-dev.txt
python -m pytest -q
python -m coverage run -m pytest -q
python -m coverage report
ruff check .
```

Con artefactos en `motor/models/`: 123 pruebas, 84 % de cobertura. Sin ellos: se
omiten 15 y la cobertura medida baja a 69 %, porque `motor/train.py` y
`motor/evaluate.py` quedan sin ejercitar (están excluidos del cálculo en
`pyproject.toml`).

## Qué cubre cada archivo

| Archivo | Foco | Pruebas |
|---|---|---|
| `test_smoke.py` | el entorno importa y las rutas base existen | 2 |
| `test_motor.py` | preprocesador, umbral, cabezas binaria y multiclase, manifiesto | 15 |
| `test_metricas.py` | coherencia de `metrics.json` con lo que publica la API | 8 |
| `test_api.py` | contrato de los seis endpoints, validación estricta, 503 sin modelos, errores sin traza | 27 |
| `test_seguridad.py` | inyección SQL, límite de tasa, cuerpo máximo, cabeceras, secretos fuera del repo | 8 |
| `test_db.py` | SQLite y PostgreSQL: creación, inserción, historial, migración idempotente | 13 |
| `test_alertas.py` | Telegram: agrupación por ventana, reintentos, sin token no envía | 12 |
| `test_cli.py` | `train`, `evaluate`, `predict`, `estado`, códigos de salida | 7 |
| `test_tablero.py` | cliente HTTP, validación del CSV, las cinco vistas y dos botones reales | 21 |
| `test_despliegue.py` | empaquetado con manifiesto, descarga por HTTP, SHA-256, extracción plana | 10 |

`test_tablero.py` incluye tres pruebas que solo corren con la API levantada
(`python -m cli serve`); sin ella se omiten sin romper la colección.

## Reglas para agregar pruebas

- Nada de red: si hace falta HTTP, se levanta un servidor local en el puerto 0.
- Nada de escribir en la base real: `conftest.py` fija `REDCENTINELA_DB` a una
  carpeta temporal y borra `DATABASE_URL` antes de importar `api.main`.
- Cada prueba que dependa de modelos o dataset lleva su `skipif`, para que el
  repositorio recién clonado pase en verde.
