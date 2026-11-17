# RECALIBRACION_UMBRAL.md

El umbral de decision del detector binario paso de **0.42** a **0.01**.

## Por que

El umbral de 0.42 se habia calibrado con un holdout de la misma
distribucion de KDDTrain+. Ahi el modelo acierta casi todo, asi que el punto
optimo queda alto. El fallo aparece con ataques que no existen en entrenamiento:
en KDDTest+ el recall de ataque cae y las familias r2l y u2r casi no se detectan.

## Como se eligio, sin mirar el examen

`scripts/umbral_familias_no_vistas.py` aparto cada familia de ataque completa,
entreno sin ella y midio macro-F1 sobre una mezcla de esa familia nunca vista y
trafico normal, en la proporcion que tiene KDDTest+ (1.32 a 1). El umbral que
maximiza el promedio de esas cuatro mediciones fue **0.01**, con macro-F1
promedio de 0.8867 en validacion.

Resultados por familia:

| Familia apartada | Macro-F1 con umbral 0.01 | Macro-F1 con umbral 0.42 |
|---|---|---|
| dos | 0.9665 | 0.9177 |
| probe | 0.9751 | 0.6297 |
| r2l | 0.6619 | 0.3111 |
| u2r | 0.9433 | 0.381 |

KDDTest+ no se uso para elegir el umbral. La curva de sensibilidad de
`docs/SENSIBILIDAD_UMBRAL.md` se calculo despues, como diagnostico, y confirma
que el cambio tiene precio: mas recalls, pero tambien mas falsos positivos.
Ese costo se acepta porque la metrica del proyecto es macro-F1 y porque un
sistema de alerta puede priorizar la deteccion; queda escrito aqui para que la
decision se pueda revisar.

## Que NO cambio

No se reentreno ningun modelo. rf.joblib, rf_multi.joblib, iforest.joblib y el
preprocesador siguen siendo los mismos archivos, con el mismo hash. Solo cambio
metadata.json, que es donde vive el punto de corte, y manifiesto.json, que se
reconstruyo para que la verificacion de integridad siga siendo valida.

La evaluacion final se regenero con `python -m motor.evaluate` y sus cifras
estan en `motor/models/metrics.json` y `docs/INFORME_METRICAS.md`.
