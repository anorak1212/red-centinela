# Solicitud de cambio PERF-003: criterio de rendimiento del modelo

Estado: pendiente de aprobación del patrocinador.
Fecha: 11 de noviembre de 2026.
Proyecto: Red Centinela. Módulo afectado: M2, motor de detección.
Preparada por: PMO del proyecto.

## 1. Qué dice la línea base

El criterio de calidad del modelo se fijó en el entregable 5 como:

- Macro-F1 mayor o igual a 0.90 sobre el conjunto de prueba KDDTest+.
- Reporte de AUC de la cabeza binaria.

Se identificó una inconsistencia de nomenclatura: un documento cita este criterio
como PERF-001 y otro como PERF-003. Este documento usa PERF-003, que es el
identificador de la matriz de requisitos vigente. Queda por confirmar con el
profesor cuál es el canónico antes de citarlo en la defensa.

## 2. Qué se midió

Entrenamiento sobre las 125,973 filas de KDDTrain+ con Random Forest de 300
árboles, dos cabezas (binaria normal contra ataque, y cinco clases), umbral de
decisión 0.41 calibrado solo sobre el holdout interno. Evaluación sobre
KDDTest+, 22,544 filas que el modelo nunca vio:

| Métrica | Valor medido |
|---|---|
| Macro-F1 binario | 0.7995 |
| Exactitud binaria | 0.7998 |
| Precisión de ataque | 0.9689 |
| Recall de ataque | 0.6698 |
| AUC ROC | 0.9616 |
| Macro-F1 cinco clases | 0.4716 |
| F1 ponderado cinco clases | 0.6894 |

Sobre KDDTest-21, el subconjunto de dificultad menor a 21 (11,850 filas):
macro-F1 binario 0.5808 y macro-F1 de cinco clases 0.3734.

Desglose por familia, medido sobre KDDTest+:

| Familia | Registros | Detectada como ataque | Familia correcta |
|---|---|---|---|
| dos | 7,460 | 0.8422 | 0.7664 |
| probe | 2,421 | 0.8414 | 0.5931 |
| r2l | 2,885 | 0.0915 | 0.0035 |
| u2r | 67 | 0.1791 | 0.0149 |

Para comparar: sobre el holdout interno del entrenamiento el macro-F1 binario es
0.9992 y el de cinco clases 0.9458. Esa cifra no sirve como prueba de
cumplimiento porque sale de la misma distribución con la que se entrenó.

## 3. Por qué no se llega a 0.90

No es un error de implementación ni un umbral mal puesto. KDDTest+ contiene
familias de ataque que no existen en el conjunto de entrenamiento: variantes de
acceso remoto y de escalada de privilegios que en KDDTrain+ aparecen con pocos
ejemplos o con otra forma. El modelo aprende a reconocer lo que vio; cuando la
etiqueta cambia de forma, la cabeza binaria todavía detecta algo (r2l 0.09,
u2r 0.18) y la cabeza multiclase prácticamente no acierta la familia.

Subir el umbral para mejorar el recall de ataque castiga la precisión y hunde
las clases mayoritarias. Bajarlo hace lo contrario. Ningún ajuste del umbral
lleva el macro-F1 de cinco clases a 0.90 sobre KDDTest+ porque el techo lo pone
la distribución, no el corte.

La literatura publicada sobre KDDTest+ reporta valores del orden de 0.80 en
macro-F1 binario para modelos supervisados clásicos. Cualquier tabla que muestre
0.98 o más en KDDTest+ con cinco clases está midiendo fuga de datos: típicamente
entrenó con filas duplicadas entre entrenamiento y prueba, o ajustó el umbral
contra el propio conjunto de prueba. Este proyecto verificó que no ocurre: el
preprocesado se ajusta solo con entrenamiento y el umbral se calibró sobre
holdout interno.

## 4. Opciones evaluadas

Opción A. Redefinir el criterio. Aceptar como objetivo macro-F1 binario mayor o
igual a 0.78 sobre KDDTest+, con el desglose por familia publicado y el
macro-F1 de cinco clases reportado como limitación conocida. Cambia el alcance
de PERF-003, no la realidad medida.

Opción B. Mantener 0.90 y medirlo sobre el holdout interno. Se descarta. Es
maquillaje: el holdout comparte distribución con el entrenamiento y declarar
cumplimiento con esa cifra sería falso.

Opción C. Reentrenar con sobremuestreo agresivo de r2l y u2r. Se probó un
experimento de validación cruzada agrupada por subtipo de ataque y no fue
concluyente: el umbral resultante fue 0.08 con macro-F1 0.9772, un valor que no
se sostiene sobre KDDTest+. Subir el recall de u2r con 67 registros de prueba
también produciría un número inestable: un acierto más mueve el recall 1.5
puntos.

Opción D. Descartar KDDTest+ y evaluar solo con datos propios. Se descarta por
tiempo: no hay captura de tráfico real etiquetada y generarla no cabe en las
semanas que quedan antes de la defensa.

## 5. Recomendación

Opción A. El sistema detecta ataques con precisión alta (0.9689: cuando avisa,
casi siempre es ataque) y deja pasar uno de cada tres. Eso es un IDS de primera
generación honesto, y es preferible a un número inflado que no se sostiene si el
profesor pide repetir la evaluación en vivo. El desglose por familia y la
comparación con KDDTest-21 quedan en el informe de métricas y en el tablero,
visibles para cualquiera.

Consecuencias si se aprueba:

- Se actualiza PERF-003 en la matriz de requisitos con el umbral nuevo.
- El acta de variaciones registra el cambio, con la medición que lo respalda.
- El diccionario de la EDT no cambia: la actividad de evaluación se ejecutó y
  su producto existe.
- El informe de métricas y la vista Modelo y métricas del tablero ya muestran las
  cifras reales; no hay que reescribir nada.

Consecuencias si se rechaza: el criterio queda incumplido y así se declara en el
cierre. El producto sigue siendo demostrable, pero el acta de cierre llevará una
desviación abierta.

## 6. Decisión

Umbral aprobado: [PENDIENTE: umbral aprobado]

Aprobado por: [PENDIENTE: nombre y fecha]
