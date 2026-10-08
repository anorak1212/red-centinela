# Suite de pruebas (A32: pruebas funcionales, de carga y de seguridad)

Todas las pruebas corren `sin red y sin dataset real`: se entrenan con un
NSL-KDD sintético y escriben solo en directorios temporales. Pueden
ejecutarse en CI (GitHub Actions) recién clonado.

## Cómo correr

```bash
pip install -r requirements.txt
pytest                 # suite completa
ruff check .           # lint
coverage run -m pytest && coverage report --fail-under=80
```

Con la API levantada (`uvicorn api.main:app`) se suma 1 prueba más
(`test_health_contra_api`); sin ella se omite, no rompe la colección.

## Qué cubre cada archivo

| Archivo | Foco | Pruebas |
|---|---|---|
| `test_smoke.py` | entorno instalado | 2 |
| `test_motor.py` | preprocesador y ensamble | 4 |
| `test_api.py` | endpoints con TestClient | 4 |
| `test_tablero.py` | cliente del tablero y CSV | 4 |
| `test_entrenamiento.py` | pipeline train/evaluate con datos sintéticos, rutas de error de datos | 8 |
| `test_carga.py` | umbrales de rendimiento (motor y API) | 5 |
| `test_seguridad.py` | inyección SQL, validación de entradas, secretos, Telegram | 10 |

Total: 37 pruebas siempre + 4 que requieren modelos entrenados o API viva.

## Cobertura objetivo

El `pyproject.toml` exige `fail_under = 80`. Medido:

- Local (con modelos): 99 % (faltan 2 guardas `if __name__ == "__main__"` y
  1 rama no alcanzable de `load_raw`, ver abajo).
- Modo CI (sin modelos, sin dataset, repo recién clonado): 92 %.

## Notas de honestidad técnica

- La rama `ValueError` de `motor/data.py:74` no es alcanzable: `pandas`
  rellena o trunca a las 43 columnas del encabezado. Se dejó como salvaguarda
  defensiva y está documentada como código muerto.
- Las pruebas de carga usan umbrales con ~3x de holgura sobre lo medido en el
  equipo del proyecto: están para detectar regresiones reales, no ruido.