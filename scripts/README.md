# Scripts

Utilidades de mantenimiento y de despliegue. Ninguna contiene secretos: todo se
lee de variables de entorno.

| Script | Para qué |
|---|---|
| `download_nslkdd.py` | Baja NSL-KDD a `datasets/raw/` y verifica el checksum |
| `build_sample_etiquetado.py` | Regenera `datasets/sample_etiquetado.csv` (150 filas, 30 por familia, con `label` y `family`) desde KDDTest+ |
| `empaquetar_artefactos.py` | Arma `dist/modelos_red_centinela.tar.gz` (17 MB) con los cinco artefactos y su manifiesto, e imprime el SHA-256 para publicarlo como release |
| `descargar_artefactos.py` | Baja ese paquete en el build del servicio, comprueba el SHA-256 y el manifiesto. `--estado` solo informa |
| `smoke_prod.py` | Recorrido de humo contra una API local o desplegada: salud, integridad, predicción, lote de 150 filas, latencia p95 y tablero |
| `experimento_umbral.py` | Experimento de validación cruzada agrupada por subtipo de ataque. Descartado y documentado: agrupar deja folds sin tráfico normal |

```powershell
python scripts\empaquetar_artefactos.py
python scripts\descargar_artefactos.py --estado
python scripts\smoke_prod.py --api http://127.0.0.1:8000
```

Los dos scripts de artefactos se prueban en `tests/test_despliegue.py`, incluido
un recorrido completo de empaquetar, descargar por HTTP local y verificar el
manifiesto en la carpeta destino.
