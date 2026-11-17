# EXPERIMENTOS_MEJORA.md

Cuatro intentos de mejorar el detector, con sus números y lo que se decidió en
cada caso. Sirve para responder en la defensa cuando pregunten por qué el modelo
es como es. Ninguna cifra de aquí se escribió a mano en `metrics.json`: ese
archivo lo genera `python -m motor.evaluate` a partir de los artefactos.

Fecha: 17 de noviembre de 2026. Todo el trabajo se hizo sobre KDDTrain+, que es
el único conjunto que el modelo podía usar para decidir. KDDTest+ se evaluó al
final de cada camino, una vez, y no se usó para elegir hiperparámetros.

## 1. Balanceo y sobremuestreo (Fase C v3)

Resultado: macro-F1 binario 0.8034 y macro-F1 de cinco clases 0.5541 con el
umbral de 0.42. La cabeza multiclase mejoró de forma clara respecto de la línea
base (0.4716); la binaria se quedó casi igual.

Decisión: se conservó el artefacto de Fase C v3. El sobremuestreo no resuelve
que en prueba aparezcan variantes que no existen en entrenamiento: repite
ejemplos conocidos con otro peso, no crea patrones nuevos.

## 2. Cambiar de familia de modelo

Protocolo: `scripts/seleccion_familias_no_vistas.py`. Se apartó una familia
completa de KDDTrain+, se entrenó sin ella y se midió el recall sobre esa
familia. Resultado en r2l y u2r no vistas:

| Candidato | Recall medio en familias no vistas |
|---|---|
| Random Forest balanceado (el modelo actual) | 0.0829 |
| HistGradientBoosting | 0.0354 |
| ExtraTrees balanceado | 0.0324 |

Decisión: se mantuvo el Random Forest. Cambiar de algoritmo empeoraba justo el
caso que queríamos arreglar. Datos en `docs/SELECCION_FAMILIAS_NO_VISTAS.json`.

## 3. Isolation Forest como red de rescate

Protocolo: `scripts/experimento_hibrido_iforest.py`. Se marcaba ataque si el RF
decía ataque **o** si el Isolation Forest lo consideraba anómalo. El corte de
anomalía se fijó por presupuesto de falsos positivos sobre normales del holdout.

| Presupuesto de falsos positivos | Recall r2l no vista | Falsos positivos en normales | Macro-F1 del holdout |
|---|---|---|---|
| Sin rescate | 0.0121 | 0.0009 | 0.9992 |
| 1 por ciento | 0.0683 | 0.0106 | 0.9940 |
| 5 por ciento | 0.0824 | 0.0505 | 0.9725 |
| 10 por ciento | 0.1477 | 0.1003 | 0.9457 |

Decisión: descartado. Compra recall a precio de precisión, y el Isolation Forest
sigue haciendo lo que dice el informe: ordenar rareza, no decidir etiquetas.
Datos en `docs/EXPERIMENTO_HIBRIDO_IFOREST.json`.

## 4. Recalibrar el umbral con familias no vistas

Protocolo: `scripts/umbral_familias_no_vistas.py`. Se aparta cada familia, se
entrena sin ella y se mide macro-F1 sobre una mezcla de esa familia nunca vista
y tráfico normal, en la proporción que tiene KDDTest+ (1.32 a 1). Se eligió el
umbral que maximiza el promedio de las cuatro mediciones: **0.01**, con 0.8867
en validación. El anterior era 0.42.

| Familia apartada | Macro-F1 con 0.01 | Macro-F1 con 0.42 |
|---|---|---|
| dos | 0.9823 | 0.9177 |
| probe | 0.9751 | 0.6297 |
| r2l | 0.6619 | 0.3111 |
| u2r | 0.9433 | 0.3810 |

Decisión: aplicado. `scripts/recalibrar_umbral.py` escribió el nuevo valor en
metadata.json, reconstruyó el manifiesto SHA-256 y dejó constancia en
`docs/RECALIBRACION_UMBRAL.md`. No se reentrenó nada: los `.joblib` son los
mismos. Después se evaluó una vez en KDDTest+:

| Métrica | Antes (0.42) | Después (0.01) |
|---|---|---|
| Macro-F1 binario | 0.8034 | 0.9251 |
| Precisión de ataque | 0.9689 | 0.8986 |
| Recall de ataque | 0.6768 | 0.9845 |
| Macro-F1 binario en KDDTest-21 | 0.5866 | 0.7496 |
| Macro-F1 cinco clases | 0.5541 | 0.5541 |

PERF-003 queda cubierto en la cabeza binaria. El costo es real: 1,058 falsos
positivos contra 285 antes, sobre 9,711 registros normales. La curva completa
está en `docs/SENSIBILIDAD_UMBRAL.md`. El mejor punto de esa curva es 0.05 con
0.927, pero no se eligió desde la curva: se habría elegido mirando el examen.

## 5. Lo que no se hizo

- No se tocó `metrics.json` a mano ni se redondeó ningún resultado.
- No se eligió umbral ni hiperparámetro mirando KDDTest+.
- No se citó el macro-F1 del holdout interno como prueba de generalización; los
  artefactos vigentes ni siquiera guardaron esa cifra, y donde no hay dato se
  escribe "no medido".
- No se usó KDDTest+ para generar datos de entrenamiento. Cualquier dato
  sintético tendría que salir solo de KDDTrain+.
- No se reescribió el holdout de 0.9984 de corridas anteriores: pertenece a
  otro modelo y mezclarlo sería inventar evidencia.

## 6. Estado de la deuda que queda

La cabeza multiclase sigue en 0.5541. Clasificar la familia de un ataque nunca
visto es otro problema, y el umbral binario no lo arregla. Esa es la limitación
que hay que decir en voz alta en la defensa, junto con el aumento de falsos
positivos que aceptamos en la cabeza binaria.
