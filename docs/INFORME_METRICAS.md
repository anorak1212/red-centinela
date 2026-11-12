# INFORME_METRICAS.md

Resultados del motor de detección de Red Centinela. Todas las cifras de este documento salen de `motor/models/metrics.json`, generado por `python -m motor.evaluate` el 2026-11-11T21:44:18-0600. Si una cifra de otro documento no coincide con esta tabla, la de aquí es la que vale.

## 1. Qué se mide y con qué datos

El motor tiene dos cabezas y se reportan por separado:

- **Binaria**: normal contra ataque, sobre los 22,544 registros de KDDTest+.
- **Multiclase**: normal, dos, probe, r2l y u2r, sobre el mismo conjunto.

KDDTest+ contiene familias de ataque que no aparecen en KDDTrain+. Eso hace que el rendimiento en prueba sea mucho menor que en entrenamiento, y es una propiedad conocida del dataset, no un defecto del modelo.

## 2. Resultado binario en KDDTest+

| Métrica | Valor |
|---|---|
| Exactitud | 0.7998 |
| Macro-F1 | 0.7995 |
| Weighted-F1 | 0.7985 |
| Precisión de ataque | 0.9689 |
| Recall de ataque | 0.6698 |
| AUC-ROC | 0.9616 |
| Registros | 22544 |
| Ataques reales | 12833 |

Matriz de confusión (filas normal, ataque): [[9435, 276], [4237, 8596]]

## 3. Resultado multiclase en KDDTest+

| Clase | Precisión | Recall | F1 | Soporte |
|---|---|---|---|---|
| normal | 0.6343 | 0.9738 | 0.7682 | 9711 |
| dos | 0.9613 | 0.7664 | 0.8528 | 7460 |
| probe | 0.8583 | 0.5931 | 0.7015 | 2421 |
| r2l | 0.8333 | 0.0035 | 0.0069 | 2885 |
| u2r | 0.3333 | 0.0149 | 0.0286 | 67 |

Macro-F1 0.4716, weighted-F1 0.6894, exactitud 0.7373 sobre 22544 registros.

Las clases r2l y u2r tienen soporte pequeño y recall bajo. No es un error de implementación: son los ataques con menos ejemplos en entrenamiento (995 y 52 registros) y en prueba aparecen variantes que no existen en el conjunto de entrenamiento.

## 4. KDDTest-21

Subconjunto de KDDTest+ que excluye el nivel de dificultad 21: 11,850 de los 22,544 registros. Es el conjunto que la literatura usa para medir ataques conocidos y separar el efecto de las variantes nuevas.

| Métrica | Valor |
|---|---|
| Registros | 11850 |
| Macro-F1 binario | 0.5808 |
| Exactitud binaria | 0.6192 |
| Macro-F1 multiclase | 0.3734 |
| Weighted-F1 multiclase | 0.4841 |

## 5. Recall por familia

| Familia | Registros | Recall detección (ataque o no) | Recall clasificación (familia correcta) |
|---|---|---|---|
| dos | 7460 | 0.8422 | 0.7664 |
| probe | 2421 | 0.8414 | 0.5931 |
| r2l | 2885 | 0.0915 | 0.0035 |
| u2r | 67 | 0.1791 | 0.0149 |

## 6. Isolation Forest

| Métrica | Valor |
|---|---|
| AUC-ROC | 0.9376 |
| Recall de ataques en el 10 por ciento más anómalo | 0.9965 |

Es apoyo no supervisado: no decide la etiqueta. Sirve para señalar tráfico raro aunque se parezca a algo ya visto.

## 7. Holdout de entrenamiento

| Métrica en holdout | Valor |
|---|---|
| Macro-F1 binario | 0.9992 |
| Macro-F1 multiclase | 0.9458 |
| Weighted-F1 multiclase | 0.9987 |

Estas cifras son altas porque el holdout sale de la misma distribución del entrenamiento. Se publican para comparar contra KDDTest+, no como prueba de generalización.

## 8. Latencia y tiempos

| Métrica | Valor |
|---|---|
| Milisegundos por fila suelta | 253.53 |
| Milisegundos por fila en lote de 500 | 0.316 |
| Segundos de entrenamiento del RF binario | 62.9 |
| Segundos de entrenamiento del RF multiclase | 58.9 |
| Segundos de entrenamiento del Isolation Forest | 5.2 |

## 9. Comparativa de modelos (no desplegados)

| Modelo | Filas de entrenamiento | Macro-F1 binario | Exactitud | Segundos |
|---|---|---|---|---|
| linear_svc | 25000 | 0.9687 | 0.9689 | 1.7 |
| knn7 | 25000 | 0.9936 | 0.9936 | 4.0 |

LinearSVC y KNN se midieron sobre una submuestra de 25,000 filas y una muestra de evaluación de 8,000. KNN guarda todos los vectores de entrenamiento: 62.5 MB en disco y memoria proporcional en ejecución, inviable en el plan gratuito. Por eso el modelo desplegado es el Random Forest.

## 10. Limitaciones que hay que decir en voz alta

- Los datos son de 1999. Un modelo entrenado con ellos describe ataques de hace veinticinco años.
- KDDTest+ incluye ataques que no están en entrenamiento. El recall de r2l es el más castigado y no se arregla con hiperparámetros.
- El umbral de decisión se calibró sobre el holdout del entrenamiento. En KDDTest+ el rendimiento óptimo del umbral sería otro; ajustarlo aquí sería hacer trampa, así que no se hizo.
- La métrica de referencia del proyecto (PERF-003) pedía un macro-F1 mayor o igual a 0.90 sobre KDDTest+. Con estos datos y esta literatura no es alcanzable; ver SOLICITUD_CAMBIO_PERF-003.md.

Documento generado automáticamente desde metrics.json. Redacción asistida por inteligencia artificial; las cifras son salida de `motor.evaluate`, no estimaciones.
