# Datasets (M2)

Datos de tráfico de red para entrenamiento, validación y pruebas.

## Fuente

- NSL-KDD: dataset público de detección de intrusiones. Descarga desde la fuente oficial y verificación por checksum documentada en el EDA.
- Archivos CSV de prueba subidos por el analista desde el tablero (ingesta M2).

## Reglas

- Los datos grandes no se versionan: `datasets/*.csv` y `*.parquet` están en `.gitignore`.
- Solo se permite versionar muestras pequeñas con el prefijo `sample_` (ejemplo: `sample_100.csv`).
- No subir archivos con datos institucionales ni credenciales de ninguna fuente.