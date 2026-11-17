# INFORME_METRICAS.md

Resultados del motor de detección de Red Centinela. Todas las cifras de este documento salen de `motor/models/metrics.json`, generado por `python -m motor.evaluate` el 2026-11-17T09:32:07-0600. Si una cifra de otro documento no coincide con esta tabla, la de aquí es la que vale.

## 1. Qué se mide y con qué datos

El motor tiene dos cabezas y se reportan por separado:

- **Binaria**: normal contra ataque, sobre los 22,544 registros de KDDTest+.
- **Multiclase**: normal, dos, probe, r2l y u2r, sobre el mismo conjunto.

KDDTest+ contiene familias de ataque que no aparecen en KDDTrain+. Eso hace que el rendimiento en prueba sea mucho menor que en entrenamiento, y es una propiedad conocida del dataset, no un defecto del modelo.

## 2. Resultado binario en KDDTest+

| Métrica | Valor |
|---|---|
| Exactitud | 0.9279 |
| Macro-F1 | 0.9251 |
| Weighted-F1 | 0.9271 |
| Precisión de ataque | 0.8986 |
| Recall de ataque | 0.9845 |
| AUC-ROC | 0.9641 |
| Registros | 22544 |
| Ataques reales | 12833 |

Matriz de confusión (filas normal, ataque): [[8285, 1426], [199, 12634]]

## 3. Resultado multiclase en KDDTest+

| Clase | Precisión | Recall | F1 | Soporte |
|---|---|---|---|---|
| normal | 0.6439 | 0.9738 | 0.7752 | 9711 |
| dos | 0.9612 | 0.7637 | 0.8511 | 7460 |
| probe | 0.8587 | 0.6026 | 0.7083 | 2421 |
| r2l | 0.9764 | 0.0718 | 0.1337 | 2885 |
| u2r | 0.6842 | 0.194 | 0.3023 | 67 |

Macro-F1 0.5541, weighted-F1 0.7096, exactitud 0.7467 sobre 22544 registros.

Las clases r2l y u2r tienen soporte pequeño y recall bajo. No es un error de implementación: son los ataques con menos ejemplos en entrenamiento (995 y 52 registros) y en prueba aparecen variantes que no existen en el conjunto de entrenamiento.

## 4. KDDTest-21

Subconjunto de KDDTest+ que excluye el nivel de dificultad 21: 11,850 de los 22,544 registros. Es el conjunto que la literatura usa para medir ataques conocidos y separar el efecto de las variantes nuevas.

| Métrica | Valor |
|---|---|
| Registros | 11850 |
| Macro-F1 binario | 0.7496 |
| Exactitud binaria | 0.8804 |
| Macro-F1 multiclase | 0.4565 |
| Weighted-F1 multiclase | 0.519 |

## 5. Recall por familia

| Familia | Registros | Recall detección (ataque o no) | Recall clasificación (familia correcta) |
|---|---|---|---|
| dos | 7460 | 1.0 | 0.7637 |
| probe | 2421 | 1.0 | 0.6026 |
| r2l | 2885 | 0.9321 | 0.0718 |
| u2r | 67 | 0.9552 | 0.194 |

## 6. Isolation Forest

| Métrica | Valor |
|---|---|
| AUC-ROC | 0.9376 |
| Recall de ataques en el 10 por ciento más anómalo | 0.9965 |

Es apoyo no supervisado: no decide la etiqueta. Sirve para señalar tráfico raro aunque se parezca a algo ya visto.

## 7. Holdout de entrenamiento

| Métrica en holdout | Valor |
|---|---|
| Macro-F1 binario | no medido |
| Macro-F1 multiclase | no medido |
| Weighted-F1 multiclase | no medido |

El entrenamiento que produjo estos artefactos no guardó las cifras del holdout, así que aquí no se publican. Rellenarlas desde otra corrida mezclaría modelos distintos. La validación cruzada de esa corrida sí quedó registrada en metadata.json.

## 8. Latencia y tiempos

| Métrica | Valor |
|---|---|
| Milisegundos por fila suelta | 102.19 |
| Milisegundos por fila en lote de 500 | 0.68 |
| Segundos de entrenamiento del RF binario | no medido |
| Segundos de entrenamiento del RF multiclase | no medido |
| Segundos de entrenamiento del Isolation Forest | no medido |

Los tiempos de entrenamiento los escribe `motor.train`. Si esta tabla dice "no medido", la evaluación corrió sobre artefactos ya entrenados y esa cifra no forma parte de esta corrida: no se rellena a ojo.

## 9. Comparativa de modelos (no desplegados)

| Modelo | Filas de entrenamiento | Macro-F1 binario | Exactitud | Segundos |
|---|---|---|---|---|
| no medido | - | - | - | - |

La comparativa se produce al entrenar (`motor.train`). Esta corrida evaluó los artefactos existentes, así que la tabla queda vacía en lugar de mostrar cifras que no se midieron hoy.

LinearSVC y KNN se midieron sobre una submuestra de 25,000 filas y una muestra de evaluación de 8,000. KNN guarda todos los vectores de entrenamiento: 62.5 MB en disco y memoria proporcional en ejecución, inviable en el plan gratuito. Por eso el modelo desplegado es el Random Forest.

## 10. Limitaciones que hay que decir en voz alta

- Los datos son de 1999. Un modelo entrenado con ellos describe ataques de hace veinticinco años.
- KDDTest+ incluye ataques que no están en entrenamiento. El recall de r2l es el más castigado y no se arregla con hiperparámetros.
- El umbral de decisión se recalibró de 0.42 a 0.01 con `leave-one-family-out` sobre KDDTrain+, sin usar KDDTest+ (`docs/UMBRAL_FAMILIAS_NO_VISTAS.json`). El precio en falsos positivos está medido en `docs/SENSIBILIDAD_UMBRAL.md` y se acepta a cambio de recuperar ataques que el modelo no vio en entrenamiento.
- La métrica de referencia (PERF-003) pedía macro-F1 mayor o igual a 0.90 sobre KDDTest+. Con el umbral recalibrado se obtiene 0.9251. La solicitud de cambio de criterio `SOLICITUD_CAMBIO_PERF-003.md` queda sin objeto, pero no se da por aprobada ni archivada sin firma del profesor.

Documento generado automáticamente desde metrics.json. Redacción asistida por inteligencia artificial; las cifras son salida de `motor.evaluate`, no estimaciones.
