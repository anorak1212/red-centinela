# Motor ML (M1)

Pipeline de datos, entrenamiento, inferencia y evaluación de los modelos de detección.

## Alcance

- Limpieza y codificación del dataset NSL-KDD (ver `datasets/`).
- Modelos supervisados: Random Forest, SVM (sobre submuestra) y KNN.
- Modelo no supervisado: Isolation Forest para anomalías.
- Evaluación por macro-F1 sobre el conjunto de prueba oficial. Umbral del proyecto: macro-F1 >= 0.90.
- Artefactos serializados con `joblib` en `motor/models/` (no se versionan; se publican como release de GitHub).

## Estado

En construcción, corresponde al entregable E2 del cronograma.

## Reglas

- Los binarios `.joblib` y `.pkl` están en `.gitignore` y no se suben.
- Cualquier reentrenamiento debe pasar la CI antes de actualizar un modelo: sin regresión silenciosa.